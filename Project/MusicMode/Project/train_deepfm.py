# -*- coding: utf-8 -*-
"""
DeepFM 精排模型训练 (GPU 加速 + 可视化)
功能：
1. 加载特征数据和 ALS 候选集
2. 构建 DeepFM 模型（GPU 训练）
3. 训练并可视化进度
4. 对候选集评分并保存结果

作者：MusicMode 推荐系统
硬件：NVIDIA GeForce RTX 4060 Laptop (8GB VRAM)
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")
FEATURE_PATH = os.path.join(MODE_DIR, "features.pkl")
CANDIDATES_PATH = os.path.join(MODE_DIR, "candidates.pkl")
DEEPFM_MODEL_PATH = os.path.join(MODE_DIR, "deepfm_model.pth")
PREDICTIONS_PATH = os.path.join(MODE_DIR, "predictions.pkl")
TRAINING_PLOT_PATH = os.path.join(MODE_DIR, "training_progress.png")

# 训练超参数
BATCH_SIZE = 256        # 全量训练数据量较大，降低 batch 防显存溢出
EPOCHS = 5              # 训练轮数
LEARNING_RATE = 0.001
DNN_HIDDEN_UNITS = (256, 128, 64)
DROPOUT = 0.2
TOP_K_RECS = 20         # 每用户推荐数

# 随机种子（保证结果可复现）
RANDOM_SEED = 42


def set_seed(seed=RANDOM_SEED):
    """设置随机种子，确保结果可复现"""
    import random
    import torch
    
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        # 确保 CUDA 卷积操作的确定性
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    
    print(f"   🎲 随机种子已设置: {seed}")


def check_gpu():
    """检查 GPU 状态"""
    print("\n" + "=" * 60)
    print("🔍 检查 GPU 状态")
    print("=" * 60)
    
    try:
        import torch
        
        if torch.cuda.is_available():
            device = torch.device('cuda')
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            print(f"   ✅ CUDA 可用!")
            print(f"   🎮 GPU: {gpu_name}")
            print(f"   💾 显存: {gpu_memory:.1f} GB")
            print(f"   📦 PyTorch: {torch.__version__}")
            
            return device
        else:
            print(f"   ⚠️ CUDA 不可用，使用 CPU")
            return torch.device('cpu')
            
    except ImportError:
        print(f"   ❌ PyTorch 未安装")
        print(f"   📌 请运行: pip install torch --index-url https://download.pytorch.org/whl/cu124")
        sys.exit(1)


def load_data():
    """加载数据"""
    print("\n" + "=" * 60)
    print("📂 [Step 1/5] 加载数据")
    print("=" * 60)
    
    # 加载特征
    print("\n   📥 加载特征数据...")
    with open(FEATURE_PATH, 'rb') as f:
        features = pickle.load(f)
    
    print(f"   ✅ 样本数: {len(features['user_encoded']):,}")
    
    # 加载候选集（如果存在）
    candidates = None
    if os.path.exists(CANDIDATES_PATH):
        print("\n   📥 加载 ALS 候选集...")
        with open(CANDIDATES_PATH, 'rb') as f:
            candidates = pickle.load(f)
        print(f"   ✅ 候选用户数: {len(candidates):,}")
    
    return features, candidates


def prepare_deepfm_data(features):
    """准备 DeepFM 训练数据"""
    print("\n" + "=" * 60)
    print("⚙️ [Step 2/5] 准备训练数据")
    print("=" * 60)
    
    from deepctr_torch.inputs import SparseFeat, get_feature_names
    
    # 构建特征列定义
    sparse_features = ['user', 'song', 'genre', 'language', 'artist']
    
    feature_columns = [
        SparseFeat('user', features['n_users'], embedding_dim=16),
        SparseFeat('song', features['n_songs'], embedding_dim=16),
        SparseFeat('genre', features['n_genres'], embedding_dim=16),
        SparseFeat('language', features['n_languages'], embedding_dim=16),
        SparseFeat('artist', features['n_artists'], embedding_dim=16),
    ]
    
    # 准备训练数据
    data = {
        'user': features['user_encoded'],
        'song': features['song_encoded'],
        'genre': features['genre_encoded'],
        'language': features['language_encoded'],
        'artist': features['artist_encoded'],
    }
    
    # 转为 DataFrame
    df = pd.DataFrame(data)
    target = features['target']
    
    # 分割训练/验证集
    from sklearn.model_selection import train_test_split
    
    train_idx, val_idx = train_test_split(
        np.arange(len(df)), 
        test_size=0.1, 
        random_state=42
    )
    
    train_data = {name: df[name].values[train_idx] for name in sparse_features}
    val_data = {name: df[name].values[val_idx] for name in sparse_features}
    train_target = target[train_idx]
    val_target = target[val_idx]
    
    print(f"   ✅ 训练集: {len(train_idx):,} 样本")
    print(f"   ✅ 验证集: {len(val_idx):,} 样本")
    print(f"   ✅ 正样本比例: {np.mean(train_target):.2%}")
    
    return feature_columns, train_data, val_data, train_target, val_target


def train_deepfm(feature_columns, train_data, val_data, train_target, val_target, device):
    """训练 DeepFM 模型"""
    print("\n" + "=" * 60)
    print("🎯 [Step 3/5] 训练 DeepFM 模型")
    print("=" * 60)
    
    from deepctr_torch.models import DeepFM
    from deepctr_torch.inputs import get_feature_names
    
    print(f"\n   📋 模型配置:")
    print(f"      - DNN 隐藏层: {DNN_HIDDEN_UNITS}")
    print(f"      - Dropout: {DROPOUT}")
    print(f"      - Batch Size: {BATCH_SIZE}")
    print(f"      - Epochs: {EPOCHS}")
    print(f"      - Learning Rate: {LEARNING_RATE}")
    print(f"      - Device: {device}")
    
    # 构建模型
    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=DNN_HIDDEN_UNITS,
        dnn_dropout=DROPOUT,
        device=device
    )
    
    # 编译
    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["binary_crossentropy", "auc"]
    )
    
    # 获取特征名
    feature_names = get_feature_names(feature_columns)
    
    # 准备输入
    train_input = {name: train_data[name] for name in feature_names}
    val_input = {name: val_data[name] for name in feature_names}
    
    print(f"\n   🚀 开始训练...")
    print("=" * 60)
    
    # 训练并记录历史
    history = model.fit(
        train_input,
        train_target,
        batch_size=BATCH_SIZE,
        epochs=EPOCHS,
        validation_data=(val_input, val_target),
        verbose=2  # 显示详细进度
    )
    
    return model, history


def plot_training_history(history):
    """可视化训练过程"""
    print("\n" + "=" * 60)
    print("📊 [Step 4/5] 可视化训练进度")
    print("=" * 60)
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    epochs = range(1, len(history.history['loss']) + 1)
    
    # 确定验证损失的键名（可能是 val_loss 或 val_binary_crossentropy）
    val_loss_key = 'val_loss' if 'val_loss' in history.history else 'val_binary_crossentropy'
    
    # 损失曲线
    ax1 = axes[0]
    ax1.plot(epochs, history.history['loss'], 'b-o', label='Training Loss', linewidth=2, markersize=8)
    if val_loss_key in history.history:
        ax1.plot(epochs, history.history[val_loss_key], 'r-s', label='Validation Loss', linewidth=2, markersize=8)
    ax1.set_xlabel('Epoch', fontsize=12)
    ax1.set_ylabel('Loss', fontsize=12)
    ax1.set_title('Training & Validation Loss', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(epochs)
    
    # AUC 曲线
    ax2 = axes[1]
    if 'auc' in history.history:
        ax2.plot(epochs, history.history['auc'], 'g-o', label='Training AUC', linewidth=2, markersize=8)
        if 'val_auc' in history.history:
            ax2.plot(epochs, history.history['val_auc'], 'm-s', label='Validation AUC', linewidth=2, markersize=8)
        ax2.set_ylabel('AUC', fontsize=12)
        ax2.set_title('Training & Validation AUC', fontsize=14, fontweight='bold')
    else:
        ax2.text(0.5, 0.5, 'AUC not available', ha='center', va='center', fontsize=14)
        ax2.set_title('AUC Curve', fontsize=14, fontweight='bold')
    
    ax2.set_xlabel('Epoch', fontsize=12)
    ax2.legend(loc='lower right', fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(epochs)
    
    plt.tight_layout()
    plt.savefig(TRAINING_PLOT_PATH, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"   ✅ 训练曲线已保存: {TRAINING_PLOT_PATH}")
    
    # 打印最终结果
    final_loss = history.history.get(val_loss_key, history.history['loss'])[-1]
    final_auc = history.history.get('val_auc', [0])[-1]
    print(f"   📈 最终验证损失: {final_loss:.4f}")
    print(f"   📈 最终验证 AUC: {final_auc:.4f}")


def save_model(model, predictions=None):
    """保存模型"""
    print("\n" + "=" * 60)
    print("💾 [Step 5/5] 保存模型")
    print("=" * 60)
    
    import torch
    
    # 保存 PyTorch 模型
    print(f"   📦 保存 DeepFM 模型: {DEEPFM_MODEL_PATH}")
    torch.save(model.state_dict(), DEEPFM_MODEL_PATH)
    
    # 保存预测结果
    if predictions is not None:
        print(f"   📦 保存预测结果: {PREDICTIONS_PATH}")
        with open(PREDICTIONS_PATH, 'wb') as f:
            pickle.dump(predictions, f)
    
    print(f"   ✅ 保存完成!")


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("   MusicMode DeepFM 精排模型训练")
    print("   GPU 加速版本 (RTX 4060)")
    print("🎵" * 30)
    
    # 0. 设置随机种子（确保结果可复现）
    set_seed(RANDOM_SEED)
    
    # 1. 检查 GPU
    device = check_gpu()
    
    # 1. 加载数据
    features, candidates = load_data()
    
    # 2. 准备训练数据
    feature_columns, train_data, val_data, train_target, val_target = prepare_deepfm_data(features)
    
    # 3. 训练 DeepFM
    model, history = train_deepfm(
        feature_columns, 
        train_data, 
        val_data, 
        train_target, 
        val_target, 
        device
    )
    
    # 4. 可视化
    plot_training_history(history)
    
    # 5. 保存
    save_model(model)
    
    print("\n" + "=" * 60)
    print("✅ DeepFM 精排模型训练完成!")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - 模型: {DEEPFM_MODEL_PATH}")
    print(f"   - 训练曲线: {TRAINING_PLOT_PATH}")
    print(f"\n🚀 下一步: 运行 sync_recs.py 将推荐结果写入数据库")


if __name__ == "__main__":
    main()
