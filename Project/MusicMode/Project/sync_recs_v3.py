# -*- coding: utf-8 -*-
"""
sync_recs_v3.py — 三路召回 + LightGBM粗排 + DeepFM/BST双模型精排集成

架构：
  召回层  (230万 → ~600): FAISS向量召回(200) + 个性化热度召回(200) + ALS协同过滤(200)
                          - 通道A（FAISS）：满意度感知，dissatisfied时强化偏好探索
                          - 通道B（热度）：满意度感知，动态调整流派过滤和艺术家加权
                          - 通道C（ALS）：新用户降级为注册偏好召回；dissatisfied时降权
  粗排层  (~600 → 300):   LightGBM 打分（仅粗排，不参与精排集成）
  精排层  (300 → 150):    DeepFM + BST 双模型加权融合
                          - DeepFM：特征共现交互（FM层+DNN层）
                          - BST：行为序列 Transformer（Chen et al., DLP-KDD 2019）
                          权重由离线 build_ensemble.py SLSQP 优化得出
  重排层  (150 → 50):     MMR（最大边际相关）软多样性 + 升级冷却/屏蔽过滤
                          - MMR：λ=0.7，70%相关性 + 30%多样性惩罚
                          - 升级冷却：负向交互1次→3天，2次→7天，3次+→14天冷宫
计划任务：每天凌晨 4 点运行
"""

import os
import sys
import pickle
import datetime
import math
import subprocess
import time
import atexit
import numpy as np
import pymysql
import faiss
import redis as _redis_lib

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
LGBM_MODEL_PATH    = os.path.join(MODE_DIR, "lgbm",   "lgbm_model.pkl")
DEEPFM_MODEL_PATH  = os.path.join(MODE_DIR, "deepfm", "deepfm_model.pth")
DEEPFM_CONFIG_PATH = os.path.join(MODE_DIR, "deepfm", "model_config.pkl")
BST_MODEL_PATH     = os.path.join(MODE_DIR, "bst", "bst_model.pth")
BST_CONFIG_PATH    = os.path.join(MODE_DIR, "bst", "model_config.pkl")
# 集成配置：由 build_ensemble.py 生成，保存在 ensemble 子目录下
ENSEMBLE_PATH      = os.path.join(MODE_DIR, "ensemble", "ensemble_config.pkl")
ALS_MODEL_PATH     = os.path.join(MODE_DIR, "als_model.pkl")
ENCODERS_PATH      = os.path.join(MODE_DIR, "encoders_v3.pkl")
USER_STATS_PATH    = os.path.join(MODE_DIR, "user_stats.pkl")
SONG_STATS_PATH    = os.path.join(MODE_DIR, "song_stats.pkl")
SVD_VECS_PATH      = os.path.join(MODE_DIR, "svd_vecs.pkl")   # SVD向量，供在线查找

# 推荐参数（v7 扩展漏斗：~600 → 300 → 150 → 50）
TOP_N          = 50    # v7：最终推荐数 20 → 50
RECALL_FAISS   = 200   # v7：FAISS 召回候选数 150 → 200
RECALL_HOT     = 200   # v7：热度召回候选数 100 → 200
RECALL_ALS     = 200   # v7：ALS 召回候选数 50 → 200
RANK_TOP       = 300   # v7：LightGBM 粗排保留数 50 → 300
ENSEMBLE_TOP   = 150   # v7：DeepFM+BST 精排保留数 25 → 150
MAX_PER_ARTIST = 10    # v7：MMR安全上限（从5升至10，MMR已接管多样性主逻辑）

# 满意度 → 艺术家加权分（通道B热度召回）
ARTIST_BONUS_MAP = {
    "dissatisfied":  800,   # 不满意：强调用户已知偏好艺术家
    "neutral":       500,   # 中立：保持现有逻辑
    "satisfied":     300,   # 满意：轻微探索新艺术家
    "very_satisfied": 150,  # 非常满意：鼓励系统发现新艺术家
}
ARTIST_BONUS_DEFAULT = 500  # 未评分时默认加权

# MMR 多样性参数
MMR_LAMBDA = 0.7  # 0.7×相关性 + 0.3×多样性惩罚（工业界常用起点）

# 用户画像权重（FAISS 召回用）
WEIGHTS = {
    'play_yesterday': 1.0,
    'play_7days':     0.6,
    'play_older':     0.3,
    'favorite':       0.8,
    'playlist':       0.7,
}

# Redis 配置（歌曲缓存层）
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB   = 0


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
# Redis 辅助函数（歌曲缓存层自动启停）
# ============================================================

_REDIS_PROC = None   # 记录由本进程启动的 redis-server 子进程


def _ensure_redis_running():
    """
    确保 Redis 服务运行中，返回 redis 连接。
      - 已运行（由 refresh_song_stats.py 启动并保持）→ 打印提示，注册退出时关闭
      - 未运行 → 自动启动 redis-server，注册退出时关闭
    无论哪种情况，sync_recs_v3.py 推荐完成退出时都负责关闭 Redis。
    """
    global _REDIS_PROC
    _r = _redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                          decode_responses=True, socket_connect_timeout=1)
    try:
        _r.ping()
        print("   ✅ Redis 服务已启动")
        atexit.register(_shutdown_redis)   # 推荐完成后统一关闭
        return _r, True
    except Exception:
        pass

    print("   ⏳ Redis 未运行，正在启动 redis-server ...")
    _REDIS_PROC = subprocess.Popen(
        ["redis-server", "--save", ""],   # 禁用 RDB 持久化，纯缓存模式
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):          # 最多等待 10 秒
        time.sleep(0.5)
        try:
            _r.ping()
            print("   ✅ Redis 启动成功")
            atexit.register(_shutdown_redis)
            return _r, True
        except Exception:
            pass
    raise SystemExit("❌ Redis 启动超时（10s），请检查 redis-server 是否在 PATH 中")


def _shutdown_redis():
    """推荐任务完成后关闭 Redis（统一负责，无论是否由本进程启动）"""
    global _REDIS_PROC
    try:
        _redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT,
                         socket_connect_timeout=1).shutdown(nosave=True)
        print("   ✅ Redis 服务已关闭")
    except Exception:
        # shutdown 命令本身会断开连接触发异常，属正常现象
        if _REDIS_PROC and _REDIS_PROC.poll() is None:
            _REDIS_PROC.terminate()
        print("   ✅ Redis 服务已关闭")


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
            # 将 user_basic DataFrame 转为 dict 以便 O(1) 查询
            ub = self.user_stats.get("user_basic")
            if ub is not None and hasattr(ub, "iterrows"):
                self.user_stats["user_basic"] = ub.set_index("user_id").to_dict("index")

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

        # BST（行为序列 Transformer，替换 DIN；需要 train_bst.py 中的 BSTModel）
        self.bst_model      = None
        self.bst_config     = None
        if os.path.exists(BST_CONFIG_PATH) and os.path.exists(BST_MODEL_PATH):
            try:
                import torch
                # 动态导入 train_bst 模块（与 sync_recs_v3.py 同目录）
                import importlib.util
                _bst_spec = importlib.util.spec_from_file_location(
                    "train_bst",
                    os.path.join(PROJECT_DIR, "train_bst.py")
                )
                _bst_mod = importlib.util.module_from_spec(_bst_spec)
                _bst_spec.loader.exec_module(_bst_mod)
                with open(BST_CONFIG_PATH, "rb") as f:
                    bst_cfg = pickle.load(f)
                bst_m = _bst_mod.BSTModel(
                    n_songs=bst_cfg["n_songs"],
                    n_users=bst_cfg["n_users"],
                    other_sparse_sizes=bst_cfg["other_sparse_sizes"],
                    dense_dim=bst_cfg["dense_dim"],
                    embed_dim=bst_cfg.get("embed_dim", 32),
                    seq_len=bst_cfg.get("seq_len", 50),
                    n_heads=bst_cfg.get("n_heads", 4),
                    d_model=bst_cfg.get("d_model", 64),
                    ffn_dim=bst_cfg.get("ffn_dim", 128),
                    dropout=bst_cfg.get("dropout", 0.4),
                )
                sd = torch.load(BST_MODEL_PATH, map_location='cpu', weights_only=True)
                bst_m.load_state_dict(sd)
                bst_m.eval()
                self.bst_model  = bst_m
                self.bst_config = bst_cfg
                self._bst_mod   = _bst_mod   # 保留模块引用，供 rank_with_bst 使用
                print(f"   ✅ BST 加载（val_AUC={bst_cfg.get('best_val_auc', 0):.4f}）")
            except Exception as e:
                print(f"   ⚠️ BST 加载失败（{e}），精排仅使用 DeepFM")

        # 双模型集成权重（DeepFM + BST，由 build_ensemble.py 离线训练）
        # LightGBM 仅参与粗排（300→50），不参与精排集成
        self.w_deepfm = 0.5
        self.w_bst    = 0.5
        if os.path.exists(ENSEMBLE_PATH):
            with open(ENSEMBLE_PATH, "rb") as f:
                ec = pickle.load(f)
            bw = ec.get("best_weights", {})
            raw_deepfm = bw.get("DeepFM", 0.0)
            raw_bst    = bw.get("BST",    0.0)
            total = raw_deepfm + raw_bst
            if total > 0:
                self.w_deepfm = raw_deepfm / total
                self.w_bst    = raw_bst    / total
            print(
                f"   ✅ 集成权重（精排）: DeepFM={self.w_deepfm:.3f}, BST={self.w_bst:.3f}"
                f"（集成 AUC={ec.get('best_overall_auc', 0):.4f}）"
            )

        # ALS
        self.als_model = None
        if os.path.exists(ALS_MODEL_PATH):
            with open(ALS_MODEL_PATH, "rb") as f:
                self.als_model = pickle.load(f)
            print("   ✅ ALS 模型加载")

        # SVD 向量（由 prepare_features_v3.py 的 save_outputs 生成）
        # 用于在线推断时为 user/song 查找 SVD 嵌入特征，避免在线重新拟合
        self.svd_vecs: dict = {"user": {}, "song": {}}
        if os.path.exists(SVD_VECS_PATH):
            with open(SVD_VECS_PATH, "rb") as f:
                self.svd_vecs = pickle.load(f)
            n_u = len(self.svd_vecs.get("user", {}))
            n_s = len(self.svd_vecs.get("song", {}))
            print(f"   ✅ SVD 向量加载：{n_u:,} 用户 / {n_s:,} 歌曲")
        else:
            print("   ⚠️ svd_vecs.pkl 不存在，SVD 特征将补零（需先运行 prepare_features_v3.py）")

        # 歌曲滚动窗口特征缓存 + 热度缓存（Redis + MySQL 双层架构）
        # 读取顺序：Redis（亚毫秒）→ 新鲜度不一致则终止，要求先运行 refresh_song_stats.py
        # 格式：
        #   self.song_rolling: {song_id: {"log_7d": float, "log_30d": float, "trending": float}}
        #   self.hot_cache:    {song_id: total_plays}（取 total_plays 最高的 10000 首）
        self.song_rolling: dict[int, dict] = {}
        self.hot_cache: dict[int, int] = {}

        # ── Step 1: 查 MySQL 权威时间戳
        _ts_conn = pymysql.connect(
            host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD,
            db=MYSQL_DB, charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor, connect_timeout=30,
        )
        with _ts_conn.cursor() as _cur:
            _cur.execute("SELECT MAX(updated_at) FROM song_rolling_stats")
            _row = _cur.fetchone()
        _ts_conn.close()
        _mysql_ts = str(_row[0]) if _row and _row[0] else None

        if not _mysql_ts:
            raise SystemExit(
                "\n❌ song_rolling_stats 表为空或不存在\n"
                "   请先运行: python refresh_song_stats.py\n"
            )

        # ── Step 2: 确保 Redis 运行（自动启动或检测已有实例）
        _redis, _ = _ensure_redis_running()
        self.redis_conn = _redis   # 供用户级缓存（pref/sati/faiss）复用

        # ── Step 3: 新鲜度验证（Redis version == MySQL updated_at）
        _redis_ts = _redis.get("song_rolling:version") or ""
        if _redis_ts != _mysql_ts:
            raise SystemExit(
                "\n❌ Redis 缓存已过期，与 MySQL 数据不一致\n"
                f"   Redis 版本: {_redis_ts or '（无）'}\n"
                f"   MySQL 版本: {_mysql_ts}\n"
                "   请运行: python refresh_song_stats.py\n"
                "   刷新完成后重新启动推荐系统\n"
            )

        # ── Step 4: 从 Redis 批量读取（pipeline，亚毫秒级）
        _keys = _redis.keys("song_rolling:[0-9]*")
        _pipe  = _redis.pipeline(transaction=False)
        for _k in _keys:
            _pipe.hgetall(_k)
        _hot_raw: dict[int, int] = {}
        for _k, _vals in zip(_keys, _pipe.execute()):
            _sid = int(_k.split(":")[1])
            self.song_rolling[_sid] = {
                "log_7d":   math.log1p(int(_vals.get("c7",  0))),
                "log_30d":  math.log1p(int(_vals.get("c30", 0))),
                "trending": float(_vals.get("tr", 1.0)),
            }
            _hot_raw[_sid] = int(_vals.get("tp", 0))

        self.hot_cache = dict(
            sorted(_hot_raw.items(), key=lambda x: x[1], reverse=True)[:10000]
        )
        print(f"   ✅ 歌曲缓存加载（Redis，已验证最新）：{len(self.song_rolling):,} 首"
              f" | 热度 Top-{len(self.hot_cache):,}")

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
            # 衰减窗口：14天前的历史评分每次执行时乘以 0.9
            decay_before = (datetime.date.today() - datetime.timedelta(days=14)).strftime("%Y-%m-%d")

            # ── Step 0：feedback_score 时间衰减（v7新增）
            # 问题：历史负分永久累积，导致老歌永久被压制（即使用户口味已变）
            # 解决：超过14天的记录乘以0.9衰减系数，每日执行一次
            # 效果示例：-2.0分在140天后 → -2.0 × 0.9^10 ≈ -0.70（逐步趋近0）
            cur.execute("""
                UPDATE recommendation_feedback
                SET feedback_score = feedback_score * 0.9
                WHERE recommend_date < %s
                  AND ABS(feedback_score) > 0.01
            """, (decay_before,))
            # 清零极小值，减少后续计算干扰
            cur.execute("""
                UPDATE recommendation_feedback
                SET feedback_score = 0
                WHERE recommend_date < %s
                  AND ABS(feedback_score) <= 0.01
            """, (decay_before,))
            print(f"   0 feedback_score 时间衰减（14天窗口）完成")

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

            # C: 计算行为评分 + 负向交互计数（v7：新增 negative_count 字段追踪）
            # 负向交互定义：推荐后不播放 / 只听一点点(comp<0.2) / 半途而废(0.2≤comp<0.8)
            cur.execute("""
                SELECT id, user_id, song_id, was_played, play_completion, was_favorited,
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

            update_data = []       # [(score_delta, new_ignore, cooldown, is_negative, user_id, song_id, id)]
            for fb in feedbacks:
                uid         = fb["user_id"]
                sid         = fb["song_id"]
                was_played  = fb["was_played"]
                comp        = fb["play_completion"] or 0.0
                was_fav     = fb["was_favorited"]
                ignore_days = fb["consecutive_ignore_days"] or 0
                score_delta = 0.0
                cooldown    = None
                new_ignore  = ignore_days
                is_negative = False   # 是否为负向交互，用于 negative_count 累计

                if uid in active_users:
                    if was_played == 0:
                        # 推荐后不播放：负向交互
                        score_delta -= 0.1
                        new_ignore  += 1
                        is_negative  = True
                        if new_ignore >= 3:
                            cooldown    = (datetime.date.today() + datetime.timedelta(days=14)).strftime("%Y-%m-%d")
                            score_delta -= 0.5
                    else:
                        new_ignore = 0
                        if comp > 0.8:
                            score_delta += 0.5          # 高完播率：正向
                        elif comp >= 0.2:
                            # 半途而废：弱正向评分但记为负向交互（用于冷却升级）
                            score_delta += 0.3
                            is_negative  = True
                        else:
                            # 只听一点点（<20%）：负向
                            score_delta -= 0.3
                            is_negative  = True
                    if was_fav:
                        score_delta += 1.0

                update_data.append((score_delta, new_ignore, cooldown, is_negative, uid, sid, fb["id"]))

            for score_delta, new_ignore, cooldown, is_negative, uid, sid, fid in update_data:
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

                # v7：负向交互时累增 negative_count（该字段需提前执行数据库迁移）
                # ALTER TABLE recommendation_feedback ADD COLUMN negative_count INT DEFAULT 0
                if is_negative:
                    try:
                        cur.execute("""
                            UPDATE recommendation_feedback
                            SET negative_count = negative_count + 1
                            WHERE user_id = %s AND song_id = %s
                        """, (uid, sid))
                    except Exception:
                        pass   # 字段不存在时静默忽略（兼容迁移前环境）

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
    """
    生成用户 FAISS 画像向量。
    优先从 Redis 缓存读取（TTL=30min），命中则直接返回，避免全量播放历史重算。
    新播放产生时由 PlayHistoryServlet 删除 user:faiss:{user_id} 以主动失效。
    """
    import base64
    _redis = getattr(res, "redis_conn", None)
    _faiss_key = f"user:faiss:{user_id}"

    # 尝试命中 Redis FAISS 向量缓存（TTL=30分钟）
    if _redis is not None:
        try:
            _cached = _redis.get(_faiss_key)
            if _cached:
                _arr = np.frombuffer(base64.b64decode(_cached), dtype=np.float32)
                return _arr.reshape(1, -1)
        except Exception:
            pass

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
        # 满意度调整系数（优先从 Redis 缓存读取，避免重复查 DB）
        sati = _get_user_sati(db, user_id, _redis)
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
    profile_vec = profile.reshape(1, -1)

    # 写入 Redis FAISS 向量缓存（TTL=30分钟）
    # 新播放产生时，PlayHistoryServlet 应删除 user:faiss:{user_id} 以主动失效
    if _redis is not None:
        try:
            _redis.setex(
                _faiss_key, 1800,
                base64.b64encode(profile_vec.tobytes()).decode()
            )
        except Exception:
            pass
    return profile_vec


def recall_candidates(db, user_id, res: Resources,
                       exclude_set, blocked_genres, blocked_artists,
                       song_meta_map) -> tuple:
    """
    三路召回，返回 (candidates, realtime_dists) 元组。

    candidates:     {song_id: score} 候选字典
    realtime_dists: Tier 2 用户的实时分布 dict（Tier 3/1 时为 {}），
                    包含 "artist"/"genre"/"lang" 三个子 dict，
                    供 build_pair_features 覆盖历史统计分布。
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

    # ── 通道B: 个性化热度召回（v7：加入满意度感知）
    # hot_cache 覆盖 360,178 首歌（songs.popularity > 0 仅 23,632 首，15× 扩展）
    # 满意度影响：① genre_filter 策略（dissatisfied/neutral 用全部流派，more inclusive）
    #             ② 偏好艺术家加权分（dissatisfied 时 +800，very_satisfied 时 +150）
    _redis_b   = getattr(res, "redis_conn", None)
    # 满意度和偏好均优先从 Redis 缓存读取，命中率 > 90% 后可消除 2 次 DB 查询
    hot_sati   = _get_user_sati(db, user_id, _redis_b)
    pref_b     = _get_user_pref(db, user_id, _redis_b)

    # 根据满意度决定流派过滤策略
    # dissatisfied/neutral → 使用所有 preferred_genres（OR 匹配，扩大覆盖）
    # satisfied/未评分     → 只用第一个流派（现有逻辑，精准过滤）
    # very_satisfied       → 不做流派过滤（广撒网，探索新领域）
    preferred_genres_list = []
    if pref_b and pref_b.get("preferred_genres"):
        preferred_genres_list = [g.strip() for g in pref_b["preferred_genres"].split(";") if g.strip()]

    if hot_sati == "very_satisfied":
        # 不做流派限制，鼓励探索
        hot_genre_filters: list = []
    elif hot_sati in ("dissatisfied", "neutral"):
        # 用全部偏好流派（OR 逻辑），提高召回覆盖面
        hot_genre_filters = preferred_genres_list
    else:
        # satisfied 或未评分：只用第一个流派（保持原有精准过滤）
        hot_genre_filters = preferred_genres_list[:1]

    # 满意度影响偏好艺术家加权分
    artist_bonus = ARTIST_BONUS_MAP.get(hot_sati, ARTIST_BONUS_DEFAULT)

    # 获取用户偏好艺术家（top-20），来源：user_stats.pkl 历史播放分布
    user_fav_artists: set = set()
    user_stats_entry = res.user_stats.get("user_basic", {}).get(user_id, {})
    _artist_dist = user_stats_entry.get("user_artist_dist", {})
    if isinstance(_artist_dist, dict):
        top_artists = sorted(_artist_dist.items(), key=lambda x: -x[1])[:20]
        user_fav_artists = {a for a, _ in top_artists}

    if res.hot_cache:
        # 按满意度动态加权排序：偏好艺术家 + artist_bonus
        hot_sorted = sorted(
            res.hot_cache.items(),
            key=lambda kv: kv[1] + (
                artist_bonus if song_meta_map.get(kv[0], ("", ""))[1] in user_fav_artists else 0
            ),
            reverse=True,
        )
        _added_hot = 0
        for sid, _cnt in hot_sorted:
            if _added_hot >= RECALL_HOT:
                break
            if sid in exclude_set or sid in candidates:
                continue
            genre, artist = song_meta_map.get(sid, ("", ""))
            # 流派过滤：hot_genre_filters 为空则不过滤（very_satisfied）
            if hot_genre_filters and not any(gf in genre for gf in hot_genre_filters):
                continue
            if any(bg in genre for bg in blocked_genres):
                continue
            if any(ba in artist for ba in blocked_artists):
                continue
            candidates[sid] = 0.05   # 低基础分，靠精排提升
            _added_hot += 1
    else:
        # 回退：songs.popularity（hot_cache 加载失败时兜底）
        with db.cursor() as cur:
            if hot_genre_filters:
                # 多流派 OR 条件拼接（PreparedStatement 参数化防注入）
                _like_conds = " OR ".join(["genre LIKE %s"] * len(hot_genre_filters))
                _like_vals  = [f"%{g}%" for g in hot_genre_filters]
                cur.execute(
                    f"SELECT id FROM songs WHERE ({_like_conds}) AND popularity > 0"
                    f" ORDER BY popularity DESC LIMIT %s",
                    _like_vals + [RECALL_HOT]
                )
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
                    candidates[sid] = 0.05

    # ── 通道C: 三层分层路由
    # Tier 3（ALS）  : 在 ALS 训练集中，且训练时有效播放 ≥ 10 首
    # Tier 2（内容）  : 非训练集用户，但有足量行为数据（歌单 ≥5首 OR 质量播放 ≥10次）
    # Tier 1（冷启动）: 无足量行为数据的新用户，基于注册偏好召回
    realtime_dists: dict = {}   # Tier 2 实时分布，传递给排序层的 build_pair_features

    # ── 第一步：Tier 3 判断（ALS 训练集 + 训练播放量二次校验）
    # P2 修复：训练播放量 < 10 时降级，避免0播放用户被误判为 Tier 3
    user_enc = None
    if res.als_model is not None:
        user_enc_map = res.user_stats.get("_uid_map", {})
        if user_id in user_enc_map:
            _uid_basic = (res.user_stats.get("user_basic", {})
                          if isinstance(res.user_stats.get("user_basic"), dict) else {})
            _train_cnt = int((_uid_basic.get(user_id) or {}).get("play_count", 0))
            if _train_cnt >= 10:
                user_enc = user_enc_map[user_id]
            else:
                print(f"      ℹ️ 用户 {user_id} 在训练集但播放量不足({_train_cnt}次)，降级至 Tier2/1")

    # ── 第二步：Tier 2/1 判断（仅当 user_enc is None 时触发）
    user_tier = 3 if user_enc is not None else 0
    if user_tier == 0:
        with db.cursor() as cur:
            # 歌单歌曲总数
            cur.execute("""
                SELECT COUNT(ps.id) AS pl_cnt
                FROM playlist_songs ps
                JOIN user_playlists up ON ps.playlist_id = up.id
                WHERE up.user_id = %s
            """, (user_id,))
            pl_cnt = int((cur.fetchone() or {}).get("pl_cnt", 0))
            # 质量播放次数（完播率 ≥ 30%）
            cur.execute("""
                SELECT COUNT(*) AS q_cnt
                FROM play_history ph
                JOIN songs s ON s.id = ph.song_id
                WHERE ph.user_id = %s
                  AND s.duration > 0
                  AND ph.play_duration / s.duration >= 0.3
            """, (user_id,))
            q_cnt = int((cur.fetchone() or {}).get("q_cnt", 0))
        if pl_cnt >= 5 or q_cnt >= 10:
            user_tier = 2
            print(f"      ℹ️ Tier 2 用户（歌单{pl_cnt}首 / 质量播放{q_cnt}次）")
        else:
            user_tier = 1
            print(f"      ℹ️ Tier 1 冷启动（歌单{pl_cnt}首 / 质量播放{q_cnt}次）")

    # als_sati 已在通道B中读取为 hot_sati（同一用户同一轮次，复用）
    als_dissatisfied = (hot_sati == "dissatisfied")

    if user_tier == 3 and res.als_model is not None:
        # ── Tier 3：ALS 协同过滤召回（dissatisfied 时降权）
        try:
            als = res.als_model
            als_score_factor = 0.07 if als_dissatisfied else 0.1
            if isinstance(als, dict) and als.get("type") == "simple_als":
                uf  = als["user_factors"]
                itf = als["item_factors"]
                if user_enc < len(uf):
                    scores  = uf[user_enc] @ itf.T
                    top_idx = np.argsort(-scores)[:RECALL_ALS + 20]
                    count   = 0
                    for enc_id in top_idx:
                        sql_id = res.faiss2mysql.get(enc_id)
                        if sql_id and sql_id not in exclude_set and sql_id not in candidates:
                            genre, artist = song_meta_map.get(sql_id, ("", ""))
                            if any(bg in genre for bg in blocked_genres):
                                continue
                            if any(ba in artist for ba in blocked_artists):
                                continue
                            candidates[sql_id] = float(scores[enc_id]) * als_score_factor
                            count += 1
                            if count >= RECALL_ALS:
                                break
            else:
                # implicit ALS
                from scipy.sparse import csr_matrix
                dummy_mat = csr_matrix((1, 1))
                ids, sc = als.recommend(
                    user_enc, dummy_mat[0], N=RECALL_ALS, filter_already_liked_items=True
                )
                for enc_id, sc_val in zip(ids.tolist(), sc.tolist()):
                    sql_id = res.faiss2mysql.get(enc_id)
                    if sql_id and sql_id not in exclude_set and sql_id not in candidates:
                        candidates[sql_id] = float(sc_val) * als_score_factor
        except Exception as e:
            print(f"      ⚠️ ALS 召回失败: {e}")

    elif user_tier == 2:
        # ── Tier 2：多信号多维度加权召回
        # 信号来源：歌单（权重0.6）+ 质量播放（完播≥30%，权重0.4）
        # 维度分配：艺术家35% / 流派40% / 语种25%
        print(f"      ℹ️ 通道C：Tier2 多维度内容召回")
        try:
            artist_w: dict = {}
            genre_w:  dict = {}
            lang_w:   dict = {}

            with db.cursor() as cur:
                # 歌单信号（权重 0.6）
                cur.execute("""
                    SELECT s.artist, s.genre, s.language
                    FROM playlist_songs ps
                    JOIN user_playlists up ON ps.playlist_id = up.id
                    JOIN songs s ON s.id = ps.song_id
                    WHERE up.user_id = %s
                """, (user_id,))
                for r in cur.fetchall():
                    if r.get("artist"):
                        artist_w[r["artist"]] = artist_w.get(r["artist"], 0) + 0.6
                    if r.get("genre"):
                        genre_w[r["genre"]]   = genre_w.get(r["genre"],   0) + 0.6
                    if r.get("language"):
                        lang_w[r["language"]] = lang_w.get(r["language"], 0) + 0.6

                # 质量播放信号（完播率 ≥ 30%，权重 0.4）
                cur.execute("""
                    SELECT s.artist, s.genre, s.language
                    FROM play_history ph
                    JOIN songs s ON s.id = ph.song_id
                    WHERE ph.user_id = %s
                      AND s.duration > 0
                      AND ph.play_duration / s.duration >= 0.3
                """, (user_id,))
                for r in cur.fetchall():
                    if r.get("artist"):
                        artist_w[r["artist"]] = artist_w.get(r["artist"], 0) + 0.4
                    if r.get("genre"):
                        genre_w[r["genre"]]   = genre_w.get(r["genre"],   0) + 0.4
                    if r.get("language"):
                        lang_w[r["language"]] = lang_w.get(r["language"], 0) + 0.4

            def _norm(d):
                """归一化权重字典为概率分布"""
                total = sum(d.values()) or 1.0
                return {k: v / total for k, v in d.items()}

            realtime_dists = {
                "artist": _norm(artist_w),
                "genre":  _norm(genre_w),
                "lang":   _norm(lang_w),
            }

            # 按权重取 Top 艺术家/流派/语种，分配召回配额
            top_artists = sorted(artist_w.items(), key=lambda x: -x[1])[:5]
            top_genres  = sorted(genre_w.items(),  key=lambda x: -x[1])[:3]
            top_langs   = sorted(lang_w.items(),   key=lambda x: -x[1])[:3]

            per_artist = max(1, int(RECALL_ALS * 0.35 / max(1, len(top_artists))))
            per_genre  = max(1, int(RECALL_ALS * 0.40 / max(1, len(top_genres))))
            per_lang   = max(1, int(RECALL_ALS * 0.25 / max(1, len(top_langs))))

            with db.cursor() as cur:
                for artist, aw in top_artists:
                    cur.execute("""
                        SELECT id FROM songs WHERE artist LIKE %s
                        ORDER BY popularity DESC LIMIT %s
                    """, (f"%{artist}%", per_artist))
                    for row in cur.fetchall():
                        sid = row["id"]
                        if sid in exclude_set or sid in candidates:
                            continue
                        g, a = song_meta_map.get(sid, ("", ""))
                        if any(bg in g for bg in blocked_genres):
                            continue
                        if any(ba in a for ba in blocked_artists):
                            continue
                        candidates[sid] = aw * 0.05

                for genre_tok, gw in top_genres:
                    cur.execute("""
                        SELECT id FROM songs WHERE genre LIKE %s
                        ORDER BY popularity DESC LIMIT %s
                    """, (f"%{genre_tok}%", per_genre))
                    for row in cur.fetchall():
                        sid = row["id"]
                        if sid in exclude_set or sid in candidates:
                            continue
                        g, a = song_meta_map.get(sid, ("", ""))
                        if any(bg in g for bg in blocked_genres):
                            continue
                        if any(ba in a for ba in blocked_artists):
                            continue
                        candidates[sid] = gw * 0.04

                for lang, lw in top_langs:
                    cur.execute("""
                        SELECT id FROM songs WHERE language = %s
                        ORDER BY popularity DESC LIMIT %s
                    """, (lang, per_lang))
                    for row in cur.fetchall():
                        sid = row["id"]
                        if sid in exclude_set or sid in candidates:
                            continue
                        g, a = song_meta_map.get(sid, ("", ""))
                        if any(bg in g for bg in blocked_genres):
                            continue
                        if any(ba in a for ba in blocked_artists):
                            continue
                        candidates[sid] = lw * 0.03

        except Exception as e:
            print(f"      ⚠️ Tier2 多维度召回失败，降级为 Tier1: {e}")
            user_tier = 1   # 降级到注册偏好冷启动

    if user_tier == 1:
        # ── Tier 1/降级：注册偏好冷启动
        print(f"      ℹ️ 通道C：Tier1 冷启动，改用注册偏好内容召回")
        try:
            # 偏好从 Redis 缓存读取（通道B中已写入，基本命中）
            pref_c    = _get_user_pref(db, user_id, getattr(res, "redis_conn", None))
            reg_artists = [
                a.strip() for a in (pref_c.get("preferred_artists") or "").split(";")
                if a.strip()
            ]
            reg_genres = [
                g.strip() for g in (pref_c.get("preferred_genres") or "").split(";")
                if g.strip()
            ]

            half_als = RECALL_ALS // 2
            with db.cursor() as cur:
                # ① 注册艺术家的热门歌曲（前 half_als 首）
                for artist in reg_artists[:5]:
                    cur.execute("""
                        SELECT id FROM songs WHERE artist LIKE %s
                        ORDER BY popularity DESC LIMIT %s
                    """, (f"%{artist}%", max(1, half_als // max(1, len(reg_artists[:5])))))
                    for row in cur.fetchall():
                        sid = row["id"]
                        if sid not in exclude_set and sid not in candidates:
                            g, a = song_meta_map.get(sid, ("", ""))
                            if any(bg in g for bg in blocked_genres): continue
                            if any(ba in a for ba in blocked_artists): continue
                            candidates[sid] = 0.03

                # ② 注册流派的热门歌曲（补足至 RECALL_ALS）
                for genre_token in reg_genres[:3]:
                    cur.execute("""
                        SELECT id FROM songs WHERE genre LIKE %s
                        ORDER BY popularity DESC LIMIT %s
                    """, (f"%{genre_token}%",
                          max(1, (RECALL_ALS - half_als) // max(1, len(reg_genres[:3])))))
                    for row in cur.fetchall():
                        sid = row["id"]
                        if sid not in exclude_set and sid not in candidates:
                            g, a = song_meta_map.get(sid, ("", ""))
                            if any(bg in g for bg in blocked_genres): continue
                            if any(ba in a for ba in blocked_artists): continue
                            candidates[sid] = 0.03
        except Exception as e:
            print(f"      ⚠️ 通道C冷启动召回失败: {e}")

    return candidates, realtime_dists


# ============================================================
# 精排层 — 特征构建 + LightGBM 打分
# ============================================================

def _safe_encode(encoder, value, default=0):
    try:
        return int(encoder.transform([str(value)])[0])
    except Exception:
        return default


def _get_user_pref(db, user_id, redis_conn):
    """
    获取用户注册偏好（preferred_genres / preferred_artists）。
    优先从 Redis Hash 缓存读取（TTL=24h），未命中则查 MySQL 并回填缓存。
    用户修改偏好时，外部需删除 user:pref:{user_id} 以主动失效。

    Args:
        db: pymysql 连接（DictCursor）
        user_id: MySQL users.id
        redis_conn: redis.Redis 实例，或 None（禁用缓存）

    Returns:
        dict: {"preferred_genres": "...", "preferred_artists": "..."}
    """
    cache_key = f"user:pref:{user_id}"
    if redis_conn is not None:
        try:
            cached = redis_conn.hgetall(cache_key)
            if cached:
                return cached
        except Exception:
            pass

    with db.cursor() as cur:
        cur.execute(
            "SELECT preferred_genres, preferred_artists FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone() or {}

    if redis_conn is not None:
        try:
            redis_conn.hset(cache_key, mapping={
                "preferred_genres":  row.get("preferred_genres")  or "",
                "preferred_artists": row.get("preferred_artists") or "",
            })
            redis_conn.expire(cache_key, 86400)   # TTL = 24h
        except Exception:
            pass
    return row


def _get_user_sati(db, user_id, redis_conn):
    """
    获取用户最新满意度评分字符串（satisfied / neutral 等）。
    优先从 Redis String 缓存读取（TTL=2h），未命中则查 MySQL 并回填缓存。
    满意度变化频率低，2h TTL 对推荐质量影响极小。

    Args:
        db: pymysql 连接（DictCursor）
        user_id: MySQL users.id
        redis_conn: redis.Redis 实例，或 None（禁用缓存）

    Returns:
        str 或 None
    """
    cache_key = f"user:sati:{user_id}"
    if redis_conn is not None:
        try:
            val = redis_conn.get(cache_key)
            if val is not None:
                return val if val != "__none__" else None
        except Exception:
            pass

    with db.cursor() as cur:
        cur.execute("""
            SELECT satisfaction FROM user_preference_feedback
            WHERE user_id = %s ORDER BY feedback_date DESC LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
    sati = row["satisfaction"] if row else None

    if redis_conn is not None:
        try:
            redis_conn.setex(cache_key, 7200, sati if sati is not None else "__none__")
        except Exception:
            pass
    return sati


def build_pair_features(user_id, song_ids, db, res: Resources, realtime_dists=None):
    """
    为 (user_id, song_ids[]) 构建特征矩阵 shape (len(song_ids), 66)。

    Args:
        realtime_dists: Tier 2 用户的实时分布 dict，包含 "artist"/"genre"/"lang" 三个子 dict。
            当非 None 时，用实时分布覆盖 user_stats.pkl 中的历史分布，
            使 user_artist_match 等特征对 Tier 2 用户更准确。

    列布局（严格对齐 train_deepfm_v3.py SPARSE_FEAT_SPECS + DENSE_FEAT_SPECS）：
      稀疏（14列，0-13）:
        0=user_id, 1=song_id, 2=genre, 3=language, 4=artist,
        5=origin_country, 6=year_bucket, 7=source_channel,
        8=city, 9=gender, 10=age_bucket, 11=tenure_bucket,
        12=duration_bucket, 13=user_peak_hour
      稠密（52列，14-65，与 train_lgbm.py DENSE_FEATURES 顺序完全一致）:
        14=user_play_count_log, 15=user_avg_completion,
        16=user_genre_diversity, 17=user_30d_active_days,
        18=song_play_count_log, 19=song_avg_completion,
        20=song_popularity_norm, 21=song_age_days_log,
        22=song_target_rate, 23=user_artist_match,
        24=user_skip_rate, 25=song_skip_rate,
        26=hour_match, 27=dow_match,
        28=days_since_artist_log, 29=days_since_last_play_log,
        30=user_has_in_playlist, 31=user_playlist_artist_count_log,
        32=user_song_prev_play_days, 33=user_song_play_count_before,
        34=user_7d_play_count_log, 35=user_30d_play_count_log,
        36=user_7d_avg_completion,
        37=song_7d_play_count_log, 38=song_30d_play_count_log,
        39=song_trending_ratio,
        40-49=svd_user_song_0..9, 50-59=svd_song_user_0..9,
        60-64=svd_user_artist_0..4, 65=svd_dot_score
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

        # 用户偏好标签（优先从 Redis 缓存读取，避免重复查询 DB）
        pref = _get_user_pref(db, user_id, getattr(res, "redis_conn", None))

        # 查询候选歌曲信息
        if not song_ids:
            return np.zeros((0, 66), dtype=np.float32)
        fmt = ",".join(["%s"] * len(song_ids))
        cur.execute(f"""
            SELECT s.id, s.genre, s.language, s.artist, s.origin_country,
                   s.release_year, s.duration, s.popularity, s.kkbox_id
            FROM songs s WHERE s.id IN ({fmt})
        """, song_ids)
        song_rows = {r["id"]: r for r in cur.fetchall()}

        # ── 新增：用户播放历史时序数据（用于 skip_rate, days_since, peak_hour）
        cur.execute("""
            SELECT ph.song_id, ph.play_time,
                   CASE WHEN s.duration > 0 THEN LEAST(1.0, ph.play_duration/s.duration) ELSE 0.5 END AS comp,
                   s.artist
            FROM play_history ph
            LEFT JOIN songs s ON s.id = ph.song_id
            WHERE ph.user_id = %s
        """, (user_id,))
        user_history = cur.fetchall()

        # ── 新增：用户歌单歌曲集合
        cur.execute("""
            SELECT ps.song_id, s.artist
            FROM playlist_songs ps
            JOIN user_playlists up ON ps.playlist_id = up.id
            LEFT JOIN songs s ON s.id = ps.song_id
            WHERE up.user_id = %s
        """, (user_id,))
        pl_rows = cur.fetchall()

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

    # Tier 2 用户：若传入实时分布，则覆盖历史统计分布
    # 原因：Tier 2 用户不在 user_stats.pkl 训练集中，实时计算的分布比冷启动近似更准确
    if realtime_dists:
        u_artist_dist = realtime_dists.get("artist", u_artist_dist)
        u_genre_dist  = realtime_dists.get("genre",  u_genre_dist)
        u_lang_dist   = realtime_dists.get("lang",   u_lang_dist)

    # 用户流派多样性 & 跳过率 & 活跃统计（从 user_stats.pkl 预计算值查找）
    _u_basic = res.user_stats.get("user_basic", {}).get(user_id, {}) if isinstance(res.user_stats.get("user_basic"), dict) else {}
    user_diversity        = float(_u_basic.get("user_genre_diversity", 0.5))
    user_peak_hour_v      = int(_u_basic.get("user_peak_hour", 0))
    user_skip_rate        = float(_u_basic.get("user_skip_rate", 0.2))
    # user_30d_active_days：优先从 pkl 取（离线精准统计），fallback 到 MySQL 实时查询值
    user_30d_active_days  = float(_u_basic.get("user_30d_active_days", float(active_30d)))

    # 用户 encoded id
    user_enc = _safe_encode(encoders.get("user_id"), str(user_id))
    user_peak_enc = _safe_encode(encoders.get("user_peak_hour"), str(user_peak_hour_v))

    # Tier 2 用户：从 realtime_dists["genre"] 实时计算香农熵，替代 pkl 默认值 0.5
    # 无需额外 SQL，realtime_dists 在 recall_candidates 中已计算好
    if realtime_dists and realtime_dists.get("genre"):
        _gp = list(realtime_dists["genre"].values())
        user_diversity = float(-sum(p * math.log(p + 1e-9) for p in _gp if p > 0))

    # Tier 2 用户：从 user_history 统计播放高峰时段，替代 pkl 默认值 0
    # user_history 在本函数已查出，此处直接复用，无额外 SQL
    if realtime_dists and user_history:
        _hcnt: dict = {}
        for _r in user_history:
            _pt = _r.get("play_time")
            if _pt and hasattr(_pt, "hour"):
                _hcnt[_pt.hour] = _hcnt.get(_pt.hour, 0) + 1
        if _hcnt:
            user_peak_hour_v = max(_hcnt, key=_hcnt.get)
            user_peak_enc = _safe_encode(
                encoders.get("user_peak_hour"), str(user_peak_hour_v)
            )

    # source_channel 默认 RECOMMENDATION
    src_enc = _safe_encode(encoders.get("source_channel"), "RECOMMENDATION")

    # ── 新增：从播放历史计算时序/跳过/最近交互特征
    today_date = datetime.date.today()
    now_hour   = datetime.datetime.now().hour
    now_dow    = datetime.datetime.now().weekday()   # 0=Monday

    # 用户 top-3 收听时段 & 星期
    _top3_hours = res.user_stats.get("user_top3_hours", {}).get(user_id, set())
    _top3_dows  = res.user_stats.get("user_top3_dows",  {}).get(user_id, set())
    hour_match_v = 1.0 if now_hour in _top3_hours else 0.0
    dow_match_v  = 1.0 if now_dow  in _top3_dows  else 0.0

    # 用户跳过率（从 user_history 实时计算，若无则用 user_stats 中预计算值）
    if user_history:
        skip_count = sum(1 for r in user_history if (r.get("comp") or 0.5) < 0.10)
        user_skip_rate = skip_count / len(user_history)

    # 最近播放该歌 / 该艺术家 的时间（days, log1p）
    # song_last_play:  {song_id: last_play_date}
    # song_play_count: {song_id: total_play_count}（用于 user_song_play_count_before）
    song_last_play:  dict[int, datetime.date] = {}
    song_play_count: dict[int, int]           = {}
    artist_last_play: dict[str, datetime.date] = {}
    for row in user_history:
        sid_h = row.get("song_id")
        pt    = row.get("play_time")
        art_h = str(row.get("artist") or "")
        if pt is None:
            continue
        d = pt.date() if hasattr(pt, "date") else pt
        if sid_h:
            song_play_count[sid_h] = song_play_count.get(sid_h, 0) + 1
            if sid_h not in song_last_play or d > song_last_play[sid_h]:
                song_last_play[sid_h] = d
        if art_h and (art_h not in artist_last_play or d > artist_last_play[art_h]):
            artist_last_play[art_h] = d

    # ── 用户滚动窗口特征（从 user_history 在线计算，与训练时 closed="left" 语义等价）
    # 在线时"截止当前"，等效于训练时对目标行之前的记录聚合
    cutoff_7d  = today_date - datetime.timedelta(days=7)
    cutoff_30d = today_date - datetime.timedelta(days=30)
    hist_7d  = [r for r in user_history
                if r.get("play_time") and r["play_time"].date() >= cutoff_7d]
    hist_30d = [r for r in user_history
                if r.get("play_time") and r["play_time"].date() >= cutoff_30d]
    user_7d_play_count_log  = math.log1p(len(hist_7d))
    user_30d_play_count_log = math.log1p(len(hist_30d))
    user_7d_avg_completion  = (
        float(sum(r.get("comp") or 0.5 for r in hist_7d) / len(hist_7d))
        if hist_7d else 0.5
    )

    # 用户歌单歌曲集合 & 艺术家计数
    pl_song_set: set[int] = set()
    pl_artist_cnt: dict[str, int] = {}
    for pr in pl_rows:
        pl_song_set.add(pr["song_id"])
        art_pl = str(pr.get("artist") or "")
        if art_pl:
            pl_artist_cnt[art_pl] = pl_artist_cnt.get(art_pl, 0) + 1

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

        # 歌曲稠密特征（从 song_stats 查询，若无则从 MySQL 兜底）
        s_stats          = res.song_stats.get(res.mysql2enc.get(sid, -1), {})
        song_play_log    = float(s_stats.get("play_count_log", math.log1p(pop)))
        song_avg_comp    = float(s_stats.get("avg_completion", 0.5))
        # song_unique_users_log 已改为 song_popularity_norm
        song_pop_norm    = float(s_stats.get("song_popularity_norm", 0.0))
        age_days         = max(0, (today_date.year - rel_year) * 365) if rel_year > 0 else 0
        song_age_log     = math.log1p(age_days)
        song_target_rate = float(s_stats.get("song_target_rate", 0.5))
        song_skip_rate_v = float(s_stats.get("song_skip_rate", 0.2))

        # 交互特征（仅保留有重要度的 user_artist_match）
        user_artist_match = float(u_artist_dist.get(artist, 0.0))

        # days_since_last_play_log（该歌上次播放距今，log1p；未播放取 log1p(9999)）
        _last_song = song_last_play.get(sid)
        if _last_song:
            _days_play = max(0, (today_date - _last_song).days)
        else:
            _days_play = 9999
        days_since_last_play_log = math.log1p(_days_play)

        # days_since_artist_log（该艺术家上次播放距今，log1p）
        _last_art = artist_last_play.get(artist)
        days_since_art     = (today_date - _last_art).days if _last_art else 9999
        days_since_art_log = math.log1p(max(0, days_since_art))

        # user_has_in_playlist / user_playlist_artist_count_log
        user_has_playlist  = 1.0 if sid in pl_song_set else 0.0
        pl_art_cnt         = pl_artist_cnt.get(artist, 0)
        user_pl_artist_log = math.log1p(pl_art_cnt)

        # user_song_prev_play_days（上次听同一首歌的天数；-1=首次）
        user_song_prev_play_days = float(_days_play) if _last_song else -1.0

        # user_song_play_count_before（此前听过这首歌的次数）
        user_song_play_cnt_before = float(song_play_count.get(sid, 0))

        # 歌曲滚动窗口特征（从 Resources.song_rolling 预计算缓存查找）
        _sr             = res.song_rolling.get(sid, {})
        song_log_7d     = _sr.get("log_7d",   0.0)
        song_log_30d    = _sr.get("log_30d",  0.0)
        song_trending   = _sr.get("trending", 1.0)

        # SVD 嵌入特征（从 Resources.svd_vecs 查找，未知用户/歌曲补零）
        _u_svd = res.svd_vecs.get("user", {}).get(user_enc, {})
        _s_svd = res.svd_vecs.get("song", {}).get(song_enc, {})
        svd_us   = [float(_u_svd.get(f"svd_user_song_{i}", 0.0)) for i in range(10)]
        svd_su   = [float(_s_svd.get(f"svd_song_user_{i}", 0.0)) for i in range(10)]
        svd_ua   = [float(_u_svd.get(f"svd_user_artist_{i}", 0.0)) for i in range(5)]
        svd_dot  = float(sum(a * b for a, b in zip(svd_us, svd_su)))

        row = [
            # ── 稀疏特征（14列，严格对齐 train_deepfm_v3.py SPARSE_FEAT_SPECS）
            user_enc,       # 0:  user_id
            song_enc,       # 1:  song_id
            genre_enc,      # 2:  genre
            lang_enc,       # 3:  language
            art_enc,        # 4:  artist
            ctry_enc,       # 5:  origin_country
            year_enc,       # 6:  year_bucket
            src_enc,        # 7:  source_channel
            city_enc,       # 8:  city
            gender_enc,     # 9:  gender
            age_enc,        # 10: age_bucket
            tenure_enc,     # 11: tenure_bucket
            dur_enc,        # 12: duration_bucket
            user_peak_enc,  # 13: user_peak_hour
            # ── 稠密特征（52列，严格对齐 train_lgbm.py DENSE_FEATURES 顺序）
            user_play_count_log,       # 14: user_play_count_log
            avg_comp_u,                # 15: user_avg_completion
            user_diversity,            # 16: user_genre_diversity
            user_30d_active_days,      # 17: user_30d_active_days
            song_play_log,             # 18: song_play_count_log
            song_avg_comp,             # 19: song_avg_completion
            song_pop_norm,             # 20: song_popularity_norm
            song_age_log,              # 21: song_age_days_log
            song_target_rate,          # 22: song_target_rate
            user_artist_match,         # 23: user_artist_match
            user_skip_rate,            # 24: user_skip_rate
            song_skip_rate_v,          # 25: song_skip_rate
            hour_match_v,              # 26: hour_match
            dow_match_v,               # 27: dow_match
            days_since_art_log,        # 28: days_since_artist_log
            days_since_last_play_log,  # 29: days_since_last_play_log
            user_has_playlist,         # 30: user_has_in_playlist
            user_pl_artist_log,        # 31: user_playlist_artist_count_log
            user_song_prev_play_days,  # 32: user_song_prev_play_days
            user_song_play_cnt_before, # 33: user_song_play_count_before
            user_7d_play_count_log,    # 34: user_7d_play_count_log
            user_30d_play_count_log,   # 35: user_30d_play_count_log
            user_7d_avg_completion,    # 36: user_7d_avg_completion
            song_log_7d,               # 37: song_7d_play_count_log
            song_log_30d,              # 38: song_30d_play_count_log
            song_trending,             # 39: song_trending_ratio
            *svd_us,                   # 40-49: svd_user_song_0..9
            *svd_su,                   # 50-59: svd_song_user_0..9
            *svd_ua,                   # 60-64: svd_user_artist_0..4
            svd_dot,                   # 65: svd_dot_score
        ]
        rows.append(row)

    return np.array(rows, dtype=np.float32)   # shape (len(song_ids), 66)


def rank_with_lgbm(candidate_ids: list, X: np.ndarray, res: Resources) -> list:
    """LightGBM 粗排打分，返回 (song_id, lgbm_score) 列表，按分降序。

    build_pair_features 输出 66 列（14稀疏+52稠密），LightGBM 训练时为 59 列
    （7稀疏+52稠密）。从 X66 中抽取对应列组装 X59，顺序与 train_lgbm.py ALL_FEATURES 一致。

    X66 列索引（build_pair_features 输出）：
      稀疏(14): 0=user_id,1=song_id,2=genre,3=lang,4=artist,5=country,
                6=year_bucket,7=src_channel,8=city,9=gender,10=age,
                11=tenure,12=dur,13=peak_hour
      稠密(52): 14-65，与 DENSE_FEATURES 顺序完全一致

    X59 列布局（对齐 train_lgbm.py ALL_FEATURES = SPARSE_FEATURES + DENSE_FEATURES）：
      稀疏(7):  0=user_id,1=song_id,2=genre,3=lang,4=artist,5=country,6=src_channel
      稠密(52): 7-58，直接映射自 X66[:,14:66]
    """
    if res.lgbm_model is None or len(candidate_ids) == 0:
        return [(sid, 0.5) for sid in candidate_ids]

    n = X.shape[0]
    # 构建 59 列特征矩阵（与训练时 ALL_FEATURES 顺序完全一致）
    X59 = np.zeros((n, 59), dtype=np.float32)
    # 稀疏特征（7列）：LightGBM 不含 year_bucket/city/gender/age/tenure/dur/peak_hour
    X59[:, 0] = X[:, 0]   # user_id_encoded
    X59[:, 1] = X[:, 1]   # song_id_encoded
    X59[:, 2] = X[:, 2]   # genre_encoded
    X59[:, 3] = X[:, 3]   # language_encoded
    X59[:, 4] = X[:, 4]   # artist_encoded
    X59[:, 5] = X[:, 5]   # origin_country_encoded
    X59[:, 6] = X[:, 7]   # source_channel_encoded（X66 col 7，跳过 year_bucket col 6）
    # 稠密特征（52列）：直接从 X66 的稠密区段（cols 14-65）复制，顺序完全一致
    X59[:, 7:59] = X[:, 14:66]

    scores = res.lgbm_model.predict(X59, num_iteration=res.lgbm_iter)
    ranked = sorted(zip(candidate_ids, scores.tolist()), key=lambda x: -x[1])
    return ranked


def _build_deep_input(X: np.ndarray, n_feat: int) -> np.ndarray:
    """
    将 build_pair_features 输出的 66 列矩阵转为 DeepFM/BST 期望的输入。

    build_pair_features 输出列数（66）== DeepFM/BST 输入列数（14稀疏+52稠密），
    直接返回 X 本身；仅在 n_feat 不匹配时补零兜底（防御性处理）。
    """
    if X.shape[1] == n_feat:
        return X
    # 兜底：尺寸不符时截取或补零（正常情况下不应进入此分支）
    n = X.shape[0]
    out = np.zeros((n, n_feat), dtype=np.float32)
    copy_cols = min(X.shape[1], n_feat)
    out[:, :copy_cols] = X[:, :copy_cols]
    return out


def rank_with_deepfm(candidate_ids: list, X: np.ndarray, res: Resources) -> list:
    """DeepFM 打分，返回 (song_id, deepfm_score) 列表"""
    if res.deepfm_model is None or len(candidate_ids) == 0:
        return [(sid, 0.5) for sid in candidate_ids]

    import torch
    n_feat = len(res.deepfm_feat_names) if res.deepfm_feat_names else 66
    X_deep = _build_deep_input(X, n_feat)
    X_tensor = torch.from_numpy(X_deep).float()

    with torch.no_grad():
        preds = res.deepfm_model(X_tensor).squeeze().cpu().numpy()

    if preds.ndim == 0:
        preds = np.array([float(preds)])

    return list(zip(candidate_ids, preds.tolist()))


def rank_with_bst(candidate_ids: list, X: np.ndarray, res: Resources,
                  user_id: int, db=None) -> list:
    """
    BST（行为序列 Transformer）打分，返回 (song_id, bst_score) 列表。

    BST 输入：
      - seq_song_ids: 用户最近 seq_len 首歌曲的 song_encoded（从 user_stats 取）
      - 候选歌曲稀疏/稠密特征（与 DeepFM 共用 X 矩阵）
      - 用户稀疏/稠密特征

    若 BST 未加载或推断失败，回退到均值分 0.5。
    """
    if res.bst_model is None or len(candidate_ids) == 0:
        return [(sid, 0.5) for sid in candidate_ids]

    try:
        import torch
        bst_cfg = res.bst_config
        seq_len = bst_cfg.get("seq_len", 50)

        # 从 user_stats 取行为序列（song_encoded 列表）
        user_stats_entry = res.user_stats.get("user_basic", {}).get(user_id, {})
        seq_raw = user_stats_entry.get("seq_song_ids", [])

        # 序列为空或过短（< 5）时，从 live DB 构建实时序列
        # 解决 Tier 2 用户 seq_song_ids 空导致 BST 全 0 填充退化的问题
        if len(seq_raw) < 5 and db is not None:
            try:
                with db.cursor() as _cur:
                    _cur.execute("""
                        SELECT song_id FROM play_history
                        WHERE user_id = %s
                        ORDER BY play_time DESC LIMIT %s
                    """, (user_id, seq_len))
                    _live_ids = [r["song_id"] for r in _cur.fetchall()]
                _song_enc = res.encoders.get("song_id")
                if _song_enc and _live_ids:
                    seq_raw = [
                        _safe_encode(_song_enc, str(sid)) for sid in _live_ids
                    ]
                    seq_raw = [e for e in seq_raw if e != 0]   # 过滤训练集外歌曲
                    print(f"      ℹ️ BST 实时序列构建：{len(seq_raw)} 首")
            except Exception as _e:
                print(f"      ℹ️ BST 实时序列构建失败: {_e}")

        # 截断/填充到 seq_len
        seq = list(seq_raw[-seq_len:]) if len(seq_raw) > seq_len else list(seq_raw)
        seq = [0] * (seq_len - len(seq)) + seq   # 左填充 0（padding token）
        seq_tensor = torch.tensor([seq] * len(candidate_ids), dtype=torch.long)  # (N, seq_len)

        # build_pair_features 输出已为 66 列（14稀疏+52稠密），与 BST 输入对齐
        # _build_deep_input 在列数匹配时直接透传，无需重映射
        BST_N_FEAT = 14 + 52   # = 66
        X_mat = _build_deep_input(X, BST_N_FEAT)       # (N, 66)
        feat_tensor = torch.from_numpy(X_mat).float()   # (N, 66)

        with torch.no_grad():
            # BSTModel forward(seq, feat): (B, seq_len), (B, 49) → (B, 1)
            preds = res.bst_model(seq_tensor, feat_tensor).squeeze().cpu().numpy()

        if preds.ndim == 0:
            preds = np.array([float(preds)])

        return list(zip(candidate_ids, preds.tolist()))

    except Exception as e:
        print(f"      ⚠️ BST 推断失败（{e}），回退到 0.5")
        return [(sid, 0.5) for sid in candidate_ids]


# ============================================================
# 重排层 — 多样性约束
# ============================================================

def mmr_rerank(ranked: list, song_meta_map: dict, res: "Resources",
               lam: float = MMR_LAMBDA,
               max_per_artist: int = MAX_PER_ARTIST,
               top_n: int = TOP_N) -> list:
    """
    MMR（最大边际相关，Maximal Marginal Relevance）多样性重排。

    替代原硬约束 diversity_rerank（同艺术家 ≤ N 首），改用软约束：
      MMR(d) = λ × relevance(d) - (1-λ) × max_sim(d, already_selected)

    参数：
        ranked         : [(song_id, score), ...] 精排后候选列表
        song_meta_map  : {song_id: (genre, artist)} 元数据
        res            : Resources 对象（提供 FAISS 向量查询）
        lam            : 相关性权重（0.7=70%相关性+30%多样性惩罚）
        max_per_artist : 安全上限硬约束（防止极端情况）
        top_n          : 最终返回数量

    返回：
        [(song_id, score), ...] 长度为 top_n
    """
    if not ranked:
        return []

    # ── 1. 查询所有候选的 FAISS 向量（80维，部分歌曲可能无向量）
    vec_map: dict[int, np.ndarray] = {}   # {song_id: embedding}
    for sid, _ in ranked:
        if sid in res.mysql2faiss:
            try:
                vec_map[sid] = res.index.reconstruct(res.mysql2faiss[sid]).astype(np.float32)
            except Exception:
                pass

    # ── 2. 归一化集成评分到 [0, 1]
    scores = np.array([s for _, s in ranked], dtype=np.float32)
    s_min, s_max = scores.min(), scores.max()
    if s_max > s_min:
        norm_scores = (scores - s_min) / (s_max - s_min)
    else:
        norm_scores = np.ones_like(scores)
    score_map = {sid: float(ns) for (sid, _), ns in zip(ranked, norm_scores)}

    # ── 3. MMR 贪心选取循环
    remaining   = [sid for sid, _ in ranked]
    selected    = []   # [(sid, original_score)]
    artist_cnt  = {}   # 艺术家计数（安全上限兜底）
    sel_vecs    = []   # 已选歌曲的向量列表

    for _ in range(top_n):
        if not remaining:
            break

        best_sid   = None
        best_score = -1e9

        for sid in remaining:
            rel = score_map[sid]   # 相关性分（归一化集成评分）

            # 计算与已选列表的最大余弦相似度（多样性惩罚）
            if sel_vecs and sid in vec_map:
                sv = vec_map[sid]
                sv_norm = sv / (np.linalg.norm(sv) + 1e-9)
                sims = []
                for ov in sel_vecs:
                    ov_norm = ov / (np.linalg.norm(ov) + 1e-9)
                    sims.append(float(np.dot(sv_norm, ov_norm)))
                max_sim = max(sims)
            else:
                # 无向量：相似度为 0（视为完全不同，鼓励选入）
                max_sim = 0.0

            mmr_val = lam * rel - (1.0 - lam) * max_sim

            # 安全上限兜底：同艺术家超限时降级惩罚
            _, artist = song_meta_map.get(sid, ("", ""))
            if artist_cnt.get(artist, 0) >= max_per_artist:
                mmr_val -= 10.0   # 软惩罚，极端情况下仍可选入

            if mmr_val > best_score:
                best_score = mmr_val
                best_sid   = sid

        if best_sid is None:
            break

        # 选入
        _, best_artist = song_meta_map.get(best_sid, ("", ""))
        original_score = dict(ranked).get(best_sid, 0.0)
        selected.append((best_sid, original_score))
        artist_cnt[best_artist] = artist_cnt.get(best_artist, 0) + 1
        remaining.remove(best_sid)

        # 记录已选向量（用于后续多样性计算）
        if best_sid in vec_map:
            sel_vecs.append(vec_map[best_sid])

    return selected


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
                # ── v7 升级冷却逻辑（基于 negative_count 字段）
                # 统一负向交互定义：推荐后不播放 / 只听一点点(<20%) / 半途而废(20-80%)
                # 冷却升级：1次→3天, 2次→7天, 3次+→14天冷宫
                # 注：高完播率(≥80%) 或 已收藏 → 不排除（用户喜欢，应继续推荐）

                # 查询每首歌的负向交互次数（negative_count 需提前迁移）
                soft_cooldown_updates = []   # [(days, uid, sid)]
                try:
                    cur.execute("""
                        SELECT song_id, MAX(negative_count) AS neg_cnt,
                               MAX(play_completion)          AS max_comp,
                               MAX(was_favorited)            AS ever_fav
                        FROM recommendation_feedback
                        WHERE user_id = %s
                        GROUP BY song_id
                    """, (uid,))
                    neg_rows = cur.fetchall()

                    for nr in neg_rows:
                        sid_r    = nr["song_id"]
                        neg_cnt  = int(nr["neg_cnt"] or 0)
                        max_comp = float(nr["max_comp"] or 0.0)
                        ever_fav = int(nr["ever_fav"] or 0)

                        # 高完播率或已收藏：不排除
                        if ever_fav or max_comp >= 0.8:
                            continue

                        # 根据负向交互次数决定冷却天数
                        if neg_cnt >= 3:
                            soft_cooldown_updates.append((14, uid, sid_r))
                        elif neg_cnt == 2:
                            soft_cooldown_updates.append((7, uid, sid_r))
                        elif neg_cnt == 1:
                            soft_cooldown_updates.append((3, uid, sid_r))

                    # 批量写入软冷却到 cooldown_until
                    for days, _uid, _sid in soft_cooldown_updates:
                        _cd = (datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
                        cur.execute("""
                            UPDATE recommendation_feedback
                            SET cooldown_until = %s
                            WHERE user_id = %s AND song_id = %s
                              AND (cooldown_until IS NULL OR cooldown_until < %s)
                        """, (_cd, _uid, _sid, _cd))
                except Exception:
                    pass   # negative_count 字段不存在（迁移前），静默兼容

                # 冷却中的歌（含刚写入的软冷却）
                cur.execute("""
                    SELECT song_id FROM recommendation_feedback
                    WHERE user_id = %s AND cooldown_until > CURDATE()
                """, (uid,))
                cooled = {r["song_id"] for r in cur.fetchall()}

                # 最终排除集：仅系统冷却（软/硬冷却），不再排除所有听过的歌
                # 原因：高完播率歌曲和已收藏歌曲应可重复推荐
                exclude_set = cooled

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

            # ── 三路召回（返回候选 + Tier2 实时分布）
            cand_dict, realtime_dists = recall_candidates(
                db, uid, res, exclude_set,
                blocked_genres, blocked_artists, song_meta_map
            )
            cand_ids = list(cand_dict.keys())
            print(f"      召回候选: {len(cand_ids)} 首")

            if not cand_ids:
                print(f"      ⚠️ 无候选歌曲，跳过")
                continue

            # ── LightGBM 粗排：~600 → 300（v7 扩展漏斗）
            # realtime_dists 在 Tier2 时非空，使 user_artist_match 特征更准确
            X = build_pair_features(uid, cand_ids, db, res, realtime_dists)
            lgbm_ranked      = rank_with_lgbm(cand_ids, X, res)
            top_coarse       = lgbm_ranked[:RANK_TOP]
            top_coarse_ids   = [sid for sid, _ in top_coarse]
            print(f"      LightGBM 粗排: top {len(top_coarse_ids)} 首")

            # ── 双模型精排集成：300 → 150（DeepFM + BST 加权融合）
            # LightGBM 仅用于粗排（~600→300），不参与精排集成，避免集成退化
            if top_coarse_ids:
                X_fine        = build_pair_features(uid, top_coarse_ids, db, res, realtime_dists)
                deepfm_scored = rank_with_deepfm(top_coarse_ids, X_fine, res)
                bst_scored    = rank_with_bst(top_coarse_ids, X_fine, res, uid, db)
                deepfm_score_map = {sid: s for sid, s in deepfm_scored}
                bst_score_map    = {sid: s for sid, s in bst_scored}
                ensemble_scored  = [
                    (sid,
                     res.w_deepfm * deepfm_score_map.get(sid, 0.5)
                     + res.w_bst  * bst_score_map.get(sid, 0.5))
                    for sid in top_coarse_ids
                ]
                ensemble_scored.sort(key=lambda x: -x[1])
                top_fine = ensemble_scored[:ENSEMBLE_TOP]
            else:
                top_fine = top_coarse[:ENSEMBLE_TOP]

            print(f"      精排集成（DeepFM×{res.w_deepfm:.2f} + BST×{res.w_bst:.2f}）: top {len(top_fine)} 首")

            # ── MMR 多样性重排：150 → 50（v7：替代硬约束 diversity_rerank）
            # MMR λ=0.7：70%集成评分相关性 + 30%余弦相似度多样性惩罚
            final_recs = mmr_rerank(top_fine, song_meta_map, res)

            # 若不足，用热度补充（优先 hot_cache，回退 songs.popularity）
            if len(final_recs) < TOP_N:
                already = {sid for sid, _ in final_recs}
                if res.hot_cache:
                    hot_ids = sorted(res.hot_cache.keys(),
                                     key=lambda s: -res.hot_cache[s])[:200]
                else:
                    with db.cursor() as cur:
                        cur.execute("""
                            SELECT id FROM songs WHERE popularity > 0
                            ORDER BY popularity DESC LIMIT 200
                        """)
                        hot_ids = [r["id"] for r in cur.fetchall()]
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
