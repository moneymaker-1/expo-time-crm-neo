import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import re 

# ==========================================
#              إعدادات النظام
# ==========================================

st.set_page_config(
    page_title="Expotime CRM", 
    layout="wide", 
    page_icon="🏢",
    initial_sidebar_state="expanded" 
)

# قائمة الدول العربية للتحديث الجديد
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "الأردن (+962)": "962", "المغرب (+212)": "212"
}

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None
if 'login_time' not in st.session_state: st.session_state['login_time'] = None

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    # الجدول الأصلي مع إضافة عمود مبلغ التعميد
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد', contract_amount REAL DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer_name TEXT, 
        updated_status TEXT, changed_by TEXT, notes TEXT, timestamp TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, real_name TEXT)''')
    
    # جديد: جدول سجل مدة الاستخدام
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, login_time TEXT, logout_time TEXT, duration_mins REAL)''')
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '1234', 'admin', 'المدير العام'))
    conn.commit()
    return conn

conn = init_db()
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# ==========================================
#           دوال التحقق (Logic)
# ==========================================

def check_duplicate_info(comp_name, mob):
    """منع التكرار الذكي"""
    c = conn.cursor()
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة', '', comp_name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"الشركة مسجلة باسم ({res[0]}) مع المندوب: {res[1]}"
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"رقم الجوال ({mob}) مسجل مع المندوب: {res[1]}"
    return None

def validate_intl_mobile(country_code, number):
    """التحقق من صحة الرقم دولياً"""
    clean_n = re.sub(r'\D', '', number)
    if country_code == "966": # السعودية
        if clean_n.startswith('0'): clean_n = clean_n[1:]
        return len(clean_n) == 9 and clean_n.startswith('5'), clean_n
    return len(clean_n) >= 7, clean_n

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    st.title("🔐 Expo Time CRM")
    choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
    user = st.text_input("اسم المستخدم")
    pw = st.text_input("كلمة المرور", type="password")
    if st.button("تأكيد"):
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (user, pw))
        account = c.fetchone()
        if account:
            st.session_state.update({'logged_in': True, 'user_role': account[2], 'real_name': account[3], 'username': user, 'login_time': datetime.now()})
            conn.execute("INSERT INTO user_sessions (username, login_time) VALUES (?,?)", (user, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); st.rerun()
        else: st.error("بيانات خاطئة")

else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج":
            if st.session_state['login_time']:
                duration = (datetime.now() - st.session_state['login_time']).seconds / 60
                conn.execute("UPDATE user_sessions SET logout_time=?, duration_mins=? WHERE username=? AND logout_time IS NULL", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(duration, 2), st.session_state['username']))
                conn.commit()
            st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (تعديل كامل + إكمال تلقائي + واتساب + مبلغ تعميد) ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        tab_my, tab_all = st.tabs(["📂 عملائي (إدارة وتعديل)", "🌍 قاعدة البيانات الشاملة"])
        
        with tab_my:
            rep_n = st.session_state['real_name']
            if role == 'admin':
                reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
                rep_n = st.selectbox("اختر المندوب:", reps) if reps else rep_n
            
            my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_n,))
            if not my_data.empty:
                search_q = st.text_input("🔎 ابحث بالاسم (إكمال تلقائي):")
                df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
                sid = st.selectbox("👇 اختر العميل:", df_view['id'], format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
                row = my_data[my_data['id'] == sid].iloc[0]
                
                with st.form("edit_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_name = st.text_input("الشركة", value=row['company_name'], disabled=(role != 'admin'))
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                        wa_url = f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}"
                        st.link_button("💬 مراسلة واتساب فورية", wa_url)
                    with c2:
                        new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                        # جديد: خانة مبلغ التعميد تظهر فقط عند اختيار "تم التعميد"
                        amt = 0.0
                        if new_st == "تم التعميد":
                            amt = st.number_input("مبلغ التعميد (SAR)", value=float(row['contract_amount']))
                        note = st.text_area("ملاحظات")
                    
                    if st.form_submit_button("💾 حفظ التعديلات"):
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, status=?, contract_amount=? WHERE id=?", (new_name, new_mob, new_st, amt, sid))
                        conn.commit(); st.success("تم التحديث"); st.rerun()

    # --- إضافة عميل (مفاتيح دول + منع تكرار + جميع الحقول الأصلية) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب")
            with c2:
                c_key = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_in = st.text_input("رقم الجوال *")
                em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
            rep = st.selectbox("المندوب", pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()) if role == 'admin' else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            
            if st.form_submit_button("حفظ"):
                is_v, f_mob = validate_intl_mobile(COUNTRY_CODES[c_key], mob_in)
                full_mob = f"+{COUNTRY_CODES[c_key]}{f_mob}"
                dup = check_duplicate_info(comp, full_mob)
                if dup: st.error(f"❌ تم الرفض: {dup}")
                elif comp and is_v:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)", (comp, sec, cont, pos, full_mob, em, evt, rep))
                    conn.commit(); st.success("تم الحفظ بنجاح")

    # --- لوحة المدير (تقرير مدة الاستخدام + الإحصائيات) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 لوحة تحكم المدير")
        t1, t2 = st.tabs(["الإحصائيات", "⏱️ سجل استخدام المناديب"])
        with t2:
            st.subheader("سجل نشاط الموظفين")
            sessions = pd.read_sql("SELECT username as 'الموظف', login_time as 'الدخول', duration_mins as 'المدة (دقيقة)' FROM user_sessions ORDER BY id DESC", conn)
            st.dataframe(sessions, use_container_width=True, hide_index=True)
