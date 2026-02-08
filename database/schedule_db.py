# databse/schedule_db.py
import sqlite3
import pandas as pd
from datetime import datetime, time
import time as time_module
import os
import json
import re
import webbrowser

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

# YouTube URL을 embed URL로 변환
def get_youtube_embed_url(url):
    """Convert YouTube URL to embed format for iframe display"""
    # Extract video ID from various YouTube URL formats
    patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([^&=%\?]{11})',
        r'(?:https?://)?(?:www\.)?youtu\.be/([^&=%\?]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([^&=%\?]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([^&=%\?]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return f'https://www.youtube.com/embed/{video_id}'
    
    # If no pattern matches, return original URL
    return url

# Current video management functions (Streamlit Cloud compatible)
# Note: These functions now work with Streamlit session state passed from app.py
# For backward compatibility, they also write to JSON file for local use

def set_current_video(file_path, title, session_state=None):
    """Set the current video to be played"""
    video_data = {
        'file_path': file_path,
        'title': title,
        'timestamp': datetime.now().isoformat()
    }
    
    # Use session state if available (Streamlit Cloud)
    if session_state is not None:
        session_state['current_video'] = video_data
    
    # Also write to file for backward compatibility (local use)
    try:
        with open('current_video.json', 'w', encoding='utf-8') as f:
            json.dump(video_data, f, ensure_ascii=False)
    except:
        pass  # Ignore file errors on Streamlit Cloud

def get_current_video(session_state=None):
    """Get the current video that should be playing"""
    # Check session state first (Streamlit Cloud)
    if session_state is not None and 'current_video' in session_state:
        return session_state['current_video']
    
    # Fall back to file (local use)
    try:
        if os.path.exists('current_video.json'):
            with open('current_video.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and isinstance(data, dict):
                    return data
    except Exception as e:
        print(f"Error reading current video: {e}")
    
    return None

def clear_current_video(session_state=None):
    """Clear the current video"""
    # Clear from session state (Streamlit Cloud)
    if session_state is not None and 'current_video' in session_state:
        del session_state['current_video']
    
    # Also clear file (local use)
    try:
        if os.path.exists('current_video.json'):
            os.remove('current_video.json')
    except:
        pass

# Check schedule once (synchronous - called from main app)
def check_schedule_once(session_state=None):
    """Check if any scheduled videos should play right now (non-blocking)"""
    try:
        current_time = datetime.now().strftime("%H:%M")
        conn = sqlite3.connect('video_schedule.db')
        c = conn.cursor()
        
        # Find active schedules matching current time
        c.execute('''
            SELECT * FROM schedules 
            WHERE schedule_time = ? AND is_active = 1
        ''', (current_time,))
        
        schedules = c.fetchall()
        
        for schedule in schedules:
            schedule_id, _, file_path, file_type, title, _, _, last_played = schedule
            
            # Check if not already played this minute
            if last_played != current_time:
                # Play the video
                if file_type == 'youtube':
                    embed_url = get_youtube_embed_url(file_path)
                    set_current_video(embed_url, title, session_state)
                elif file_type == 'local':
                    # For local files, still try to open (works only locally)
                    if os.path.exists(file_path):
                        if os.name == 'nt':
                            os.startfile(file_path)
                        else:
                            os.system(f'open "{file_path}"')
                elif file_type == "html":
                    set_current_video(f'file://{os.path.abspath(file_path)}', title, session_state)
                
                # Update database with play time
                c.execute('UPDATE schedules SET last_played = ? WHERE id = ?', (current_time, schedule_id))
                conn.commit()
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Schedule check error: {e}")
        return False

# Background scheduler (legacy - kept for compatibility)
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
                        embed_url = get_youtube_embed_url(file_path)
                        set_current_video(embed_url, title)
                    elif file_type == 'local':
                        if os.path.exists(file_path):
                            os.startfile(file_path) if os.name == 'nt' else os.system(f'open "{file_path}"')
                    elif file_type == "html":
                        set_current_video(f'file://{os.path.abspath(file_path)}', title)
                    
                    # 데이터베이스에 재생 시간 업데이트
                    c.execute('UPDATE schedules SET last_played = ? WHERE id = ?', (current_time, schedule_id))
                    conn.commit()
            
            conn.close()
            
        except Exception as e:
            print(f"스케줄 체크 오류: {e}")
        
        # 30초마다 체크
        time_module.sleep(30)