import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import re 

# قائمة الدول العربية الـ 22
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "الأردن (+962)": "962", "البحرين (+973)": "973", "العراق (+964)": "964",
    "اليمن (+967)": "967", "فلسطين (+970)": "970", "لبنان (+961)": "961",
    "سوريا (+963)": "963", "المغرب (+212)": "212", "الجزائر (+213)": "213",
    "تونس (+216)": "216", "ليبيا (+218)": "218", "السودان (+249)": "249",
    "موريتانيا (+222)": "222", "الصومال (+252)": "252", "جيبوتي (+253)": "253",
    "جزر القمر (+269)": "269"
}

# ==========================================
#              إعدادات النظام
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢")

# تحسين مظهر الجداول والقوائم عبر CSS بسيط
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stTextInput>div>div>input, .stSelectbox>div>div>select { border-radius: 5px; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    </style>
    """, unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

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
#              واجهة التطبيق
# ==========================================

# --- صفحة الدخول (تنسيق مركزي) ---
if not st.session_state['logged_in']:
    _, center_col, _ = st.columns([1, 1.5, 1])
    with center_col:
        st.markdown("<h1 style='text-align: center;'>🔐 Expo Time CRM</h1>", unsafe_allow_html=True)
        with st.container(border=True):
            choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
            if choice == "تسجيل دخول":
                user = st.text_input("اسم المستخدم")
                pw = st.text_input("كلمة المرور", type="password")
                if st.button("دخول"):
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (user, pw))
                    res = c.fetchone()
                    if res:
                        st.session_state.update({'logged_in': True, 'user_role': res[2], 'real_name': res[3]})
                        st.rerun()
                    else: st.error("❌ بيانات خاطئة")
            else:
                name = st.text_input("الاسم الكامل")
                user = st.text_input("اسم المستخدم")
                pw = st.text_input("كلمة المرور", type="password")
                if st.button("تسجيل"):
                    try:
                        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user, pw, 'rep', name))
                        conn.commit(); st.success("✅ تم التسجيل بنجاح")
                    except: st.error("⚠️ المستخدم موجود مسبقاً")

else:
    role = st.session_state['user_role']
    with st.sidebar:
        st.markdown(f"### 👤 مرحباً: {st.session_state['real_name']}")
        menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("القائمة الرئيسية", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (تنسيق البطاقة والمعلومات المترابطة) ---
    if nav == "بوابة Mبيعات":
        st.header("💼 إدارة علاقات العملاء")
        rep_n = st.session_state['real_name']
        if role == 'admin':
            reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
            rep_n = st.selectbox("اختر المندوب:", ["الكل"] + reps) if reps else rep_n
        
        query = "SELECT * FROM customers" if rep_n == "الكل" else "SELECT * FROM customers WHERE sales_rep=?"
        params = () if rep_n == "الكل" else (rep_n,)
        my_data = pd.read_sql(query, conn, params=params)

        if not my_data.empty:
            sid = st.selectbox("👇 اختر العميل لإدارة ملفه:", my_data['id'].tolist(), format_func=lambda x: my_data[my_data['id']==x]['company_name'].values[0])
            row = my_data[my_data['id'] == sid].iloc[0]
            
            col_info, col_action = st.columns([1, 1.2], gap="large")
            
            with col_info:
                with st.container(border=True):
                    st.markdown("#### 📋 بيانات التواصل")
                    st.markdown(f"**🏢 الشركة:** {row['company_name']}")
                    st.markdown(f"**📱 الجوال:** {row['mobile']}")
                    st.link_button("💬 مراسلة واتساب فورية", f"https://wa.me/{re.sub(r'\D', '', row['mobile'])}")
                    st.markdown(f"**📧 الإيميل:** {row['email'] or 'غير مسجل'}")
                    st.markdown(f"**📍 القطاع:** {row['sector']}")

            with col_action:
                with st.form("status_update_form"):
                    st.markdown("#### 🚀 تحديث مرحلة العميل")
                    new_st = st.selectbox("انقل العميل إلى:", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                    note = st.text_area("سجل ملاحظات المتابعة (ماذا تم؟)")
                    if st.form_submit_button("✅ حفظ العملية"):
                        conn.execute("UPDATE customers SET status=? WHERE id=?", (new_st, sid))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (sid, row['company_name'], new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم الحفظ"); st.rerun()

    # --- إضافة عميل (تنسيق الحقول المترابطة) ---
    elif nav == "إضافة عميل":
        st.header("➕ تسجيل عميل جديد")
        with st.form("add_client_form", clear_on_submit=True):
            col_a, col_b = st.columns(2, gap="medium")
            with col_a:
                st.markdown("##### 🏢 معلومات المنشأة")
                comp = st.text_input("اسم الشركة *")
                sector = st.selectbox("قطاع العمل", ["تقنية", "عقارات", "تجارة", "صناعة", "خدمات"])
                event = st.text_input("الفعالية المهتم بها")
            with col_b:
                st.markdown("##### 👤 معلومات الاتصال")
                code = st.selectbox("الدولة (المفتاح)", list(COUNTRY_CODES.keys()))
                mob = st.text_input("رقم الجوال (بدون أصفار) *")
                email = st.text_input("البريد الإلكتروني")
            
            st.divider()
            rep = st.text_input("المندوب المسؤول", value=st.session_state['real_name'], disabled=(role != 'admin'))
            if st.form_submit_button("💾 حفظ العميل في النظام"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                exists = conn.execute("SELECT sales_rep FROM customers WHERE mobile=?", (full_mob,)).fetchone()
                if exists: st.error(f"⚠️ العميل مسجل مسبقاً مع المندوب: {exists[0]}")
                elif comp and mob:
                    conn.execute("INSERT INTO customers (company_name, sector, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?)", 
                                 (comp, sector, full_mob, email, event, rep))
                    conn.commit(); st.success("✅ تم الحفظ بنجاح")

    # --- لوحة المدير (تنسيق الجداول) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 لوحة قيادة الأداء")
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1: d1 = st.date_input("من تاريخ", date(2025, 1, 1))
            with c2: d2 = st.date_input("إلى تاريخ", date.today())
        
        hist_df = pd.read_sql("SELECT * FROM status_history", conn)
        if not hist_df.empty:
            hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
            filtered = hist_df[(hist_df['timestamp'].dt.date >= d1) & (hist_df['timestamp'].dt.date <= d2)]
            if not filtered.empty:
                st.subheader("📋 ملخص إنجازات المناديب")
                st.dataframe(filtered.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0), use_container_width=True)

    # --- إدارة المستخدمين ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة فريق العمل")
        t1, t2 = st.tabs(["إضافة وحذف", "تعديل بيانات"])
        with t1:
            with st.form("new_user"):
                u, p, n = st.text_input("اسم المستخدم"), st.text_input("كلمة المرور"), st.text_input("الاسم الكامل")
                if st.button("إنشاء حساب مندوب"):
                    conn.execute("INSERT INTO users VALUES (?,?,?,?)", (u, p, 'rep', n)); conn.commit(); st.rerun()
            st.divider()
            st.dataframe(pd.read_sql("SELECT username, real_name FROM users", conn), use_container_width=True)

    # --- استيراد ملف ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد قاعدة بيانات")
        with st.container(border=True):
            f = st.file_uploader("ارفع ملف Excel أو CSV", type=['xlsx', 'csv'])
            if f and st.button("بدء عملية الاستيراد"):
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.to_sql('customers', conn, if_exists='append', index=False)
                st.success("✅ تم استيراد كافة العملاء بنجاح")

    # --- البحث الشامل ---
    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث الذكي")
        q = st.text_input("🔎 اكتب اسم الشركة، رقم الجوال، أو اسم المندوب...")
        if q:
            all_c = pd.read_sql("SELECT * FROM customers", conn)
            res = all_c[all_c.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            st.dataframe(res, use_container_width=True, hide_index=True)
