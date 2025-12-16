import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import re 

# قائمة الدول العربية
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "الأردن (+962)": "962", "المغرب (+212)": "212", "العراق (+964)": "964"
}

# ==========================================
#              إعدادات النظام
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢")

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

if not st.session_state['logged_in']:
    st.title("🔐 Expo Time CRM")
    user = st.text_input("اسم المستخدم")
    pw = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (user, pw))
        res = c.fetchone()
        if res:
            st.session_state.update({'logged_in': True, 'user_role': res[2], 'real_name': res[3]})
            st.rerun()
        else: st.error("بيانات خاطئة")
else:
    role = st.session_state['user_role']
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (تعمل وممتازة) ---
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المبيعات")
        rep_n = st.session_state['real_name']
        if role == 'admin':
            reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
            rep_n = st.selectbox("اختر المندوب:", reps) if reps else rep_n
        
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_n,))
        if not my_data.empty:
            search_q = st.text_input("🔎 ابحث بالاسم:")
            df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
            if not df_view.empty:
                sid = st.selectbox("👇 اختر العميل:", df_view['id'].tolist(), format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
                row = my_data[my_data['id'] == sid].iloc[0]
                
                c1, c2 = st.columns(2)
                with c1:
                    st.info(f"الشركة: {row['company_name']}")
                    st.link_button("💬 واتساب مباشر", f"https://wa.me/{re.sub(r'\D', '', row['mobile'])}")
                with c2:
                    with st.form("up_st"):
                        new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                        note = st.text_area("ملاحظات")
                        if st.form_submit_button("حفظ"):
                            conn.execute("UPDATE customers SET status=? WHERE id=?", (new_st, sid))
                            conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (sid, row['company_name'], new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit(); st.success("تم الحفظ"); st.rerun()

    # --- إصلاح استيراد ملف ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف Excel", type=['xlsx', 'csv'])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            st.dataframe(df.head())
            if st.button("🚀 بدء الاستيراد والربط"):
                # توحيد أسماء الأعمدة للربط
                df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
                # محاولة مطابقة الأعمدة (عربي/انجليزي)
                df.rename(columns={'اسم_الشركة': 'company_name', 'الجوال': 'mobile', 'المندوب': 'sales_rep'}, inplace=True)
                
                # تنفيذ الإدخال
                df.to_sql('customers', conn, if_exists='append', index=False)
                st.success(f"✅ تم استيراد {len(df)} عميل بنجاح!")

    # --- إصلاح البحث الشامل ---
    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث الشامل")
        query = st.text_input("🔎 ابحث عن شركة، رقم، أو مندوب:")
        if query:
            all_df = pd.read_sql("SELECT * FROM customers", conn)
            # بحث ذكي في كل الأعمدة
            results = all_df[all_df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
            if not results.empty:
                st.write(f"النتائج: {len(results)}")
                st.dataframe(results, use_container_width=True, hide_index=True)
            else:
                st.warning("لا توجد نتائج مطابقة.")

    # --- إضافة عميل (مفاتيح الدول ومنع التكرار) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                code = st.selectbox("الدولة", list(COUNTRY_CODES.keys()))
            with c2:
                mob = st.text_input("الجوال *")
                rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                # منع التكرار
                exists = conn.execute("SELECT sales_rep FROM customers WHERE mobile=?", (full_mob,)).fetchone()
                if exists: st.error(f"الرقم مكرر مع المندوب: {exists[0]}")
                elif comp and mob:
                    conn.execute("INSERT INTO customers (company_name, mobile, sales_rep) VALUES (?,?,?)", (comp, full_mob, rep))
                    conn.commit(); st.success("تم الحفظ")

    # --- لوحة المدير (الإحصائيات) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 أداء الموظفين")
        c1, c2 = st.columns(2)
        with c1: d1 = st.date_input("من", date(2025,1,1))
        with c2: d2 = st.date_input("إلى", date.today())
        
        hist = pd.read_sql("SELECT * FROM status_history", conn)
        if not hist.empty:
            hist['timestamp'] = pd.to_datetime(hist['timestamp'])
            filtered = hist[(hist['timestamp'].dt.date >= d1) & (hist['timestamp'].dt.date <= d2)]
            if not filtered.empty:
                summary = filtered.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
                st.dataframe(summary, use_container_width=True)
            else: st.info("لا بيانات للفترة المحددة.")
