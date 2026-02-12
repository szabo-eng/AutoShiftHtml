"""
מערכת שיבוץ מבצעית 2026 - גרסה מודולרית מלאה
עם הפרדה מלאה של HTML, CSS ו-Python
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
import sys

# Firebase - אופציונלי
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase not available - running without database support")

# הוסף את תיקיית components ל-path
sys.path.insert(0, str(Path(__file__).parent / 'components'))

from html_templates import TemplateManager, ShiftComponents

# הגדרות לוגים
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# קבועים
REQUIRED_REQUEST_COLUMNS = ['שם', 'תאריך מבוקש', 'משמרת', 'תחנה']
REQUIRED_SHIFT_COLUMNS = ['תחנה', 'משמרת', 'סוג תקן']
DAYS_HEB = {
    'Sunday': 'ראשון', 'Monday': 'שני', 'Tuesday': 'שלישי',
    'Wednesday': 'רביעי', 'Thursday': 'חמישי', 'Friday': 'שישי', 'Saturday': 'שבת'
}
DATE_FORMATS = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']

# הגדרות דף
st.set_page_config(
    page_title="מערכת שיבוץ מבצעית 2026", 
    page_icon="📅", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# אתחול Template Manager
try:
    from html_templates import TemplateManager, ShiftComponents
    template_manager = TemplateManager()
    html_components = ShiftComponents(template_manager)
    logger.info("Template system initialized successfully")
except Exception as e:
    logger.warning(f"Template system not available: {e}")
    html_components = None


# טעינת CSS
def load_css():
    """טעינת קובץ CSS חיצוני"""
    css_path = Path(__file__).parent / "assets" / "style.css"
    
    if css_path.exists():
        with open(css_path, 'r', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        logger.info("CSS loaded from external file")
    else:
        # CSS fallback
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800&family=Rubik:wght@400;500;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Heebo', sans-serif; }
        [data-testid="stAppViewContainer"] { direction: rtl !important; background: linear-gradient(135deg, #faf8f5 0%, #f4f1ed 100%); }
        h1 { font-family: 'Rubik', sans-serif !important; font-weight: 800 !important;
             background: linear-gradient(135deg, #1a4d7a 0%, #2e6ba8 100%);
             -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important; }
        .day-header { background: linear-gradient(135deg, #1a4d7a 0%, #2e6ba8 100%);
                      color: white; padding: 1.5rem 1rem; border-radius: 12px 12px 0 0;
                      text-align: center; margin-bottom: 0.5rem; }
        .day-name { font-size: 1.2rem; font-weight: 700; display: block; margin-bottom: 0.25rem; }
        .shift-mini { background: linear-gradient(135deg, #fff 0%, #f9f9f9 100%);
                      padding: 1rem; border-radius: 8px; border-right: 5px solid #1a4d7a;
                      margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .shift-mini:hover { transform: translateX(-3px); }
        .shift-mini.atan { border-right-color: #e67e22; }
        .shift-top { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
        .shift-title { font-weight: 700; color: #1a4d7a; }
        .shift-status { padding: 0.5rem; border-radius: 6px; font-weight: 600; margin-bottom: 0.5rem; }
        .status-assigned { background: rgba(39, 174, 96, 0.1); color: #27ae60; }
        .status-empty { background: rgba(231, 76, 60, 0.1); color: #e74c3c; }
        .status-cancelled { background: rgba(127, 140, 141, 0.1); color: #7f8c8d; }
        </style>
        """, unsafe_allow_html=True)
        logger.warning("Using embedded CSS")

load_css()


# Firebase
def initialize_firebase():
    """אתחול Firebase (אופציונלי)"""
    if not FIREBASE_AVAILABLE:
        logger.warning("Firebase library not installed")
        return None
    
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.warning(f"Firebase not available: {e}")
            return None
    return firestore.client()

db = initialize_firebase()


# פונקציות עזר
def parse_date_safe(date_str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"פורמט תאריך לא תקין: {date_str}")


def get_day_name(date_str):
    try:
        return DAYS_HEB.get(parse_date_safe(date_str).strftime('%A'), "")
    except:
        return ""


def validate_dataframes(req_df, shi_df):
    errors = []
    if set(REQUIRED_REQUEST_COLUMNS) - set(req_df.columns):
        errors.append("❌ עמודות חסרות בקובץ בקשות")
    if set(REQUIRED_SHIFT_COLUMNS) - set(shi_df.columns):
        errors.append("❌ עמודות חסרות בתבנית משמרות")
    return errors


def get_atan_column(df):
    cols = [c for c in df.columns if "אט" in c and "מורשה" in c]
    return cols[0] if cols else None


@st.cache_data(ttl=60)
def get_balance():
    scores = {}
    try:
        if db:
            for doc in db.collection('employee_history').stream():
                scores[doc.id] = doc.to_dict().get('total_shifts', 0)
    except:
        pass
    return scores


def auto_assign(dates, shi_df, req_df, balance):
    temp_schedule, temp_assigned = {}, {d: set() for d in dates}
    running_balance = balance.copy()
    atan_col = get_atan_column(req_df)
    
    for date_str in dates:
        for idx, shift_row in shi_df.iterrows():
            shift_key = f"{date_str}_{shift_row['תחנה']}_{shift_row['משמרת']}_{idx}"
            if shift_key in st.session_state.cancelled_shifts:
                continue
            
            potential = req_df[
                (req_df['תאריך מבוקש'] == date_str) &
                (req_df['משמרת'] == shift_row['משמרת']) &
                (req_df['תחנה'] == shift_row['תחנה']) &
                (~req_df['שם'].isin(temp_assigned[date_str]))
            ].copy()
            
            if "אט" in str(shift_row['סוג תקן']) and atan_col:
                potential = potential[potential[atan_col] == 'כן']
            
            if not potential.empty:
                potential['score'] = potential['שם'].map(lambda x: running_balance.get(x, 0))
                best = potential.sort_values('score').iloc[0]['שם']
                temp_schedule[shift_key] = best
                temp_assigned[date_str].add(best)
                running_balance[best] = running_balance.get(best, 0) + 1
    
    return temp_schedule, temp_assigned


@st.dialog("שיבוץ עובד למשמרת")
def show_assignment_dialog(shift_key, date_str, station, shift_type, req_df, balance, shi_df):
    st.markdown(f"### {get_day_name(date_str)} - {date_str}")
    st.write(f"**{station}** | **{shift_type}**")
    
    if not isinstance(st.session_state.assigned_today, dict):
        st.session_state.assigned_today = {}
    
    already_working = st.session_state.assigned_today.get(date_str, set())
    candidates = req_df[
        (req_df['תאריך מבוקש'] == date_str) &
        (req_df['משמרת'] == shift_type) &
        (req_df['תחנה'] == station) &
        (~req_df['שם'].isin(already_working))
    ].copy()
    
    # בדיקת אטן
    shift_row = None
    for idx, s in shi_df.iterrows():
        test_key = f"{date_str}_{s['תחנה']}_{s['משמרת']}_{idx}"
        if test_key == shift_key:
            shift_row = s
            break
    
    if shift_row is not None and "אט" in str(shift_row['סוג תקן']):
        atan_col = get_atan_column(req_df)
        if atan_col:
            candidates = candidates[candidates[atan_col] == 'כן']
    
    if candidates.empty:
        st.warning("😕 אין מועמדים פנויים")
        if st.button("סגור", type="secondary", use_container_width=True):
            st.rerun()
    else:
        candidates['balance'] = candidates['שם'].map(lambda x: balance.get(x, 0))
        candidates = candidates.sort_values('balance')
        
        selected = st.radio(
            "בחר עובד:",
            options=candidates['שם'].tolist(),
            format_func=lambda x: f"👤 {x} (מאזן: {balance.get(x, 0)})",
            key=f"radio_{shift_key}"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ אישור", type="primary", use_container_width=True):
                st.session_state.final_schedule[shift_key] = selected
                if date_str not in st.session_state.assigned_today:
                    st.session_state.assigned_today[date_str] = set()
                st.session_state.assigned_today[date_str].add(selected)
                st.success(f"✅ {selected} שובץ/ה!")
                st.rerun()
        with col2:
            if st.button("❌ ביטול", use_container_width=True):
                st.rerun()


# פונקציית עזר ליצירת HTML של משמרת
def render_shift_card(shift_row, date_str, idx, assigned, cancelled):
    """יוצר HTML של כרטיס משמרת באמצעות התבניות"""
    is_atan = "אט" in str(shift_row['סוג תקן'])
    
    # בחר סטטוס
    if cancelled:
        status_html = html_components.status_cancelled() if html_components else '<div class="shift-status status-cancelled">🚫 מבוטל</div>'
    elif assigned:
        status_html = html_components.status_assigned(assigned) if html_components else f'<div class="shift-status status-assigned">👤 {assigned}</div>'
    else:
        status_html = html_components.status_empty() if html_components else '<div class="shift-status status-empty">⚠️ חסר</div>'
    
    # צור כרטיס
    if html_components:
        return html_components.shift_card(
            shift_type=shift_row['משמרת'],
            shift_category=shift_row['סוג תקן'],
            station=shift_row['תחנה'],
            status_html=status_html,
            is_atan=is_atan
        )
    else:
        # Fallback ללא templates
        atan_class = 'atan' if is_atan else ''
        return f'''
        <div class="shift-mini {atan_class}">
            <div class="shift-top">
                <div class="shift-title">{shift_row['משמרת']}</div>
                <div class="shift-badge">{shift_row['סוג תקן']}</div>
            </div>
            <div class="shift-station">{shift_row['תחנה']}</div>
            {status_html}
        </div>
        '''


# Session State
if 'final_schedule' not in st.session_state:
    st.session_state.final_schedule = {}
if 'assigned_today' not in st.session_state:
    st.session_state.assigned_today = {}
if 'cancelled_shifts' not in st.session_state:
    st.session_state.cancelled_shifts = set()


# Sidebar
with st.sidebar:
    st.markdown("# ⚙️ ניהול מערכת")
    
    st.markdown("### 📁 קבצים")
    req_file = st.file_uploader("בקשות עובדים", type=['csv'])
    shi_file = st.file_uploader("תבנית משמרות", type=['csv'])
    
    st.divider()
    
    if req_file and shi_file:
        if st.button("🪄 שיבוץ אוטומטי", type="primary", use_container_width=True):
            st.session_state.trigger_auto = True
            st.rerun()
    
    if st.session_state.final_schedule:
        if st.button("💾 שמירה", type="primary", use_container_width=True):
            st.success("✅ נשמר!")
        
        if st.button("📥 ייצוא", use_container_width=True):
            export_data = []
            for shift_key, employee in st.session_state.final_schedule.items():
                parts = shift_key.split('_')
                export_data.append({'תאריך': parts[0], 'תחנה': parts[1], 'משמרת': parts[2], 'עובד': employee})
            csv = pd.DataFrame(export_data).to_csv(index=False, encoding='utf-8-sig')
            st.download_button("⬇️ הורד", csv, f"shibutz_{datetime.now().strftime('%Y%m%d')}.csv", 
                             mime="text/csv", use_container_width=True)
    
    if st.button("🧹 איפוס", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    
    if st.session_state.final_schedule:
        st.markdown("### 📊 סטטיסטיקות")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("משמרות", len(st.session_state.final_schedule))
        with c2:
            st.metric("עובדים", len(set(st.session_state.final_schedule.values())))


# Main
st.title("📅 לוח שיבוצים")

if req_file and shi_file:
    try:
        req_df = pd.read_csv(req_file, encoding='utf-8-sig')
        shi_df = pd.read_csv(shi_file, encoding='utf-8-sig')
        
        errors = validate_dataframes(req_df, shi_df)
        if errors:
            for e in errors: st.error(e)
            st.stop()
        
        dates = sorted(req_df['תאריך מבוקש'].unique(), key=parse_date_safe)
        balance = get_balance()
        
        # שיבוץ אוטומטי
        if st.session_state.get('trigger_auto'):
            with st.spinner('מבצע שיבוץ...'):
                temp_schedule, temp_assigned = auto_assign(dates, shi_df, req_df, balance)
                st.session_state.final_schedule, st.session_state.assigned_today = temp_schedule, temp_assigned
                st.session_state.trigger_auto = False
            st.success(f"✅ {len(st.session_state.final_schedule)} משמרות שובצו")
            st.rerun()
        
        # מדדים
        if st.session_state.final_schedule:
            total = len(shi_df) * len(dates) - len(st.session_state.cancelled_shifts)
            assigned = len(st.session_state.final_schedule)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("סך משמרות", total)
            c2.metric("משובצות", assigned)
            c3.metric("חסרות", total - assigned)
            c4.metric("השלמה", f"{assigned/total*100:.0f}%" if total > 0 else "0%")
        
        st.markdown("---")
        
        # לוח שיבוץ - כותרות
        header_cols = st.columns(7)
        for i, d in enumerate(dates[:7]):
            with header_cols[i]:
                # שימוש בתבנית HTML
                if html_components:
                    header_html = html_components.day_header(get_day_name(d), d)
                else:
                    header_html = f'<div class="day-header"><span class="day-name">{get_day_name(d)}</span><span class="day-date">{d}</span></div>'
                
                st.markdown(header_html, unsafe_allow_html=True)
        
        # משמרות
        for idx in range(len(shi_df)):
            shift_cols = st.columns(7)
            s = shi_df.iloc[idx]
            
            for i, d in enumerate(dates[:7]):
                with shift_cols[i]:
                    key = f"{d}_{s['תחנה']}_{s['משמרת']}_{idx}"
                    assigned = st.session_state.final_schedule.get(key)
                    cancelled = key in st.session_state.cancelled_shifts
                    
                    # שימוש בפונקציה ליצירת HTML
                    shift_html = render_shift_card(s, d, idx, assigned, cancelled)
                    st.markdown(shift_html, unsafe_allow_html=True)
                    
                    # כפתורי פעולה
                    if cancelled:
                        if st.button("🔄 שחזר", key=f"restore_{key}", use_container_width=True):
                            st.session_state.cancelled_shifts.remove(key)
                            st.rerun()
                    elif assigned:
                        if st.button("🗑️ הסר", key=f"remove_{key}", use_container_width=True):
                            del st.session_state.final_schedule[key]
                            if d in st.session_state.assigned_today:
                                st.session_state.assigned_today[d].discard(assigned)
                            st.rerun()
                    else:
                        ca, cb = st.columns([3, 1])
                        with ca:
                            if st.button("➕ שבץ", key=f"add_{key}", use_container_width=True):
                                show_assignment_dialog(key, d, s['תחנה'], s['משמרת'], req_df, balance, shi_df)
                        with cb:
                            if st.button("🚫", key=f"cancel_{key}"):
                                st.session_state.cancelled_shifts.add(key)
                                st.rerun()
    
    except Exception as e:
        st.error(f"❌ {str(e)}")
        logger.error(f"Error: {e}", exc_info=True)

else:
    st.info("👈 העלה קבצים להתחלה")
    
    with st.expander("📖 הוראות"):
        st.markdown("""
        ### 🚀 מערכת מודולרית משופרת!
        
        **מבנה הפרויקט:**
        - `app.py` - לוגיקה עסקית
        - `assets/style.css` - עיצוב
        - `templates/*.html` - תבניות HTML
        - `components/html_templates.py` - מנהל תבניות
        
        **שימוש:**
        1. העלה קבצים
        2. שבץ אוטומטית
        3. התאם ידנית
        4. שמור/ייצא
        """)
