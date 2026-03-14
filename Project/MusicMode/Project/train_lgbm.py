# -*- coding: utf-8 -*-
"""
train_lgbm.py — LightGBM 精排模型训练

特点：
  - 输入: features_v3.pkl（25个特征，来自 prepare_features_v3.py）
  - 目标: 预测"30天内重复收听"概率（二分类）
  - 模型: LightGBM（num_leaves=127, max_depth=7, n_estimators=2000）
  - 特征: 所有 13 个稀疏特征（原始值）+ 12 个稠密特征
  - 输出: lgbm_model.pkl（精排模型）+ lgbm_feature_importance.png

执行：
  python train_lgbm.py

预计时间：约 15-30 分钟（7.37M 样本，CPU 训练）
预期 AUC：0.87-0.90

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import lightgbm as lgb

warnings.filterwarnings('ignore')

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES = os.path.join(MODE_DIR, "features_v3.pkl")
OUTPUT_MODEL   = os.path.join(MODE_DIR, "lgbm_model.pkl")
OUTPUT_PLOT    = os.path.join(MODE_DIR, "lgbm_importance.png")

# 训练配置
VALID_RATIO  = 0.1    # 验证集比例
RANDOM_SEED  = 42
N_JOBS       = -1     # 使用全部 CPU 核心

# LightGBM 超参数（KKBOX Kaggle 竞赛最优实践）
LGBM_PARAMS = {
    "objective":       "binary",
    "metric":          "auc",
    "boosting_type":   "gbdt",
    "num_leaves":      127,
    "max_depth":       7,
    "min_child_samples": 100,
    "learning_rate":   0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":    5,
    "reg_alpha":       0.1,
    "reg_lambda":      0.1,
    "n_estimators":    2000,
    "early_stopping_rounds": 100,
    "verbose":         -1,
    "n_jobs":          N_JOBS,
    "random_state":    RANDOM_SEED,
}


# ============================================================
# 特征列定义
# ============================================================

# 稀疏特征（直接用原始编码值，LightGBM 自动处理）
SPARSE_FEATURES = [
    "user_id_encoded", "song_id_encoded",
    "gender_encoded", "age_bucket_encoded", "city_encoded",
    "tenure_bucket_encoded", "genre_encoded", "language_encoded",
    "artist_encoded", "origin_country_encoded",
    "year_bucket_encoded", "duration_bucket_encoded",
    "source_channel_encoded",
]

# 稠密特征
DENSE_FEATURES = [
    "user_play_count_log", "user_avg_completion",
    "user_genre_diversity", "user_30d_active_days",
    "song_play_count_log", "song_avg_completion",
    "song_popularity_norm", "song_age_days_log",
    "user_genre_match", "user_artist_match",
    "user_language_match", "user_country_match",
]

ALL_FEATURES = SPARSE_FEATURES + DENSE_FEATURES


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "🌲" * 31)
    print("   LightGBM 精排模型训练")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🌲" * 31)

    # ── 1. 加载特征数据
    print(f"\n📥 加载特征: {INPUT_FEATURES}")
    if not os.path.exists(INPUT_FEATURES):
        print("❌ 特征文件不存在！请先运行 prepare_features_v3.py")
        sys.exit(1)

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)

    # ── 2. 构建特征矩阵
    print(f"\n🔧 构建特征矩阵...")
    arrays = {}
    for col in ALL_FEATURES:
        if col in feat:
            arrays[col] = feat[col]
        else:
            print(f"   ⚠️  缺少特征 {col}，用 0 填充")
            arrays[col] = np.zeros(len(feat["target"]))

    X = np.column_stack([arrays[c] for c in ALL_FEATURES]).astype(np.float32)
    y = feat["target"].astype(np.int8)

    print(f"   特征矩阵形状: {X.shape}")
    print(f"   正样本率: {y.mean():.4f}")

    # ── 3. 训练集/验证集分割
    print(f"\n🔀 分割数据集（验证集 {VALID_RATIO*100:.0f}%）...")
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=VALID_RATIO, random_state=RANDOM_SEED, stratify=y
    )
    print(f"   训练集: {X_train.shape[0]:,} 样本")
    print(f"   验证集: {X_val.shape[0]:,} 样本")

    train_data = lgb.Dataset(X_train, label=y_train, feature_name=ALL_FEATURES)
    val_data   = lgb.Dataset(X_val,   label=y_val,   feature_name=ALL_FEATURES,
                              reference=train_data)

    # ── 4. 训练
    print(f"\n🚀 开始训练 LightGBM ...")
    print(f"   参数: num_leaves={LGBM_PARAMS['num_leaves']}, "
          f"max_depth={LGBM_PARAMS['max_depth']}, "
          f"n_estimators={LGBM_PARAMS['n_estimators']}")

    callbacks = [
        lgb.early_stopping(LGBM_PARAMS["early_stopping_rounds"], verbose=True),
        lgb.log_evaluation(period=50),
    ]

    model = lgb.train(
        params={k: v for k, v in LGBM_PARAMS.items()
                if k not in ("n_estimators", "early_stopping_rounds")},
        train_set=train_data,
        num_boost_round=LGBM_PARAMS["n_estimators"],
        valid_sets=[train_data, val_data],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    # ── 5. 评估
    print(f"\n📊 模型评估...")
    val_pred = model.predict(X_val, num_iteration=model.best_iteration)
    val_auc  = roc_auc_score(y_val, val_pred)
    train_pred = model.predict(X_train, num_iteration=model.best_iteration)
    train_auc  = roc_auc_score(y_train, train_pred)

    print(f"   训练集 AUC: {train_auc:.4f}")
    print(f"   验证集 AUC: {val_auc:.4f}")
    print(f"   最佳迭代轮次: {model.best_iteration}")

    # ── 6. 特征重要性图
    print(f"\n📈 绘制特征重要性图...")
    importance_df = pd.DataFrame({
        "feature": ALL_FEATURES,
        "importance": model.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False)

    fig, ax = plt.subplots(figsize=(10, max(6, len(ALL_FEATURES) * 0.4)))
    ax.barh(importance_df["feature"][::-1], importance_df["importance"][::-1])
    ax.set_xlabel("Importance (Gain)")
    ax.set_title(f"LightGBM Feature Importance (val AUC={val_auc:.4f})")
    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=120)
    plt.close()
    print(f"   ✅ 已保存: {OUTPUT_PLOT}")

    # ── 7. 保存模型
    print(f"\n💾 保存模型: {OUTPUT_MODEL}")
    model_payload = {
        "model":           model,
        "feature_names":   ALL_FEATURES,
        "best_iteration":  model.best_iteration,
        "val_auc":         val_auc,
        "train_auc":       train_auc,
        "train_time":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_train":         X_train.shape[0],
        "n_val":           X_val.shape[0],
        "feature_importance": importance_df.to_dict("records"),
    }
    with open(OUTPUT_MODEL, "wb") as f:
        pickle.dump(model_payload, f, protocol=4)
    print(f"   ✅ 模型已保存（{os.path.getsize(OUTPUT_MODEL)/1024/1024:.1f} MB）")

    # ── 8. 打印 Top10 特征
    print(f"\n🏆 Top-10 重要特征:")
    for i, row in importance_df.head(10).iterrows():
        print(f"   {row['feature']:<35} {row['importance']:>12.0f}")

    print(f"\n" + "=" * 62)
    print(f"✅ LightGBM 训练完成！")
    print(f"   验证集 AUC: {val_auc:.4f}")
    print(f"   完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)
    print(f"\n🚀 下一步: python train_deepfm_v3.py")


if __name__ == "__main__":
    main()
