# -*- coding: utf-8 -*-
"""
DeepFM 精排模型训练 (GPU AMP + CPU 多线程数据加载)
功能：
1. 加载特征数据（动态支持 5~8 个 SparseFeat）
2. 混合精度（AMP FP16）训练，GPU Tensor Core 加速
3. DataLoader num_workers=4 + pin_memory，CPU 预取并行
4. 每步实时 tqdm 进度条（loss / AUC 即时显示）
5. 保存模型权重 + 特征配置（model_config.pkl）

硬件：NVIDIA RTX 4060 Laptop (8GB VRAM) + i9-13900HX (32线程)
"""

import os
import sys
import pickle
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")
FEATURE_PATH    = os.path.join(MODE_DIR, "features.pkl")
CANDIDATES_PATH = os.path.join(MODE_DIR, "candidates.pkl")
DEEPFM_MODEL_PATH   = os.path.join(MODE_DIR, "deepfm_model.pth")
MODEL_CONFIG_PATH   = os.path.join(MODE_DIR, "model_config.pkl")   # 新增：保存特征配置
TRAINING_PLOT_PATH  = os.path.join(MODE_DIR, "training_progress.png")

# 训练超参数
BATCH_SIZE    = 4096        # 从 256 → 4096，减少 steps/epoch ~16x
EPOCHS        = 5
LEARNING_RATE = 0.001
DNN_HIDDEN_UNITS = (256, 128, 64)
DROPOUT       = 0.2
EMBEDDING_DIM = 16
NUM_WORKERS   = 4           # CPU 数据加载线程数

RANDOM_SEED = 42


# ============================================
# 工具函数
# ============================================

def set_seed(seed=RANDOM_SEED):
    import random, torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def check_gpu():
    import torch
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"\n✅ GPU: {name}  ({vram:.1f} GB VRAM)")
        print(f"   PyTorch {torch.__version__}  CUDA {torch.version.cuda}")
        print(f"   AMP (FP16 混合精度) 已启用")
        print(f"   DataLoader num_workers={NUM_WORKERS}, pin_memory=True")
        return torch.device('cuda')
    else:
        print("⚠️  CUDA 不可用，回退 CPU")
        return torch.device('cpu')


# ============================================
# Step 1: 加载数据
# ============================================

def load_data():
    print("\n" + "=" * 60)
    print("📂 [Step 1/4] 加载特征数据")
    print("=" * 60)

    with open(FEATURE_PATH, 'rb') as f:
        features = pickle.load(f)

    n = len(features['user_encoded'])
    print(f"\n   样本数: {n:,}")
    print(f"   用户数: {features['n_users']:,}")
    print(f"   歌曲数: {features['n_songs']:,}")
    print(f"   流派数: {features['n_genres']:,}")
    print(f"   语言数: {features['n_languages']:,}")
    print(f"   艺术家数: {features['n_artists']:,}")
    for extra in ('n_cities', 'n_genders', 'n_source_types'):
        if extra in features:
            print(f"   {extra}: {features[extra]:,}")

    candidates = None
    if os.path.exists(CANDIDATES_PATH):
        with open(CANDIDATES_PATH, 'rb') as f:
            candidates = pickle.load(f)
        print(f"   候选用户数: {len(candidates):,}")

    return features, candidates


# ============================================
# Step 2: 准备训练数据 + 构建特征列
# ============================================

def prepare_deepfm_data(features):
    print("\n" + "=" * 60)
    print("⚙️  [Step 2/4] 构建特征列 & 分割数据")
    print("=" * 60)

    from deepctr_torch.inputs import SparseFeat

    # 核心特征（必须存在）
    feat_specs = [
        ('user',     'n_users'),
        ('song',     'n_songs'),
        ('genre',    'n_genres'),
        ('language', 'n_languages'),
        ('artist',   'n_artists'),
    ]
    # 扩展特征（可选，v6.0 新增）
    optional_specs = [
        ('city',        'n_cities',        'city_encoded'),
        ('gender',      'n_genders',       'gender_encoded'),
        ('source_type', 'n_source_types',  'source_type_encoded'),
    ]

    feature_columns = [
        SparseFeat(name, features[n_key], embedding_dim=EMBEDDING_DIM)
        for name, n_key in feat_specs
    ]
    sparse_features = [name for name, _ in feat_specs]

    for name, n_key, enc_key in optional_specs:
        if n_key in features and enc_key in features:
            feature_columns.append(SparseFeat(name, features[n_key], embedding_dim=EMBEDDING_DIM))
            sparse_features.append(name)
            print(f"   ✅ 可选特征 [{name}] 已加入（{features[n_key]} 个类别）")

    print(f"\n   特征总数: {len(feature_columns)} 个 SparseFeat")

    # 构造数据字典
    data = {
        'user':     features['user_encoded'],
        'song':     features['song_encoded'],
        'genre':    features['genre_encoded'],
        'language': features['language_encoded'],
        'artist':   features['artist_encoded'],
    }
    for name, n_key, enc_key in optional_specs:
        if enc_key in features:
            data[name] = features[enc_key]

    df = pd.DataFrame(data)
    target = features['target'].astype(np.float32)

    # 90/10 分割
    from sklearn.model_selection import train_test_split
    train_idx, val_idx = train_test_split(
        np.arange(len(df)), test_size=0.1, random_state=RANDOM_SEED
    )

    train_data = {name: df[name].values[train_idx] for name in sparse_features}
    val_data   = {name: df[name].values[val_idx]   for name in sparse_features}
    train_target = target[train_idx]
    val_target   = target[val_idx]

    pos_rate = np.mean(train_target)
    print(f"   训练集: {len(train_idx):,}  验证集: {len(val_idx):,}")
    print(f"   正样本比例: {pos_rate:.2%}")

    return feature_columns, sparse_features, train_data, val_data, train_target, val_target


# ============================================
# Step 3: 训练（AMP + 并行 DataLoader）
# ============================================

def train_deepfm(feature_columns, sparse_features,
                 train_data, val_data, train_target, val_target, device):
    import torch
    import torch.utils.data as Data
    from torch.amp import autocast, GradScaler
    from torch.optim import Adam
    from deepctr_torch.models import DeepFM
    from deepctr_torch.inputs import get_feature_names
    from sklearn.metrics import roc_auc_score, log_loss

    print("\n" + "=" * 60)
    print("🚀 [Step 3/4] 训练 DeepFM（AMP + 并行 DataLoader）")
    print("=" * 60)
    print(f"\n   DNN 隐藏层: {DNN_HIDDEN_UNITS}")
    print(f"   Dropout:    {DROPOUT}")
    print(f"   Batch Size: {BATCH_SIZE:,}")
    print(f"   Epochs:     {EPOCHS}")
    print(f"   LR:         {LEARNING_RATE}")
    print(f"   Device:     {device}")

    # 构建模型（用 'cpu' 初始化，手动 .to(device) 以便后面 compile）
    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=DNN_HIDDEN_UNITS,
        dnn_dropout=DROPOUT,
        device=str(device)
    )

    # torch.compile Inductor 后端需要 Triton（仅 Linux 支持），Windows 跳过
    if sys.platform != 'win32':
        try:
            model = torch.compile(model, mode='default')
            print("   torch.compile ✅")
        except Exception:
            print("   torch.compile 不可用，跳过")
    else:
        print("   torch.compile 跳过（Windows / Triton 不支持）")

    model = model.to(device)
    optimizer = Adam(model.parameters(), lr=LEARNING_RATE)
    loss_fn = torch.nn.BCELoss(reduction='mean')
    scaler = GradScaler(device=str(device)) if device.type == 'cuda' else None
    use_amp = (device.type == 'cuda')

    # 准备张量数据
    feature_names = get_feature_names(feature_columns)

    def make_tensor(data_dict):
        arrays = [data_dict[f].reshape(-1, 1) for f in feature_names]
        return torch.from_numpy(np.concatenate(arrays, axis=-1))

    X_train = make_tensor(train_data)
    y_train = torch.from_numpy(train_target)
    X_val   = make_tensor(val_data).to(device).float()
    y_val   = torch.from_numpy(val_target).to(device).float()

    train_dataset = Data.TensorDataset(X_train, y_train)
    train_loader  = Data.DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        pin_memory=(device.type == 'cuda'),
        persistent_workers=(NUM_WORKERS > 0),
        prefetch_factor=2 if NUM_WORKERS > 0 else None,
    )

    steps_per_epoch = len(train_loader)
    print(f"\n   Steps/epoch: {steps_per_epoch:,}")
    print(f"\n{'='*60}")

    history = {'loss': [], 'val_loss': [], 'val_auc': []}

    for epoch in range(EPOCHS):
        model.train()
        epoch_loss = 0.0
        t_epoch = time.time()

        pbar = tqdm(
            train_loader,
            total=steps_per_epoch,
            desc=f"Epoch {epoch+1:2d}/{EPOCHS}",
            ncols=100,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}"
        )

        for step, (x_batch, y_batch) in enumerate(pbar):
            x_batch = x_batch.to(device, non_blocking=True).float()
            y_batch = y_batch.to(device, non_blocking=True).float()

            optimizer.zero_grad(set_to_none=True)

            if use_amp:
                with autocast(device_type='cuda'):
                    y_pred = model(x_batch).squeeze()
                # BCELoss 需要 float32，在 autocast 外计算
                loss = loss_fn(y_pred.float(), y_batch.float())
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                y_pred = model(x_batch).squeeze()
                loss = loss_fn(y_pred, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            epoch_loss += loss.item()
            avg_loss = epoch_loss / (step + 1)

            if (step + 1) % 50 == 0 or step == 0:
                pbar.set_postfix(loss=f"{avg_loss:.4f}", refresh=False)

        # 验证集评估
        model.eval()
        val_preds_list = []
        val_batch_size = BATCH_SIZE * 4
        val_dataset = Data.TensorDataset(X_val, y_val)
        val_loader  = Data.DataLoader(val_dataset, batch_size=val_batch_size, shuffle=False)

        with torch.no_grad():
            for xv, _ in val_loader:
                if use_amp:
                    with autocast(device_type='cuda'):
                        vp = model(xv).squeeze()
                else:
                    vp = model(xv).squeeze()
                val_preds_list.append(vp.cpu().float().numpy())

        val_preds = np.concatenate(val_preds_list)
        val_true  = y_val.cpu().numpy()

        val_loss = log_loss(val_true, val_preds)
        val_auc  = roc_auc_score(val_true, val_preds)
        history['loss'].append(epoch_loss / steps_per_epoch)
        history['val_loss'].append(val_loss)
        history['val_auc'].append(val_auc)

        elapsed = time.time() - t_epoch
        print(f"  → Epoch {epoch+1}/{EPOCHS}  "
              f"loss={epoch_loss/steps_per_epoch:.4f}  "
              f"val_loss={val_loss:.4f}  val_AUC={val_auc:.4f}  "
              f"({elapsed:.0f}s)")

    # 如果用了 torch.compile，拆包回原始模型
    raw_model = model
    if hasattr(model, '_orig_mod'):
        raw_model = model._orig_mod

    return raw_model, history


# ============================================
# Step 4: 可视化 + 保存
# ============================================

def plot_training_history(history):
    print("\n" + "=" * 60)
    print("📊 绘制训练曲线")
    print("=" * 60)

    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    epochs = range(1, len(history['loss']) + 1)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax1 = axes[0]
    ax1.plot(epochs, history['loss'],     'b-o', label='Train Loss',  lw=2, ms=8)
    ax1.plot(epochs, history['val_loss'], 'r-s', label='Val Loss',    lw=2, ms=8)
    ax1.set_xlabel('Epoch'); ax1.set_ylabel('Loss')
    ax1.set_title('Loss Curve', fontweight='bold')
    ax1.legend(); ax1.grid(alpha=0.3); ax1.set_xticks(list(epochs))

    ax2 = axes[1]
    ax2.plot(epochs, history['val_auc'], 'g-o', label='Val AUC', lw=2, ms=8)
    ax2.set_xlabel('Epoch'); ax2.set_ylabel('AUC')
    ax2.set_title('Validation AUC', fontweight='bold')
    ax2.legend(); ax2.grid(alpha=0.3); ax2.set_xticks(list(epochs))
    ax2.set_ylim([max(0.5, min(history['val_auc']) - 0.02), 1.0])

    plt.tight_layout()
    plt.savefig(TRAINING_PLOT_PATH, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"   训练曲线已保存: {TRAINING_PLOT_PATH}")
    print(f"   最终 val_loss={history['val_loss'][-1]:.4f}  val_AUC={history['val_auc'][-1]:.4f}")


def save_model(model, feature_columns, history):
    import torch

    print("\n" + "=" * 60)
    print("💾 保存模型")
    print("=" * 60)

    # 保存模型权重
    torch.save(model.state_dict(), DEEPFM_MODEL_PATH)
    size_mb = os.path.getsize(DEEPFM_MODEL_PATH) / 1024 / 1024
    print(f"   模型权重: {DEEPFM_MODEL_PATH}  ({size_mb:.1f} MB)")

    # 保存特征配置（供 build_faiss_index.py 重建模型）
    config = {
        'feature_columns': feature_columns,
        'dnn_hidden_units': DNN_HIDDEN_UNITS,
        'dnn_dropout': DROPOUT,
        'embedding_dim': EMBEDDING_DIM,
        'history': history,
    }
    with open(MODEL_CONFIG_PATH, 'wb') as f:
        pickle.dump(config, f)
    print(f"   模型配置: {MODEL_CONFIG_PATH}")
    print("   ✅ 保存完成")


# ============================================
# main
# ============================================

def main():
    print("\n" + "=" * 60)
    print("  MusicMode DeepFM — GPU AMP + CPU 并行数据加载")
    print(f"  Batch={BATCH_SIZE}  Epochs={EPOCHS}  Workers={NUM_WORKERS}")
    print("=" * 60)

    set_seed(RANDOM_SEED)
    device = check_gpu()

    features, candidates = load_data()

    feature_columns, sparse_features, train_data, val_data, train_target, val_target = \
        prepare_deepfm_data(features)

    model, history = train_deepfm(
        feature_columns, sparse_features,
        train_data, val_data, train_target, val_target, device
    )

    plot_training_history(history)
    save_model(model, feature_columns, history)

    print("\n" + "=" * 60)
    print("✅ DeepFM 训练完成!")
    print(f"   模型: {DEEPFM_MODEL_PATH}")
    print(f"   配置: {MODEL_CONFIG_PATH}")
    print(f"   曲线: {TRAINING_PLOT_PATH}")
    print("=" * 60)
    print("\n下一步: python build_faiss_index.py")


if __name__ == "__main__":
    main()
