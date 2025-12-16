import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import re 

# ==========================================
#              إعدادات الجمالية (CSS)
# ==========================================
def apply_custom_style():
    st.markdown("""
        <style>
        /* استيراد خط كاييرو العربي المعتمد للمواقع الاحترافية */
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Cairo', sans-serif;
            text-align: right;
        }
        
        /* لون الهوية (الأزرق الملكي) للأزرار والعناوين */
        .stButton>button {
            background-color: #1a4d8c !important;
            color: white !important;
            border-radius: 10px !important;
            border: none !important;
            transition: 0.3s;
            font-weight: bold;
        }
        
        .stButton>button:hover {
            background-color: #2c6eb5 !important;
            box-shadow: 0 4px 15px rgba(26, 77, 140, 0.3);
        }
        
        /* تنسيق الحاويات والقوائم */
        [data-testid="stSidebar"] {
            background-color: #1a4d8c;
        }
        [data-testid="stSidebar"] * {
            color: white !important;
        }
        
        /* تحسين شكل بطاقة العميل */
        .stInfo {
            border-right: 5px solid #1a4d8c !important;
            background-color: #f0f4f8 !important;
            color: #1a4d8c !important;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
#              إعدادات النظام
# ==========================================

st.set_page_config(
    page_title="Expotime CRM",
    layout="wide",
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

apply_custom_style()

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'user_role' not in st.session_state: 
    st.session_state['user_role'] = None

if 'real_name' not in st.session_state: 
    st.session_state['real_name'] = None

# --- قائمة الدول العربية ---
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "الأردن (+962)": "962", "البحرين (+973)": "973", "العراق (+964)": "964"
}

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
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '1234', 'admin', 'المدير العام'))
        conn.commit()
    conn.commit()
    return conn

conn = init_db()
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# ==========================================
#              دوال النظام المعتمدة
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

def update_customer_info(cid, new_name, new_mobile, new_email):
    c = conn.cursor()
    c.execute("UPDATE customers SET company_name = ?, mobile = ?, email = ? WHERE id = ?", 
              (new_name, new_mobile, new_email, cid))
    conn.commit()

def update_customer_status(cid, cname, new_status, user, notes=""):
    c = conn.cursor()
    c.execute("UPDATE customers SET status = ? WHERE id = ?", (new_status, cid))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (cid, cname, new_status, user, notes, now))
    conn.commit()

def get_all_data(): return pd.read_sql("SELECT * FROM customers", conn)
def get_my_data(rep): return pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep,))
def get_client_history(cid): return pd.read_sql("SELECT * FROM status_history WHERE customer_id = ? ORDER BY id DESC", conn, params=(cid,))
def get_history_log(): return pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn)
def get_all_reps(): return pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()

def add_customer(data):
    c = conn.cursor()
    c.execute('''INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
    conn.commit()

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>EXPO TIME CRM</h1>", unsafe_allow_html=True)
        choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
        
        if choice == "تسجيل دخول":
            user = st.text_input("اسم المستخدم")
            pw = st.text_input("كلمة المرور", type="password")
            if st.button("دخول"):
                account = login_user(user, pw)
                if account:
                    st.session_state['logged_in'] = True
                    st.session_state['user_role'] = account[2]
                    st.session_state['real_name'] = account[3]
                    st.rerun()
                else: st.error("بيانات خاطئة")
        else:
            name = st.text_input("الاسم الكامل")
            user = st.text_input("اسم المستخدم")
            pw = st.text_input("كلمة المرور", type="password")
            if st.button("تسجيل"):
                if create_user(user, pw, name): st.success("تم التسجيل")
                else: st.error("المستخدم موجود")

else:
    role = st.session_state['user_role']
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        if role == 'admin':
            menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"]
        else:
            menu = ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج":
            st.session_state.clear()
            st.rerun()

    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المبيعات")
        rep_n = st.session_state['real_name']
        if role == 'admin':
            reps = get_all_reps()
            rep_n = st.selectbox("اختر المندوب:", reps) if reps else rep_n
        
        my_data = get_my_data(rep_n)
        if not my_data.empty:
            sid = st.selectbox("👇 اختر العميل:", my_data['id'].tolist(), format_func=lambda x: my_data[my_data['id']==x]['company_name'].values[0])
            row = my_data[my_data['id'] == sid].iloc[0]
            
            c1, c2 = st.columns([1, 1])
            with c1:
                st.info(f"**🏢 الشركة:** {row['company_name']}\n\n**📱 الجوال:** {row['mobile']}")
                st.link_button("💬 واتساب فوراً", f"https://wa.me/{re.sub(r'\D', '', row['mobile'])}")
            with c2:
                with st.form("up_form"):
                    new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                    note = st.text_area("ملاحظات")
                    if st.form_submit_button("حفظ التحديث"):
                        update_customer_status(sid, row['company_name'], new_st, st.session_state['real_name'], note)
                        st.success("تم الحفظ"); st.rerun()
            
            st.divider()
            st.subheader("🕒 سجل المتابعة (Timeline)")
            history = get_client_history(sid)
            for _, h in history.iterrows():
                st.caption(f"{h['timestamp']} - {h['updated_status']} ({h['changed_by']})")
                if h['notes']: st.info(h['notes'])

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("add_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                code = st.selectbox("الدولة *", list(COUNTRY_CODES.keys()))
                sector = st.selectbox("القطاع", SECTORS)
            with c2:
                mob = st.text_input("رقم الجوال *")
                contact = st.text_input("الشخص المسؤول")
                pos = st.text_input("المنصب")
            
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                if comp and mob:
                    add_customer((comp, sector, contact, pos, full_mob, "", "", rep, "جديد"))
                    st.success("تم الحفظ بنجاح")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات النظام")
        all_data = get_all_data()
        st.metric("إجمالي عدد العملاء", len(all_data))
        
        hist = get_history_log()
        if not hist.empty:
            summary = hist.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
            st.subheader("📈 ملخص إنجازات المناديب")
            st.dataframe(summary, use_container_width=True)

    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        users_df = pd.read_sql("SELECT username, real_name, role FROM users", conn)
        st.dataframe(users_df, use_container_width=True)

    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف Excel", type=['xlsx', 'csv'])
        if f and st.button("بدء الاستيراد"):
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df.to_sql('customers', conn, if_exists='append', index=False)
            st.success("تم الاستيراد")

    elif nav == "بحث شامل":
        st.header("🔍 البحث في الداتا")
        q = st.text_input("ابحث عن شركة، جوال، أو مندوب:")
        if q:
            all_c = get_all_data()
            res = all_c[all_c.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            st.dataframe(res, use_container_width=True)
