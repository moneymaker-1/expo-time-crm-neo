import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import re

# ==========================================
#              إعدادات النظام (الأصلية)
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢")

# قائمة الدول العربية للتحديث الجديد
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "المغرب (+212)": "212"
}

# تتبع وقت الدخول للميزة الجديدة
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'login_time' not in st.session_state: st.session_state['login_time'] = None

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    # الجدول الأصلي
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد')''')
    # جدول السجل
    c.execute('''CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer_name TEXT, 
        updated_status TEXT, changed_by TEXT, notes TEXT, timestamp TEXT)''')
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, real_name TEXT)''')
    # جديد: جدول مدة الاستخدام
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, login_time TEXT, logout_time TEXT, duration_mins REAL)''')
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '1234', 'admin', 'المدير العام'))
    conn.commit()
    return conn

conn = init_db()

# ==========================================
#           دوال التحقق المضافة
# ==========================================

def is_duplicate_company(new_name):
    """منع تكرار الأسماء المتشابهة"""
    existing = pd.read_sql("SELECT company_name FROM customers", conn)['company_name'].tolist()
    new_t = set(re.findall(r'\w+', new_name.lower()))
    for ex in existing:
        if new_t.issubset(set(re.findall(r'\w+', ex.lower()))): return True, ex
    return False, None

def validate_intl_mobile(country_code, number):
    """التحقق الدولي المضاف"""
    clean_n = re.sub(r'\D', '', number)
    if country_code == "966":
        if clean_n.startswith('0'): clean_n = clean_n[1:]
        return len(clean_n) == 9 and clean_n.startswith('5'), clean_n
    return len(clean_n) >= 7, clean_n

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Expo Time CRM")
        user = st.text_input("اسم المستخدم")
        pw = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
            acc = c.fetchone()
            if acc:
                st.session_state.update({'logged_in': True, 'user_role': acc[2], 'real_name': acc[3], 'username': user, 'login_time': datetime.now()})
                conn.execute("INSERT INTO user_sessions (username, login_time) VALUES (?,?)", (user, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                st.rerun()
            else: st.error("بيانات خاطئة")
else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج":
            if st.session_state['login_time']:
                duration = (datetime.now() - st.session_state['login_time']).seconds / 60
                conn.execute("UPDATE user_sessions SET logout_time=?, duration_mins=? WHERE username=? AND logout_time IS NULL", 
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(duration, 2), st.session_state['username']))
                conn.commit()
            st.session_state.clear(); st.rerun()

    # بوابة المبيعات (مع البحث التلقائي وزر الواتساب)
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المتابعة")
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(st.session_state['real_name'],))
        if not my_data.empty:
            search = st.text_input("🔎 ابحث في عملائك:")
            df_f = my_data[my_data['company_name'].str.contains(search, case=False)] if search else my_data
            sid = st.selectbox("اختر العميل:", df_f['id'], format_func=lambda x: df_f[df_f['id']==x]['company_name'].values[0])
            row = my_data[my_data['id']==sid].iloc[0]
            
            c1, c2 = st.columns(2)
            with c1:
                st.info(f"الشركة: {row['company_name']}\n\nالجوال: {row['mobile']}")
                st.link_button("💬 مراسلة واتساب", f"https://wa.me/{row['mobile'].replace('+', '')}")
            with c2:
                with st.form("up"):
                    ns = st.selectbox("الحالة", ["جديد", "تم الاتصال", "تم التعميد", "تم الرفض"])
                    if st.form_submit_button("حفظ"):
                        conn.execute("UPDATE customers SET status=? WHERE id=?", (ns, sid))
                        conn.commit(); st.rerun()

    # لوحة المدير (مع تقرير مدة الاستخدام المضاف)
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات المدير")
        t1, t2 = st.tabs(["الإحصائيات", "⏱️ سجل استخدام المناديب"])
        with t2:
            st.subheader("سجل نشاط الموظفين")
            sessions = pd.read_sql("SELECT username as 'الموظف', login_time as 'الدخول', duration_mins as 'المدة (دقيقة)' FROM user_sessions", conn)
            st.dataframe(sessions, use_container_width=True)
