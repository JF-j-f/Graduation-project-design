# -*- coding: utf-8 -*-
"""
build_ensemble.py — LightGBM + DeepFM 集成系数校准

功能：
  在验证集上搜索最优混合系数 α：
    final_score = α × LightGBM_score + (1-α) × DeepFM_score
  输出: ensemble_config.pkl（含最优 α 和集成 AUC）

执行：
  python build_ensemble.py

预计时间：约 3-5 分钟

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from datetime import datetime

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES   = os.path.join(MODE_DIR, "features_v3.pkl")
INPUT_LGBM       = os.path.join(MODE_DIR, "lgbm_model.pkl")
INPUT_DEEPFM     = os.path.join(MODE_DIR, "deepfm_model_v3.pth")
INPUT_DEEPFM_CFG = os.path.join(MODE_DIR, "model_config_v3.pkl")
OUTPUT_ENSEMBLE  = os.path.join(MODE_DIR, "ensemble_config.pkl")

# 搜索 α 的范围（步长 0.05，从偏 LightGBM 到偏 DeepFM）
ALPHA_RANGE = np.arange(0.0, 1.05, 0.05)

VALID_RATIO  = 0.1
RANDOM_SEED  = 42
BATCH_SIZE   = 8192   # DeepFM 推断批次


# ============================================================
# 工具
# ============================================================

def check_files():
    missing = []
    for path, name in [
        (INPUT_FEATURES,   "features_v3.pkl"),
        (INPUT_LGBM,       "lgbm_model.pkl"),
        (INPUT_DEEPFM,     "deepfm_model_v3.pth"),
        (INPUT_DEEPFM_CFG, "model_config_v3.pkl"),
    ]:
        if not os.path.exists(path):
            missing.append(name)
    if missing:
        print("❌ 缺少必要文件:")
        for m in missing:
            print(f"   - {m}")
        print("\n   请按顺序执行:")
        print("   1. python prepare_features_v3.py")
        print("   2. python train_lgbm.py")
        print("   3. python train_deepfm_v3.py")
        sys.exit(1)


# ============================================================
# Step 1: 加载数据 & 划分验证集
# ============================================================

def load_val_data():
    print("\n" + "=" * 62)
    print("📂 [Step 1/4] 加载特征数据 & 划分验证集")
    print("=" * 62)

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)

    # ── LightGBM 需要的特征矩阵
    SPARSE_FEATURES = [
        "user_id_encoded", "song_id_encoded",
        "gender_encoded", "age_bucket_encoded", "city_encoded",
        "tenure_bucket_encoded", "genre_encoded", "language_encoded",
        "artist_encoded", "origin_country_encoded",
        "year_bucket_encoded", "duration_bucket_encoded",
        "source_channel_encoded",
    ]
    DENSE_FEATURES = [
        "user_play_count_log", "user_avg_completion",
        "user_genre_diversity", "user_30d_active_days",
        "song_play_count_log", "song_avg_completion",
        "song_popularity_norm", "song_age_days_log",
        "user_genre_match", "user_artist_match",
        "user_language_match", "user_country_match",
    ]
    ALL_FEATURES = SPARSE_FEATURES + DENSE_FEATURES

    arrays = {}
    for col in ALL_FEATURES:
        if col in feat:
            arrays[col] = feat[col]
        else:
            arrays[col] = np.zeros(len(feat["target"]))

    X = np.column_stack([arrays[c] for c in ALL_FEATURES]).astype(np.float32)
    y = feat["target"].astype(np.int8)

    from sklearn.model_selection import train_test_split
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=VALID_RATIO, random_state=RANDOM_SEED, stratify=y
    )
    print(f"   验证集: {len(y_val):,} 样本  |  正样本率: {y_val.mean():.4f}")

    return X_val, y_val, feat, ALL_FEATURES


# ============================================================
# Step 2: LightGBM 推断
# ============================================================

def lgbm_predict(X_val):
    print("\n" + "=" * 62)
    print("🌲 [Step 2/4] LightGBM 预测")
    print("=" * 62)

    with open(INPUT_LGBM, "rb") as f:
        payload = pickle.load(f)

    lgbm_model = payload["model"]
    best_iter  = payload.get("best_iteration", None)
    val_auc    = payload.get("val_auc", float("nan"))

    preds = lgbm_model.predict(X_val, num_iteration=best_iter)
    print(f"   LightGBM 验证集 AUC（来自训练记录）: {val_auc:.4f}")
    return preds


# ============================================================
# Step 3: DeepFM 推断
# ============================================================

def deepfm_predict(feat, y_val_size):
    print("\n" + "=" * 62)
    print("🧠 [Step 3/4] DeepFM v3 预测")
    print("=" * 62)

    import torch
    from deepctr_torch.models import DeepFM
    from deepctr_torch.inputs import get_feature_names
    from sklearn.model_selection import train_test_split

    with open(INPUT_DEEPFM_CFG, "rb") as f:
        cfg = pickle.load(f)

    feature_columns  = cfg["feature_columns"]
    dnn_hidden_units = cfg.get("dnn_hidden_units", (512, 256, 128, 64))
    dnn_dropout      = cfg.get("dnn_dropout", 0.2)
    sparse_specs     = cfg.get("sparse_feat_specs", [])
    dense_specs      = cfg.get("dense_feat_specs", [])

    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=dnn_hidden_units,
        dnn_dropout=dnn_dropout,
        device='cpu',
    )
    state_dict = torch.load(INPUT_DEEPFM, map_location='cpu', weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"   DeepFM v3 加载完成  |  特征列: {len(feature_columns)} 个")

    # 重建数据字典
    feature_names = get_feature_names(feature_columns)
    n_total = len(feat["target"])
    target  = feat["target"].astype(np.float32)
    indices = np.arange(n_total)

    _, val_idx = train_test_split(
        indices, test_size=VALID_RATIO, random_state=RANDOM_SEED, stratify=target
    )

    data_dict = {}
    for feat_name, enc_key, n_key, _ in sparse_specs:
        if enc_key in feat:
            data_dict[feat_name] = feat[enc_key][val_idx].astype(np.int32)
    for feat_name in dense_specs:
        if feat_name in feat:
            arr = feat[feat_name][val_idx].astype(np.float32)
            data_dict[feat_name] = np.nan_to_num(arr, nan=0.0)

    # 构建 Tensor
    arrays = [data_dict[f].reshape(-1, 1) for f in feature_names]
    X_tensor = torch.from_numpy(np.concatenate(arrays, axis=1)).float()

    # 批量推断
    val_preds = []
    n = X_tensor.shape[0]
    with torch.no_grad():
        for start in range(0, n, BATCH_SIZE):
            batch = X_tensor[start:start+BATCH_SIZE]
            out = model(batch).squeeze().cpu().numpy()
            val_preds.append(out)

    preds = np.concatenate(val_preds)
    print(f"   推断完成: {len(preds):,} 个样本")
    return preds


# ============================================================
# Step 4: 搜索最优 α
# ============================================================

def search_alpha(y_val, lgbm_preds, deepfm_preds):
    print("\n" + "=" * 62)
    print("🔍 [Step 4/4] 搜索最优集成系数 α")
    print("=" * 62)

    from sklearn.metrics import roc_auc_score

    y_val_f = y_val.astype(np.float32)
    lgbm_auc   = roc_auc_score(y_val_f, lgbm_preds)
    deepfm_auc = roc_auc_score(y_val_f, deepfm_preds)
    print(f"\n   LightGBM  AUC: {lgbm_auc:.4f}")
    print(f"   DeepFM v3 AUC: {deepfm_auc:.4f}")

    print(f"\n   {'α':>6}  {'集成 AUC':>12}")
    print("   " + "-" * 22)

    best_alpha = 0.5
    best_auc   = 0.0
    results    = []

    for alpha in ALPHA_RANGE:
        ensemble = alpha * lgbm_preds + (1 - alpha) * deepfm_preds
        auc = roc_auc_score(y_val_f, ensemble)
        results.append((alpha, auc))
        marker = " ← 最优" if auc > best_auc else ""
        print(f"   α={alpha:.2f}   AUC={auc:.4f}{marker}")
        if auc > best_auc:
            best_auc   = auc
            best_alpha = alpha

    print(f"\n{'='*62}")
    print(f"   最优 α = {best_alpha:.2f}")
    print(f"   集成 AUC = {best_auc:.4f}")
    print(f"   vs 单模型最优 = {max(lgbm_auc, deepfm_auc):.4f}")
    improvement = (best_auc - max(lgbm_auc, deepfm_auc)) * 100
    print(f"   集成提升: +{improvement:.2f} AUC 百分点")

    return best_alpha, best_auc, lgbm_auc, deepfm_auc, results


# ============================================================
# 保存配置
# ============================================================

def save_ensemble_config(best_alpha, best_auc, lgbm_auc, deepfm_auc, results):
    config = {
        "alpha":       best_alpha,      # final_score = α*LGBM + (1-α)*DeepFM
        "ensemble_auc": best_auc,
        "lgbm_auc":    lgbm_auc,
        "deepfm_auc":  deepfm_auc,
        "search_results": results,      # [(alpha, auc), ...]
        "calibrated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version":     "v3",
    }
    with open(OUTPUT_ENSEMBLE, "wb") as f:
        pickle.dump(config, f, protocol=4)
    print(f"\n   ✅ 集成配置已保存: {OUTPUT_ENSEMBLE}")


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "=" * 62)
    print("   集成系数校准 — LightGBM + DeepFM")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    check_files()

    X_val, y_val, feat, all_features = load_val_data()
    lgbm_preds   = lgbm_predict(X_val)
    deepfm_preds = deepfm_predict(feat, len(y_val))

    best_alpha, best_auc, lgbm_auc, deepfm_auc, results = search_alpha(
        y_val, lgbm_preds, deepfm_preds
    )
    save_ensemble_config(best_alpha, best_auc, lgbm_auc, deepfm_auc, results)

    print("\n" + "=" * 62)
    print("✅ 集成系数校准完成！")
    print(f"   final_score = {best_alpha:.2f} × LightGBM + "
          f"{1-best_alpha:.2f} × DeepFM")
    print(f"   集成 AUC: {best_auc:.4f}")
    print("=" * 62)
    print("\n🚀 下一步:")
    print("   python sync_recs_v3.py   # 生成个性化推荐")


if __name__ == "__main__":
    main()
