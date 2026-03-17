# -*- coding: utf-8 -*-
"""
sync_recs_v3.py — 三路召回 + LightGBM+DeepFM 集成精排

架构：
  召回层  (230万 → ~300): FAISS向量召回 + 热度召回 + ALS协同过滤
  精排层  (300 → 50):     LightGBM 打分
  集成层  (50 → 25):      DeepFM 打分 + α 加权融合
  重排层  (25 → 20):      多样性约束（同艺术家 ≤ 3 首）+ 冷却/屏蔽过滤

计划任务：每天凌晨 4 点运行
"""

import os
import sys
import pickle
import datetime
import math
import numpy as np
import pymysql
import faiss

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# 配置
# ============================================================

MYSQL_HOST     = "localhost"
MYSQL_USER     = "root"
MYSQL_PASSWORD = "JF123456"
MYSQL_DB       = "musicweb"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR    = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

# 模型文件
FAISS_INDEX_PATH   = os.path.join(MODE_DIR, "song_index.faiss")
SONG_ID_MAP_PATH   = os.path.join(MODE_DIR, "song_id_map.pkl")
LGBM_MODEL_PATH    = os.path.join(MODE_DIR, "lgbm_model.pkl")
DEEPFM_MODEL_PATH  = os.path.join(MODE_DIR, "deepfm_model_v3.pth")
DEEPFM_CONFIG_PATH = os.path.join(MODE_DIR, "model_config_v3.pkl")
ENSEMBLE_PATH      = os.path.join(MODE_DIR, "ensemble_config.pkl")
ALS_MODEL_PATH     = os.path.join(MODE_DIR, "als_model.pkl")
ENCODERS_PATH      = os.path.join(MODE_DIR, "encoders_v3.pkl")
USER_STATS_PATH    = os.path.join(MODE_DIR, "user_stats.pkl")
SONG_STATS_PATH    = os.path.join(MODE_DIR, "song_stats.pkl")

# 推荐参数
TOP_N          = 20    # 最终推荐数
RECALL_FAISS   = 150   # FAISS 召回候选数
RECALL_HOT     = 100   # 热度召回候选数
RECALL_ALS     = 50    # ALS 召回候选数
RANK_TOP       = 50    # LightGBM 保留数
ENSEMBLE_TOP   = 25    # DeepFM 集成后保留数
MAX_PER_ARTIST = 3     # 多样性：同艺术家最多推荐数

# 用户画像权重（FAISS 召回用）
WEIGHTS = {
    'play_yesterday': 1.0,
    'play_7days':     0.6,
    'play_older':     0.3,
    'favorite':       0.8,
    'playlist':       0.7,
}


# ============================================================
# 工具
# ============================================================

def get_db():
    return pymysql.connect(
        host=MYSQL_HOST, user=MYSQL_USER,
        password=MYSQL_PASSWORD, db=MYSQL_DB,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )


# ============================================================
# 资源加载
# ============================================================

class Resources:
    """一次性加载所有静态资源，供全部用户共享"""

    def __init__(self):
        print("📥 加载推荐系统资源...")

        # FAISS 索引
        self.index        = faiss.read_index(FAISS_INDEX_PATH)
        with open(SONG_ID_MAP_PATH, "rb") as f:
            self.map_data = pickle.load(f)

        # 编码器
        self.encoders = {}
        if os.path.exists(ENCODERS_PATH):
            with open(ENCODERS_PATH, "rb") as f:
                self.encoders = pickle.load(f)

        # 用户统计（keyed by user_encoded）
        self.user_stats = {}
        if os.path.exists(USER_STATS_PATH):
            with open(USER_STATS_PATH, "rb") as f:
                self.user_stats = pickle.load(f)

        # 歌曲统计（keyed by song_encoded）
        self.song_stats = {}
        if os.path.exists(SONG_STATS_PATH):
            with open(SONG_STATS_PATH, "rb") as f:
                self.song_stats = pickle.load(f)

        # LightGBM
        self.lgbm_model  = None
        self.lgbm_feats  = None
        if os.path.exists(LGBM_MODEL_PATH):
            with open(LGBM_MODEL_PATH, "rb") as f:
                payload          = pickle.load(f)
                self.lgbm_model  = payload["model"]
                self.lgbm_feats  = payload["feature_names"]
                self.lgbm_iter   = payload.get("best_iteration")
            print(f"   ✅ LightGBM 加载（val_AUC={payload.get('val_auc', 0):.4f}）")

        # DeepFM
        self.deepfm_model   = None
        self.deepfm_feat_names = None
        self.deepfm_sparse  = []
        self.deepfm_dense   = []
        if os.path.exists(DEEPFM_CONFIG_PATH) and os.path.exists(DEEPFM_MODEL_PATH):
            import torch
            from deepctr_torch.models import DeepFM
            from deepctr_torch.inputs import get_feature_names
            with open(DEEPFM_CONFIG_PATH, "rb") as f:
                cfg = pickle.load(f)
            feature_columns = cfg["feature_columns"]
            m = DeepFM(
                linear_feature_columns=feature_columns,
                dnn_feature_columns=feature_columns,
                dnn_hidden_units=cfg.get("dnn_hidden_units", (512, 256, 128, 64)),
                dnn_dropout=cfg.get("dnn_dropout", 0.2),
                device='cpu',
            )
            sd = torch.load(DEEPFM_MODEL_PATH, map_location='cpu', weights_only=True)
            m.load_state_dict(sd)
            m.eval()
            self.deepfm_model      = m
            self.deepfm_feat_names = get_feature_names(feature_columns)
            self.deepfm_sparse     = cfg.get("sparse_feat_specs", [])
            self.deepfm_dense      = cfg.get("dense_feat_specs", [])
            print(f"   ✅ DeepFM v3 加载（val_AUC={cfg.get('best_val_auc', 0):.4f}）")

        # 集成系数
        self.alpha = 0.5  # 默认 50/50
        if os.path.exists(ENSEMBLE_PATH):
            with open(ENSEMBLE_PATH, "rb") as f:
                ec = pickle.load(f)
            self.alpha = ec["alpha"]
            print(f"   ✅ 集成系数 α={self.alpha:.2f}（集成 AUC={ec.get('ensemble_auc', 0):.4f}）")

        # ALS
        self.als_model = None
        if os.path.exists(ALS_MODEL_PATH):
            with open(ALS_MODEL_PATH, "rb") as f:
                self.als_model = pickle.load(f)
            print("   ✅ ALS 模型加载")

        # MySQL ID ↔ FAISS 索引 双向映射（从 song_id_map.pkl 直接加载）
        md = self.map_data
        if "faiss_to_mysql" in md:
            # v4_cold_start 格式（全量 2.3M 歌曲）
            self.faiss2mysql: dict[int, int] = md["faiss_to_mysql"]
            self.mysql2faiss: dict[int, int] = md["mysql_to_faiss"]
            self.mysql2enc:   dict[int, int] = md["mysql_to_enc"]
            print(f"   ✅ FAISS 索引：{self.index.ntotal:,} 首歌曲"
                  f"（暖: {md.get('n_warm', '?'):,}, 冷: {self.index.ntotal - md.get('n_warm', 0):,}）")
        else:
            # 旧格式兼容
            self.mysql2faiss: dict[int, int] = {}
            self.faiss2mysql: dict[int, int] = {}
            self.mysql2enc:   dict[int, int] = {}
            print(f"   ✅ FAISS 索引：{self.index.ntotal:,} 首歌曲（旧格式，需重建映射）")

    def build_song_mappings(self, db_songs: list):
        """构建 MySQL song_id ↔ FAISS idx / song_encoded 的双向映射"""
        # song_encoder: LabelEncoder over kkbox_id strings
        song_enc = self.encoders.get("song_id") or self.encoders.get("song")
        if song_enc is None:
            print("   ⚠️  song_id 编码器不存在，无法建立 FAISS 映射")
            return

        # encoder 是按 str(songs.id) 训练的，用整数 ID 做 key
        kb_to_enc = {kb: idx for idx, kb in enumerate(song_enc.classes_)}

        for row in db_songs:
            sql_id = row["id"]
            str_id = str(sql_id)
            if str_id in kb_to_enc:
                enc_id = kb_to_enc[str_id]
                # FAISS index pos == song_encoded (verify: built in build_faiss_index.py)
                self.mysql2faiss[sql_id] = enc_id
                self.faiss2mysql[enc_id] = sql_id
                self.mysql2enc[sql_id]   = enc_id

        print(f"   ✅ 歌曲映射建立：{len(self.mysql2faiss):,} 首歌曲可检索")


# ============================================================
# 反馈回收（与 v2 完全相同）
# ============================================================

def update_feedback(db):
    print("\n🔄 [Step 1] 回收近期推荐反馈（最近7天）...")
    try:
        with db.cursor() as cur:
            today    = datetime.date.today().strftime("%Y-%m-%d")
            lookback = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")

            # A: 同步播放完播率
            cur.execute("""
                UPDATE recommendation_feedback rf
                JOIN (
                    SELECT ph.user_id, ph.song_id,
                           LEAST(1.0, MAX(ph.play_duration) / s.duration) AS completion
                    FROM play_history ph
                    JOIN songs s ON s.id = ph.song_id
                    WHERE DATE(ph.play_time) BETWEEN %s AND %s
                      AND ph.play_duration > 0 AND s.duration > 0
                    GROUP BY ph.user_id, ph.song_id
                ) AS played ON rf.user_id = played.user_id AND rf.song_id = played.song_id
                SET rf.was_played = 1, rf.play_completion = played.completion
                WHERE rf.recommend_date BETWEEN %s AND %s
            """, (lookback, today, lookback, today))
            print(f"   A 同步播放完播率: {cur.rowcount} 条")

            # B: 同步收藏状态
            cur.execute("""
                UPDATE recommendation_feedback rf
                JOIN playlist_songs ps ON ps.song_id = rf.song_id
                JOIN user_playlists up ON up.id = ps.playlist_id
                    AND up.user_id = rf.user_id AND up.is_default = 1
                SET rf.was_favorited = 1
                WHERE rf.recommend_date BETWEEN %s AND %s
            """, (lookback, today))
            print(f"   B 同步收藏状态: {cur.rowcount} 条")

            # C: 计算行为评分
            cur.execute("""
                SELECT id, user_id, was_played, play_completion, was_favorited,
                       consecutive_ignore_days
                FROM recommendation_feedback
                WHERE recommend_date BETWEEN %s AND %s
            """, (lookback, today))
            feedbacks = cur.fetchall()

            if not feedbacks:
                print("   ℹ️ 近期没有推荐记录，跳过反馈回收")
                return

            cur.execute("""
                SELECT DISTINCT user_id FROM play_history
                WHERE DATE(play_time) BETWEEN %s AND %s
            """, (lookback, today))
            active_users = {r["user_id"] for r in cur.fetchall()}

            update_data = []
            for fb in feedbacks:
                uid         = fb["user_id"]
                was_played  = fb["was_played"]
                comp        = fb["play_completion"] or 0.0
                was_fav     = fb["was_favorited"]
                ignore_days = fb["consecutive_ignore_days"] or 0
                score_delta = 0.0
                cooldown    = None
                new_ignore  = ignore_days

                if uid in active_users:
                    if was_played == 0:
                        score_delta -= 0.1
                        new_ignore  += 1
                        if new_ignore >= 3:
                            cooldown    = (datetime.date.today() + datetime.timedelta(days=14)).strftime("%Y-%m-%d")
                            score_delta -= 0.5
                    else:
                        new_ignore = 0
                        score_delta += 0.5 if comp > 0.8 else (0.3 if comp >= 0.2 else -0.3)
                    if was_fav:
                        score_delta += 1.0

                update_data.append((score_delta, new_ignore, cooldown, fb["id"]))

            for score_delta, new_ignore, cooldown, fid in update_data:
                if cooldown:
                    cur.execute("""
                        UPDATE recommendation_feedback
                        SET feedback_score = feedback_score + %s,
                            consecutive_ignore_days = %s, cooldown_until = %s
                        WHERE id = %s
                    """, (score_delta, new_ignore, cooldown, fid))
                else:
                    cur.execute("""
                        UPDATE recommendation_feedback
                        SET feedback_score = feedback_score + %s,
                            consecutive_ignore_days = %s
                        WHERE id = %s
                    """, (score_delta, new_ignore, fid))
            print(f"   C 更新行为评分: {len(update_data)} 条")

            # D: 显式满意度评分
            satisfaction_map = {
                "very_satisfied": 3.0, "satisfied": 1.5, "neutral": 0.0, "dissatisfied": -2.0
            }
            cur.execute("""
                SELECT user_id, satisfaction, feedback_date FROM user_preference_feedback
                WHERE feedback_date BETWEEN %s AND %s
            """, (lookback, today))
            for row in cur.fetchall():
                delta = satisfaction_map.get(row["satisfaction"], 0.0)
                if delta:
                    cur.execute("""
                        UPDATE recommendation_feedback
                        SET feedback_score = feedback_score + %s
                        WHERE user_id = %s AND recommend_date = %s
                    """, (delta, row["user_id"], row["feedback_date"]))
            print("   D 显式满意度同步完成")

            db.commit()
            print("   ✅ 反馈回收完成")
    except Exception as e:
        print(f"   ❌ 反馈回收失败: {e}")
        import traceback; traceback.print_exc()
        db.rollback()


# ============================================================
# 召回层
# ============================================================

def build_user_profile(db, user_id, res: Resources,
                        blocked_genres, blocked_artists):
    """生成用户 FAISS 画像向量（与 v2 相同逻辑）"""
    today     = datetime.datetime.now()
    yesterday = today - datetime.timedelta(days=1)
    seven_days = today - datetime.timedelta(days=7)

    vectors, weights_list = [], []
    song_meta_cache = {}

    def genre_proxy(cur, genre_str, max_p=1):
        keyword = genre_str.split(';')[0].strip()
        if not keyword:
            return []
        cur.execute("""
            SELECT id FROM songs
            WHERE genre LIKE %s
            ORDER BY popularity DESC LIMIT 5
        """, (f"%{keyword}%",))
        proxies = []
        for row in cur.fetchall():
            if row["id"] in res.mysql2faiss:
                proxies.append(res.index.reconstruct(res.mysql2faiss[row["id"]]))
        return proxies[:max_p]

    with db.cursor() as cur:
        # 满意度调整系数
        cur.execute("""
            SELECT satisfaction FROM user_preference_feedback
            WHERE user_id = %s ORDER BY feedback_date DESC LIMIT 1
        """, (user_id,))
        sati_row = cur.fetchone()
        sati = sati_row["satisfaction"] if sati_row else None
        SATI = {
            "dissatisfied":   (3.0, 0.3),
            "neutral":        (1.5, 0.8),
            "satisfied":      (0.5, 1.0),
            "very_satisfied": (0.2, 1.0),
        }
        pref_w, hist_damp = SATI.get(sati, (0.2, 1.0))

        # 播放历史
        cur.execute("""
            SELECT ph.song_id, ph.play_time,
                   CASE WHEN s.duration > 0 THEN LEAST(1.0, ph.play_duration/s.duration) ELSE 0.5 END AS comp
            FROM play_history ph LEFT JOIN songs s ON s.id = ph.song_id
            WHERE ph.user_id = %s
        """, (user_id,))
        for row in cur.fetchall():
            sid  = row["song_id"]
            pt   = row["play_time"]
            comp = row["comp"] or 0.5
            base_w = WEIGHTS["play_yesterday"] if pt >= yesterday else (
                     WEIGHTS["play_7days"]     if pt >= seven_days else WEIGHTS["play_older"])
            cf = 1.5 if comp > 0.8 else (0.5 if comp < 0.2 else 1.0)
            w  = base_w * cf * hist_damp

            if sid in res.mysql2faiss:
                vectors.append(res.index.reconstruct(res.mysql2faiss[sid]))
                weights_list.append(w)
            else:
                cur.execute("SELECT genre FROM songs WHERE id = %s", (sid,))
                meta = cur.fetchone()
                genre = (meta.get("genre") or "") if meta else ""
                song_meta_cache[sid] = genre
                if genre and not any(bg in genre for bg in blocked_genres):
                    for pv in genre_proxy(cur, genre):
                        vectors.append(pv)
                        weights_list.append(w * 0.5)

        # 默认收藏歌单
        cur.execute("""
            SELECT ps.song_id FROM playlist_songs ps
            JOIN user_playlists up ON ps.playlist_id = up.id
            WHERE up.is_default = TRUE AND up.user_id = %s
        """, (user_id,))
        for row in cur.fetchall():
            sid = row["song_id"]
            if sid in res.mysql2faiss:
                vectors.append(res.index.reconstruct(res.mysql2faiss[sid]))
                weights_list.append(WEIGHTS["favorite"] * hist_damp)

        # 自建歌单
        cur.execute("""
            SELECT ps.song_id FROM playlist_songs ps
            JOIN user_playlists up ON ps.playlist_id = up.id
            WHERE up.user_id = %s
        """, (user_id,))
        for row in cur.fetchall():
            sid = row["song_id"]
            if sid in res.mysql2faiss:
                vectors.append(res.index.reconstruct(res.mysql2faiss[sid]))
                weights_list.append(WEIGHTS["playlist"] * hist_damp)

        # 用户偏好标签
        cur.execute("SELECT preferred_genres, preferred_artists FROM users WHERE id = %s", (user_id,))
        pref = cur.fetchone()
        if pref:
            limit = 100 if pref_w >= 1.5 else 50
            for token in (pref.get("preferred_genres") or "").split(";"):
                token = token.strip()
                if not token:
                    continue
                cur.execute("""
                    SELECT id FROM songs
                    WHERE (genre LIKE %s OR language LIKE %s)
                    ORDER BY popularity DESC LIMIT %s
                """, (f"%{token}%", f"%{token}%", limit))
                for r in cur.fetchall():
                    if r["id"] in res.mysql2faiss:
                        vectors.append(res.index.reconstruct(res.mysql2faiss[r["id"]]))
                        weights_list.append(pref_w)
            for artist in (pref.get("preferred_artists") or "").split(";"):
                artist = artist.strip()
                if not artist:
                    continue
                cur.execute("""
                    SELECT id FROM songs WHERE artist LIKE %s
                    ORDER BY popularity DESC LIMIT %s
                """, (f"%{artist}%", limit))
                for r in cur.fetchall():
                    if r["id"] in res.mysql2faiss:
                        vectors.append(res.index.reconstruct(res.mysql2faiss[r["id"]]))
                        weights_list.append(pref_w)

    if not vectors:
        return None

    v_arr = np.array(vectors, dtype=np.float32)
    w_arr = np.array(weights_list, dtype=np.float32).reshape(-1, 1)
    profile = np.sum(v_arr * w_arr, axis=0)
    norm = np.linalg.norm(profile)
    if norm > 0:
        profile /= norm
    return profile.reshape(1, -1)


def recall_candidates(db, user_id, res: Resources,
                       exclude_set, blocked_genres, blocked_artists,
                       song_meta_map) -> dict:
    """
    三路召回，返回 {song_id: faiss_score} 候选字典
    """
    candidates = {}

    # ── 通道A: FAISS 向量召回
    profile_vec = build_user_profile(db, user_id, res, blocked_genres, blocked_artists)
    if profile_vec is not None:
        D, I = res.index.search(profile_vec, RECALL_FAISS + 50)
        for score, fidx in zip(D[0], I[0]):
            if fidx < 0:
                continue
            sql_id = res.faiss2mysql.get(fidx)
            if sql_id and sql_id not in exclude_set and sql_id not in candidates:
                genre, artist = song_meta_map.get(sql_id, ("", ""))
                if any(bg in genre for bg in blocked_genres):
                    continue
                if any(ba in artist for ba in blocked_artists):
                    continue
                candidates[sql_id] = float(score)
                if len([k for k in candidates]) >= RECALL_FAISS:
                    break

    # ── 通道B: 热度召回（用户偏好流派 × 近期热门）
    with db.cursor() as cur:
        cur.execute("SELECT preferred_genres FROM users WHERE id = %s", (user_id,))
        pref = cur.fetchone()
        genre_filter = ""
        if pref and pref.get("preferred_genres"):
            # 取第一个流派偏好
            first_genre = pref["preferred_genres"].split(";")[0].strip()
            if first_genre:
                genre_filter = first_genre

        if genre_filter:
            cur.execute("""
                SELECT id FROM songs
                WHERE genre LIKE %s AND popularity > 0
                ORDER BY popularity DESC LIMIT %s
            """, (f"%{genre_filter}%", RECALL_HOT))
        else:
            cur.execute("""
                SELECT id FROM songs WHERE popularity > 0
                ORDER BY popularity DESC LIMIT %s
            """, (RECALL_HOT,))
        for row in cur.fetchall():
            sid = row["id"]
            if sid not in exclude_set and sid not in candidates:
                genre, artist = song_meta_map.get(sid, ("", ""))
                if any(bg in genre for bg in blocked_genres):
                    continue
                if any(ba in artist for ba in blocked_artists):
                    continue
                candidates[sid] = 0.05   # 低基础分，靠精排提升

    # ── 通道C: ALS 协同过滤召回
    if res.als_model is not None:
        # 获取用户 encoded id
        user_enc = None
        user_enc_map = res.user_stats.get("_uid_map", {})
        if user_id in user_enc_map:
            user_enc = user_enc_map[user_id]

        if user_enc is not None:
            try:
                als = res.als_model
                if isinstance(als, dict) and als.get("type") == "simple_als":
                    uf  = als["user_factors"]
                    itf = als["item_factors"]
                    if user_enc < len(uf):
                        scores = uf[user_enc] @ itf.T
                        top_idx = np.argsort(-scores)[:RECALL_ALS + 20]
                        count = 0
                        for enc_id in top_idx:
                            sql_id = res.faiss2mysql.get(enc_id)
                            if sql_id and sql_id not in exclude_set and sql_id not in candidates:
                                genre, artist = song_meta_map.get(sql_id, ("", ""))
                                if any(bg in genre for bg in blocked_genres):
                                    continue
                                if any(ba in artist for ba in blocked_artists):
                                    continue
                                candidates[sql_id] = float(scores[enc_id]) * 0.1
                                count += 1
                                if count >= RECALL_ALS:
                                    break
                else:
                    # implicit ALS
                    from scipy.sparse import csr_matrix
                    dummy_mat = csr_matrix((1, 1))
                    ids, sc = als.recommend(user_enc, dummy_mat[0], N=RECALL_ALS, filter_already_liked_items=True)
                    for enc_id, sc_val in zip(ids.tolist(), sc.tolist()):
                        sql_id = res.faiss2mysql.get(enc_id)
                        if sql_id and sql_id not in exclude_set and sql_id not in candidates:
                            candidates[sql_id] = float(sc_val) * 0.1
            except Exception as e:
                print(f"      ⚠️ ALS 召回失败: {e}")

    return candidates


# ============================================================
# 精排层 — 特征构建 + LightGBM 打分
# ============================================================

def _safe_encode(encoder, value, default=0):
    try:
        return int(encoder.transform([str(value)])[0])
    except Exception:
        return default


def build_pair_features(user_id, song_ids, db, res: Resources):
    """
    为 (user_id, song_ids[]) 构建 25 个特征的矩阵
    返回 np.ndarray shape (len(song_ids), 25)
    """
    encoders = res.encoders

    # ── 从 MySQL 实时查询用户信息
    with db.cursor() as cur:
        cur.execute("""
            SELECT u.gender, u.city, u.bd, u.create_time,
                   COUNT(ph.id) AS play_count,
                   AVG(CASE WHEN s.duration > 0 THEN LEAST(1.0, ph.play_duration/s.duration) END) AS avg_comp,
                   SUM(CASE WHEN DATE(ph.play_time) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 END) AS active_30d
            FROM users u
            LEFT JOIN play_history ph ON ph.user_id = u.id
            LEFT JOIN songs s ON s.id = ph.song_id
            WHERE u.id = %s
        """, (user_id,))
        urow = cur.fetchone() or {}

        # 计算用户 genre/artist/language/country 分布（简化：用偏好标签）
        cur.execute("SELECT preferred_genres, preferred_artists FROM users WHERE id = %s", (user_id,))
        pref = cur.fetchone() or {}

        # 查询候选歌曲信息
        if not song_ids:
            return np.zeros((0, 25), dtype=np.float32)
        fmt = ",".join(["%s"] * len(song_ids))
        cur.execute(f"""
            SELECT s.id, s.genre, s.language, s.artist, s.origin_country,
                   s.release_year, s.duration, s.popularity, s.kkbox_id
            FROM songs s WHERE s.id IN ({fmt})
        """, song_ids)
        song_rows = {r["id"]: r for r in cur.fetchall()}

    # ── 用户稀疏编码
    gender_enc = _safe_encode(encoders.get("gender"), urow.get("gender") or "unknown")
    city_enc   = _safe_encode(encoders.get("city"),   urow.get("city")   or "unknown")

    bd = urow.get("bd") or 25
    if bd <= 0 or bd > 100:
        bd = 25
    if   bd < 18:  age_bucket = 0
    elif bd < 26:  age_bucket = 1
    elif bd < 36:  age_bucket = 2
    elif bd < 51:  age_bucket = 3
    else:          age_bucket = 4
    age_enc = _safe_encode(encoders.get("age_bucket"), str(age_bucket))

    create_time = urow.get("create_time") or datetime.datetime.now()
    tenure_days = (datetime.datetime.now() - create_time).days if isinstance(create_time, datetime.datetime) else 0
    if   tenure_days < 30:   tenure_b = 0
    elif tenure_days < 180:  tenure_b = 1
    elif tenure_days < 365:  tenure_b = 2
    else:                    tenure_b = 3
    tenure_enc = _safe_encode(encoders.get("tenure_bucket"), str(tenure_b))

    play_count  = urow.get("play_count") or 0
    avg_comp_u  = float(urow.get("avg_comp") or 0.5)
    active_30d  = urow.get("active_30d")  or 0
    user_play_count_log = math.log1p(play_count)
    user_30d_active     = float(active_30d)

    # 用户流派分布（优先从 play history 统计，回退到注册偏好标签）
    u_genre_dist   = res.user_stats.get("user_genre_dist",   {}).get(user_id, {})
    u_artist_dist  = res.user_stats.get("user_artist_dist",  {}).get(user_id, {})
    u_lang_dist    = res.user_stats.get("user_language_dist",{}).get(user_id, {})
    u_country_dist = res.user_stats.get("user_country_dist", {}).get(user_id, {})

    has_play_history = bool(u_genre_dist)  # 有播放历史 → 使用历史分布

    # 新用户（无播放历史）使用注册偏好标签近似分布
    if not has_play_history:
        reg_genres   = [g.strip() for g in (pref.get("preferred_genres")  or "").split(";") if g.strip()]
        reg_artists  = [a.strip() for a in (pref.get("preferred_artists") or "").split(";") if a.strip()]
        if reg_genres:
            prob = 1.0 / len(reg_genres)
            u_genre_dist  = {g: prob for g in reg_genres}
            u_lang_dist   = {g: prob for g in reg_genres}   # 语言偏好用流派近似
        if reg_artists:
            prob = 1.0 / len(reg_artists)
            u_artist_dist = {a: prob for a in reg_artists}

    # 用户流派多样性
    user_diversity = float(res.user_stats.get("user_basic", {}).get(user_id, {}).get(
        "user_genre_diversity", 0.5) if isinstance(res.user_stats.get("user_basic"), dict)
        else 0.5)

    # 用户 encoded id
    user_enc = _safe_encode(encoders.get("user_id"), str(user_id))
    # source_channel 默认 RECOMMENDATION
    src_enc = _safe_encode(encoders.get("source_channel"), "RECOMMENDATION")

    rows = []
    for sid in song_ids:
        sr = song_rows.get(sid, {})

        genre    = str(sr.get("genre")          or "unknown")
        language = str(sr.get("language")        or "unknown")
        artist   = str(sr.get("artist")         or "unknown")
        country  = str(sr.get("origin_country") or "XX")
        rel_year = sr.get("release_year") or 0
        duration = sr.get("duration") or 0
        pop      = sr.get("popularity") or 0
        # encoder 按 str(songs.id) 训练，直接用整数 ID
        song_enc = _safe_encode(encoders.get("song_id"), str(sid))
        genre_enc = _safe_encode(encoders.get("genre"), genre)
        lang_enc  = _safe_encode(encoders.get("language"), language)
        art_enc   = _safe_encode(encoders.get("artist"),   artist)
        ctry_enc  = _safe_encode(encoders.get("origin_country"), country)

        if   rel_year < 1980: yb = 0
        elif rel_year < 1990: yb = 1
        elif rel_year < 2000: yb = 2
        elif rel_year < 2010: yb = 3
        elif rel_year < 2020: yb = 4
        else:                 yb = 5
        year_enc = _safe_encode(encoders.get("year_bucket"), str(yb))

        if   duration < 90:   db_b = 0
        elif duration < 240:  db_b = 1
        elif duration < 420:  db_b = 2
        else:                 db_b = 3
        dur_enc = _safe_encode(encoders.get("duration_bucket"), str(db_b))

        # 歌曲稠密特征（从 song_stats 查询，若无则从 MySQL）
        s_stats = res.song_stats.get(res.mysql2enc.get(sid, -1), {})
        song_play_log  = float(s_stats.get("play_count_log", math.log1p(pop)))
        song_avg_comp  = float(s_stats.get("avg_completion", 0.5))
        song_pop_norm  = float(pop) / 100.0
        age_days       = max(0, (datetime.date.today().year - rel_year) * 365) if rel_year > 0 else 0
        song_age_log   = math.log1p(age_days)

        # 交互特征：用 play-history 分布匹配（新用户用注册偏好近似）
        user_genre_match    = float(u_genre_dist.get(genre,   0.0))
        user_artist_match   = float(u_artist_dist.get(artist,  0.0))
        user_language_match = float(u_lang_dist.get(language,  0.0))
        user_country_match  = float(u_country_dist.get(country, 0.5))

        row = [
            # 13 稀疏特征（严格对齐 train_deepfm_v3.py SPARSE_FEAT_SPECS 顺序）
            user_enc,    # 0: user_id
            song_enc,    # 1: song_id
            genre_enc,   # 2: genre
            lang_enc,    # 3: language
            art_enc,     # 4: artist
            ctry_enc,    # 5: origin_country
            year_enc,    # 6: year_bucket
            src_enc,     # 7: source_channel
            city_enc,    # 8: city
            gender_enc,  # 9: gender
            age_enc,     # 10: age_bucket
            tenure_enc,  # 11: tenure_bucket
            dur_enc,     # 12: duration_bucket
            # 12 稠密特征（对齐 DENSE_FEAT_SPECS 顺序）
            user_play_count_log, avg_comp_u,
            user_diversity,
            user_30d_active,
            song_play_log, song_avg_comp,
            song_pop_norm,  song_age_log,
            user_genre_match, user_artist_match,
            user_language_match, user_country_match,
        ]
        rows.append(row)

    return np.array(rows, dtype=np.float32)


def rank_with_lgbm(candidate_ids: list, X: np.ndarray, res: Resources) -> list:
    """LightGBM 打分，返回 (song_id, lgbm_score) 列表，按分降序"""
    if res.lgbm_model is None or len(candidate_ids) == 0:
        return [(sid, 0.5) for sid in candidate_ids]

    scores = res.lgbm_model.predict(X, num_iteration=res.lgbm_iter)
    ranked = sorted(zip(candidate_ids, scores.tolist()), key=lambda x: -x[1])
    return ranked


def rank_with_deepfm(candidate_ids: list, X: np.ndarray, res: Resources) -> list:
    """DeepFM 打分，返回 (song_id, deepfm_score) 列表"""
    if res.deepfm_model is None or len(candidate_ids) == 0:
        return [(sid, 0.5) for sid in candidate_ids]

    import torch
    feat_names = res.deepfm_feat_names
    X_tensor   = torch.from_numpy(X).float()

    with torch.no_grad():
        preds = res.deepfm_model(X_tensor).squeeze().cpu().numpy()

    if preds.ndim == 0:
        preds = np.array([float(preds)])

    return list(zip(candidate_ids, preds.tolist()))


# ============================================================
# 重排层 — 多样性约束
# ============================================================

def diversity_rerank(ranked: list, song_meta_map: dict,
                     max_per_artist: int = MAX_PER_ARTIST,
                     top_n: int = TOP_N) -> list:
    """同艺术家最多 max_per_artist 首，取前 top_n"""
    artist_count = {}
    result = []
    for sid, score in ranked:
        _, artist = song_meta_map.get(sid, ("", ""))
        cnt = artist_count.get(artist, 0)
        if cnt < max_per_artist:
            result.append((sid, score))
            artist_count[artist] = cnt + 1
        if len(result) >= top_n:
            break
    return result


# ============================================================
# 主推荐流程
# ============================================================

def generate_recommendations():
    db = get_db()
    try:
        # Step 1: 反馈回收
        update_feedback(db)

        # Step 2: 加载资源
        print("\n📥 [Step 2] 加载模型资源...")
        res = Resources()
        # 映射已在 Resources.__init__ 中从 song_id_map.pkl 直接加载，无需额外构建

        # 预加载所有歌曲元数据（genre, artist）用于屏蔽和多样性过滤
        with db.cursor() as cur:
            cur.execute("SELECT id, genre, artist FROM songs")
            song_meta_map = {
                r["id"]: (r["genre"] or "", r["artist"] or "")
                for r in cur.fetchall()
            }

        # Step 3: 生成推荐
        print("\n🚀 [Step 3] 生成个性化推荐...")
        with db.cursor() as cur:
            cur.execute("DELETE FROM recommendations WHERE source_type = 'deepfm'")
            cur.execute("SELECT id FROM users WHERE username IN ('jf', 'jf2')")
            users = cur.fetchall()

        today_str = datetime.date.today().strftime("%Y-%m-%d")

        for u in users:
            uid = u["id"]
            print(f"\n   处理用户 ID={uid}...")

            with db.cursor() as cur:
                # 已听过的歌
                cur.execute("SELECT song_id FROM play_history WHERE user_id = %s", (uid,))
                listened = {r["song_id"] for r in cur.fetchall()}

                # 冷却中的歌
                cur.execute("""
                    SELECT song_id FROM recommendation_feedback
                    WHERE user_id = %s AND cooldown_until > CURDATE()
                """, (uid,))
                cooled = {r["song_id"] for r in cur.fetchall()}

                exclude_set = listened | cooled

                # 屏蔽列表
                cur.execute("""
                    SELECT block_type, block_value, blocked_until, block_count, is_active
                    FROM user_content_blocks WHERE user_id = %s
                """, (uid,))
                blocks = cur.fetchall()

            blocked_genres  = set()
            blocked_artists = set()
            for b in blocks:
                if b["is_active"] == 1:
                    if b["block_type"] == "genre":
                        blocked_genres.add(b["block_value"])
                    else:
                        blocked_artists.add(b["block_value"])

            # ── 三路召回
            cand_dict = recall_candidates(
                db, uid, res, exclude_set,
                blocked_genres, blocked_artists, song_meta_map
            )
            cand_ids = list(cand_dict.keys())
            print(f"      召回候选: {len(cand_ids)} 首")

            if not cand_ids:
                print(f"      ⚠️ 无候选歌曲，跳过")
                continue

            # ── LightGBM 精排：300 → 50
            X = build_pair_features(uid, cand_ids, db, res)
            lgbm_ranked = rank_with_lgbm(cand_ids, X, res)
            top50 = lgbm_ranked[:RANK_TOP]
            top50_ids = [sid for sid, _ in top50]
            lgbm_score_map = {sid: s for sid, s in top50}
            print(f"      LightGBM 精排: top {len(top50_ids)} 首")

            # ── DeepFM 集成：50 → 25
            if top50_ids:
                X50 = build_pair_features(uid, top50_ids, db, res)
                deepfm_scored = rank_with_deepfm(top50_ids, X50, res)
                deepfm_score_map = {sid: s for sid, s in deepfm_scored}
                alpha = res.alpha
                ensemble_scored = [
                    (sid, alpha * lgbm_score_map.get(sid, 0.5)
                          + (1 - alpha) * deepfm_score_map.get(sid, 0.5))
                    for sid in top50_ids
                ]
                ensemble_scored.sort(key=lambda x: -x[1])
                top25 = ensemble_scored[:ENSEMBLE_TOP]
            else:
                top25 = top50[:ENSEMBLE_TOP]

            print(f"      集成排序: top {len(top25)} 首")

            # ── 多样性重排：25 → 20
            final_recs = diversity_rerank(top25, song_meta_map)

            # 若不足，用热度补充
            if len(final_recs) < TOP_N:
                with db.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM songs WHERE popularity > 0
                        ORDER BY popularity DESC LIMIT 200
                    """)
                    hot_ids = [r["id"] for r in cur.fetchall()]
                already = {sid for sid, _ in final_recs}
                for sid in hot_ids:
                    if sid not in exclude_set and sid not in already:
                        genre, artist = song_meta_map.get(sid, ("", ""))
                        if any(bg in genre for bg in blocked_genres):
                            continue
                        if any(ba in artist for ba in blocked_artists):
                            continue
                        final_recs.append((sid, 0.05))
                        if len(final_recs) >= TOP_N:
                            break

            print(f"      最终推荐: {len(final_recs)} 首")

            # ── 写入数据库
            with db.cursor() as cur:
                for sql_id, score in final_recs:
                    cur.execute("""
                        INSERT INTO recommendations (user_id, song_id, score)
                        VALUES (%s, %s, %s)
                    """, (uid, sql_id, round(score, 6)))
                    cur.execute("""
                        INSERT IGNORE INTO recommendation_feedback (user_id, song_id, recommend_date)
                        VALUES (%s, %s, %s)
                    """, (uid, sql_id, today_str))

        db.commit()
        print("\n✅ 全部推荐生成完成！")

    except Exception as e:
        print(f"\n❌ 推荐生成失败: {e}")
        import traceback; traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    generate_recommendations()
