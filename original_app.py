import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import pandas as pd
from datetime import datetime, time
import threading
import time as time_module
import os
import json
import re
import scrapetube

from database.schedule_db import (
    init_db, 
    add_schedule, 
    get_schedules,
    delete_schedule, 
    update_schedule, 
    toggle_schedule,
    is_youtube_url,
    get_current_video,
    clear_current_video,
    set_current_video,
    check_schedule_once)

# 페이지 설정
st.set_page_config(page_title="비디오 스케줄러", page_icon="🎬", layout="wide")

# Helper function to extract YouTube video ID
def extract_youtube_id(url):
    youtube_regex = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None


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
                        # Use embedded player for Streamlit Cloud
                        set_current_video(file_path, title)
                    elif file_type == 'local':
                        if os.path.exists(file_path):
                            if os.name == 'nt':
                                os.startfile(file_path)
                            else:
                                os.system(f'open "{file_path}"')
                    elif file_type == "html":
                        # Use embedded display for HTML files
                        set_current_video(f'file://{os.path.abspath(file_path)}', title)
                    
                    # 데이터베이스에 재생 시간 업데이트
                    c.execute('UPDATE schedules SET last_played = ? WHERE id = ?', (current_time, schedule_id))
                    conn.commit()
            
            conn.close()
            
        except Exception as e:
            print(f"스케줄 체크 오류: {e}")
        
        # 30초마다 체크
        time_module.sleep(30)

# 세션 상태 초기화
if 'scheduler_started' not in st.session_state:
    st.session_state.scheduler_started = False
    init_db()
    
    # 백그라운드 스케줄러 시작
    scheduler_thread = threading.Thread(target=check_schedule, daemon=True)
    scheduler_thread.start()
    st.session_state.scheduler_started = True
    # Sets a flag to prevent creating multiple threads. 
    # Without this, every time Streamlit reruns (which happens often), 
    # it would create a new scheduler thread, leading to duplicates.
# Initialize current_video in session state (Streamlit Cloud compatible)
if 'current_video' not in st.session_state:
    st.session_state.current_video = None    

# 편집 모드 세션 상태 초기화
if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None

# YouTube 검색 세션 상태 초기화
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'selected_video' not in st.session_state:
    st.session_state.selected_video = None

# UI
st.title("🎬 비디오 스케줄러")

# Check if there's a current video to play
current_video = get_current_video()
if current_video:
    # Handle both old format (url) and new format (file_path)
    video_url = current_video.get('file_path') or current_video.get('url', '')
    video_title = current_video.get('title', 'Unknown Video')
    
    st.success(f"▶️ 현재 재생 중: {video_title}")
    video_id = extract_youtube_id(video_url)
    if video_id:
        # Embed YouTube video with autoplay
        youtube_embed = f"""
        <iframe width="100%" height="500" 
                src="https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0" 
                frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowfullscreen>
        </iframe>
        """
        components.html(youtube_embed, height=500)
        
        if st.button("⏹️ 재생 중지"):
            clear_current_video()
            st.rerun()
    else:
        st.error("유효하지 않은 YouTube URL입니다.")
        if st.button("⏹️ 닫기"):
            clear_current_video()
            st.rerun()

st.markdown("---")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["🔍 YouTube 검색", "📅 스케줄 추가", "📋 스케줄 목록"])

with tab1:
    st.header("YouTube 비디오 검색")
    
    # 검색 입력
    search_col1, search_col2 = st.columns([4, 1])
    with search_col1:
        search_query = st.text_input("검색어를 입력하세요", placeholder="예: 요가 운동", key="youtube_search")
    with search_col2:
        st.write("")
        st.write("")
        search_button = st.button("🔍 검색", type="primary", use_container_width=True)
    
    # 검색 실행
    if search_button and search_query:
        with st.spinner("검색 중..."):
            try:
                # scrapetube를 사용하여 YouTube 검색
                videos = scrapetube.get_search(search_query, limit=10)
                results = []
                
                for video in videos:
                    video_id = video.get('videoId')
                    if video_id:
                        video_data = {
                            'title': video.get('title', {}).get('runs', [{}])[0].get('text', 'No Title'),
                            'link': f'https://www.youtube.com/watch?v={video_id}',
                            'videoId': video_id,
                            'thumbnails': [{'url': f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'}],
                            'channel': {
                                'name': video.get('longBylineText', {}).get('runs', [{}])[0].get('text', 'Unknown')
                            },
                            'duration': video.get('lengthText', {}).get('simpleText', 'N/A'),
                            'viewCount': {
                                'short': video.get('shortViewCountText', {}).get('simpleText', 'N/A')
                            }
                        }
                        results.append(video_data)
                
                st.session_state.search_results = results
                st.success(f"✅ {len(st.session_state.search_results)}개의 결과를 찾았습니다!")
            except Exception as e:
                st.error(f"검색 중 오류가 발생했습니다: {e}")
                st.session_state.search_results = []
    
    # 검색 결과 표시
    if st.session_state.search_results:
        st.markdown("---")
        st.subheader("검색 결과")
        
        for idx, video in enumerate(st.session_state.search_results):
            with st.container():
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    # 썸네일 표시
                    thumbnail_url = video['thumbnails'][0]['url'] if video.get('thumbnails') else ""
                    if thumbnail_url:
                        st.image(thumbnail_url, use_container_width=True)
                
                with col2:
                    # 제목과 정보
                    st.markdown(f"**{video['title']}**")
                    st.caption(f"👤 {video.get('channel', {}).get('name', 'Unknown')}")
                    st.caption(f"⏱️ {video.get('duration', 'N/A')} | 👁️ {video.get('viewCount', {}).get('short', 'N/A')}")
                    
                    # URL 표시
                    video_url = video['link']
                    st.text(f"URL: {video_url}")
                    
                    # 버튼들 (재생, 선택)
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button(f"▶️ 재생", key=f"play_{idx}", type="primary"):
                            # Set as current video to play in the app
                            set_current_video(video_url, video['title'])
                            st.rerun()
                    with btn_col2:
                        if st.button(f"➕ 스케줄 추가", key=f"select_{idx}", type="secondary"):
                            st.session_state.selected_video = video
                
                # 선택된 비디오에 대한 스케줄 추가 폼
                if st.session_state.selected_video and st.session_state.selected_video['link'] == video['link']:
                    with st.expander("⏰ 스케줄 설정", expanded=True):
                        st.info(f"선택된 비디오: {video['title']}")
                        
                        schedule_col1, schedule_col2 = st.columns(2)
                        with schedule_col1:
                            schedule_title = st.text_input(
                                "스케줄 제목", 
                                value=video['title'][:50],
                                key=f"schedule_title_{idx}"
                            )
                        with schedule_col2:
                            schedule_time_input = st.text_input(
                                "재생 시간 (HH:MM)", 
                                value="12:00",
                                help="24시간 형식으로 입력",
                                key=f"schedule_time_{idx}"
                            )
                        
                        button_col1, button_col2 = st.columns(2)
                        with button_col1:
                            if st.button("✅ 스케줄 추가", key=f"add_schedule_{idx}", type="primary", use_container_width=True):
                                if schedule_title and schedule_time_input:
                                    add_schedule(schedule_time_input, video_url, "youtube", schedule_title)
                                    st.success(f"✅ '{schedule_title}' 스케줄이 {schedule_time_input}에 추가되었습니다!")
                                    st.session_state.selected_video = None
                                    time_module.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("⚠️ 제목과 시간을 모두 입력해주세요.")
                        
                        with button_col2:
                            if st.button("❌ 취소", key=f"cancel_schedule_{idx}", use_container_width=True):
                                st.session_state.selected_video = None
                                st.rerun()
                
                st.markdown("---")
    else:
        st.info("🔍 검색어를 입력하고 검색 버튼을 클릭하세요.")

with tab2:
    st.header("새 스케줄 추가")
    
    col1, col2 = st.columns(2)
    
    with col1:
        title = st.text_input("제목", placeholder="예: 아침의 조용한 영상", key="title_input")
        schedule_time = st.text_input("재생 시간", value="12:00", help="HH:MM 형식으로 입력 (24시간제)", key="schedule_time_input")
        
    with col2:
        file_type = st.radio("파일 유형", ["YouTube URL", "로컬 파일", "html"], horizontal=True)
        
        if file_type == "YouTube URL":
            file_path = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
        elif file_type == "local":
            file_path = st.text_input("파일 경로", placeholder="C:/videos/video.mp4")
        elif file_type == "html":
            file_path = st.text_input("HTML 파일 경로", placeholder="C:/path/to/file.html")
    
    if st.button("➕ 스케줄 추가", type="primary", use_container_width=True):
        if title and file_path:
            time_str = schedule_time
            f_type = "youtube" if file_type == "YouTube URL" else "local" if file_type == "로컬 파일" else "html"
            
            # 유효성 검사
            valid = True
            if f_type == "youtube" and not is_youtube_url(file_path):
                st.error("⚠️ 유효한 YouTube URL을 입력해주세요.")
                valid = False
            elif f_type == "local" and not os.path.exists(file_path):
                st.warning("⚠️ 파일이 존재하지 않습니다. 경로를 확인해주세요.")
            
            if valid:
                add_schedule(time_str, file_path, f_type, title)
                st.success(f"✅ '{title}' 스케줄이 {time_str}에 추가되었습니다!")
                st.rerun()
        else:
            st.error("⚠️ 제목과 파일 경로를 모두 입력해주세요.")

with tab3:
    st.header("등록된 스케줄")
    
    # 현재 시간 표시
    current_time = datetime.now().strftime("%H:%M:%S")
    st.info(f"🕐 현재 시간: {current_time}")
    
    schedules_df = get_schedules()
    
    if not schedules_df.empty:
        for idx, row in schedules_df.iterrows():
            with st.container():
                # 편집 모드인 경우
                if st.session_state.editing_id == row['id']:
                    st.subheader(f"✏️ {row['title']} 편집")
                    
                    edit_col1, edit_col2 = st.columns(2)
                    
                    with edit_col1:
                        edit_title = st.text_input("제목", value=row['title'], key=f"edit_title_{row['id']}")
                        edit_time = st.text_input("재생 시간", value=row['schedule_time'], key=f"edit_time_{row['id']}")
                    
                    with edit_col2:
                        current_file_type = "YouTube URL" if row['file_type'] == 'youtube' else "로컬 파일"
                        edit_file_type = st.radio("파일 유형", ["YouTube URL", "로컬 파일"], 
                                                  index=0 if row['file_type'] == 'youtube' else 1,
                                                  key=f"edit_type_{row['id']}", horizontal=True)
                        edit_file_path = st.text_input("파일 경로/URL", value=row['file_path'], key=f"edit_path_{row['id']}")
                    
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("💾 저장", key=f"save_{row['id']}", use_container_width=True, type="primary"):
                            f_type = "youtube" if edit_file_type == "YouTube URL" else "local"
                            
                            # 유효성 검사
                            valid = True
                            if f_type == "youtube" and not is_youtube_url(edit_file_path):
                                st.error("⚠️ 유효한 YouTube URL을 입력해주세요.")
                                valid = False
                            elif f_type == "local" and not os.path.exists(edit_file_path):
                                st.warning("⚠️ 파일이 존재하지 않습니다. 경로를 확인해주세요.")
                            
                            if valid:
                                update_schedule(row['id'], edit_time, edit_file_path, f_type, edit_title)
                                st.session_state.editing_id = None
                                st.success(f"✅ '{edit_title}' 스케줄이 수정되었습니다!")
                                st.rerun()
                    
                    with btn_col2:
                        if st.button("❌ 취소", key=f"cancel_{row['id']}", use_container_width=True):
                            st.session_state.editing_id = None
                            st.rerun()
                
                # 일반 표시 모드
                else:
                    col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 1, 1, 1])
                    
                    with col1:
                        status = "🟢" if row['is_active'] else "🔴"
                        st.write(f"{status} **{row['title']}**")
                    
                    with col2:
                        st.write(f"🕐 {row['schedule_time']}")
                    
                    with col3:
                        file_type_display = "📺 YouTube" if row['file_type'] == 'youtube' else "📁 로컬"
                        st.write(file_type_display)
                    
                    with col4:
                        if st.button("🔄" if row['is_active'] else "▶️", key=f"toggle_{row['id']}"):
                            new_status = 0 if row['is_active'] else 1
                            toggle_schedule(row['id'], new_status)
                            st.rerun()
                    
                    with col5:
                        if st.button("✏️", key=f"edit_{row['id']}"):
                            st.session_state.editing_id = row['id']
                            st.rerun()
                    
                    with col6:
                        if st.button("🗑️", key=f"delete_{row['id']}"):
                            delete_schedule(row['id'])
                            st.rerun()
                    
                    with st.expander("상세 정보"):
                        st.text(f"파일 경로: {row['file_path']}")
                        st.text(f"등록일: {row['created_at']}")
                
                st.markdown("---")
    else:
        st.info("📝 등록된 스케줄이 없습니다. '스케줄 추가' 탭에서 새 스케줄을 추가해보세요!")

# 사이드바
with st.sidebar:
    st.header("ℹ️ 사용 방법")
    st.markdown("""
    **YouTube 검색 (신규!):**
    1. **YouTube 검색** 탭에서 검색어 입력
    2. 검색 결과에서 원하는 비디오 선택
    3. 재생 시간 설정 후 스케줄 추가
    
    **직접 추가:**
    1. **스케줄 추가** 탭에서 재생할 시간과 비디오를 설정
    2. YouTube URL 또는 로컬 파일 경로 입력
    3. 설정한 시간이 되면 자동으로 재생됩니다
    
    **참고사항:**
    - 백그라운드에서 30초마다 스케줄을 체크합니다
    - 🟢 활성화된 스케줄만 재생됩니다
    - YouTube 비디오는 앱 내에서 자동 재생됩니다
    - 스케줄 시간이 되면 페이지 클릭/새로고침 시 자동 재생
    - 수동 새로고침 버튼으로 언제든지 확인 가능
    """)
    
    st.markdown("---")
    st.info(f"🟢 스케줄러 실행 중")
    
    if st.button("🔄 새로고침"):
        st.rerun()
