# -*- coding: utf-8 -*-
"""
FAISS 索引构建脚本
功能：
1. 从训练好的 DeepFM 模型中提取歌曲 Embedding
2. 拼接 song + genre + language + artist 四个维度的 Embedding → 64维复合向量
3. 构建 FAISS 向量索引用于快速相似歌曲检索
4. 输出 song_index.faiss（向量索引） 和 song_id_map.pkl（索引位置→歌曲编码映射）

作者：MusicMode 推荐系统
"""

import os
import sys
import pickle
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")
FEATURE_PATH = os.path.join(MODE_DIR, "features.pkl")
ENCODER_PATH = os.path.join(MODE_DIR, "encoders.pkl")
DEEPFM_MODEL_PATH = os.path.join(MODE_DIR, "deepfm_model.pth")

# 输出
FAISS_INDEX_PATH  = os.path.join(MODE_DIR, "song_index.faiss")
SONG_ID_MAP_PATH  = os.path.join(MODE_DIR, "song_id_map.pkl")
MODEL_CONFIG_PATH = os.path.join(MODE_DIR, "model_config.pkl")

# Embedding 维度：song+genre+language+artist 各 16 维 = 64 维
EMBEDDING_DIM = 64


def load_model_and_features():
    """加载模型和特征数据"""
    print("\n" + "=" * 60)
    print("📂 [Step 1/4] 加载模型和特征")
    print("=" * 60)

    import torch
    from deepctr_torch.models import DeepFM

    # 加载特征维度
    print("\n   📥 加载特征数据...")
    with open(FEATURE_PATH, 'rb') as f:
        features = pickle.load(f)

    print(f"   ✅ 歌曲数: {features['n_songs']:,}")
    print(f"   ✅ 流派数: {features['n_genres']:,}")
    print(f"   ✅ 语言数: {features['n_languages']:,}")
    print(f"   ✅ 艺术家数: {features['n_artists']:,}")

    # 加载编码器
    print("\n   📥 加载编码器...")
    with open(ENCODER_PATH, 'rb') as f:
        encoders = pickle.load(f)
    print(f"   ✅ 编码器加载完成")

    # 重建模型：优先使用训练时保存的 model_config.pkl
    print("\n   📥 重建 DeepFM 模型...")
    if os.path.exists(MODEL_CONFIG_PATH):
        with open(MODEL_CONFIG_PATH, 'rb') as f:
            cfg = pickle.load(f)
        feature_columns  = cfg['feature_columns']
        dnn_hidden_units = cfg.get('dnn_hidden_units', (256, 128, 64))
        dnn_dropout      = cfg.get('dnn_dropout', 0.2)
        print(f"   ✅ 从 model_config.pkl 加载特征列（{len(feature_columns)} 个）")
    else:
        # 回退：硬编码 5 个特征（兼容旧模型）
        from deepctr_torch.inputs import SparseFeat
        feature_columns = [
            SparseFeat('user',     features['n_users'],     embedding_dim=16),
            SparseFeat('song',     features['n_songs'],     embedding_dim=16),
            SparseFeat('genre',    features['n_genres'],    embedding_dim=16),
            SparseFeat('language', features['n_languages'], embedding_dim=16),
            SparseFeat('artist',   features['n_artists'],   embedding_dim=16),
        ]
        dnn_hidden_units = (256, 128, 64)
        dnn_dropout = 0.2
        print("   ⚠️  model_config.pkl 不存在，使用 5 特征默认配置")

    model = DeepFM(
        linear_feature_columns=feature_columns,
        dnn_feature_columns=feature_columns,
        dnn_hidden_units=dnn_hidden_units,
        dnn_dropout=dnn_dropout,
        device='cpu'
    )

    state_dict = torch.load(DEEPFM_MODEL_PATH, map_location='cpu', weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"   ✅ 模型加载成功")

    return model, features, encoders


def extract_embeddings(model, features):
    """从模型中提取歌曲 Embedding"""
    print("\n" + "=" * 60)
    print("🔢 [Step 2/4] 提取歌曲 Embedding")
    print("=" * 60)

    embedding_dict = model.embedding_dict

    # 提取各维度的 Embedding 矩阵
    song_emb = embedding_dict['song'].weight.data.numpy()    # (n_songs, 16)
    genre_emb = embedding_dict['genre'].weight.data.numpy()   # (n_genres, 16)
    language_emb = embedding_dict['language'].weight.data.numpy()  # (n_languages, 16)
    artist_emb = embedding_dict['artist'].weight.data.numpy()  # (n_artists, 16)

    print(f"   song Embedding: {song_emb.shape}")
    print(f"   genre Embedding: {genre_emb.shape}")
    print(f"   language Embedding: {language_emb.shape}")
    print(f"   artist Embedding: {artist_emb.shape}")

    # 为每首歌构建复合特征向量
    # 需要知道每首歌对应的 genre、language、artist 编码
    song_encoded = features['song_encoded']
    genre_encoded = features['genre_encoded']
    language_encoded = features['language_encoded']
    artist_encoded = features['artist_encoded']

    # 构建歌曲→属性的映射（取每首歌最常关联的属性）
    print("\n   🔗 构建歌曲属性映射...")
    from collections import Counter

    song_genre_map = {}
    song_lang_map = {}
    song_artist_map = {}

    for i in range(len(song_encoded)):
        sid = song_encoded[i]
        if sid not in song_genre_map:
            song_genre_map[sid] = []
            song_lang_map[sid] = []
            song_artist_map[sid] = []
        song_genre_map[sid].append(genre_encoded[i])
        song_lang_map[sid].append(language_encoded[i])
        song_artist_map[sid].append(artist_encoded[i])

    # 取众数作为该歌曲的属性
    song_attrs = {}
    for sid in song_genre_map:
        genre_mode = Counter(song_genre_map[sid]).most_common(1)[0][0]
        lang_mode = Counter(song_lang_map[sid]).most_common(1)[0][0]
        artist_mode = Counter(song_artist_map[sid]).most_common(1)[0][0]
        song_attrs[sid] = (genre_mode, lang_mode, artist_mode)

    # 构建复合 Embedding 矩阵
    n_songs = features['n_songs']
    song_vectors = np.zeros((n_songs, EMBEDDING_DIM), dtype=np.float32)

    for sid in range(n_songs):
        if sid in song_attrs:
            g_id, l_id, a_id = song_attrs[sid]
            song_vectors[sid] = np.concatenate([
                song_emb[sid], genre_emb[g_id], language_emb[l_id], artist_emb[a_id]
            ])
        else:
            # 没有属性信息的歌曲，只用 song embedding + 零填充
            song_vectors[sid, :16] = song_emb[sid]

    # L2 归一化（FAISS 的 IndexFlatIP 需要归一化后才等价于余弦相似度）
    from numpy.linalg import norm
    norms = norm(song_vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    song_vectors = song_vectors / norms

    print(f"\n   ✅ 复合 Embedding 矩阵: {song_vectors.shape}")
    print(f"   ✅ 已 L2 归一化")

    return song_vectors, song_attrs


def build_faiss_index(song_vectors):
    """构建 FAISS 索引"""
    print("\n" + "=" * 60)
    print("🔍 [Step 3/4] 构建 FAISS 索引")
    print("=" * 60)

    import faiss

    n_songs, dim = song_vectors.shape
    print(f"\n   📋 索引配置:")
    print(f"      - 歌曲数: {n_songs:,}")
    print(f"      - 向量维度: {dim}")

    # 使用 IndexFlatIP（内积搜索，归一化后等价于余弦相似度）
    # 对于 35 万首歌，暴力搜索已经足够快（毫秒级）
    index = faiss.IndexFlatIP(dim)
    index.add(song_vectors)

    print(f"   ✅ FAISS 索引构建完成")
    print(f"   ✅ 索引中向量数: {index.ntotal:,}")

    # 验证检索速度
    print("\n   ⏱️ 检索速度测试...")
    import time
    query = song_vectors[0:1]  # 用第一首歌做测试
    start = time.time()
    for _ in range(100):
        scores, indices = index.search(query, 20)  # 搜 Top-20
    elapsed = (time.time() - start) / 100 * 1000
    print(f"   ✅ 单次 Top-20 检索耗时: {elapsed:.2f} ms")

    # 展示检索结果示例
    scores, indices = index.search(query, 5)
    print(f"\n   📋 检索示例（第0首歌的 Top-5 相似歌曲）:")
    for i in range(5):
        print(f"      #{i+1}: 歌曲编码={indices[0][i]}, 相似度={scores[0][i]:.4f}")

    return index


def save_index(index, song_attrs, encoders):
    """保存索引和映射"""
    print("\n" + "=" * 60)
    print("💾 [Step 4/4] 保存索引")
    print("=" * 60)

    import faiss

    # 保存 FAISS 索引
    print(f"\n   📦 保存 FAISS 索引: {FAISS_INDEX_PATH}")
    faiss.write_index(index, FAISS_INDEX_PATH)
    index_size = os.path.getsize(FAISS_INDEX_PATH) / 1024 / 1024
    print(f"   ✅ 索引大小: {index_size:.1f} MB")

    # 保存歌曲映射（编码ID → 属性映射）
    print(f"\n   📦 保存歌曲映射: {SONG_ID_MAP_PATH}")
    map_data = {
        'song_attrs': song_attrs,           # {encoded_id: (genre, lang, artist)}
        'n_songs': len(song_attrs),
        'embedding_dim': EMBEDDING_DIM,
    }
    with open(SONG_ID_MAP_PATH, 'wb') as f:
        pickle.dump(map_data, f)
    print(f"   ✅ 映射保存完成")


def main():
    """主函数"""
    print("\n" + "🎵" * 30)
    print("   MusicMode FAISS 索引构建")
    print("🎵" * 30)

    # 1. 加载模型和特征
    model, features, encoders = load_model_and_features()

    # 2. 提取 Embedding
    song_vectors, song_attrs = extract_embeddings(model, features)

    # 3. 构建 FAISS 索引
    index = build_faiss_index(song_vectors)

    # 4. 保存
    save_index(index, song_attrs, encoders)

    print("\n" + "=" * 60)
    print("✅ FAISS 索引构建完成!")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   - 索引: {FAISS_INDEX_PATH}")
    print(f"   - 映射: {SONG_ID_MAP_PATH}")
    print(f"\n🚀 下一步: 运行 sync_recs_v2.py 生成推荐")


if __name__ == "__main__":
    main()
