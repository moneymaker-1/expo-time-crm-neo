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

# قائمة الدول العربية
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "العراق (+964)": "964",
    "المغرب (+212)": "212", "تونس (+216)": "216"
}

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

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
    return conn

conn = init_db()
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# --- دوال التحقق ---
def check_duplicate_info(comp_name, mob):
    c = conn.cursor()
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة', '', comp_name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"الشركة مسجلة باسم ({res[0]}) مع المندوب: {res[1]}"
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"رقم الجوال ({mob}) مسجل مع المندوب: {res[1]}"
    return None

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
        c.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (user, pw))
        account = c.fetchone()
        if account:
            st.session_state.update({'logged_in': True, 'user_role': account[2], 'real_name': account[3]})
            st.rerun()
        else: st.error("بيانات خاطئة")

else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (مع البحث في القسمين) ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        tab_my, tab_all = st.tabs(["📂 عملائي (بحث وإدارة)", "🌍 قاعدة البيانات الشاملة"])
        
        with tab_my:
            rep_name = st.session_state['real_name']
            if role == 'admin':
                reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
                rep_name = st.selectbox("اختر المندوب:", reps) if reps else rep_name
            
            my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_name,))
            if not my_data.empty:
                search_my = st.text_input("🔎 ابحث في عملائك:")
                df_my = my_data[my_data.astype(str).apply(lambda x: x.str.contains(search_my, case=False)).any(axis=1)]
                sid = st.selectbox("اختر العميل:", df_my['id'], format_func=lambda x: df_my[df_my['id']==x]['company_name'].values[0])
                # ... (بقية كود التعديل والواتساب) ...
            else: st.info("لا توجد بيانات.")

        with tab_all:
            st.subheader("🌍 البحث والتعديل في قاعدة البيانات")
            all_df = pd.read_sql("SELECT * FROM customers", conn)
            search_all = st.text_input("🔎 ابحث في الداتا كاملة (اسم، جوال، مندوب...):")
            df_all = all_df[all_df.astype(str).apply(lambda x: x.str.contains(search_all, case=False)).any(axis=1)]
            
            if role == 'admin':
                edited_df = st.data_editor(df_all, use_container_width=True, hide_index=True, column_config={"id": None})
                if st.button("💾 حفظ تغييرات الداتا"):
                    for i, r in edited_df.iterrows():
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, sales_rep=?, status=? WHERE id=?", (r['company_name'], r['mobile'], r['sales_rep'], r['status'], r['id']))
                    conn.commit(); st.success("تم التحديث")
            else:
                st.dataframe(df_all, use_container_width=True, hide_index=True, column_config={"id": None})

    # --- إضافة عميل (نفس الحقول الأصلية) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                sec = st.selectbox("القطاع", SECTORS)
                cont = st.text_input("الشخص المسؤول")
                pos = st.text_input("المنصب")
            with c2:
                c_key = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_in = st.text_input("رقم الجوال *")
                em = st.text_input("الإيميل *")
                evt = st.text_input("الفعالية")
            reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
            rep = st.selectbox("المندوب", reps) if role == 'admin' and reps else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[c_key]}{mob_in.strip()}"
                dup = check_duplicate_info(comp, full_mob)
                if dup: st.error(dup)
                elif comp and mob_in:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)", (comp, sec, cont, pos, full_mob, em, evt, rep))
                    conn.commit(); st.success("تم الحفظ")

    # --- لوحة المدير (مع البحث في السجلات) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 الإحصائيات وسجلات النظام")
        df_hist = pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn)
        search_log = st.text_input("🔎 ابحث في سجلات المتابعة (اسم الشركة، المندوب، الحالة):")
        df_log_f = df_hist[df_hist.astype(str).apply(lambda x: x.str.contains(search_log, case=False)).any(axis=1)]
        st.dataframe(df_log_f, use_container_width=True, hide_index=True)

    # --- المستخدمين (مع البحث) ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        users_df = pd.read_sql("SELECT username, role, real_name FROM users", conn)
        search_user = st.text_input("🔎 ابحث عن مستخدم:")
        df_u_f = users_df[users_df.astype(str).apply(lambda x: x.str.contains(search_user, case=False)).any(axis=1)]
        st.dataframe(df_u_f, use_container_width=True, hide_index=True)

    # --- بحث شامل ---
    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث الشامل")
        s = st.text_input("🔎 اكتب أي شيء للبحث (شركة، جوال، إيميل، مندوب، فعالية...):")
        if s:
            df_full = pd.read_sql("SELECT * FROM customers", conn)
            st.dataframe(df_full[df_full.astype(str).apply(lambda x: x.str.contains(s, case=False)).any(axis=1)], use_container_width=True, hide_index=True, column_config={"id": None})
