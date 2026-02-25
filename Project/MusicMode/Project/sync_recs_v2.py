# -*- coding: utf-8 -*-
"""
多通道混合推荐脚本 (sync_recs_v2.py)
功能：
1. 回收反馈：更新 recommendation_feedback 分数和冷却状态
2. 用户画像：多源加权（播放+收藏+自建歌单）生成 64 维偏好向量
3. FAISS 召回：基于向量相似度召回歌曲
4. 兜底策略：无向量歌曲按内容特征/热度兜底
5. 结果落盘：更新 recommendations，同时写入 recommendation_feedback 待明日追踪

计划任务：每天凌晨 4 点运行
"""

import os
import sys
import pickle
import numpy as np
import pymysql
import datetime
import faiss

# ============================================
# 配置
# ============================================

MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "JF123456"
MYSQL_DB = "musicweb"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Mode")

FAISS_INDEX_PATH = os.path.join(MODE_DIR, "song_index.faiss")
SONG_ID_MAP_PATH = os.path.join(MODE_DIR, "song_id_map.pkl")
ENCODER_PATH = os.path.join(MODE_DIR, "encoders.pkl")

# 用户画像权重
WEIGHTS = {
    'play_yesterday': 1.0,
    'play_7days': 0.6,
    'play_older': 0.3,
    'favorite_default': 0.8,
    'playlist_custom': 0.7
}

TOP_N = 10

def get_db_connection():
    return pymysql.connect(
        host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, db=MYSQL_DB,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )

def load_resources():
    print("📥 加载资源文件...")
    # 1. FAISS 索引
    index = faiss.read_index(FAISS_INDEX_PATH)
    # 2. 映射数据
    with open(SONG_ID_MAP_PATH, 'rb') as f:
        map_data = pickle.load(f)
    # 3. 编码器
    with open(ENCODER_PATH, 'rb') as f:
        encoders = pickle.load(f)
    
    song_encoder = encoders['song']
    
    # 构建快速映射字典：MySQL ID -> FAISS INDEX, 和 FAISS INDEX -> MySQL ID
    print("🔗 构建 MySQL ID 与 FAISS 索引双向映射...")
    db = get_db_connection()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, kkbox_id FROM songs WHERE kkbox_id IS NOT NULL AND kkbox_id != ''")
            sql_songs = cur.fetchall()
    finally:
        db.close()
        
    mysql2faiss = {}
    faiss2mysql = {}
    
    # 优化：提前构建字典，不在 230 万次循环中调用极慢的 transform()
    kb_to_faiss_dict = {kb_id: idx for idx, kb_id in enumerate(song_encoder.classes_)}
    
    for row in sql_songs:
        sql_id = row['id']
        kb_id = row['kkbox_id']
        if kb_id in kb_to_faiss_dict:
            faiss_idx = kb_to_faiss_dict[kb_id]
            mysql2faiss[sql_id] = faiss_idx
            faiss2mysql[faiss_idx] = sql_id
            
    print(f"   ✅ 成功映射歌曲数: {len(mysql2faiss):,}")
    return index, map_data, song_encoder, mysql2faiss, faiss2mysql

def update_feedback(db):
    """回收昨日推荐反馈，计算反馈得分和冷却名单"""
    print("\n🔄 [Step 1] 回收昨日推荐反馈...")
    try:
        with db.cursor() as cur:
            yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            
            # 获取昨日所有的反馈记录
            cur.execute("""
                SELECT id, user_id, was_played, play_completion, was_favorited, consecutive_ignore_days 
                FROM recommendation_feedback 
                WHERE recommend_date = %s
            """, (yesterday,))
            feedbacks = cur.fetchall()
            
            if not feedbacks:
                print("   ℹ️ 昨日没有推荐记录，跳过反馈回收。")
                return

            # 查询昨日活跃用户
            cur.execute("""
                SELECT DISTINCT user_id FROM play_history 
                WHERE DATE(play_time) = %s
            """, (yesterday,))
            active_users = set(row['user_id'] for row in cur.fetchall())
            print(f"   ✅ 昨日活跃用户数: {len(active_users)}")

            update_data = []
            for fb in feedbacks:
                fid = fb['id']
                uid = fb['user_id']
                was_played = fb['was_played']
                comp = fb['play_completion'] or 0.0
                was_fav = fb['was_favorited']
                ignore_days = fb['consecutive_ignore_days'] or 0
                
                score_delta = 0.0
                cooldown = "NULL"
                new_ignore = ignore_days
                
                if uid in active_users:
                    if was_played == 0:
                        score_delta -= 0.1
                        new_ignore += 1
                        if new_ignore >= 3:
                            cooldown = f"'{ (datetime.date.today() + datetime.timedelta(days=14)).strftime('%Y-%m-%d') }'"
                            score_delta -= 0.5
                    else:
                        new_ignore = 0  # 重置
                        if comp < 0.2:
                            score_delta -= 0.3
                        elif comp > 0.8:
                            score_delta += 0.5
                        else:
                            score_delta += 0.3
                            
                    if was_fav:
                        score_delta += 1.0
                else:
                    # 未登录，不惩罚也不加分
                    pass
                
                # 累加分数并写入
                update_data.append((score_delta, new_ignore, cooldown, fid))

            # 批量更新
            updated = 0
            for item in update_data:
                # 注意：cooldown 可能为空
                cd_val = item[2]
                if cd_val == "NULL":
                    cur.execute("""
                        UPDATE recommendation_feedback 
                        SET feedback_score = feedback_score + %s, consecutive_ignore_days = %s
                        WHERE id = %s
                    """, (item[0], item[1], item[3]))
                else:
                    cur.execute(f"""
                        UPDATE recommendation_feedback 
                        SET feedback_score = feedback_score + %s, consecutive_ignore_days = %s, cooldown_until = {cd_val}
                        WHERE id = %s
                    """, (item[0], item[1], item[3]))
                updated += 1
                
            db.commit()
            print(f"   ✅ 更新了 {updated} 条反馈记录。")
    except Exception as e:
        print(f"   ❌ 反馈回收失败: {e}")
        db.rollback()

def find_genre_proxy(cur, genre_str, mysql2faiss, index, genre_cache, max_proxies=1):
    """通过 genre 关键词在 KKBOX 歌曲中找代理向量（带缓存）"""
    if not genre_str:
        return []
    keyword = genre_str.split(';')[0].split('；')[0].split(',')[0].strip()
    if not keyword:
        return []
    
    # 缓存命中
    if keyword in genre_cache:
        return genre_cache[keyword][:max_proxies]
    
    # 缓存未命中，查询并缓存
    proxies = []
    cur.execute("""
        SELECT id FROM songs 
        WHERE genre LIKE %s AND kkbox_id IS NOT NULL AND kkbox_id != ''
        ORDER BY popularity DESC LIMIT 5
    """, (f"%{keyword}%",))
    for row in cur.fetchall():
        if row['id'] in mysql2faiss:
            vec = index.reconstruct(mysql2faiss[row['id']])
            proxies.append(vec)
    genre_cache[keyword] = proxies
    return proxies[:max_proxies]

def get_user_profile(db, user_id, mysql2faiss, index, genre_cache, song_meta_cache):
    """多源加权生成用户画像 64 维向量（含外部歌曲桥接）"""
    today = datetime.datetime.now()
    yesterday = today - datetime.timedelta(days=1)
    seven_days = today - datetime.timedelta(days=7)

    vectors = []
    weights = []

    with db.cursor() as cur:
        # 1. 播放历史
        cur.execute("SELECT song_id, play_time FROM play_history WHERE user_id = %s", (user_id,))
        for row in cur.fetchall():
            sid = row['song_id']
            ptime = row['play_time']
            if ptime >= yesterday:
                w = WEIGHTS['play_yesterday']
            elif ptime >= seven_days:
                w = WEIGHTS['play_7days']
            else:
                w = WEIGHTS['play_older']
                
            if sid in mysql2faiss:
                vec = index.reconstruct(mysql2faiss[sid])
                vectors.append(vec)
                weights.append(w)
            else:
                # 桥接：外部歌曲 → 用缓存的 genre 找代理向量
                genre = song_meta_cache.get(sid)
                if genre is None:
                    cur.execute("SELECT genre FROM songs WHERE id = %s", (sid,))
                    meta = cur.fetchone()
                    genre = meta.get('genre', '') if meta else ''
                    song_meta_cache[sid] = genre
                if genre:
                    proxies = find_genre_proxy(cur, genre, mysql2faiss, index, genre_cache, 1)
                    for pvec in proxies:
                        vectors.append(pvec)
                        weights.append(w * 0.5)  # 代理权重打折
                
        # 2. 收藏
        cur.execute("SELECT song_id FROM favorites WHERE user_id = %s", (user_id,))
        for row in cur.fetchall():
            sid = row['song_id']
            if sid in mysql2faiss:
                vectors.append(index.reconstruct(mysql2faiss[sid]))
                weights.append(WEIGHTS['favorite_default'])
            else:
                genre = song_meta_cache.get(sid)
                if genre is None:
                    cur.execute("SELECT genre FROM songs WHERE id = %s", (sid,))
                    meta = cur.fetchone()
                    genre = meta.get('genre', '') if meta else ''
                    song_meta_cache[sid] = genre
                if genre:
                    proxies = find_genre_proxy(cur, genre, mysql2faiss, index, genre_cache, 1)
                    for pvec in proxies:
                        vectors.append(pvec)
                        weights.append(WEIGHTS['favorite_default'] * 0.5)
                
        # 3. 自建歌单
        cur.execute("""
            SELECT ps.song_id 
            FROM playlist_songs ps
            JOIN user_playlists up ON ps.playlist_id = up.id
            WHERE up.user_id = %s
        """, (user_id,))
        for row in cur.fetchall():
            sid = row['song_id']
            if sid in mysql2faiss:
                vectors.append(index.reconstruct(mysql2faiss[sid]))
                weights.append(WEIGHTS['playlist_custom'])

        # 4. 冷启动兜底：用户无任何行为时，读取注册偏好标签
        if not vectors:
            cur.execute("SELECT preferred_genres, preferred_artists FROM users WHERE id = %s", (user_id,))
            pref = cur.fetchone()
            if pref:
                # 用 genre 偏好找代理
                if pref.get('preferred_genres'):
                    for gid in pref['preferred_genres'].split(','):
                        gid = gid.strip()
                        if gid:
                            cur.execute("""
                                SELECT id FROM songs 
                                WHERE genre_ids LIKE %s AND kkbox_id IS NOT NULL AND kkbox_id != ''
                                ORDER BY popularity DESC LIMIT 3
                            """, (f"%{gid}%",))
                            for row in cur.fetchall():
                                if row['id'] in mysql2faiss:
                                    vectors.append(index.reconstruct(mysql2faiss[row['id']]))
                                    weights.append(0.5)
                # 用 artist 偏好找代理
                if pref.get('preferred_artists'):
                    for art in pref['preferred_artists'].split(','):
                        art = art.strip()
                        if art:
                            cur.execute("""
                                SELECT id FROM songs 
                                WHERE artist LIKE %s AND kkbox_id IS NOT NULL AND kkbox_id != ''
                                ORDER BY popularity DESC LIMIT 3
                            """, (f"%{art}%",))
                            for row in cur.fetchall():
                                if row['id'] in mysql2faiss:
                                    vectors.append(index.reconstruct(mysql2faiss[row['id']]))
                                    weights.append(0.6)

    if not vectors:
        return None  # 真的什么都没有
        
    v_arr = np.array(vectors)
    w_arr = np.array(weights).reshape(-1, 1)
    profile = np.sum(v_arr * w_arr, axis=0)
    
    # 归一化
    norm = np.linalg.norm(profile)
    if norm > 0:
        profile = profile / norm
        
    return np.array([profile], dtype=np.float32)

def generate_recommendations():
    """核心推荐流程"""
    db = get_db_connection()
    try:
        # Step 1: 回收反馈
        update_feedback(db)
        
        # 加载资源
        index, map_data, song_encoder, mysql2faiss, faiss2mysql = load_resources()
        
        print("\n🚀 [Step 2] 开始生成推荐...")
        with db.cursor() as cur:
            # 只清除 AI 生成的推荐，保留 Java 端的 cold_start 推荐
            cur.execute("DELETE FROM recommendations WHERE source_type = 'deepfm'")
            
            # 获取所有普通用户（排除管理员）
            cur.execute("SELECT id FROM users WHERE status='active' AND username != 'admin'")
            users = cur.fetchall()
            
            # 预加载热门歌曲候选池（避免 ORDER BY RAND() 慢查询）
            import random
            cur.execute("SELECT id FROM songs WHERE popularity > 0 ORDER BY popularity DESC LIMIT 500")
            hot_pool = [r['id'] for r in cur.fetchall()]
            random.shuffle(hot_pool)
            
            # genre 和歌曲元数据缓存
            genre_cache = {}
            song_meta_cache = {}
            
            for u in users:
                uid = u['id']
                
                # 获取已听过的歌和被冷却的歌
                cur.execute("SELECT song_id FROM play_history WHERE user_id = %s", (uid,))
                listened = set(r['song_id'] for r in cur.fetchall())
                
                cur.execute("SELECT song_id FROM recommendation_feedback WHERE user_id = %s AND cooldown_until > CURDATE()", (uid,))
                cooled = set(r['song_id'] for r in cur.fetchall())
                
                exclude_set = listened.union(cooled)
                
                # 生成画像
                profile_vec = get_user_profile(db, uid, mysql2faiss, index, genre_cache, song_meta_cache)
                
                recs = []
                if profile_vec is not None:
                    # 通道A: FAISS 检索 (多搜一些因为要过滤)
                    D, I = index.search(profile_vec, 100)
                    for i in range(100):
                        fidx = I[0][i]
                        score = float(D[0][i])
                        if fidx in faiss2mysql:
                            sql_id = faiss2mysql[fidx]
                            if sql_id not in exclude_set and sql_id not in [r[0] for r in recs]:
                                recs.append((sql_id, score))
                                if len(recs) >= TOP_N:
                                    break
                
                # 若 FAISS 结果不足，用预加载的热门池补充
                if len(recs) < TOP_N:
                    need = TOP_N - len(recs)
                    for sid in hot_pool:
                        if sid not in exclude_set and sid not in [r[0] for r in recs]:
                            recs.append((sid, 0.1))
                            need -= 1
                            if need <= 0:
                                break
                                
                # 写入 recommendations 
                for sql_id, score in recs:
                    cur.execute("INSERT INTO recommendations (user_id, song_id, score) VALUES (%s, %s, %s)", (uid, sql_id, score))
                
                # 同时写入 recommendation_feedback 待明日追踪
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                for sql_id, score in recs:
                    cur.execute("""
                        INSERT IGNORE INTO recommendation_feedback (user_id, song_id, recommend_date)
                        VALUES (%s, %s, %s)
                    """, (uid, sql_id, today_str))

        db.commit()
        print("   ✅ 全部推荐生成并写入数据库完成！")
    finally:
        db.close()

if __name__ == "__main__":
    generate_recommendations()
