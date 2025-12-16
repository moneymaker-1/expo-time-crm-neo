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

# قائمة جميع الدول العربية (للتحديث الجديد)
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "العراق (+964)": "964",
    "اليمن (+967)": "967", "فلسطين (+970)": "970", "لبنان (+961)": "961",
    "سوريا (+963)": "963", "المغرب (+212)": "212", "الجزائر (+213)": "213",
    "تونس (+216)": "216", "ليبيا (+218)": "218", "السودان (+249)": "249",
    "موريتانيا (+222)": "222", "الصومال (+252)": "252", "جيبوتي (+253)": "253", "جزر القمر (+269)": "269"
}

# إدارة الجلسة (تتبع الوقت)
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None
if 'login_time' not in st.session_state: st.session_state['login_time'] = None

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer_name TEXT, 
        updated_status TEXT, changed_by TEXT, notes TEXT, timestamp TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, real_name TEXT)''')
    
    # جدول سجل مدة الاستخدام المضاف حديثاً
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
#           دوال التحقق المتقدمة
# ==========================================

def is_duplicate_company(new_name):
    """منع التكرار الذكي للأسماء المتشابهة"""
    existing = pd.read_sql("SELECT company_name FROM customers", conn)['company_name'].tolist()
    stop_words = ["شركة", "مؤسسة", "المحدودة", "للتجارة", "والمقاولات", "مصنع"]
    def clean(n):
        n = n.lower().strip()
        for w in stop_words: n = n.replace(w, "")
        return set(re.findall(r'\w+', n))
    new_tokens = clean(new_name)
    for ex in existing:
        ex_tokens = clean(ex)
        if new_tokens.issubset(ex_tokens) or ex_tokens.issubset(new_tokens): return True, ex
    return False, None

def validate_intl_mobile(country_code, number):
    """التحقق البرمجي من الرقم الدولي"""
    clean_n = re.sub(r'\D', '', number)
    if country_code == "966":
        if clean_n.startswith('0'): clean_n = clean_n[1:]
        return len(clean_n) == 9 and clean_n.startswith('5'), clean_n
    return len(clean_n) >= 7 and len(clean_n) <= 12, clean_n

def validate_email(email):
    regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(regex, email) is not None

# ==========================================
#              دوال النظام
# ==========================================

def login_user(username, password):
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (username, password))
    return c.fetchone()

def create_user(username, password, real_name, role='rep'):
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, password, role, real_name))
        conn.commit()
        return True
    except: return False

def update_customer_status(cid, cname, new_status, user, notes=""):
    c = conn.cursor()
    c.execute("UPDATE customers SET status = ? WHERE id = ?", (new_status, cid))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (cid, cname, new_status, user, notes, now))
    conn.commit()

def get_all_users(): return pd.read_sql("SELECT username, role, real_name FROM users", conn)
def get_all_reps(): return pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
def get_all_data(): return pd.read_sql("SELECT * FROM customers", conn)
def get_my_data(rep): return pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep,))

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Expo Time CRM")
        choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
        user = st.text_input("اسم المستخدم")
        pw = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            account = login_user(user, pw)
            if account:
                st.session_state.update({'logged_in': True, 'user_role': account[2], 'real_name': account[3], 'username': user, 'login_time': datetime.now()})
                conn.execute("INSERT INTO user_sessions (username, login_time) VALUES (?,?)", (user, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                st.rerun()
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
                conn.execute("UPDATE user_sessions SET logout_time=?, duration_mins=? WHERE username=? AND logout_time IS NULL", 
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(duration, 2), st.session_state['username']))
                conn.commit()
            st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (مع البحث التلقائي وزر الواتساب) ---
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المتابعة الذكية")
        rep_name = st.session_state['real_name']
        my_data = get_my_data(rep_name)
        if not my_data.empty:
            search_input = st.text_input("🔎 ابحث (اسم، جوال...):")
            df_view = my_data[my_data.astype(str).apply(lambda x: x.str.contains(search_input, case=False)).any(axis=1)] if search_input else my_data
            
            client_options = {row['id']: f"{row['company_name']}" for i, row in df_view.iterrows()}
            if client_options:
                selected_id = st.selectbox("👇 اختر العميل:", options=list(client_options.keys()), format_func=lambda x: client_options[x])
                client_row = my_data[my_data['id'] == selected_id].iloc[0]
                
                c1, c2 = st.columns([1, 1.5])
                with c1:
                    st.subheader("📋 بيانات العميل")
                    st.info(f"**الشركة:** {client_row['company_name']}\n\n**الجوال:** {client_row['mobile']}")
                    wa_url = f"https://wa.me/{client_row['mobile'].replace('+', '').replace(' ', '')}"
                    st.link_button("💬 مراسلة واتساب فورية", wa_url, use_container_width=True)
                
                with c2:
                    st.subheader("🚀 تحديث المرحلة")
                    with st.form("status_update"):
                        new_stage = st.selectbox("الحالة:", TRIP_STAGES, index=TRIP_STAGES.index(client_row['status']) if client_row['status'] in TRIP_STAGES else 0)
                        note = st.text_area("ملاحظات المتابعة:")
                        if st.form_submit_button("✅ حفظ"):
                            update_customer_status(selected_id, client_row['company_name'], new_stage, st.session_state['real_name'], note)
                            st.success("تم الحفظ بنجاح!"); st.rerun()

    # --- إضافة عميل (منع التكرار والتحقق الدولي) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب")
            with c2:
                ckey = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_in = st.text_input("رقم الجوال *")
                em = st.text_input("الإيميل *")
            
            if st.form_submit_button("حفظ"):
                is_dup, dup_n = is_duplicate_company(comp)
                is_valid_mob, f_mob = validate_intl_mobile(COUNTRY_CODES[ckey], mob_in)
                full_mob = f"+{COUNTRY_CODES[ckey]}{f_mob}"
                
                if is_dup: st.error(f"❌ خطأ: العميل مسجل مسبقاً باسم: ({dup_n})")
                elif not comp or not is_valid_mob or not validate_email(em):
                    st.error("تأكد من تعبئة الحقول وصحة البيانات")
                else:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, sales_rep) VALUES (?,?,?,?,?,?)",
                                 (comp, sec, cont, full_mob, em, st.session_state['real_name']))
                    conn.commit(); st.success(f"تمت الإضافة بنجاح: {full_mob}")

    # --- لوحة المدير (مع تقرير مدة الاستخدام) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 لوحة تحكم المدير")
        t1, t2 = st.tabs(["الإحصائيات", "⏱️ سجل استخدام الموظفين"])
        with t1:
            df = get_all_data()
            if not df.empty:
                st.plotly_chart(px.bar(df, x='sales_rep', color='status', title="أداء المناديب"))
        with t2:
            st.subheader("سجل نشاط الموظفين")
            sessions_df = pd.read_sql("SELECT username as 'الموظف', login_time as 'الدخول', logout_time as 'الخروج', duration_mins as 'المدة (دقائق)' FROM user_sessions ORDER BY id DESC", conn)
            st.dataframe(sessions_df, use_container_width=True)

    # --- الصفحات الأخرى (استيراد، مستخدمين، بحث) تبقى كما هي في كودك الأصلي ---
