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
    "الكويت (+965)": "965", "قطر (+974)": "974", "الأردن (+962)": "962"
}

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None
if 'login_time' not in st.session_state: st.session_state['login_time'] = None

# --- قاعدة البيانات الأصلية ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    # الحقول الأصلية + مبلغ التعميد
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد', contract_amount REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer_name TEXT, 
        updated_status TEXT, changed_by TEXT, notes TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, real_name TEXT)''')
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
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    st.title("🔐 Expo Time CRM")
    choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
    user = st.text_input("اسم المستخدم")
    pw = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (user, pw))
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
        # استعادة كامل قائمة المدير
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج":
            if st.session_state['login_time']:
                duration = (datetime.now() - st.session_state['login_time']).seconds / 60
                conn.execute("UPDATE user_sessions SET logout_time=?, duration_mins=? WHERE username=? AND logout_time IS NULL", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(duration, 2), st.session_state['username']))
                conn.commit()
            st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (استعادة كافة التبويبات والملاحظات) ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        t_my, t_all = st.tabs(["📂 عملائي (بحث وإدارة)", "🌍 قاعدة البيانات الشاملة"])
        
        with t_my:
            rep_n = st.session_state['real_name']
            if role == 'admin':
                reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
                rep_n = st.selectbox("اختر المندوب:", reps) if reps else rep_n
            
            my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_n,))
            if not my_data.empty:
                search_q = st.text_input("🔎 ابحث بالاسم (التكملة الذكية):")
                df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
                client_opts = {row['id']: row['company_name'] for i, row in df_view.iterrows()}
                
                if client_opts:
                    sid = st.selectbox("👇 اختر العميل:", list(client_opts.keys()), format_func=lambda x: client_opts[x])
                    row = my_data[my_data['id'] == sid].iloc[0]
                    
                    with st.form("edit_form"):
                        c1, c2 = st.columns(2)
                        with c1:
                            new_name = st.text_input("الشركة", value=row['company_name'], disabled=(role != 'admin'))
                            new_mob = st.text_input("الجوال", value=row['mobile'])
                            st.link_button("💬 واتساب مباشر", f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}")
                        with c2:
                            new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                            amt = st.number_input("مبلغ التعميد", value=float(row['contract_amount'])) if new_st == "تم التعميد" else 0.0
                            note = st.text_area("ملاحظات المتابعة (سجل ملاحظاتك هنا...)", placeholder="اكتب ملاحظاتك...")
                        
                        if st.form_submit_button("💾 حفظ"):
                            conn.execute("UPDATE customers SET company_name=?, mobile=?, status=?, contract_amount=? WHERE id=?", (new_name, new_mob, new_st, amt, sid))
                            conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (sid, new_name, new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit(); st.success("تم الحفظ"); st.rerun()
            else: st.info("لا توجد بيانات.")

        with t_all: # استعادة قاعدة البيانات الشاملة
            st.subheader("🌍 قاعدة البيانات الشاملة")
            df_all = pd.read_sql("SELECT * FROM customers", conn)
            st.dataframe(df_all, use_container_width=True, hide_index=True, column_config={"id": None})

    # --- استعادة إضافة عميل (كما كانت أولاً) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب")
            with c2:
                c_key = st.selectbox("مفتاح الدولة", list(COUNTRY_CODES.keys()))
                mob_in = st.text_input("رقم الجوال *")
                em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
            rep = st.selectbox("المندوب", pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()) if role == 'admin' else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[c_key]}{mob_in.strip()}"
                conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)", (comp, sec, cont, pos, full_mob, em, evt, rep))
                conn.commit(); st.success("تم الحفظ")

    # --- لوحة المدير (استعادة الإحصائيات الأصلية) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 لوحة تحكم المدير")
        t1, t2 = st.tabs(["📈 الإحصائيات العامة", "⏱️ سجل استخدام المناديب"])
        with t1:
            df_stats = pd.read_sql("SELECT * FROM customers", conn)
            if not df_stats.empty:
                st.plotly_chart(px.bar(df_stats, x='sales_rep', color='status'), use_container_width=True)
                st.subheader("سجل المتابعات التفصيلي")
                st.dataframe(pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn), use_container_width=True)
        with t2:
            st.dataframe(pd.read_sql("SELECT username as 'الموظف', login_time, duration_mins FROM user_sessions ORDER BY id DESC", conn), use_container_width=True)

    # --- استعادة المستخدمين بالكامل ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t_a, t_b, t_c = st.tabs(["إضافة", "تعديل", "حذف"])
        with t_a:
            n, u, p = st.text_input("الاسم الكامل"), st.text_input("يوزر"), st.text_input("باس")
            if st.button("إنشاء"):
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, 'rep', n))
                conn.commit(); st.success("تم")
        with t_b: # تعديل الباسورد
            u_list = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
            u_sel = st.selectbox("المستخدم", u_list)
            np = st.text_input("باس جديد")
            if st.button("تحديث"):
                conn.execute("UPDATE users SET password=? WHERE username=?", (np, u_sel))
                conn.commit(); st.success("تم التحديث")
        with t_c: # الحذف
            u_del = st.selectbox("حذف مستخدم", [x for x in u_list if x != 'admin'])
            if st.button("❌ حذف نهائي"):
                conn.execute("DELETE FROM users WHERE username=?", (u_del,))
                conn.commit(); st.success("تم"); st.rerun()

    # --- استعادة استيراد ملف وبحث شامل ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد Excel/CSV")
        f = st.file_uploader("اختر ملف", type=['csv', 'xlsx'])
        if f and st.button("بدء الاستيراد"):
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df.to_sql('customers', conn, if_exists='append', index=False)
            st.success("تم الاستيراد")

    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث الشامل")
        s = st.text_input("🔎 ابحث عن أي معلومة:")
        if s:
            df_full = pd.read_sql("SELECT * FROM customers", conn)
            st.dataframe(df_full[df_full.astype(str).apply(lambda x: x.str.contains(s, case=False)).any(axis=1)], use_container_width=True, hide_index=True)
