# -*- coding: utf-8 -*-
import pymysql

def update_table_comments():
    db = pymysql.connect(
        host='localhost',
        user='root',
        password='JF123456',
        db='musicweb',
        charset='utf8mb4'
    )
    cur = db.cursor()
    
    comments = {
        'appeals': '用户申诉表',
        'favorites': '歌曲收藏表',
        'play_history': '播放历史表',
        'playlist_info': '[已废弃] 外部歌单表',
        'playlist_songs': '歌单歌曲表',
        'recommendation_feedback': '推荐反馈表',
        'recommendations': '歌曲推荐表',
        'song_info': '[已废弃] 歌曲草稿表',
        'songs': '歌曲主表',
        'songs_update_temp': '[已废弃] 歌曲更新表',
        'user_playlists': '用户歌单表',
        'users': '用户信息表'
    }
    
    try:
        for table, comment in comments.items():
            sql = f"ALTER TABLE {table} COMMENT = '{comment}'"
            print(f"Executing: {sql}")
            cur.execute(sql)
        db.commit()
        print("所有表注释更新成功！")
    except Exception as e:
        db.rollback()
        print(f"更新失败: {e}")
    finally:
        cur.close()
        db.close()

if __name__ == "__main__":
    update_table_comments()
