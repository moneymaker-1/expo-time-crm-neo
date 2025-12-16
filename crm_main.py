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

    # --- بوابة المبيعات ---
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المبيعات المباشرة")
        rep_n = st.session_state['real_name']
        if role == 'admin':
            reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
            rep_n = st.selectbox("اختر المندوب:", reps) if reps else rep_n
        
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_n,))
        if not my_data.empty:
            sid = st.selectbox("👇 اختر العميل لإدارة رحلته:", my_data['id'].tolist(), format_func=lambda x: my_data[my_data['id']==x]['company_name'].values[0])
            row = my_data[my_data['id'] == sid].iloc[0]
            
            c1, c2 = st.columns(2)
            with c1:
                st.info(f"اسم العميل: {row['company_name']}")
                # زر الواتساب المباشر
                st.link_button("💬 مراسلة واتساب فورية", f"https://wa.me/{re.sub(r'\D', '', row['mobile'])}")
            with c2:
                with st.form("update_status_form"):
                    new_st = st.selectbox("الحالة الحالية", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                    note = st.text_area("ملاحظات المتابعة")
                    if st.form_submit_button("حفظ التحديث"):
                        conn.execute("UPDATE customers SET status=? WHERE id=?", (new_st, sid))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (sid, row['company_name'], new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم التحديث"); st.rerun()

    # --- لوحة المدير (جداول إحصائية فقط) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات إنجازات المناديب")
        col_start, col_end = st.columns(2)
        with col_start: d1 = st.date_input("من تاريخ", date(2025, 1, 1))
        with col_end: d2 = st.date_input("إلى تاريخ", date.today())
        
        hist_df = pd.read_sql("SELECT * FROM status_history", conn)
        if not hist_df.empty:
            hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
            filtered = hist_df[(hist_df['timestamp'].dt.date >= d1) & (hist_df['timestamp'].dt.date <= d2)]
            
            if not filtered.empty:
                # جدول مجمع يوضح عدد الحالات لكل مندوب
                summary = filtered.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
                st.subheader("📋 ملخص النشاط لكل يوزر (كم تعميد، كم اجتماع، إلخ)")
                st.dataframe(summary, use_container_width=True)
                
                st.subheader("📝 سجل الحركات التفصيلي")
                st.dataframe(filtered[['changed_by', 'customer_name', 'updated_status', 'timestamp', 'notes']], use_container_width=True, hide_index=True)
            else: st.warning("لا توجد سجلات في هذه الفترة.")

    # --- إدارة المستخدمين ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة مستخدم", "تعديل باسورد", "حذف"])
        with t1:
            n, u, p = st.text_input("الاسم الكامل"), st.text_input("اليوزر"), st.text_input("الباسورد")
            if st.button("حفظ المستخدم الجديد"):
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, 'rep', n))
                conn.commit(); st.success("تم الإضافة")
        with t2:
            u_list = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
            u_sel = st.selectbox("المستخدم", u_list)
            np = st.text_input("الباسورد الجديد")
            if st.button("تحديث"):
                conn.execute("UPDATE users SET password=? WHERE username=?", (np, u_sel)); conn.commit(); st.success("تم التعديل")
        with t3:
            u_del = st.selectbox("حذف مستخدم نهائياً", [x for x in u_list if x != 'admin'])
            if st.button("تأكيد الحذف"):
                conn.execute("DELETE FROM users WHERE username=?", (u_del,)); conn.commit(); st.success("تم الحذف"); st.rerun()

    # --- استيراد ملف ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد ملف العملاء")
        f = st.file_uploader("اختر ملف Excel أو CSV", type=['xlsx', 'csv'])
        if f and st.button("بدء الاستيراد الفوري"):
            try:
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.to_sql('customers', conn, if_exists='append', index=False)
                st.success("✅ تم استيراد البيانات وربطها بالمناديب بنجاح")
            except Exception as e: st.error(f"حدث خطأ في الملف: {e}")

    # --- إضافة عميل ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("add_client_final"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                code = st.selectbox("الدولة *", list(COUNTRY_CODES.keys()))
            with c2:
                mob = st.text_input("رقم الجوال *")
                rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            if st.form_submit_button("حفظ العميل"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                # منع التكرار البرمجي
                exists = conn.execute("SELECT sales_rep FROM customers WHERE mobile=?", (full_mob,)).fetchone()
                if exists: st.error(f"⚠️ مكرر! العميل مسجل مسبقاً مع المندوب: {exists[0]}")
                elif comp and mob:
                    conn.execute("INSERT INTO customers (company_name, mobile, sales_rep) VALUES (?,?,?)", (comp, full_mob, rep))
                    conn.commit(); st.success("تم الحفظ بنجاح")

    # --- البحث الشامل ---
    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث الشامل")
        query = st.text_input("🔎 ابحث عن أي معلومة:")
        if query:
            all_c = pd.read_sql("SELECT * FROM customers", conn)
            res = all_c[all_c.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
            st.dataframe(res, use_container_width=True, hide_index=True)
