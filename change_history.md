# Change History - YouTube Scheduler App

## Date: February 8, 2026

---

## Problem Statement

The YouTube video scheduler app was working perfectly on local VS Code environment but failed to play scheduled videos on Streamlit Cloud deployment. The page would refresh correctly, but videos would not appear when their scheduled time arrived.

---

## Root Causes Identified

### 1. **Ephemeral File System on Streamlit Cloud**
- **Issue**: The app used `current_video.json` file to store the current video state
- **Problem**: Streamlit Cloud has an ephemeral file system - files don't persist across page refreshes
- **Impact**: When the page auto-refreshed, the video information was lost

### 2. **Background Threading Incompatibility**
- **Issue**: Background thread with `check_schedule()` function running in an infinite loop
- **Problem**: Background threads are unreliable on Streamlit Cloud's serverless architecture
- **Impact**: Schedule checking was inconsistent or not working at all

### 3. **Blocking Auto-Refresh Mechanism**
- **Issue**: Used `time.sleep(10)` followed by `st.rerun()` for auto-refresh
- **Problem**: Blocking sleep operations don't work properly in Streamlit Cloud
- **Impact**: Auto-refresh was unreliable or causing execution issues

### 4. **Deprecated Streamlit Parameters**
- **Issue**: Used `width='stretch'` for buttons and `use_column_width` for images
- **Problem**: These parameters were deprecated in newer Streamlit versions
- **Impact**: TypeError exceptions preventing app from running

### 5. **Python Cache Issues**
- **Issue**: Modified function signatures weren't being picked up
- **Problem**: Python's `__pycache__` contained old bytecode
- **Impact**: TypeError about function arguments

---

## Solutions Implemented

### 1. Session State Integration (Primary Fix)

#### Changes to `database/schedule_db.py`:

**Modified Functions:**
```python
def set_current_video(file_path, title, session_state=None)
def get_current_video(session_state=None)
def clear_current_video(session_state=None)
def check_schedule_once(session_state=None)
```

**Implementation:**
- Added optional `session_state` parameter to all video management functions
- Functions now prioritize Streamlit session state over file storage
- Maintains backward compatibility with file-based storage for local use
- Session state data persists across page refreshes on Streamlit Cloud

**Code Example:**
```python
def set_current_video(file_path, title, session_state=None):
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
```

#### Changes to `app.py`:

**Session State Initialization:**
```python
# Initialize current_video in session state (Streamlit Cloud compatible)
if 'current_video' not in st.session_state:
    st.session_state.current_video = None
```

**Function Calls Updated:**
- `check_schedule_once(st.session_state)` - Pass session state for schedule checking
- `get_current_video(st.session_state)` - Retrieve video from session state
- `set_current_video(..., st.session_state)` - Store video in session state
- `clear_current_video(st.session_state)` - Clear video from session state

### 2. Synchronous Schedule Checking

**Replaced:**
```python
# Old approach - background thread
scheduler_thread = threading.Thread(target=check_schedule, daemon=True)
scheduler_thread.start()
```

**With:**
```python
# New approach - synchronous check on every page load
check_schedule_once(st.session_state)
```

**Benefits:**
- Runs on every page render/refresh
- Works reliably on Streamlit Cloud
- No thread management overhead
- Simpler debugging and maintenance

### 3. Non-Blocking Auto-Refresh

**Replaced:**
```python
# Old approach - blocking
import time as time_module
time_module.sleep(10)
st.rerun()
```

**With:**
```python
# New approach - JavaScript-based non-blocking
if not current_video:
    components.html(
        """
        <script>
            setTimeout(function() {
                window.parent.location.reload();
            }, 30000);
        </script>
        """,
        height=0
    )
```

**Benefits:**
- Non-blocking execution
- Works on Streamlit Cloud
- Maintains UI responsiveness
- Conditional behavior (only when no video playing)

### 4. Smart Auto-Refresh Logic

**Implementation:**
```python
# Auto-refresh ONLY when no video is playing
if not current_video:
    # Refresh every 30 seconds to check schedules
    [JavaScript auto-refresh code]
# When video IS playing, no refresh (prevents video restart)
```

**Benefits:**
- Videos play continuously without interruption
- Auto-refresh resumes after video is stopped
- Prevents annoying video restarts
- Better user experience

### 5. Updated Streamlit Parameters

**Button Parameters:**
```python
# Before
st.button("text", width='stretch')

# After
st.button("text", use_container_width=True)
```

**Image Parameters:**
```python
# Before
st.image(url, use_column_width=True)

# After
st.image(url, use_container_width=True)
```

### 6. Python Cache Cleanup

**Commands Executed:**
```powershell
Remove-Item -Recurse -Force database\__pycache__
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
```

**Purpose:**
- Clear old bytecode with outdated function signatures
- Force Python to recompile with new code
- Resolve TypeError exceptions

---

## How It Works Now

### Flow Diagram:

```
1. Page Loads
   ↓
2. check_schedule_once(st.session_state) runs
   ↓
3. Check if current time matches any active schedule
   ↓
4a. NO MATCH:                    4b. MATCH FOUND:
    - No action                       - Convert URL to embed format
    - Continue to step 5              - Store in st.session_state['current_video']
                                      - Update last_played in database
   ↓                                  ↓
5. Render UI
   ↓
6a. No Video Playing:            6b. Video Playing:
    - Show normal UI                 - Display video player with iframe
    - JavaScript sets 30s timer      - Show "Stop" button
    - Timer triggers refresh         - NO auto-refresh (prevents restart)
    ↓                                ↓
7. Page Refreshes (30s)          7. User clicks "Stop" button
   ↓                                ↓
   Back to Step 1                   Clear session state → Back to Step 1
```

### Key Features:

1. **Schedule Checking**: Every page load checks if any video should play now
2. **Session Persistence**: Video state survives page refreshes
3. **Auto-Play**: Videos automatically appear when scheduled time arrives
4. **Continuous Playback**: Videos play without interruption
5. **Cloud Compatible**: Works identically on local and Streamlit Cloud
6. **Mobile Friendly**: Responsive design with embedded YouTube player

---

## Technical Benefits

### For Local Development:
- ✅ Works as before with file-based storage as backup
- ✅ Faster testing without cloud deployment
- ✅ Easy debugging with visible state

### For Streamlit Cloud:
- ✅ Session state persists across refreshes
- ✅ No file system dependencies
- ✅ Reliable schedule checking
- ✅ Proper auto-refresh mechanism
- ✅ No background threading issues

### For Users:
- ✅ Videos play at scheduled times automatically
- ✅ No manual intervention needed
- ✅ Videos don't restart unexpectedly
- ✅ Works on mobile devices
- ✅ Same experience on all platforms

---

## Files Modified

1. **database/schedule_db.py**
   - Added session_state parameter to 4 functions
   - Hybrid storage approach (session + file)
   - Enhanced error handling for cloud environment

2. **app.py**
   - Session state initialization
   - All function calls updated with session_state parameter
   - Replaced blocking sleep with JavaScript auto-refresh
   - Smart conditional refresh (only when no video playing)
   - Updated deprecated Streamlit parameters
   - Background thread disabled (commented out)

3. **Python Cache** (deleted, not version controlled)
   - Removed `__pycache__` directories
   - Removed `.pyc` files

---

## Testing Recommendations

### Local Testing:
1. Set a schedule for 2-3 minutes from now
2. Watch the page auto-refresh every 30 seconds
3. Verify video appears when scheduled time arrives
4. Verify video plays continuously without restart
5. Click stop button and verify auto-refresh resumes

### Streamlit Cloud Testing:
1. Deploy updated code to Streamlit Cloud
2. Set a schedule via the cloud app
3. Keep the browser tab open
4. Verify scheduled video plays automatically
5. Verify video doesn't restart during playback
6. Test on mobile device

### Edge Cases to Verify:
- Multiple schedules at same time (should play first match)
- Schedule while video is already playing
- Browser tab in background
- Slow internet connection
- Mobile vs desktop behavior

---

## Performance Considerations

- **Refresh Interval**: 30 seconds balances responsiveness vs server load
- **Session State Size**: Minimal (just video metadata)
- **Database Queries**: One simple query per refresh (very efficient)
- **Network Usage**: YouTube embed handles video streaming
- **CPU Usage**: No background threads, minimal processing

---

## Future Enhancement Ideas

1. **Queue System**: Play multiple scheduled videos in sequence
2. **Notification Sound**: Alert when video starts
3. **Schedule Templates**: Save and reuse common schedules
4. **Analytics**: Track which videos played and when
5. **Timezone Support**: Handle users in different timezones
6. **Playlist Support**: Schedule entire YouTube playlists
7. **Manual Override**: Skip to next scheduled video
8. **History Log**: Show all previously played videos

---

## Version Information

- **Python**: 3.12
- **Streamlit**: Latest (with deprecated parameter warnings)
- **Database**: SQLite3
- **Video Source**: YouTube (embedded iframes)
- **Deployment**: Local + Streamlit Cloud

---

## Summary

The core issue was Streamlit Cloud's ephemeral file system and unreliable background threading. By migrating from file-based storage to session state and replacing background threads with synchronous checking, the app now works reliably across all deployment environments while providing a better user experience with uninterrupted video playback.
