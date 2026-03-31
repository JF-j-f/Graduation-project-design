# -*- coding: utf-8 -*-
"""
build_faiss_index.py — FAISS 向量索引构建（v3）

功能：
1. 从训练好的 DeepFM v3 模型中提取歌曲侧 Embedding
2. 拼接 song(32) + genre(32) + language(32) + artist(32) + origin_country(32)
   → 160维复合向量（代表歌曲内容语义）
3. L2 归一化后构建 FAISS IndexFlatIP 索引（余弦相似度搜索）
4. 输出 song_index.faiss + song_id_map.pkl

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import time
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

INPUT_FEATURES   = os.path.join(MODE_DIR, "features_v3.pkl")
INPUT_MODEL      = os.path.join(MODE_DIR, "deepfm", "deepfm_model.pth")
INPUT_CONFIG     = os.path.join(MODE_DIR, "deepfm", "model_config.pkl")

OUTPUT_FAISS     = os.path.join(MODE_DIR, "song_index.faiss")
OUTPUT_MAP       = os.path.join(MODE_DIR, "song_id_map.pkl")

# 复合向量维度：song(32)+genre(32)+language(32)+artist(32)+origin_country(32) = 160
# ⚠️ v3 所有 SparseFeat 统一 embedding_dim=32（与 train_deepfm_v3.py SPARSE_FEAT_SPECS 一致）
EMBEDDING_DIM = 160

# 组成复合向量的 embedding 名称（需与 DeepFM v3 的 SparseFeat 名称一致）
SONG_EMB_PARTS = [
    ("song_id",        32),
    ("genre",          32),
    ("language",       32),
    ("artist",         32),
    ("origin_country", 32),
]


# ============================================================
# Step 1: 加载模型和特征
# ============================================================

def load_model_and_features():
    print("\n" + "=" * 62)
    print("📂 [Step 1/4] 加载模型和特征")
    print("=" * 62)

    import torch
    from deepctr_torch.models import DeepFM

    # 加载 features_v3.pkl
    print("\n   📥 加载特征数据 features_v3.pkl ...")
    if not os.path.exists(INPUT_FEATURES):
        print(f"❌ 特征文件不存在: {INPUT_FEATURES}")
        print("   请先运行 prepare_features_v3.py")
        sys.exit(1)

    with open(INPUT_FEATURES, "rb") as f:
        features = pickle.load(f)

    print(f"   ✅ 歌曲数:          {features['n_songs']:,}")
    print(f"   ✅ 流派数:          {features.get('n_genres', 'N/A')}")
    print(f"   ✅ 语言数:          {features.get('n_languages', 'N/A')}")
    print(f"   ✅ 艺术家数:        {features.get('n_artists', 'N/A')}")
    print(f"   ✅ 发行国数:        {features.get('n_origin_countries', 'N/A')}")

    # 重建模型（从 model_config_v3.pkl 读取特征列）
    print(f"\n   📥 重建 DeepFM v3 模型 ...")
    if not os.path.exists(INPUT_CONFIG):
        print(f"❌ 模型配置不存在: {INPUT_CONFIG}")
        print("   请先运行 train_deepfm_v3.py")
        sys.exit(1)

    with open(INPUT_CONFIG, "rb") as f:
        cfg = pickle.load(f)

    feature_columns  = cfg["feature_columns"]
    dnn_hidden_units = cfg.get("dnn_hidden_units", (512, 256, 128, 64))
    dnn_dropout      = cfg.get("dnn_dropout", 0.2)
    print(f"   ✅ 特征列: {len(feature_columns)} 个  |  DNN: {dnn_hidden_units}")

    if not os.path.exists(INPUT_MODEL):
        print(f"❌ 模型权重不存在: {INPUT_MODEL}")
        print("   请先运行 train_deepfm_v3.py")
        sys.exit(1)

    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=dnn_hidden_units,
        dnn_dropout=dnn_dropout,
        device='cpu',
    )
    state_dict = torch.load(INPUT_MODEL, map_location='cpu', weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    print("   ✅ 模型加载成功")

    return model, features


# ============================================================
# Step 2: 提取歌曲复合 Embedding
# ============================================================

def extract_embeddings(model, features):
    """
    构建全量歌曲 Embedding（暖歌曲 + 冷门歌曲）
    暖歌曲：协同(song_id) + 内容(genre/lang/artist/country) 混合向量
    冷门歌曲：song_id 部分置零，仅用内容 embedding 代理
    """
    print("\n" + "=" * 62)
    print(f"🔢 [Step 2/4] 提取歌曲复合 Embedding（{EMBEDDING_DIM}维）")
    print("=" * 62)

    import pandas as pd
    from sqlalchemy import create_engine

    embedding_dict = model.embedding_dict

    # 提取各 Embedding 矩阵
    emb_matrices = {}
    for name, dim in SONG_EMB_PARTS:
        if name in embedding_dict:
            mat = embedding_dict[name].weight.data.numpy()
            emb_matrices[name] = mat
            print(f"   {name:<18} embedding: {mat.shape}")
        else:
            print(f"   ⚠️  {name} 不在 embedding_dict，用零填充")
            n_key = f"n_{name}s" if not name.endswith("y") else f"n_{name[:-1]}ies"
            vocab_size = features.get(n_key, 1) + 1
            emb_matrices[name] = np.zeros((vocab_size, dim), dtype=np.float32)

    # 加载 encoders（用于冷门歌曲内容编码）
    encoders_path = os.path.join(MODE_DIR, "encoders_v3.pkl")
    with open(encoders_path, "rb") as f:
        encoders = pickle.load(f)

    # 构建 real_songs.id → encoded_id 的映射（暖歌曲）
    song_enc = encoders.get("song_id")
    id_to_enc = {}   # int(songs.id) → encoded_id
    if song_enc is not None:
        for enc_id, val in enumerate(song_enc.classes_):
            try:
                id_to_enc[int(val)] = enc_id
            except (ValueError, TypeError):
                pass

    # 构建暖歌曲的 song_vectors（协同+内容混合）
    print("\n   🔗 构建暖歌曲属性映射...")
    from collections import Counter
    song_id_enc  = features["song_id_encoded"]
    genre_enc    = features["genre_encoded"]
    lang_enc     = features["language_encoded"]
    artist_enc   = features["artist_encoded"]
    country_enc  = features.get("origin_country_encoded",
                                 np.zeros(len(song_id_enc), dtype=np.int32))

    attr_accum = {}
    for i in range(len(song_id_enc)):
        sid = int(song_id_enc[i])
        if sid not in attr_accum:
            attr_accum[sid] = {k: Counter() for k in ("genre", "language", "artist", "origin_country")}
        attr_accum[sid]["genre"][int(genre_enc[i])]            += 1
        attr_accum[sid]["language"][int(lang_enc[i])]          += 1
        attr_accum[sid]["artist"][int(artist_enc[i])]          += 1
        attr_accum[sid]["origin_country"][int(country_enc[i])] += 1

    song_attrs = {sid: {k: c.most_common(1)[0][0] for k, c in d.items()}
                  for sid, d in attr_accum.items()}

    n_songs  = features["n_songs"]
    warm_vecs = np.zeros((n_songs, EMBEDDING_DIM), dtype=np.float32)
    song_emb  = emb_matrices["song_id"]
    song_dim  = SONG_EMB_PARTS[0][1]

    offset = 0
    warm_vecs[:, offset:offset+song_dim] = song_emb[:n_songs]
    offset += song_dim
    for name, dim in SONG_EMB_PARTS[1:]:
        mat = emb_matrices[name]
        for sid in range(n_songs):
            if sid in song_attrs:
                attr_id = song_attrs[sid][name]
                if attr_id < len(mat):
                    warm_vecs[sid, offset:offset+dim] = mat[attr_id]
        offset += dim
    print(f"   ✅ 暖歌曲 Embedding: {warm_vecs.shape}")

    # ── 加载全量歌曲（含冷门歌曲）──────────────────────────────
    print("\n   📥 加载全量歌曲元数据（含冷门）...")
    engine = create_engine(
        "mysql+pymysql://root:JF123456@localhost:3306/musicweb?charset=utf8mb4",
        pool_pre_ping=True
    )
    all_songs_df = pd.read_sql(
        "SELECT id, genre, language, artist, origin_country FROM songs ORDER BY id",
        engine
    )
    engine.dispose()
    n_all = len(all_songs_df)
    print(f"   ✅ 全量歌曲: {n_all:,} 首（暖歌曲: {n_songs:,}，冷门: {n_all - len(id_to_enc):,}）")

    # 预计算每个内容特征的 val_to_enc 字典（用于冷门歌曲快速编码）
    val_to_enc_cache = {}
    for name, _ in SONG_EMB_PARTS[1:]:
        enc = encoders.get(name)
        if enc is not None:
            val_to_enc_cache[name] = {str(v): int(i) for i, v in enumerate(enc.classes_)}
        else:
            val_to_enc_cache[name] = {}

    # 构建全量 Embedding 矩阵（向量化）
    print("   🔨 构建全量 Embedding 矩阵（向量化）...")
    real_ids  = all_songs_df["id"].values
    all_vecs  = np.zeros((n_all, EMBEDDING_DIM), dtype=np.float32)

    # 暖歌曲：直接用 warm_vecs
    warm_flags = np.array([rid in id_to_enc for rid in real_ids])
    warm_idx   = np.where(warm_flags)[0]
    cold_idx   = np.where(~warm_flags)[0]

    for i in warm_idx:
        all_vecs[i] = warm_vecs[id_to_enc[int(real_ids[i])]]

    # 冷门歌曲：内容代理向量（song_id 部分保持零）
    if len(cold_idx) > 0:
        offset = SONG_EMB_PARTS[0][1]   # 跳过 song_id(16维)
        for name, dim in SONG_EMB_PARTS[1:]:
            v2e  = val_to_enc_cache[name]
            mat  = emb_matrices[name]
            vals = all_songs_df[name].fillna("unknown").astype(str).values
            enc_ids = pd.Series(vals).map(v2e).fillna(0).astype(int).values
            enc_ids = np.clip(enc_ids, 0, len(mat) - 1)
            all_vecs[cold_idx, offset:offset+dim] = mat[enc_ids[cold_idx]]
            offset += dim

    # L2 归一化
    norms = np.linalg.norm(all_vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    all_vecs /= norms

    # 构建双向映射
    faiss_to_mysql = {int(i): int(rid) for i, rid in enumerate(real_ids)}
    mysql_to_faiss = {int(rid): int(i) for i, rid in enumerate(real_ids)}
    mysql_to_enc   = {int(real_ids[i]): id_to_enc[int(real_ids[i])] for i in warm_idx}

    print(f"   ✅ 全量 Embedding 矩阵: {all_vecs.shape}")
    print(f"   ✅ L2 归一化完成")

    return all_vecs, faiss_to_mysql, mysql_to_faiss, mysql_to_enc


# ============================================================
# Step 3: 构建 FAISS 索引
# ============================================================

def build_faiss_index(song_vectors):
    print("\n" + "=" * 62)
    print("🔍 [Step 3/4] 构建 FAISS 索引")
    print("=" * 62)

    import faiss

    n_songs, dim = song_vectors.shape
    print(f"\n   歌曲数:   {n_songs:,}")
    print(f"   向量维度: {dim}")
    print(f"   索引类型: IndexFlatIP（余弦相似度）")

    index = faiss.IndexFlatIP(dim)
    index.add(song_vectors)
    print(f"\n   ✅ FAISS 索引构建完成，向量数: {index.ntotal:,}")

    # 检索速度测试
    print("\n   ⏱️ 检索速度测试（Top-20，100次平均）...")
    query = song_vectors[:1]
    t0 = time.time()
    for _ in range(100):
        index.search(query, 20)
    elapsed_ms = (time.time() - t0) / 100 * 1000
    print(f"   ✅ 单次 Top-20 检索耗时: {elapsed_ms:.2f} ms")

    # 示例输出
    scores, indices = index.search(query, 5)
    print(f"\n   📋 检索示例（第0首歌的 Top-5 相似歌曲）:")
    for i in range(5):
        print(f"      #{i+1}: 歌曲编码={indices[0][i]}, 相似度={scores[0][i]:.4f}")

    return index


# ============================================================
# Step 4: 保存
# ============================================================

def save_index(index, faiss_to_mysql, mysql_to_faiss, mysql_to_enc, features):
    print("\n" + "=" * 62)
    print("💾 [Step 4/4] 保存索引和映射")
    print("=" * 62)

    import faiss

    faiss.write_index(index, OUTPUT_FAISS)
    size_mb = os.path.getsize(OUTPUT_FAISS) / 1024 / 1024
    print(f"   ✅ FAISS 索引: {OUTPUT_FAISS}  ({size_mb:.1f} MB)")

    map_data = {
        "faiss_to_mysql": faiss_to_mysql,    # {faiss_idx: real_songs.id}
        "mysql_to_faiss": mysql_to_faiss,    # {real_songs.id: faiss_idx}
        "mysql_to_enc":   mysql_to_enc,      # {real_songs.id: encoded_id}（暖歌曲）
        "n_warm":         features["n_songs"],
        "n_all":          index.ntotal,
        "embedding_dim":  EMBEDDING_DIM,
        "emb_parts":      SONG_EMB_PARTS,
        "version":        "v4_cold_start",
    }
    with open(OUTPUT_MAP, "wb") as f:
        pickle.dump(map_data, f, protocol=4)
    print(f"   ✅ 歌曲映射: {OUTPUT_MAP}  (暖歌曲: {features['n_songs']:,}, 全量: {index.ntotal:,})")


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "🎵" * 31)
    print("   MusicMode FAISS 索引构建（5×32维嵌入，共160维）")
    print("🎵" * 31)

    model, features = load_model_and_features()
    all_vecs, faiss_to_mysql, mysql_to_faiss, mysql_to_enc = extract_embeddings(model, features)
    index = build_faiss_index(all_vecs)
    save_index(index, faiss_to_mysql, mysql_to_faiss, mysql_to_enc, features)

    print("\n" + "=" * 62)
    print("✅ FAISS 索引构建完成！")
    print(f"   索引: {OUTPUT_FAISS}")
    print(f"   映射: {OUTPUT_MAP}")
    print("=" * 62)
    print("\n🚀 下一步:")
    print("   python build_ensemble.py   # 校准集成系数 α")


if __name__ == "__main__":
    main()
