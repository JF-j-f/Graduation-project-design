# -*- coding: utf-8 -*-
import os
import pymysql

def run_sql_file():
    db = pymysql.connect(
        host='localhost',
        user='root',
        password='JF123456',
        db='musicweb',
        charset='utf8mb4'
    )
    cur = db.cursor()
    
    sql_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'update_comments.sql')
    with open(sql_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    try:
        for line in lines:
            line = line.strip()
            if line and not line.startswith('--'):
                print(f"Executing: {line}")
                cur.execute(line)
        db.commit()
        print("SQL executed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        cur.close()
        db.close()

if __name__ == "__main__":
    run_sql_file()
