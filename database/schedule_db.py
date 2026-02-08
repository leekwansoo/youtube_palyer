# databse/schedule_db.py
import sqlite3
import pandas as pd
from datetime import datetime, time
import time as time_module
import os
import webbrowser
import re

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('video_schedule.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_time TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            title TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_played TEXT DEFAULT NULL
        )
    ''')
    
    # 기존 테이블에 last_played 컬럼 추가 (이미 있으면 무시)
    try:
        c.execute('ALTER TABLE schedules ADD COLUMN last_played TEXT DEFAULT NULL')
        conn.commit()
    except:
        pass
    
    conn.close()

# 스케줄 추가
def add_schedule(schedule_time, file_path, file_type, title):
    conn = sqlite3.connect('video_schedule.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO schedules (schedule_time, file_path, file_type, title)
        VALUES (?, ?, ?, ?)
    ''', (schedule_time, file_path, file_type, title))
    conn.commit()
    conn.close()

# 스케줄 조회
def get_schedules():
    conn = sqlite3.connect('video_schedule.db')
    df = pd.read_sql_query("SELECT * FROM schedules ORDER BY schedule_time", conn)
    conn.close()
    return df

# 스케줄 삭제
def delete_schedule(schedule_id):
    conn = sqlite3.connect('video_schedule.db')
    c = conn.cursor()
    c.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()

# 스케줄 수정
def update_schedule(schedule_id, schedule_time, file_path, file_type, title):
    conn = sqlite3.connect('video_schedule.db')
    c = conn.cursor()
    c.execute('''
        UPDATE schedules 
        SET schedule_time = ?, file_path = ?, file_type = ?, title = ?
        WHERE id = ?
    ''', (schedule_time, file_path, file_type, title, schedule_id))
    conn.commit()
    conn.close()

# 스케줄 활성화/비활성화
def toggle_schedule(schedule_id, is_active):
    conn = sqlite3.connect('video_schedule.db')
    c = conn.cursor()
    c.execute("UPDATE schedules SET is_active = ? WHERE id = ?", (is_active, schedule_id))
    conn.commit()
    conn.close()

# YouTube URL 확인
def is_youtube_url(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    return re.match(youtube_regex, url) is not None

# 비디오 재생 체크 (백그라운드)
def check_schedule():
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M")
            conn = sqlite3.connect('video_schedule.db')
            c = conn.cursor()
            
            # 현재 시간과 일치하는 활성화된 스케줄 찾기
            c.execute('''
                SELECT * FROM schedules 
                WHERE schedule_time = ? AND is_active = 1
            ''', (current_time,))
            
            schedules = c.fetchall()
            
            for schedule in schedules:
                schedule_id, _, file_path, file_type, title, _, _, last_played = schedule
                
                # 같은 시간대에 이미 재생되었는지 확인 (last_played와 current_time 비교)
                if last_played != current_time:
                    # 재생 처리
                    if file_type == 'youtube':
                        webbrowser.open(file_path)
                    elif file_type == 'local':
                        if os.path.exists(file_path):
                            os.startfile(file_path) if os.name == 'nt' else os.system(f'open "{file_path}"')
                    elif file_type == "html":
                        webbrowser.open(f'file://{os.path.abspath(file_path)}')
                    
                    # 데이터베이스에 재생 시간 업데이트
                    c.execute('UPDATE schedules SET last_played = ? WHERE id = ?', (current_time, schedule_id))
                    conn.commit()
            
            conn.close()
            
        except Exception as e:
            print(f"스케줄 체크 오류: {e}")
        
        # 30초마다 체크
        time_module.sleep(30)