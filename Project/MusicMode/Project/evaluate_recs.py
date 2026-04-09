#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在线推荐效果评估脚本 evaluate_recs.py
计算指标：CTR、平均完播率、收藏率、跳曲率、Precision@10、覆盖度、NDCG@10、Intra-list Diversity
输出到控制台 + Mode/evaluation_report.txt
"""

import sys
import os
import math
import datetime
import pymysql
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 数据库连接配置 ──────────────────────────────────────────
DB_CONFIG = dict(
    host='localhost', port=3306,
    user='root', password='JF123456',
    db='musicweb', charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

REPORT_PATH = os.path.join(os.path.dirname(__file__), '..', 'Mode', 'evaluation_report.txt')


def get_db():
    return pymysql.connect(**DB_CONFIG)


# ── 1. 系统整体指标 ─────────────────────────────────────────
def compute_overall_metrics(cur):
    # 排除 admin 用户的数据，避免测试账号拉低系统指标
    cur.execute("""
        SELECT
            COUNT(*)                                                          AS total_recs,
            SUM(rf.was_played)                                                AS total_played,
            SUM(rf.was_favorited)                                             AS total_favorited,
            AVG(CASE WHEN rf.was_played = 1 THEN rf.play_completion END)      AS avg_completion,
            SUM(CASE WHEN rf.was_played = 1 AND rf.play_completion < 0.2 THEN 1 ELSE 0 END) AS skips,
            COUNT(DISTINCT rf.song_id)                                        AS distinct_songs
        FROM recommendation_feedback rf
        JOIN users u ON u.id = rf.user_id
        WHERE u.username != 'admin'
    """)
    row = cur.fetchone()

    cur.execute("SELECT COUNT(*) AS total FROM songs")
    song_total = cur.fetchone()['total']

    total       = row['total_recs'] or 0
    played      = row['total_played'] or 0
    favorited   = row['total_favorited'] or 0
    avg_comp    = row['avg_completion'] or 0.0
    skips       = row['skips'] or 0
    distinct    = row['distinct_songs'] or 0

    ctr         = played / total          if total   > 0 else 0.0
    fav_rate    = favorited / total       if total   > 0 else 0.0
    skip_rate   = skips / played          if played  > 0 else 0.0
    coverage    = distinct / song_total   if song_total > 0 else 0.0

    return {
        'total_recs':    total,
        'total_played':  played,
        'total_favorited': favorited,
        'ctr':           ctr,
        'avg_completion': float(avg_comp),
        'fav_rate':      fav_rate,
        'skip_rate':     skip_rate,
        'coverage':      coverage,
        'distinct_songs': distinct,
        'total_songs':   song_total,
    }


# ── 2. 逐用户指标 ──────────────────────────────────────────
def compute_per_user_metrics(cur):
    cur.execute("""
        SELECT
            u.username,
            rf.user_id,
            COUNT(*)                                                            AS total_recs,
            SUM(rf.was_played)                                                  AS played,
            SUM(rf.was_favorited)                                               AS favorited,
            AVG(CASE WHEN rf.was_played = 1 THEN rf.play_completion END)       AS avg_completion,
            SUM(CASE WHEN rf.was_played=1 AND rf.play_completion < 0.2 THEN 1 ELSE 0 END) AS skips
        FROM recommendation_feedback rf
        JOIN users u ON u.id = rf.user_id
        WHERE u.username != 'admin'
        GROUP BY rf.user_id, u.username
        ORDER BY rf.user_id
    """)
    rows = cur.fetchall()

    results = []
    for r in rows:
        total   = r['total_recs'] or 0
        played  = r['played']     or 0
        favs    = r['favorited']  or 0
        skips   = r['skips']      or 0
        avg_c   = float(r['avg_completion'] or 0.0)
        results.append({
            'user_id':       r['user_id'],
            'username':      r['username'],
            'total_recs':    total,
            'ctr':           played / total       if total  > 0 else 0.0,
            'avg_completion': avg_c,
            'fav_rate':      favs   / total       if total  > 0 else 0.0,
            'skip_rate':     skips  / played      if played > 0 else 0.0,
        })
    return results


# ── 3. NDCG@10（按 feedback_score 降序，用 was_played 作为相关性） ───
def compute_ndcg_at_k(cur, k=10):
    """
    NDCG@K：归一化折损累积增益
    相关性 = was_played（0/1），按 feedback_score 降序排列
    """
    cur.execute("""
        SELECT rf.user_id, rf.recommend_date, rf.was_played, rf.feedback_score,
               ROW_NUMBER() OVER (
                   PARTITION BY rf.user_id, rf.recommend_date
                   ORDER BY rf.feedback_score DESC
               ) AS rn
        FROM recommendation_feedback rf
        JOIN users u ON u.id = rf.user_id
        WHERE u.username != 'admin'
    """)
    all_rows = cur.fetchall()

    groups = defaultdict(list)
    for row in all_rows:
        key = (row['user_id'], str(row['recommend_date']))
        if row['rn'] <= k:
            groups[key].append(int(row['was_played'] or 0))

    if not groups:
        return 0.0

    ndcg_scores = []
    for relevances in groups.values():
        # DCG
        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))
        # Ideal DCG（所有相关项排最前）
        ideal = sorted(relevances, reverse=True)
        idcg  = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
        ndcg_scores.append(dcg / idcg if idcg > 0 else 0.0)

    return sum(ndcg_scores) / len(ndcg_scores)


# ── 4. Intra-list Diversity（推荐列表内流派多样性，Shannon 熵均值） ──
def compute_intra_list_diversity(cur):
    """
    对每个用户当前推荐列表，计算流派分布的 Shannon 熵
    返回所有用户推荐列表的平均熵（越高越多样）
    """
    cur.execute("""
        SELECT r.user_id, s.genre
        FROM recommendations r
        JOIN songs s ON s.id = r.song_id
        JOIN users u ON u.id = r.user_id
        WHERE u.username != 'admin' AND s.genre IS NOT NULL AND s.genre != ''
    """)
    rows = cur.fetchall()

    user_genres = defaultdict(list)
    for row in rows:
        user_genres[row['user_id']].append(row['genre'])

    if not user_genres:
        return 0.0

    entropies = []
    for genres in user_genres.values():
        total = len(genres)
        counts = defaultdict(int)
        for g in genres:
            primary = g.split(';')[0].strip()
            counts[primary] += 1
        entropy = -sum((c / total) * math.log2(c / total)
                       for c in counts.values() if c > 0)
        entropies.append(entropy)

    return sum(entropies) / len(entropies)


# ── 5. Precision@10（按 feedback_score 降序，取前10推荐） ───
def compute_precision_at_k(cur, k=10):
    """
    对每个 (user_id, recommend_date) 组，按 feedback_score 降序取前K，
    计算 was_played 比例，最后取所有组的均值。
    """
    # 排除 admin 用户
    cur.execute("""
        SELECT rf.user_id, rf.recommend_date, rf.was_played, rf.feedback_score,
               ROW_NUMBER() OVER (
                   PARTITION BY rf.user_id, rf.recommend_date
                   ORDER BY rf.feedback_score DESC
               ) AS rn
        FROM recommendation_feedback rf
        JOIN users u ON u.id = rf.user_id
        WHERE u.username != 'admin'
    """)
    all_rows = cur.fetchall()

    groups = {}
    for row in all_rows:
        key = (row['user_id'], str(row['recommend_date']))
        if row['rn'] <= k:
            groups.setdefault(key, []).append(row['was_played'])

    if not groups:
        return 0.0

    precisions = [sum(v) / len(v) for v in groups.values() if v]
    return sum(precisions) / len(precisions) if precisions else 0.0


# ── 6. 格式化输出 ──────────────────────────────────────────
def format_report(overall, per_user, p_at_10, ndcg_10, diversity, generated_at):
    lines = []
    lines.append("=" * 60)
    lines.append("  音乐推荐系统效果评估报告")
    lines.append(f"  生成时间：{generated_at}")
    lines.append("=" * 60)

    lines.append("\n【系统整体指标】")
    lines.append(f"  总推荐条数      : {overall['total_recs']:,}")
    lines.append(f"  CTR（点击率）   : {overall['ctr']:.2%}  ({overall['total_played']:,} 首被播放)")
    lines.append(f"  平均完播率      : {overall['avg_completion']:.2%}  (已播放歌曲)")
    lines.append(f"  收藏率          : {overall['fav_rate']:.2%}  ({overall['total_favorited']:,} 首被收藏)")
    lines.append(f"  跳曲率          : {overall['skip_rate']:.2%}  (完播<20%/已播放)")
    lines.append(f"  Precision@10    : {p_at_10:.2%}")
    lines.append(f"  NDCG@10         : {ndcg_10:.4f}")
    lines.append(f"  列表内多样性    : {diversity:.4f}  (流派 Shannon 熵均值)")
    lines.append(f"  覆盖度          : {overall['coverage']:.4%}  ({overall['distinct_songs']:,} / {overall['total_songs']:,} 首歌)")

    lines.append("\n【逐用户指标】")
    header = f"  {'用户名':<12}{'总推荐':>8}{'CTR':>8}{'完播率':>8}{'收藏率':>8}{'跳曲率':>8}"
    lines.append(header)
    lines.append("  " + "-" * 52)
    for u in per_user:
        lines.append(
            f"  {u['username']:<12}"
            f"{u['total_recs']:>8,}"
            f"{u['ctr']:>8.2%}"
            f"{u['avg_completion']:>8.2%}"
            f"{u['fav_rate']:>8.2%}"
            f"{u['skip_rate']:>8.2%}"
        )

    lines.append("\n【指标说明】")
    lines.append("  CTR         = was_played=1 / 总推荐数")
    lines.append("  平均完播率  = AVG(play_completion) WHERE was_played=1")
    lines.append("  收藏率      = was_favorited=1 / 总推荐数")
    lines.append("  跳曲率      = play_completion<0.2 / was_played=1")
    lines.append("  Precision@10= 每用户每日推荐中 feedback_score 前10首的 was_played 均值")
    lines.append("  NDCG@10     = 归一化折损累积增益（考虑排名权重，相关性=was_played）")
    lines.append("  列表内多样性= 当前推荐列表中流派分布的 Shannon 熵均值（越高越多样）")
    lines.append("  覆盖度      = 被推荐过的不同歌曲数 / songs 总数")
    lines.append("\n" + "=" * 60)

    return "\n".join(lines)


# ── 主入口 ──────────────────────────────────────────────────
def main():
    print("🔍 连接数据库，计算推荐效果指标...")
    db = get_db()
    try:
        with db.cursor() as cur:
            overall   = compute_overall_metrics(cur)
            per_user  = compute_per_user_metrics(cur)
            p_at_10   = compute_precision_at_k(cur, k=10)
            ndcg_10   = compute_ndcg_at_k(cur, k=10)
            diversity = compute_intra_list_diversity(cur)
    finally:
        db.close()

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = format_report(overall, per_user, p_at_10, ndcg_10, diversity, generated_at)

    # 控制台输出
    print(report)

    # 写入文件
    report_dir = os.path.dirname(REPORT_PATH)
    os.makedirs(report_dir, exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n✅ 报告已写入: {os.path.abspath(REPORT_PATH)}")


if __name__ == '__main__':
    main()
