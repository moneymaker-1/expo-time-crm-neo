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

# قائمة الدول العربية للتحديث
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "المغرب (+212)": "212"
}

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

# --- قاعدة البيانات (نفس هيكلك الأصلي) ---
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
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# ==========================================
#           دوال التحقق (الجديدة)
# ==========================================
def check_duplicate_info(comp_name, mob):
    c = conn.cursor()
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة', '', comp_name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"الشركة مكررة مع المندوب: {res[1]}"
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"رقم الجوال مكرر مع المندوب: {res[1]}"
    return None

# ==========================================
#              واجهة التطبيق
# ==========================================

# --- استعادة صفحة الدخول كما كانت أولاً بالضبط ---
if not st.session_state['logged_in']:
    st.title("🔐 Expo Time CRM")
    choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
    
    if choice == "تسجيل دخول":
        user = st.text_input("اسم المستخدم")
        pw = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (user, pw))
            account = c.fetchone()
            if account:
                st.session_state.update({'logged_in': True, 'user_role': account[2], 'real_name': account[3]})
                st.rerun()
            else: st.error("بيانات خاطئة")
    else:
        name = st.text_input("الاسم الكامل")
        user = st.text_input("اسم المستخدم")
        pw = st.text_input("كلمة المرور", type="password")
        if st.button("تسجيل"):
            try:
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user, pw, 'rep', name))
                conn.commit(); st.success("تم التسجيل")
            except: st.error("المستخدم موجود")

else:
    # --- القائمة الجانبية (نفس الأصل) ---
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (مع صلاحيات المدير بالتعديل) ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        tab_my, tab_all = st.tabs(["📂 عملائي", "🌍 قاعدة البيانات الشاملة"])
        
        with tab_my:
            rep_name = st.session_state['real_name']
            if role == 'admin':
                reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
                rep_name = st.selectbox("عرض عملاء المندوب:", reps) if reps else rep_name
            
            my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_name,))
            if not my_data.empty:
                search_q = st.text_input("🔎 ابحث بالاسم:")
                df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)] if search_q else my_data
                
                client_opts = {row['id']: row['company_name'] for i, row in df_view.iterrows()}
                sid = st.selectbox("اختر العميل:", list(client_opts.keys()), format_func=lambda x: client_opts[x])
                row = my_data[my_data['id'] == sid].iloc[0]
                
                # إمكانية التعديل الكاملة للمدير والمندوب في نفس الخانة
                with st.form("edit_area"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_cname = st.text_input("اسم الشركة", value=row['company_name'])
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                        st.link_button("💬 واتساب", f"https://wa.me/{row['mobile'].replace('+', '')}")
                    with c2:
                        new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']) if row['status'] in TRIP_STAGES else 0)
                        note = st.text_area("ملاحظات")
                    
                    if st.form_submit_button("حفظ"):
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, status=? WHERE id=?", (new_cname, new_mob, new_st, sid))
                        conn.commit(); st.success("تم الحفظ"); st.rerun()

        with tab_all:
            st.subheader("🌍 تعديل الداتا الرئيسية")
            all_data = pd.read_sql("SELECT * FROM customers", conn)
            if role == 'admin':
                # المدير يمكنه التعديل في الجدول مباشرة
                edited_df = st.data_editor(all_data, use_container_width=True, hide_index=True, column_config={"id": None})
                if st.button("💾 حفظ تغييرات الجدول الرئيسي"):
                    for i, r in edited_df.iterrows():
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, sales_rep=?, status=? WHERE id=?", (r['company_name'], r['mobile'], r['sales_rep'], r['status'], r['id']))
                    conn.commit(); st.success("تم التحديث")
            else:
                st.dataframe(all_data, use_container_width=True, hide_index=True, column_config={"id": None})

    # --- إضافة عميل (مع مفتاح الدولة ومنع التكرار) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("الشركة *")
                c_key = st.selectbox("الدولة", list(COUNTRY_CODES.keys()))
            with c2:
                mob_in = st.text_input("الجوال *")
                rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[c_key]}{mob_in}"
                dup = check_duplicate_info(comp, full_mob)
                if dup: st.error(dup)
                elif comp and mob_in:
                    conn.execute("INSERT INTO customers (company_name, mobile, sales_rep) VALUES (?,?,?)", (comp, full_mob, rep))
                    conn.commit(); st.success("تم الحفظ")

    # --- استيراد ملف (كما كان أولاً) ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف", type=['xlsx', 'csv'])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            if st.button("بدء الاستيراد"):
                df.to_sql('customers', conn, if_exists='append', index=False)
                st.success("تم")
