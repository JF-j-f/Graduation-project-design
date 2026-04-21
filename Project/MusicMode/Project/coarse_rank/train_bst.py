# -*- coding: utf-8 -*-
"""
train_bst.py — BST（行为序列 Transformer）粗排模型训练
架构：
  输入层：
    ├─ 用户行为序列: seq_song_ids (B×50)  ←── features_seq.pkl
    ├─ feat_flat (B×66)：
    │     col 0:    user_id_encoded         ←── user Embedding(n_users, 32)
    │     col 1:    song_id_encoded         ←── target song Embedding(n_songs, 32)
    │     col 2-13: 其他稀疏特征（12个）     ←── 独立 Embedding 表
    │     col 14+:  稠密特征（52个 in pkl）  ←── Linear 投影
  序列 Transformer 层（3层 Encoder）：
    [历史序列 + 目标 token] → 位置编码 → Transformer(3层) → 分离
    历史部分：注意力加权池化 → seq_repr(d_model)
  融合层：
    concat(seq_repr, target_emb, user_emb, dense_proj) → Flatten
  MLP 输出层：
    Linear(→256) → BN → ReLU → Drop → Linear(→128) → BN → ReLU → Drop → Linear(→64) → BN → ReLU → Drop → Linear(→1) → Sigmoid

训练环境：RTX 5090 32GB × 1 / CPU Xeon 8470Q 25核心 / 内存 90GB
开发者：JunFu
"""

import os
import sys
import pickle
import time
import math
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_auc_score

# ============================================================
# 配置
# ============================================================

MODE_DIR = Path(__file__).resolve().parents[2] / "Mode"
FE_DIR   = MODE_DIR / "feature_engineering"
BST_DIR  = MODE_DIR / "coarse_rank" / "bst"   # BST 粗排层模型输出目录
BST_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FEATURES  = FE_DIR / "features_v3.pkl"
INPUT_SEQ       = FE_DIR / "features_seq.pkl"
OUTPUT_MODEL    = BST_DIR / "bst_model.pth"
OUTPUT_CONFIG   = BST_DIR / "model_config.pkl"
OUTPUT_PLOT     = BST_DIR / "training_progress.png"
OUTPUT_HISTORY  = BST_DIR / "bst_metrics.csv"

# K折OOF开关（供元学习器训练使用）
RUN_OOF        = True
N_OOF_SPLITS   = 5   # 5折OOF
OOF_PREDS_PATH = BST_DIR / "bst_oof.npy"
OOF_IDX_PATH   = os.path.join(BST_DIR, "bst_oof_idx.npy")

# 训练超参
BATCH_SIZE          = 4096      # 样本数
EPOCHS              = 40        # 最大训练轮数（早停兜底，实际运行约16轮）
LEARNING_RATE       = 5e-5      # 初始学习率（CosineAnnealingLR 起点）
L2_REG              = 8e-4      # 权重衰减
LR_ETA_MIN          = 1e-6      # CosineAnnealingLR 最小学习率下限
EARLY_STOP_PATIENCE = 7         # 早停耐心轮数
VALID_RATIO         = 0.10      # 验证集比例（按时间切分，后 10%）
RANDOM_SEED         = 42        # 随机种子
NUM_WORKERS         = 4         # DataLoader 子进程数
# BST 模型超参
EMBED_DIM   = 32                # 稀疏特征 Embedding 维度（用户、歌曲、其他稀疏特征共享）
SEQ_LEN     = 50                # 用户历史行为序列长度（固定为 50，短序列前面 padding）
N_HEADS     = 8                 # Transformer 多头注意力头数（d_model=128 被8整除，注意力更精细）
D_MODEL     = 128               # Transformer 隐层维度（注意力输出维度，必须能被 n_heads 整除）
FFN_DIM     = 256               # Transformer 前馈网络隐藏层维度
DROPOUT     = 0.45              # Dropout 比率（防止过拟合）

# 稀疏特征规格：(pkl_encoded_key, pkl_vocab_size_key)
# 顺序必须与 build_pair_features 的行向量列 0-13 完全对齐
SPARSE_FEAT_SPECS = [
    ("user_id_encoded",          "n_users"),         # col 0 → user embedding
    ("song_id_encoded",          "n_songs"),          # col 1 → song embedding
    ("genre_encoded",            "n_genres"),         # col 2
    ("language_encoded",         "n_languages"),      # col 3
    ("artist_encoded",           "n_artists"),        # col 4
    ("origin_country_encoded",   "n_countries"),      # col 5
    ("year_bucket_encoded",      "n_year_buckets"),   # col 6
    ("source_channel_encoded",   "n_sources"),        # col 7
    ("city_encoded",             "n_cities"),         # col 8
    ("gender_encoded",           "n_genders"),        # col 9
    ("age_bucket_encoded",       "n_age_buckets"),    # col 10
    ("tenure_bucket_encoded",    "n_tenures"),        # col 11
    ("duration_bucket_encoded",  "n_dur_buckets"),    # col 12
    ("user_peak_hour_encoded",   "n_peak_hours"),     # col 13
]

# 稠密特征（与 train_deepfm_v3.py / train_lgbm.py 完全对齐，共 52 维）
DENSE_FEAT_SPECS = [
    # 用户基础统计
    "user_play_count_log",
    "user_avg_completion",
    "user_genre_diversity",
    "user_30d_active_days",
    # 歌曲基础统计
    "song_play_count_log",
    "song_avg_completion",
    "song_popularity_norm",
    "song_age_days_log",
    "song_target_rate",
    # 交互特征
    "user_artist_match",
    "user_skip_rate",
    "song_skip_rate",
    # 时序匹配
    "hour_match",
    "dow_match",
    # 最近交互
    "days_since_artist_log",
    "days_since_last_play_log",
    # 歌单亲和力
    "user_has_in_playlist",
    "user_playlist_artist_count_log",
    # 记忆衰减
    "user_song_prev_play_days",
    "user_song_play_count_before",
    # 滚动窗口
    "user_7d_play_count_log",
    "user_30d_play_count_log",
    "user_7d_avg_completion",
    "song_7d_play_count_log",
    "song_30d_play_count_log",
    "song_trending_ratio",
    # SVD 嵌入
    *[f"svd_user_song_{i}" for i in range(10)],
    *[f"svd_song_user_{i}" for i in range(10)],
    *[f"svd_user_artist_{i}" for i in range(5)],
    "svd_dot_score",
]
N_SPARSE       = len(SPARSE_FEAT_SPECS)   # 14
N_DENSE        = len(DENSE_FEAT_SPECS)    # 52
N_OTHER_SPARSE = N_SPARSE - 2             # 12（排除 user_id 和 song_id）


# ============================================================
# 工具函数
# ============================================================

def set_seed(seed: int = RANDOM_SEED) -> None:
    """固定随机种子，保证实验可复现。"""
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark     = False


def check_gpu() -> torch.device:
    """检测并返回可用计算设备。"""
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
        print(f"\n✅ GPU: {name}  ({vram:.1f} GB VRAM)")
        print(f"   PyTorch {torch.__version__}  CUDA {torch.version.cuda}")
        return torch.device("cuda")
    else:
        print("⚠️  CUDA 不可用，回退 CPU（训练较慢）")
        return torch.device("cpu")


# ============================================================
# Dataset
# ============================================================

class BSTDataset(Dataset):
    """
    BST 训练数据集。

    每个样本包含：
      seq_song_ids : (seq_len,)  long   — 用户历史歌曲序列
      sparse_data  : (N_SPARSE,) long   — 稀疏特征（列 0-13）
      dense_data   : (N_DENSE,)  float  — 稠密特征（列 14-48）
      target       : scalar      float  — 0/1 标签
    """

    def __init__(self, seq_arr: np.ndarray, sparse_arr: np.ndarray,
                 dense_arr: np.ndarray, target_arr: np.ndarray):
        """
        Args:
            seq_arr    : (N, seq_len) int32
            sparse_arr : (N, N_SPARSE) int32
            dense_arr  : (N, N_DENSE) float32
            target_arr : (N,) float32
        """
        self.seq     = torch.from_numpy(seq_arr).long()
        self.sparse  = torch.from_numpy(sparse_arr).long()
        self.dense   = torch.from_numpy(dense_arr).float()
        self.target  = torch.from_numpy(target_arr).float()

    def __len__(self) -> int:
        return len(self.target)

    def __getitem__(self, idx):
        return (
            self.seq[idx],      # (seq_len,)
            self.sparse[idx],   # (N_SPARSE,)
            self.dense[idx],    # (N_DENSE,)
            self.target[idx],   # scalar
        )


# ============================================================
# BST 模型
# ============================================================

class PositionalEncoding(nn.Module):
    """
    正弦波位置编码
    支持可变序列长度，对 padding token（ID=0）无额外处理（模型自行学习忽略）。
    """

    def __init__(self, d_model: int, max_len: int = 200, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        # 预计算位置编码矩阵
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)   # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, seq_len, d_model)
        Returns:
            (B, seq_len, d_model)
        """
        x = x + self.pe[:, : x.size(1), :]
        return self.dropout(x)


class BSTModel(nn.Module):
    """
    行为序列 Transformer 精排模型（BST）。

    输入（与 sync_recs_v3.py 推断接口一致）：
      seq  : (B, seq_len)    long  — 历史歌曲序列（song_encoded）
      feat : (B, 14+N_DENSE) float — 稀疏+稠密特征矩阵
               col 0:    user_id_encoded
               col 1:    song_id_encoded（目标歌曲）
               col 2-13: 其他稀疏特征
               col 14+:  稠密特征

    输出：
      (B, 1) float — CTR 预测概率（Sigmoid）
    """

    def __init__(
        self,
        n_songs:            int,
        n_users:            int,
        other_sparse_sizes: list,   # 长度 = N_OTHER_SPARSE = 12
        dense_dim:          int,    # N_DENSE = 44
        embed_dim:          int = EMBED_DIM,
        seq_len:            int = SEQ_LEN,
        n_heads:            int = N_HEADS,
        d_model:            int = D_MODEL,
        ffn_dim:            int = FFN_DIM,
        dropout:            float = DROPOUT,
    ):
        super().__init__()
        self.seq_len   = seq_len
        self.d_model   = d_model
        self.embed_dim = embed_dim

        # 保存词表上界，用于 forward() 中的越界保护
        # feat[n_key] 已含 ENCODE_OFFSET=2（0=Padding, 1=UNK, 2+=真实值），
        # 合法 ID 范围：[0, n_songs-1]，无需额外 +1
        self.n_songs   = n_songs
        self.n_users   = n_users
        self.other_n   = list(other_sparse_sizes)  # 各其他稀疏特征词表大小

        # ── Embedding 层 ──
        # 歌曲 Embedding（序列 + 目标歌曲共享权重，ID=0 为 padding token）
        self.song_embed = nn.Embedding(n_songs, embed_dim, padding_idx=0)
        # 用户 Embedding
        self.user_embed = nn.Embedding(n_users, embed_dim, padding_idx=0)
        # 其他稀疏特征 Embedding（各自独立）
        self.other_embeds = nn.ModuleList([
            nn.Embedding(vocab_size, embed_dim, padding_idx=0)
            for vocab_size in other_sparse_sizes
        ])

        # ── 序列 Transformer 层 ──
        # embed_dim(32) → d_model(128); max_len 覆盖 seq_len+1（含目标 token）
        self.seq_proj   = nn.Linear(embed_dim, d_model)
        self.pos_enc    = PositionalEncoding(d_model, max_len=seq_len + 10, dropout=dropout)
        encoder_layer   = nn.TransformerEncoderLayer(
            d_model         = d_model,
            nhead           = n_heads,
            dim_feedforward = ffn_dim,
            dropout         = dropout,
            batch_first     = True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=3)

        # 注意力加权池化：对历史序列输出学习每个 token 的重要性权重
        self.attn_pool = nn.Linear(d_model, 1)

        # ── 稠密特征投影 ──
        self.dense_proj = nn.Sequential(
            nn.Linear(dense_dim, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.ReLU(),
        )

        # ── MLP 融合层 ──
        # 输入维度：seq_repr(d_model) + target_emb(embed_dim) + user_emb(embed_dim)
        #           + other_embs(N_OTHER_SPARSE*embed_dim) + dense_proj(embed_dim)
        n_other = len(other_sparse_sizes)
        mlp_in_dim = d_model + embed_dim + embed_dim + n_other * embed_dim + embed_dim

        # MLP：mlp_in → 256 → 128 → 64 → 1
        # Dropout 沿金字塔递减：dropout → dropout×0.75 → dropout×0.5
        self.mlp = nn.Sequential(
            nn.Linear(mlp_in_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout * 0.75),
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(64, 1),
        )

        # 权重初始化
        self._init_weights()

    def _init_weights(self) -> None:
        """Xavier 均匀初始化线性层权重，0 初始化偏置。"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, mean=0, std=0.01)
                if m.padding_idx is not None:
                    m.weight.data[m.padding_idx].zero_()

    def forward(self, seq: torch.Tensor, feat: torch.Tensor) -> torch.Tensor:
        """
        Args:
            seq  : (B, seq_len) long — 历史歌曲序列（song_encoded，0=padding）
            feat : (B, 14+dense_dim) float — 稀疏（int值浮点存储）+ 稠密特征

        Returns:
            (B, 1) float — CTR 概率
        """
        B = seq.size(0)

        # ── 从 feat 中分离稀疏/稠密特征 ──
        # clamp 双向保护：min=0 防负值，max=n-1 防越界（低频ID已在预处理阶段映射到UNK=1，
        # 此处作为最后一道安全网，避免服务推断时出现未见ID引发 CUDA index error）
        user_id     = feat[:, 0].long().clamp(min=0, max=self.n_users - 1)   # (B,)
        song_id     = feat[:, 1].long().clamp(min=0, max=self.n_songs - 1)   # (B,)
        other_int   = feat[:, 2:14].long().clamp(min=0)                      # (B, 12) 逐列保护见下方
        dense_feats = feat[:, 14:]                                            # (B, dense_dim)

        # ── 目标歌曲 Embedding ──
        target_emb = self.song_embed(song_id)              # (B, embed_dim)

        # ── 行为序列编码 ──
        # seq 双向 clamp：0=padding 不变，未见 ID 截断到 n_songs-1 内（实为 UNK 区域）
        seq_emb  = self.song_embed(seq.clamp(min=0, max=self.n_songs - 1))   # (B, seq_len, embed_dim)
        seq_h    = self.seq_proj(seq_emb)                  # (B, seq_len, d_model)

        # 目标 token 追加至序列末尾，与历史序列共同过 Transformer
        # 实现目标歌曲与历史行为的双向注意力交叉
        target_h = self.seq_proj(target_emb.unsqueeze(1))  # (B, 1, d_model)
        full_seq = torch.cat([seq_h, target_h], dim=1)     # (B, seq_len+1, d_model)
        full_seq = self.pos_enc(full_seq)

        # Padding mask：历史 ID=0 的位置屏蔽；目标 token 不屏蔽
        pad_mask     = (seq == 0)                           # (B, seq_len)
        pad_mask_ext = torch.cat(
            [pad_mask, torch.zeros(B, 1, dtype=torch.bool, device=pad_mask.device)], dim=1
        )  # (B, seq_len+1)

        seq_out = self.transformer(full_seq, src_key_padding_mask=pad_mask_ext)  # (B, seq_len+1, d_model)

        # 注意力加权池化（历史部分），模型自主学习每首历史歌曲的重要性
        hist_out = seq_out[:, :-1, :]                                          # (B, seq_len, d_model)
        attn_w   = self.attn_pool(hist_out)                                    # (B, seq_len, 1)
        attn_w   = attn_w.masked_fill(pad_mask.unsqueeze(-1), float("-inf"))
        attn_w   = torch.softmax(attn_w, dim=1)
        # 序列全为 padding 时 softmax 产生 NaN，用均匀权重替代
        all_pad  = pad_mask.all(dim=1).view(-1, 1, 1).expand_as(attn_w)       # (B, seq_len, 1)
        attn_w   = torch.where(all_pad, torch.full_like(attn_w, 1.0 / self.seq_len), attn_w)
        seq_repr = (hist_out * attn_w).sum(dim=1)                              # (B, d_model)

        # ── 用户 Embedding ──
        user_emb   = self.user_embed(user_id)             # (B, embed_dim)

        # ── 其他稀疏特征 Embedding ──
        # 各稀疏特征词表大小不同，逐列施加上界保护
        other_emb_list = [
            embed(other_int[:, i].clamp(max=self.other_n[i] - 1))
            for i, embed in enumerate(self.other_embeds)
        ]
        other_cat = torch.cat(other_emb_list, dim=-1)     # (B, 12*embed_dim)

        # ── 稠密特征投影 ──
        dense_repr = self.dense_proj(dense_feats)          # (B, embed_dim)

        # ── 融合 + MLP ──
        combined = torch.cat(
            [seq_repr, target_emb, user_emb, other_cat, dense_repr], dim=-1
        )   # (B, d_model + embed_dim + embed_dim + 12*embed_dim + embed_dim)

        out = self.mlp(combined).float()  # 显式转 float32，确保 AMP 下不产生 float16 边界值
        return torch.sigmoid(out)         # (B, 1)，值域严格 (0, 1)


# ============================================================
# Step 1: 加载数据
# ============================================================

def load_data():
    """加载 features_v3.pkl 和 features_seq.pkl，返回构建 Dataset 所需的 numpy 数组。"""
    print("\n" + "=" * 62)
    print("📂 [Step 1/4] 加载特征数据")
    print("=" * 62)

    for path in [INPUT_FEATURES, INPUT_SEQ]:
        if not os.path.exists(path):
            print(f"❌ 文件不存在：{path}")
            print("   请先运行 prepare_features_v3.py")
            sys.exit(1)

    with open(INPUT_FEATURES, "rb") as f:
        feat = pickle.load(f)

    # ── 字段完整性验证
    _req_enc  = [enc for enc, _ in SPARSE_FEAT_SPECS]
    _req_n    = [nk  for _,   nk in SPARSE_FEAT_SPECS]
    _missing  = [k for k in (_req_enc + _req_n + DENSE_FEAT_SPECS + ["target", "play_time_unix"])
                 if k not in feat]
    if _missing:
        print(f"\n❌ pkl 缺少字段（共 {len(_missing)} 个），请重新运行 prepare_features_v3.py：")
        for k in _missing:
            print(f"   - {k}")
        sys.exit(1)

    with open(INPUT_SEQ, "rb") as f:
        seq_data = pickle.load(f)

    N = len(feat["target"])
    print(f"   总样本数: {N:,}")

    # ── 构建 sparse_arr (N, 14)
    sparse_parts = []
    for enc_key, _ in SPARSE_FEAT_SPECS:
        col = feat[enc_key]
        if isinstance(col, pd.Series):
            col = col.values
        sparse_parts.append(col.astype(np.int32).reshape(-1, 1))
    sparse_arr = np.hstack(sparse_parts)   # (N, 14)

    # ── 构建 dense_arr (N, 44)
    dense_parts = []
    for name in DENSE_FEAT_SPECS:
        col = feat[name]
        if isinstance(col, pd.Series):
            col = col.values
        col = col.astype(np.float32)
        col = np.nan_to_num(col, nan=0.0, posinf=10.0, neginf=-10.0)
        dense_parts.append(col.reshape(-1, 1))
    dense_arr = np.hstack(dense_parts)     # (N, 44)

    # ── 序列 (N, 50)
    seq_arr = seq_data["seq_song_ids"].astype(np.int32)   # (N, 50)

    # ── 目标
    target_arr = feat["target"].astype(np.float32)
    if isinstance(target_arr, pd.Series):
        target_arr = target_arr.values

    # ── 时序切分（按 play_time_unix 升序，后 10% 为验证集）
    play_time = feat["play_time_unix"]
    if isinstance(play_time, pd.Series):
        play_time = play_time.values
    sorted_idx = np.argsort(play_time, kind="stable")
    split_pt   = int(N * (1 - VALID_RATIO))
    train_idx  = sorted_idx[:split_pt]
    valid_idx  = sorted_idx[split_pt:]

    print(f"   训练集: {len(train_idx):,}  验证集: {len(valid_idx):,}")
    print(f"   正样本率 (train): {target_arr[train_idx].mean():.4f}")
    print(f"   正样本率 (valid): {target_arr[valid_idx].mean():.4f}")

    # ── 低频 ID 过滤（min_count=3，只统计训练集，防长尾 ID 死记硬背）
    # 与 DeepFM 对齐：0=Padding 语义特殊不可替换，低频 ID 统一映射到 1（UNK）
    _MIN_COUNT = 3
    print("   🔧 低频 ID 过滤（min_count=3）...")
    song_col = sparse_arr[:, 1].copy()   # col 1 = song_id_encoded
    user_col = sparse_arr[:, 0].copy()   # col 0 = user_id_encoded
    _s_counts = np.bincount(song_col[train_idx].astype(np.int32),
                            minlength=int(song_col.max()) + 1)
    _u_counts = np.bincount(user_col[train_idx].astype(np.int32),
                            minlength=int(user_col.max()) + 1)
    rare_song_ids = np.where(_s_counts < _MIN_COUNT)[0]
    rare_user_ids = np.where(_u_counts < _MIN_COUNT)[0]
    sparse_arr[:, 1] = np.where(np.isin(sparse_arr[:, 1], rare_song_ids), 1, sparse_arr[:, 1])
    sparse_arr[:, 0] = np.where(np.isin(sparse_arr[:, 0], rare_user_ids), 1, sparse_arr[:, 0])
    # 同步处理行为序列：非 padding（>0）的低频歌曲 ID 也映射到 UNK(1)
    seq_flat = seq_arr.ravel()
    seq_rare_mask = (seq_flat > 0) & np.isin(seq_flat, rare_song_ids)
    seq_flat[seq_rare_mask] = 1
    # ravel 在连续内存上直接写回，无需 reshape（seq_arr 已同步修改）
    print(f"   ✅ 稀疏用户 {len(rare_user_ids)} 个 → UNK(1)，"
          f"稀疏歌曲 {len(rare_song_ids)} 首 → UNK(1)（含序列）")

    # 词表大小
    n_info = {}
    for enc_key, n_key in SPARSE_FEAT_SPECS:
        n_info[n_key] = int(feat[n_key])

    print(f"   n_songs={n_info['n_songs']:,}  n_users={n_info['n_users']:,}")

    return (
        sparse_arr, dense_arr, seq_arr, target_arr,
        train_idx, valid_idx, n_info
    )


# ============================================================
# Step 2: 构建模型
# ============================================================

def build_model(n_info: dict, device: torch.device) -> BSTModel:
    """
    根据词表大小构建 BSTModel 并移至计算设备。

    Args:
        n_info: 包含各特征词表大小的字典
        device: 目标计算设备

    Returns:
        初始化完成的 BSTModel
    """
    # 其他稀疏特征词表大小（排除 user_id 和 song_id，即列 2-13）
    other_sparse_keys = [nk for _, nk in SPARSE_FEAT_SPECS[2:]]   # 12 个
    other_sparse_sizes = [n_info[k] for k in other_sparse_keys]

    model = BSTModel(
        n_songs            = n_info["n_songs"],
        n_users            = n_info["n_users"],
        other_sparse_sizes = other_sparse_sizes,
        dense_dim          = N_DENSE,
        embed_dim          = EMBED_DIM,
        seq_len            = SEQ_LEN,
        n_heads            = N_HEADS,
        d_model            = D_MODEL,
        ffn_dim            = FFN_DIM,
        dropout            = DROPOUT,
    )
    model = model.to(device)

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n   BST 模型参数量: {n_params:,}")
    print(f"   d_model={D_MODEL}, n_heads={N_HEADS}, embed_dim={EMBED_DIM}")
    print(f"   seq_len={SEQ_LEN}, dropout={DROPOUT}")

    return model


# ============================================================
# K折OOF交叉验证（供元学习器训练使用）
# ============================================================

def run_kfold_oof(sparse_arr, dense_arr, seq_arr, target_arr, train_idx, n_info, device):
    """
    使用K折交叉验证在训练区间（train_idx）生成OOF预测，
    供 build_ensemble.py 的逻辑回归元学习器训练使用。

    BST已使用全局时序切分，与DeepFM OOF的切分基准一致，
    保证两模型的OOF索引完全对齐。

    Args:
        sparse_arr: (N, 14) 稀疏特征矩阵
        dense_arr:  (N, 44) 稠密特征矩阵
        seq_arr:    (N, 50) 行为序列矩阵
        target_arr: (N,)   标签
        train_idx:  训练集在原始数据集中的索引（全局时序前90%）
        n_info:     词表大小字典（用于构建模型）
        device:     torch计算设备
    """
    print("\n" + "=" * 62)
    print(f"🔁 [{N_OOF_SPLITS}折 OOF] BST 交叉验证预测（全局时序切分）")
    print("=" * 62)

    n_train  = len(train_idx)
    fold_sz  = n_train // N_OOF_SPLITS
    f_edges  = [k * fold_sz for k in range(N_OOF_SPLITS)] + [n_train]

    oof_preds = np.zeros(n_train, dtype=np.float32)

    for k in range(N_OOF_SPLITS):
        fold_mask = np.zeros(n_train, dtype=bool)
        fold_mask[f_edges[k]:f_edges[k + 1]] = True

        fold_val_local   = np.where(fold_mask)[0]    # 在 train_idx 中的位置
        fold_train_local = np.where(~fold_mask)[0]

        print(f"\n  [折 {k + 1}/{N_OOF_SPLITS}]  "
              f"训练={len(fold_train_local):,}  验证={len(fold_val_local):,}")

        # 按位置（local index）从预排好的训练集数组中切片
        fold_train_ds = BSTDataset(
            seq_arr[fold_train_local],
            sparse_arr[fold_train_local],
            dense_arr[fold_train_local],
            target_arr[fold_train_local],
        )
        fold_val_ds = BSTDataset(
            seq_arr[fold_val_local],
            sparse_arr[fold_val_local],
            dense_arr[fold_val_local],
            target_arr[fold_val_local],
        )

        fold_train_ldr = DataLoader(
            fold_train_ds, batch_size=BATCH_SIZE, shuffle=True,
            num_workers=NUM_WORKERS, pin_memory=(device.type == "cuda"),
            persistent_workers=False,                           # 每 Epoch 重启 worker，Windows 下防止 IPC 积累卡死
            prefetch_factor=2 if NUM_WORKERS > 0 else None,
        )
        fold_val_ldr = DataLoader(
            fold_val_ds, batch_size=BATCH_SIZE * 2, shuffle=False,
            num_workers=NUM_WORKERS, pin_memory=(device.type == "cuda"),
            persistent_workers=False,                           # 同上
            prefetch_factor=2 if NUM_WORKERS > 0 else None,
        )

        # 每折独立初始化模型（避免折间信息泄漏）
        fold_model = build_model(n_info, device)

        optimizer = torch.optim.Adam(
            fold_model.parameters(), lr=LEARNING_RATE, weight_decay=L2_REG
        )
        criterion = nn.BCELoss()
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=EPOCHS, eta_min=LR_ETA_MIN
        )
        scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

        best_auc   = 0.0
        best_preds = None
        no_improve = 0

        for epoch in range(1, EPOCHS + 1):
            # 训练一个epoch
            fold_model.train()
            for seq_b, sparse_b, dense_b, tgt_b in fold_train_ldr:
                seq_b  = seq_b.to(device)
                tgt_b  = tgt_b.to(device)
                feat_b = torch.cat(
                    [sparse_b.float().to(device), dense_b.to(device)], dim=-1
                )
                optimizer.zero_grad()
                with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                    out = fold_model(seq_b, feat_b).squeeze(-1)
                out  = out.float().clamp(min=1e-7, max=1.0 - 1e-7)
                loss = criterion(out, tgt_b.float())
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(fold_model.parameters(), max_norm=0.3)
                scaler.step(optimizer)
                scaler.update()
            scheduler.step()

            # 验证集评估
            fold_model.eval()
            preds_list = []
            with torch.no_grad():
                for seq_b, sparse_b, dense_b, _ in fold_val_ldr:
                    seq_b  = seq_b.to(device)
                    feat_b = torch.cat(
                        [sparse_b.float().to(device), dense_b.to(device)], dim=-1
                    )
                    out = fold_model(seq_b, feat_b).squeeze(-1).float().clamp(min=1e-7, max=1.0 - 1e-7)
                    preds_list.append(out.cpu().numpy())

            ep_preds = np.concatenate(preds_list)
            ep_auc   = roc_auc_score(target_arr[fold_val_local], ep_preds)
            print(f"     Epoch {epoch:2d}  val_AUC={ep_auc:.4f}")

            if ep_auc > best_auc:
                best_auc   = ep_auc
                best_preds = ep_preds.copy()
                no_improve = 0
            else:
                no_improve += 1
                if no_improve >= EARLY_STOP_PATIENCE:
                    print(f"     ⏹️  早停（best={best_auc:.4f}）")
                    break

        # 写入OOF预测
        oof_preds[fold_val_local] = best_preds if best_preds is not None else ep_preds

        # 释放折模型显存 和 DataLoader worker 进程
        del fold_train_ldr, fold_val_ldr   # 主动回收，避免 worker 残留影响下一折
        del fold_model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # 汇总OOF整体AUC
    oof_labels = target_arr[np.arange(n_train)]  # train_idx 对应的标签（已是本地序）
    oof_auc    = roc_auc_score(oof_labels, oof_preds)
    print(f"\n✅ OOF总体 AUC: {oof_auc:.4f}")

    # 保存OOF结果（train_idx 保存为原始数据集索引，供 build_ensemble.py 对齐）
    np.save(OOF_PREDS_PATH, oof_preds)
    np.save(OOF_IDX_PATH,   train_idx)
    print(f"   OOF预测保存: {OOF_PREDS_PATH}")
    print(f"   OOF索引保存: {OOF_IDX_PATH}")

    return oof_preds, train_idx


# ============================================================
# Step 3: 训练循环
# ============================================================

def train_epoch(
    model: BSTModel,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
    scaler: torch.amp.GradScaler,
) -> tuple:
    """
    单轮训练。

    Returns:
        (train_loss, train_auc)
    """
    model.train()
    total_loss = 0.0
    all_preds  = []
    all_labels = []

    for seq, sparse, dense, target in tqdm(loader, desc="   Train", leave=False, ncols=90):
        seq    = seq.to(device)
        target = target.to(device)

        # ── 构建 feat 矩阵（sparse 以 float 存储，dense 直接使用）
        feat = torch.cat(
            [sparse.float().to(device), dense.to(device)], dim=-1
        )   # (B, 14+44=58)

        optimizer.zero_grad()
        with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
            out = model(seq, feat).squeeze(-1)   # (B,)
        # BCELoss 必须在 autocast 外用 float32 计算；clamp 防止边界值触发 CUDA assertion
        out = out.float().clamp(min=1e-7, max=1.0 - 1e-7)
        loss = criterion(out, target.float())

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.3)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * len(target)
        all_preds.append(out.detach().cpu().float().numpy())
        all_labels.append(target.detach().cpu().numpy())

    all_preds  = np.concatenate(all_preds)
    all_labels = np.concatenate(all_labels)
    avg_loss   = total_loss / len(all_labels)
    try:
        auc = roc_auc_score(all_labels, all_preds)
    except Exception:
        auc = 0.5

    return avg_loss, auc


@torch.no_grad()
def eval_epoch(
    model: BSTModel,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple:
    """
    验证集评估。

    Returns:
        (val_loss, val_auc)
    """
    model.eval()
    total_loss = 0.0
    all_preds  = []
    all_labels = []

    for seq, sparse, dense, target in tqdm(loader, desc="   Valid", leave=False, ncols=90):
        seq    = seq.to(device)
        target = target.to(device)
        feat   = torch.cat(
            [sparse.float().to(device), dense.to(device)], dim=-1
        )
        out  = model(seq, feat).squeeze(-1).float().clamp(min=1e-7, max=1.0 - 1e-7)
        loss = criterion(out, target.float())

        total_loss += loss.item() * len(target)
        all_preds.append(out.cpu().float().numpy())
        all_labels.append(target.cpu().numpy())

    all_preds  = np.concatenate(all_preds)
    all_labels = np.concatenate(all_labels)
    avg_loss   = total_loss / len(all_labels)
    try:
        auc = roc_auc_score(all_labels, all_preds)
    except Exception:
        auc = 0.5

    return avg_loss, auc


def train_bst_model():
    """BST 训练主函数。"""
    # 脚本级计时：在任何工作开始前就记录，覆盖数据加载、OOF、主训练全程
    _script_start = datetime.now()
    print("\n" + "=" * 62)
    print("🚀 BST 行为序列 Transformer 精排模型训练")
    print(f"   启动时间: {_script_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    set_seed(RANDOM_SEED)
    device = check_gpu()

    # Step 1: 加载数据
    sparse_arr, dense_arr, seq_arr, target_arr, train_idx, valid_idx, n_info = load_data()

    # Step 1.5: K折OOF（在全量训练前生成，供元学习器使用）
    # 注意：传入已按 train_idx 切片的子集，OOF内部在子集上按位置折叠
    if RUN_OOF:
        # 传入已按 train_idx 切片的子集数组，OOF 内部在子集上以本地位置索引折叠
        # 使用 np.arange 而非原始 train_idx，避免二次索引错位导致 bst_oof_idx.npy 对齐错误
        train_idx_local = np.arange(len(train_idx))
        run_kfold_oof(
            sparse_arr[train_idx],
            dense_arr[train_idx],
            seq_arr[train_idx],
            target_arr[train_idx],
            train_idx_local,
            n_info,
            device,
        )

    # Step 2: 构建 DataLoader
    print("\n" + "=" * 62)
    print("🗂️  [Step 2/4] 构建 DataLoader")
    print("=" * 62)

    train_ds = BSTDataset(
        seq_arr[train_idx], sparse_arr[train_idx],
        dense_arr[train_idx], target_arr[train_idx]
    )
    valid_ds = BSTDataset(
        seq_arr[valid_idx], sparse_arr[valid_idx],
        dense_arr[valid_idx], target_arr[valid_idx]
    )

    train_loader = DataLoader(
        train_ds, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=NUM_WORKERS, pin_memory=(device.type == "cuda"),
        persistent_workers=(NUM_WORKERS > 0),
        prefetch_factor=2 if NUM_WORKERS > 0 else None,
    )
    valid_loader = DataLoader(
        valid_ds, batch_size=BATCH_SIZE * 2, shuffle=False,
        num_workers=NUM_WORKERS, pin_memory=(device.type == "cuda"),
        persistent_workers=(NUM_WORKERS > 0),
        prefetch_factor=2 if NUM_WORKERS > 0 else None,
    )

    # Step 3: 构建模型
    print("\n" + "=" * 62)
    print("🔧 [Step 3/4] 构建 BST 模型")
    print("=" * 62)
    model = build_model(n_info, device)

    optimizer = torch.optim.Adam(
        model.parameters(), lr=LEARNING_RATE, weight_decay=L2_REG
    )
    criterion = nn.BCELoss()
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=EPOCHS, eta_min=LR_ETA_MIN
    )
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    # Step 4: 训练
    print("\n" + "=" * 62)
    print("🏋️  [Step 4/4] 开始训练（最大 {} Epoch）".format(EPOCHS))
    print("=" * 62)

    best_val_auc = 0.0
    best_epoch   = 0
    no_improve   = 0
    history      = []
    t_start      = time.time()

    for epoch in range(1, EPOCHS + 1):
        t_ep = time.time()

        train_loss, train_auc = train_epoch(
            model, train_loader, optimizer, criterion, device, scaler
        )
        val_loss, val_auc = eval_epoch(model, valid_loader, criterion, device)

        # CosineAnnealingLR：每 epoch 末调用，不依赖指标，平滑衰减
        scheduler.step()
        current_lr = optimizer.param_groups[0]["lr"]

        elapsed   = time.time() - t_ep
        total_ela = time.time() - t_start
        print(
            f"   Epoch {epoch:02d}/{EPOCHS}  "
            f"Train Loss={train_loss:.4f} AUC={train_auc:.4f}  "
            f"Val Loss={val_loss:.4f} AUC={val_auc:.4f}  "
            f"LR={current_lr:.1e}  Elapsed={elapsed:.0f}s"
        )

        history.append({
            "epoch": epoch,
            "train_loss": train_loss, "train_auc": train_auc,
            "val_loss": val_loss,     "val_auc": val_auc,
            "lr": current_lr,
        })

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            best_epoch   = epoch
            no_improve   = 0
            torch.save(model.state_dict(), OUTPUT_MODEL)
            print(f"   💾 保存最佳模型 (Val AUC={best_val_auc:.4f})")
        else:
            no_improve += 1
            if no_improve >= EARLY_STOP_PATIENCE:
                print(f"\n⏹️  早停触发（{EARLY_STOP_PATIENCE} epoch 无改善），"
                      f"最佳 Epoch={best_epoch}，Val AUC={best_val_auc:.4f}")
                break

    total_time = time.time() - t_start
    print(f"\n✅ 训练完成！总耗时: {total_time/60:.1f} 分钟")
    print(f"   最佳 Epoch: {best_epoch}  最佳 Val AUC: {best_val_auc:.4f}")

    # ── 保存配置（model_config.pkl）
    # other_sparse_sizes 与 SPARSE_FEAT_SPECS[2:] 对应
    other_sparse_keys  = [nk for _, nk in SPARSE_FEAT_SPECS[2:]]
    other_sparse_sizes = [n_info[k] for k in other_sparse_keys]

    config = {
        "n_songs":            n_info["n_songs"],
        "n_users":            n_info["n_users"],
        "other_sparse_sizes": other_sparse_sizes,
        "dense_dim":          N_DENSE,
        "embed_dim":          EMBED_DIM,
        "seq_len":            SEQ_LEN,
        "n_heads":            N_HEADS,
        "d_model":            D_MODEL,
        "ffn_dim":            FFN_DIM,
        "dropout":            DROPOUT,
        "best_val_auc":       best_val_auc,
        "best_epoch":         best_epoch,
        "train_samples":      len(train_idx),
        "valid_samples":      len(valid_idx),
    }
    with open(OUTPUT_CONFIG, "wb") as f:
        pickle.dump(config, f)
    print(f"   配置已保存: {OUTPUT_CONFIG}")

    # ── 保存训练曲线
    hist_df = pd.DataFrame(history)
    hist_df.to_csv(OUTPUT_HISTORY, index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(hist_df["epoch"], hist_df["train_loss"], label="Train Loss")
    axes[0].plot(hist_df["epoch"], hist_df["val_loss"],   label="Val Loss")
    axes[0].axvline(x=best_epoch, color="red", linestyle="--", alpha=0.6, label="Best Epoch")
    axes[0].set_title("BST Training Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("BCE Loss")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(hist_df["epoch"], hist_df["train_auc"], label="Train AUC")
    axes[1].plot(hist_df["epoch"], hist_df["val_auc"],   label="Val AUC")
    axes[1].axvline(x=best_epoch, color="red", linestyle="--", alpha=0.6, label="Best Epoch")
    axes[1].axhline(y=best_val_auc, color="green", linestyle=":", alpha=0.6,
                    label=f"Best Val AUC={best_val_auc:.4f}")
    axes[1].set_title("BST Training AUC")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("AUC")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    plt.suptitle(f"BST Training Progress — Best Val AUC={best_val_auc:.4f} (Epoch {best_epoch})")
    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   训练曲线已保存: {OUTPUT_PLOT}")

    # 脚本总耗时：与 _script_start 对齐，涵盖数据加载、OOF、主训练全程
    _elapsed = str(datetime.now() - _script_start).split(".")[0]
    print("\n" + "=" * 62)
    print(f"✅ BST 训练完成！")
    print(f"   最佳 val_AUC: {best_val_auc:.4f}（Epoch {best_epoch}）")
    print(f"   结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   总耗时:   {_elapsed}")
    print("=" * 62)

    return best_val_auc


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    best_auc = train_bst_model()
