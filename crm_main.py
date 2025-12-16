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

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .timeline-card { border-right: 4px solid #007bff; padding: 10px 15px; margin-bottom: 10px; background-color: #f8f9fa; border-radius: 5px; }
    .status-badge { background-color: #e1ecf4; color: #007bff; padding: 2px 8px; border-radius: 10px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

if 'logged_in' not in st.session_state: 
    st.session_state['logged_in'] = False

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
    _, center_col, _ = st.columns([1, 1.5, 1])
    with center_col:
        st.markdown("<h1 style='text-align: center;'>🔐 Expo Time CRM</h1>", unsafe_allow_html=True)
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
        if nav == "خروج": 
            st.session_state.clear()
            st.rerun()

    # --- بوابة المبيعات (مع التايم لاين) ---
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المبيعات والمتابعة")
        rep_n = st.session_state['real_name']
        if role == 'admin':
            reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
            rep_n = st.selectbox("عرض عملاء المندوب:", ["الكل"] + reps) if reps else rep_n
        
        query = "SELECT * FROM customers" if rep_n == "الكل" else "SELECT * FROM customers WHERE sales_rep=?"
        params = () if rep_n == "الكل" else (rep_n,)
        my_data = pd.read_sql(query, conn, params=params)

        if not my_data.empty:
            sid = st.selectbox("👇 اختر العميل:", my_data['id'].tolist(), format_func=lambda x: my_data[my_data['id']==x]['company_name'].values[0])
            row = my_data[my_data['id'] == sid].iloc[0]
            
            # قسم البيانات والتحديث
            col_info, col_action = st.columns([1, 1], gap="large")
            with col_info:
                st.subheader("📋 معلومات العميل")
                st.info(f"**الشركة:** {row['company_name']}\n\n**الجوال:** {row['mobile']}")
                st.link_button("💬 واتساب مباشر", f"https://wa.me/{re.sub(r'\D', '', row['mobile'])}")
            
            with col_action:
                st.subheader("🚀 تحديث الحالة")
                with st.form("up_form"):
                    new_st = st.selectbox("تغيير الحالة إلى:", TRIP_STAGES, index=TRIP_STAGES.index(row['status']) if row['status'] in TRIP_STAGES else 0)
                    note = st.text_area("ملاحظات المتابعة الحالية")
                    if st.form_submit_button("حفظ التحديث"):
                        conn.execute("UPDATE customers SET status=? WHERE id=?", (new_st, sid))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (sid, row['company_name'], new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم الحفظ"); st.rerun()

            # --- التايم لاين (سجل المتابعة التاريخي) ---
            st.divider()
            st.subheader("🕒 سجل المتابعة (Timeline)")
            history = pd.read_sql("SELECT * FROM status_history WHERE customer_id=? ORDER BY id DESC", conn, params=(sid,))
            if not history.empty:
                for _, h in history.iterrows():
                    st.markdown(f"""
                    <div class="timeline-card">
                        <small>{h['timestamp']}</small> | <span class="status-badge">{h['updated_status']}</span><br>
                        <strong>بواسطة:</strong> {h['changed_by']}<br>
                        <strong>الملاحظات:</strong> {h['notes'] or 'لا يوجد'}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write("لا يوجد سجل متابعة سابق لهذا العميل.")
        else:
            st.warning("لا يوجد عملاء مسجلين.")

    # --- باقي النوافذ (بنفس التنسيق المترابط) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                code = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                sector = st.selectbox("القطاع", ["تقنية", "عقارات", "تجارة", "صناعة", "خدمات"])
            with c2:
                mob = st.text_input("الجوال *")
                contact = st.text_input("الشخص المسؤول")
                event = st.text_input("الفعالية")
            if st.form_submit_button("حفظ"):
                f_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                conn.execute("INSERT INTO customers (company_name, sector, contact_person, mobile, event_name, sales_rep) VALUES (?,?,?,?,?,?)", (comp, sector, contact, f_mob, event, st.session_state['real_name']))
                conn.commit(); st.success("تم الحفظ")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إنجازات المناديب")
        d1 = st.date_input("من", date(2025, 1, 1))
        d2 = st.date_input("إلى", date.today())
        hist = pd.read_sql("SELECT * FROM status_history", conn)
        if not hist.empty:
            hist['timestamp'] = pd.to_datetime(hist['timestamp'])
            filt = hist[(hist['timestamp'].dt.date >= d1) & (hist['timestamp'].dt.date <= d2)]
            if not filt.empty:
                st.dataframe(filt.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0), use_container_width=True)

    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 المستخدمين")
        u, p, n = st.text_input("يوزر"), st.text_input("باس"), st.text_input("الاسم")
        if st.button("إضافة"):
            conn.execute("INSERT INTO users VALUES (?,?,?,?)", (u,p,'rep',n)); conn.commit(); st.rerun()
        st.dataframe(pd.read_sql("SELECT username, real_name FROM users", conn), use_container_width=True)

    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد")
        f = st.file_uploader("Excel", type=['xlsx', 'csv'])
        if f and st.button("رفع"):
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df.to_sql('customers', conn, if_exists='append', index=False); st.success("تم")
