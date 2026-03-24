# -*- coding: utf-8 -*-
"""
train_din.py — DIN 精排模型训练

特点：
  - 输入: features_v3.pkl（来自 prepare_features_v3.py）
  - 目标: 预测"30天内重复收听"概率（二分类）
  - 模型: DeepFM 架构变体（DNN=(256,128,64)，与 DeepFM 形成模型多样性）
  - 输出: din_model.pth + din_metrics.csv
  - 框架: DeepCTR-Torch

执行：
  python train_din.py

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES   = os.path.join(MODE_DIR, "features_v3.pkl")
DIN_DIR          = os.path.join(MODE_DIR, "din")
os.makedirs(DIN_DIR, exist_ok=True)
OUTPUT_MODEL     = os.path.join(DIN_DIR, "din_model.pth")
OUTPUT_CONFIG    = os.path.join(DIN_DIR, "model_config.pkl")
OUTPUT_PLOT      = os.path.join(DIN_DIR, "training_progress.png")
OUTPUT_HISTORY   = os.path.join(DIN_DIR, "din_metrics.csv")

# 训练超参数
BATCH_SIZE       = 8192        # 每批样本数，较大批次梯度更稳定
EPOCHS           = 30          # 最大训练轮数，配合早停使用
LEARNING_RATE    = 0.001       # 初始学习率
DNN_HIDDEN_UNITS = (256, 128, 64)  # DNN 各隐藏层维度
DROPOUT          = 0.4         # Dropout 丢弃比例
NUM_WORKERS      = 4           # DataLoader 并行工作进程数
RANDOM_SEED      = 42          # 随机种子，保证实验可复现

# ReduceLROnPlateau 学习率衰减参数
LR_PATIENCE      = 3           # 验证 loss 连续 N 轮无改善后触发 LR 衰减
LR_FACTOR        = 0.5         # 每次触发后 LR 乘以该因子
LR_MIN           = 5e-6        # LR 下限，低于此值不再衰减

# 早停参数
EARLY_STOP_PATIENCE = 10       # 验证 AUC 连续 N 轮无提升则终止训练

# 验证集比例
VALID_RATIO = 0.1              # 10%，与 LightGBM/DeepFM 一致


# ============================================================
# 特征列定义（与 DeepFM 基本一致，但 DIN 需要 behavior 序列特征）
# ============================================================

# (deepctr特征名, pkl编码键, pkl基数键, embedding维度)
# ⚠️ DeepCTR-Torch 要求所有 SparseFeat embedding_dim 一致
SPARSE_FEAT_SPECS = [
    ("user_id",         "user_id_encoded",          "n_users",         16),
    ("song_id",         "song_id_encoded",           "n_songs",         16),
    ("genre",           "genre_encoded",             "n_genres",        16),
    ("language",        "language_encoded",          "n_languages",     16),
    ("artist",          "artist_encoded",            "n_artists",       16),
    ("origin_country",  "origin_country_encoded",    "n_countries",     16),
    ("year_bucket",     "year_bucket_encoded",       "n_year_buckets",  16),
    ("source_channel",  "source_channel_encoded",    "n_sources",       16),
    ("city",            "city_encoded",              "n_cities",        16),
    ("gender",          "gender_encoded",            "n_genders",       16),
    ("age_bucket",      "age_bucket_encoded",        "n_age_buckets",   16),
    ("tenure_bucket",   "tenure_bucket_encoded",     "n_tenures",       16),
    ("duration_bucket", "duration_bucket_encoded",   "n_dur_buckets",   16),
    ("user_peak_hour",  "user_peak_hour_encoded",    "n_peak_hours",    16),
]

DENSE_FEAT_SPECS = [
    "user_play_count_log",
    "user_avg_completion",
    "song_play_count_log",
    "song_avg_completion",
    "song_unique_users_log",
    "song_age_days_log",
    "user_genre_match",
    "user_artist_match",
    "user_language_match",
    "user_country_match",
    "user_skip_rate",
    "song_skip_rate",
    "hour_match",
    "days_since_artist_log",
    *[f"svd_user_song_{i}" for i in [0, 2, 3, 4, 5, 6, 9]],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in [0, 3, 4]],
    "svd_dot_score",
    "user_history_position",
]


# ============================================================
# 工具函数
# ============================================================

def set_seed(seed=RANDOM_SEED):
    import random, torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark     = False


def check_gpu():
    import torch
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"\n✅ GPU: {name}  ({vram:.1f} GB VRAM)")
        return torch.device('cuda')
    else:
        print("⚠️  CUDA 不可用，回退 CPU")
        return torch.device('cpu')


# ============================================================
# 数据准备（DIN 使用与 DeepFM 相同的特征，但用 DIN 模型架构）
# ============================================================

def prepare_din_data(feat):
    print("\n" + "=" * 62)
    print("⚙️  [Step 2/4] 构建特征列 & 分割数据集")
    print("=" * 62)

    from deepctr_torch.inputs import SparseFeat, DenseFeat, get_feature_names

    # ── 构建特征列
    feature_columns = []
    active_sparse_specs = []
    for feat_name, enc_key, n_key, embed_dim in SPARSE_FEAT_SPECS:
        if enc_key in feat and n_key in feat:
            vocab_size = int(feat[n_key]) + 1
            feature_columns.append(
                SparseFeat(feat_name, vocabulary_size=vocab_size,
                           embedding_dim=embed_dim)
            )
            active_sparse_specs.append((feat_name, enc_key, n_key, embed_dim))
        else:
            print(f"   ⚠️  缺少稀疏特征 [{feat_name}]，跳过")

    active_dense_specs = []
    for feat_name in DENSE_FEAT_SPECS:
        if feat_name in feat:
            feature_columns.append(DenseFeat(feat_name, dimension=1))
            active_dense_specs.append(feat_name)
        else:
            print(f"   ⚠️  缺少稠密特征 [{feat_name}]，跳过")

    print(f"\n   稀疏特征: {len(active_sparse_specs)} | 稠密特征: {len(active_dense_specs)}")

    # ── 构建数据字典
    n_samples = len(feat["target"])
    data_dict = {}
    for feat_name, enc_key, _, _ in active_sparse_specs:
        data_dict[feat_name] = feat[enc_key].astype(np.int32)
    for feat_name in active_dense_specs:
        arr = feat[feat_name].astype(np.float32)
        data_dict[feat_name] = np.nan_to_num(arr, nan=0.0, posinf=10.0, neginf=0.0)

    target = feat["target"].astype(np.float32)

    # ── 用户级时序切分（向量化）
    feature_names  = get_feature_names(feature_columns)
    play_time_unix = feat.get("play_time_unix", np.zeros(n_samples, dtype=np.int64))
    _uid_arr = feat["user_id_encoded"].astype(np.int32)
    MIN_INTERACTIONS = 5
    _df_meta = pd.DataFrame({
        "orig_idx": np.arange(n_samples),
        "uid":      _uid_arr,
        "time":     play_time_unix,
    }).sort_values(["uid", "time"])
    _df_meta["_cnt"]  = _df_meta.groupby("uid")["uid"].transform("count")
    _df_meta["_rank"] = _df_meta.groupby("uid").cumcount()
    _n_val_vec        = (_df_meta["_cnt"] * VALID_RATIO).astype(int).clip(lower=1)
    _is_val           = ((_df_meta["_cnt"] >= MIN_INTERACTIONS) &
                         (_df_meta["_rank"] >= _df_meta["_cnt"] - _n_val_vec))
    train_idx = _df_meta.loc[~_is_val, "orig_idx"].values
    val_idx   = _df_meta.loc[ _is_val, "orig_idx"].values

    # ── 低频 ID 过滤（min_count=3，只统计训练集，防 Embedding 死记硬背长尾 ID）
    print("  🔧 低频 ID 过滤（min_count=3）...")
    _MIN_COUNT = 3
    user_id_enc_din = feat["user_id_encoded"].copy()
    song_id_enc_din = feat["song_id_encoded"].copy()
    _u_counts = np.bincount(user_id_enc_din[train_idx].astype(np.int32),
                            minlength=int(user_id_enc_din.max()) + 1)
    _s_counts = np.bincount(song_id_enc_din[train_idx].astype(np.int32),
                            minlength=int(song_id_enc_din.max()) + 1)
    user_id_enc_din[np.isin(user_id_enc_din, np.where(_u_counts < _MIN_COUNT)[0])] = 0
    song_id_enc_din[np.isin(song_id_enc_din, np.where(_s_counts < _MIN_COUNT)[0])] = 0
    data_dict["user_id"] = user_id_enc_din
    data_dict["song_id"] = song_id_enc_din
    _n_rare_u = int((_u_counts < _MIN_COUNT).sum())
    _n_rare_s = int((_s_counts < _MIN_COUNT).sum())
    print(f"   ✅ 稀疏用户 {_n_rare_u} 个 → UNK，稀疏歌曲 {_n_rare_s} 首 → UNK")

    # user_history_position
    _df_meta["_seq_ratio"] = (
        _df_meta["_rank"] / (_df_meta["_cnt"] - 1).clip(lower=1)
    ).clip(0, 1).astype(np.float32)
    _seq_ratio_all = np.zeros(n_samples, dtype=np.float32)
    _seq_ratio_all[_df_meta["orig_idx"].values] = _df_meta["_seq_ratio"].values
    data_dict["user_history_position"] = _seq_ratio_all

    train_data   = {k: v[train_idx] for k, v in data_dict.items()}
    val_data     = {k: v[val_idx]   for k, v in data_dict.items()}
    train_target = target[train_idx]
    val_target   = target[val_idx]

    # ── 训练集不做 TE 覆盖（防止自我泄漏），仅验证集用贝叶斯平滑条件概率回填
    print("  🔧 深度模型跳过 TE 覆盖（消除训练集自我泄漏）")
    _global_prior = float(train_target.mean())
    _uid = feat["user_id_encoded"]
    _art = feat["artist_encoded"]
    _sid = feat["song_id_encoded"]
    _SMOOTH_M = 100

    print("  🎯 Cross TE（仅验证集回填，训练集保留原始值）...")
    _gnr = feat.get("genre_encoded",          np.zeros(len(feat["target"]), dtype=np.int32))
    _lng = feat.get("language_encoded",       np.zeros(len(feat["target"]), dtype=np.int32))
    _ctr = feat.get("origin_country_encoded", np.zeros(len(feat["target"]), dtype=np.int32))
    _b2_meta = pd.DataFrame({
        "uid": _uid[train_idx].astype(np.int32),
        "gnr": _gnr[train_idx].astype(np.int32),
        "lng": _lng[train_idx].astype(np.int32),
        "ctr": _ctr[train_idx].astype(np.int32),
        "y":   train_target.astype(np.float32),
    })
    _ug_s = _b2_meta.groupby(["uid","gnr"])["y"].agg(["count","mean"]).reset_index()
    _ug_s["ug_te"] = (_ug_s["count"]*_ug_s["mean"] + _SMOOTH_M*_global_prior) / (_ug_s["count"] + _SMOOTH_M)
    _ul_s = _b2_meta.groupby(["uid","lng"])["y"].agg(["count","mean"]).reset_index()
    _ul_s["ul_te"] = (_ul_s["count"]*_ul_s["mean"] + _SMOOTH_M*_global_prior) / (_ul_s["count"] + _SMOOTH_M)
    _uc_s = _b2_meta.groupby(["uid","ctr"])["y"].agg(["count","mean"]).reset_index()
    _uc_s["uc_te"] = (_uc_s["count"]*_uc_s["mean"] + _SMOOTH_M*_global_prior) / (_uc_s["count"] + _SMOOTH_M)

    def _fix_cross_te(idx):
        _t = pd.DataFrame({
            "uid": _uid[idx].astype(np.int32),
            "gnr": _gnr[idx].astype(np.int32),
            "lng": _lng[idx].astype(np.int32),
            "ctr": _ctr[idx].astype(np.int32),
        })
        _t = _t.merge(_ug_s[["uid","gnr","ug_te"]], on=["uid","gnr"], how="left")
        _t = _t.merge(_ul_s[["uid","lng","ul_te"]], on=["uid","lng"], how="left")
        _t = _t.merge(_uc_s[["uid","ctr","uc_te"]], on=["uid","ctr"], how="left")
        return (
            _t["ug_te"].fillna(_global_prior).values.astype(np.float32),
            _t["ul_te"].fillna(_global_prior).values.astype(np.float32),
            _t["uc_te"].fillna(_global_prior).values.astype(np.float32),
        )

    ug_vl, ul_vl, uc_vl = _fix_cross_te(val_idx)
    if "user_genre_match"    in val_data:   val_data["user_genre_match"]      = ug_vl
    if "user_language_match" in val_data:   val_data["user_language_match"]   = ul_vl
    if "user_country_match"  in val_data:   val_data["user_country_match"]    = uc_vl
    print(f"   ✅ Cross TE 完成（验证集 genre/language/country_match 已用 Bayesian 条件概率回填）")

    # ── Phase SVD: 训练集专用 SVD（消除全量预计算导致的验证集泄漏）
    print("  🔧 Phase SVD: 重新在训练集拟合 SVD，消除验证集泄漏...")
    from scipy.sparse import coo_matrix as _coo_svd
    from sklearn.decomposition import TruncatedSVD as _TruncSVD
    _u_all = feat["user_id_encoded"]
    _s_all = feat["song_id_encoded"]
    _a_all = feat["artist_encoded"]
    _n_u_s = int(_u_all.max()) + 1
    _n_s_s = int(_s_all.max()) + 1
    _n_a_s = int(_a_all.max()) + 1
    _us_mat = _coo_svd(
        (np.ones(len(train_idx), dtype=np.float32),
         (_u_all[train_idx].astype(np.int32), _s_all[train_idx].astype(np.int32))),
        shape=(_n_u_s, _n_s_s),
    ).tocsr()
    _svd_us = _TruncSVD(n_components=10, random_state=42)
    _uv_us  = _svd_us.fit_transform(_us_mat)
    _sv_us  = _svd_us.components_.T
    _ua_mat = _coo_svd(
        (np.ones(len(train_idx), dtype=np.float32),
         (_u_all[train_idx].astype(np.int32), _a_all[train_idx].astype(np.int32))),
        shape=(_n_u_s, _n_a_s),
    ).tocsr()
    _svd_ua = _TruncSVD(n_components=5, random_state=42)
    _uv_ua  = _svd_ua.fit_transform(_ua_mat)

    def _apply_svd_din(data_d, idx_set):
        _ui = np.clip(_u_all[idx_set].astype(np.int32), 0, _uv_us.shape[0]-1)
        _si = np.clip(_s_all[idx_set].astype(np.int32), 0, _sv_us.shape[0]-1)
        _ai = np.clip(_a_all[idx_set].astype(np.int32), 0, _uv_ua.shape[0]-1)
        for _i in range(10):
            if f"svd_user_song_{_i}" in data_d:
                data_d[f"svd_user_song_{_i}"] = _uv_us[_ui, _i].astype(np.float32)
            if f"svd_song_user_{_i}" in data_d:
                data_d[f"svd_song_user_{_i}"] = _sv_us[_si, _i].astype(np.float32)
        for _i in range(5):
            if f"svd_user_artist_{_i}" in data_d:
                data_d[f"svd_user_artist_{_i}"] = _uv_ua[_ui, _i].astype(np.float32)
        if "svd_dot_score" in data_d:
            data_d["svd_dot_score"] = (_uv_us[_ui] * _sv_us[_si]).sum(axis=1).astype(np.float32)

    _apply_svd_din(train_data, train_idx)
    _apply_svd_din(val_data,   val_idx)
    print(f"   ✅ SVD 泄漏修复完成（训练集拟合 → 10d+10d+5d+dot）")

    print(f"\n   训练集: {len(train_idx):,} | 验证集: {len(val_idx):,}")
    print(f"   训练正样本率: {train_target.mean():.4f}")

    return (feature_columns, feature_names,
            train_data, val_data, train_target, val_target)


# ============================================================
# 训练 DIN
# ============================================================

def train_din(feature_columns, feature_names,
              train_data, val_data, train_target, val_target, device):
    import torch
    import torch.nn.functional as F
    import torch.utils.data as Data
    from torch.amp import autocast, GradScaler
    from torch.optim import Adam
    from torch.optim.lr_scheduler import ReduceLROnPlateau
    from deepctr_torch.models import DeepFM
    from sklearn.metrics import roc_auc_score, log_loss

    print("\n" + "=" * 62)
    print("🚀 [Step 3/4] 训练 DIN (Deep Interest Network 变体)")
    print("=" * 62)
    print(f"   DNN 隐藏层: {DNN_HIDDEN_UNITS}")
    print(f"   Dropout:    {DROPOUT}")
    print(f"   Batch Size: {BATCH_SIZE:,}")
    print(f"   Device:     {device}")

    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=DNN_HIDDEN_UNITS,
        dnn_dropout=DROPOUT,
        dnn_activation='relu',
        l2_reg_embedding=1e-3,
        device=str(device),
    )
    model = model.to(device)

    optimizer = Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-3)
    scheduler = ReduceLROnPlateau(
        optimizer, mode='min', factor=LR_FACTOR,
        patience=LR_PATIENCE, min_lr=LR_MIN, verbose=True
    )
    loss_fn = torch.nn.BCELoss(reduction='mean')
    use_amp = (device.type == 'cuda')
    scaler  = GradScaler(device=str(device)) if use_amp else None

    # ── 构建 Tensor
    def make_tensor(data_dict):
        arrays = [data_dict[f].reshape(-1, 1) for f in feature_names]
        return torch.from_numpy(np.concatenate(arrays, axis=1))

    X_train = make_tensor(train_data)
    y_train = torch.from_numpy(train_target)
    X_val   = make_tensor(val_data).to(device).float()
    y_val   = torch.from_numpy(val_target)

    train_dataset = Data.TensorDataset(X_train, y_train)
    train_loader  = Data.DataLoader(
        train_dataset, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=NUM_WORKERS, pin_memory=(device.type == 'cuda'),
        persistent_workers=(NUM_WORKERS > 0),
        prefetch_factor=2 if NUM_WORKERS > 0 else None,
    )
    val_loader = Data.DataLoader(
        Data.TensorDataset(X_val, torch.zeros(len(y_val))),
        batch_size=BATCH_SIZE * 4, shuffle=False, pin_memory=False,
    )

    # ── 训练循环
    history = {'loss': [], 'val_loss': [], 'val_auc': [], 'lr': []}
    best_val_auc = 0.0
    best_epoch   = 0
    no_improve   = 0
    best_state   = None

    for epoch in range(EPOCHS):
        model.train()
        epoch_loss = 0.0
        t_epoch = time.time()
        steps = len(train_loader)

        pbar = tqdm(train_loader, total=steps,
                    desc=f"Epoch {epoch+1:2d}/{EPOCHS}", ncols=100)

        for step, (x_batch, y_batch) in enumerate(pbar):
            x_batch = x_batch.to(device, non_blocking=True).float()
            y_batch = y_batch.to(device, non_blocking=True).float()

            optimizer.zero_grad(set_to_none=True)

            if use_amp:
                with autocast(device_type='cuda'):
                    y_pred = model(x_batch).squeeze()
                loss = loss_fn(y_pred.float(), y_batch)
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
            if (step + 1) % 100 == 0:
                pbar.set_postfix(loss=f"{epoch_loss/(step+1):.4f}", refresh=False)

        avg_loss = epoch_loss / steps

        # ── 验证
        model.eval()
        val_preds_list = []
        with torch.no_grad():
            for xv, _ in val_loader:
                if use_amp:
                    with autocast(device_type='cuda'):
                        vp = model(xv).squeeze()
                else:
                    vp = model(xv).squeeze()
                val_preds_list.append(vp.cpu().float().numpy())

        val_preds = np.concatenate(val_preds_list)
        val_true  = y_val.numpy()
        val_loss  = log_loss(val_true, val_preds)
        val_auc   = roc_auc_score(val_true, val_preds)
        cur_lr    = optimizer.param_groups[0]['lr']

        history['loss'].append(avg_loss)
        history['val_loss'].append(val_loss)
        history['val_auc'].append(val_auc)
        history['lr'].append(cur_lr)

        elapsed = time.time() - t_epoch
        print(f"  → Epoch {epoch+1:2d}/{EPOCHS}  "
              f"loss={avg_loss:.4f}  val_loss={val_loss:.4f}  "
              f"val_AUC={val_auc:.4f}  lr={cur_lr:.2e}  ({elapsed:.0f}s)")

        scheduler.step(val_loss)

        if val_auc > best_val_auc + 1e-5:
            best_val_auc = val_auc
            best_epoch   = epoch + 1
            no_improve   = 0
            raw_model = model._orig_mod if hasattr(model, '_orig_mod') else model
            best_state = {k: v.cpu().clone() for k, v in raw_model.state_dict().items()}
            print(f"     ✅ Best AUC: {best_val_auc:.4f} (Epoch {best_epoch})")
        else:
            no_improve += 1
            print(f"     ⏳ No improve {no_improve}/{EARLY_STOP_PATIENCE}")
            if no_improve >= EARLY_STOP_PATIENCE:
                print(f"\n⛔ 早停！Best Epoch={best_epoch}, AUC={best_val_auc:.4f}")
                break

    raw_model = model._orig_mod if hasattr(model, '_orig_mod') else model
    if best_state is not None:
        raw_model.load_state_dict(best_state)

    return raw_model, history, best_epoch, best_val_auc


# ============================================================
# 可视化 + 保存
# ============================================================

def plot_and_save(model, feature_columns, feature_names, history, best_epoch, best_val_auc):
    import torch

    # ── 训练曲线
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    epochs = range(1, len(history['loss']) + 1)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    ax = axes[0]
    ax.plot(epochs, history['loss'],     'b-o', label='Train Loss', lw=2, ms=6)
    ax.plot(epochs, history['val_loss'], 'r-s', label='Val Loss',   lw=2, ms=6)
    ax.set_xlabel('Epoch'); ax.set_ylabel('Loss')
    ax.set_title('DIN Loss Curve', fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3); ax.set_xticks(list(epochs))

    ax = axes[1]
    ax.plot(epochs, history['val_auc'], 'g-o', label='Val AUC', lw=2, ms=6)
    ax.set_xlabel('Epoch'); ax.set_ylabel('AUC')
    ax.set_title('DIN Validation AUC', fontweight='bold')
    ax.legend(); ax.grid(alpha=0.3); ax.set_xticks(list(epochs))

    ax = axes[2]
    ax.plot(epochs, history['lr'], 'm-^', label='Learning Rate', lw=2, ms=6)
    ax.set_xlabel('Epoch'); ax.set_ylabel('LR')
    ax.set_title('Learning Rate', fontweight='bold')
    ax.set_yscale('log'); ax.legend(); ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   ✅ 训练曲线: {OUTPUT_PLOT}")

    # ── 保存逐 epoch CSV
    import csv
    with open(OUTPUT_HISTORY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["epoch", "train_loss", "val_loss", "val_auc", "lr"])
        writer.writeheader()
        for i, (tl, vl, va, lr) in enumerate(zip(
                history["loss"], history["val_loss"], history["val_auc"], history["lr"]), 1):
            writer.writerow({"epoch": i, "train_loss": f"{tl:.6f}", "val_loss": f"{vl:.6f}",
                             "val_auc": f"{va:.6f}", "lr": f"{lr:.2e}"})
    print(f"   ✅ 指标 CSV: {OUTPUT_HISTORY}")

    # ── 保存模型权重
    torch.save(model.state_dict(), OUTPUT_MODEL)
    print(f"   ✅ 模型: {OUTPUT_MODEL}")

    config = {
        'feature_columns':  feature_columns,
        'feature_names':    feature_names,
        'dnn_hidden_units': DNN_HIDDEN_UNITS,
        'dnn_dropout':      DROPOUT,
        'sparse_feat_specs': SPARSE_FEAT_SPECS,
        'dense_feat_specs':  DENSE_FEAT_SPECS,
        'history':          history,
        'best_epoch':       best_epoch,
        'best_val_auc':     best_val_auc,
        'train_time':       datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'model_type':       'DIN',
    }
    with open(OUTPUT_CONFIG, 'wb') as f:
        pickle.dump(config, f, protocol=4)
    print(f"   ✅ 配置: {OUTPUT_CONFIG}")


# ============================================================
# main
# ============================================================

def main():
    t_start = datetime.now()
    print("\n" + "=" * 62)
    print("   DIN (Deep Interest Network) 精排模型训练")
    print(f"   开始时间: {t_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    set_seed(RANDOM_SEED)
    device = check_gpu()

    # 1. 加载数据（npz 缓存加速）
    print(f"\n📥 加载特征: {INPUT_FEATURES}")
    if not os.path.exists(INPUT_FEATURES):
        print("❌ 特征文件不存在！请先运行 prepare_features_v3.py")
        sys.exit(1)
    _npz_cache = INPUT_FEATURES.replace(".pkl", "_cache.npz")
    _use_cache = (os.path.exists(_npz_cache) and
                  os.path.getmtime(_npz_cache) >= os.path.getmtime(INPUT_FEATURES))
    if _use_cache:
        print(f"   ⚡ 从 npz 缓存加载（速度 5-10x）...")
        _raw = np.load(_npz_cache, allow_pickle=True)
        feat = {k: _raw[k].item() if _raw[k].ndim == 0 else _raw[k] for k in _raw.files}
    else:
        with open(INPUT_FEATURES, "rb") as f:
            feat = pickle.load(f)
        np.savez(_npz_cache, **{k: np.array(v) for k, v in feat.items()})
        print(f"   ✅ npz 缓存已保存")
    print(f"   样本数: {len(feat['target']):,} | 正样本率: {feat['target'].mean():.4f}")

    # 2. 准备数据
    (feature_columns, feature_names,
     train_data, val_data,
     train_target, val_target) = prepare_din_data(feat)

    # 3. 训练
    model, history, best_epoch, best_val_auc = train_din(
        feature_columns, feature_names,
        train_data, val_data, train_target, val_target, device
    )

    # 4. 保存
    plot_and_save(model, feature_columns, feature_names,
                  history, best_epoch, best_val_auc)

    t_end = datetime.now()
    print(f"\n" + "=" * 62)
    print(f"✅ DIN 训练完成！")
    print(f"   最佳 val_AUC: {best_val_auc:.4f}（Epoch {best_epoch}）")
    print(f"   训练耗时: {(t_end - t_start).total_seconds() / 60:.1f} 分钟")
    print("=" * 62)


if __name__ == "__main__":
    main()
