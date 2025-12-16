import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
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
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Expo Time CRM")
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
                else: st.error("بيانات خاطئة")
        else:
            name = st.text_input("الاسم الكامل")
            user = st.text_input("اسم المستخدم الجديد")
            pw = st.text_input("كلمة المرور", type="password")
            if st.button("تسجيل"):
                try:
                    conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user, pw, 'rep', name))
                    conn.commit(); st.success("تم التسجيل")
                except: st.error("المستخدم موجود")
else:
    role = st.session_state['user_role']
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (المطورة) ---
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المبيعات")
        rep_n = st.session_state['real_name']
        if role == 'admin':
            reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
            rep_n = st.selectbox("اختر المندوب:", reps) if reps else rep_n
        
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_n,))
        if not my_data.empty:
            sid = st.selectbox("👇 اختر العميل:", my_data['id'].tolist(), format_func=lambda x: my_data[my_data['id']==x]['company_name'].values[0])
            row = my_data[my_data['id'] == sid].iloc[0]
            
            # لوحة بيانات العميل الشاملة
            st.markdown("### 📋 بطاقة بيانات العميل")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**🏢 الشركة:** {row['company_name']}")
                st.write(f"**👤 المسؤول:** {row['contact_person'] or 'غير مسجل'}")
            with c2:
                st.write(f"**📱 الجوال:** {row['mobile']}")
                st.write(f"**📧 الإيميل:** {row['email'] or 'غير مسجل'}")
            with c3:
                st.write(f"**🤝 المندوب:** {row['sales_rep']}")
                st.link_button("💬 مراسلة واتساب", f"https://wa.me/{re.sub(r'\D', '', row['mobile'])}")
            
            st.divider()
            with st.form("up_form"):
                # المدير فقط يعدل اسم الشركة والجوال
                new_n = st.text_input("تعديل اسم الشركة", value=row['company_name'], disabled=(role != 'admin'))
                new_m = st.text_input("تعديل الجوال", value=row['mobile'], disabled=(role != 'admin'))
                new_st = st.selectbox("الحالة الحالية", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                note = st.text_area("ملاحظات المتابعة")
                if st.form_submit_button("حفظ"):
                    conn.execute("UPDATE customers SET company_name=?, mobile=?, status=? WHERE id=?", (new_n, new_m, new_st, sid))
                    conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (sid, new_n, new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit(); st.success("تم التحديث"); st.rerun()

    # --- المستخدمين (مفعل بالكامل الآن) ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["قائمة وإضافة", "تعديل كلمة مرور", "حذف"])
        with t1:
            st.subheader("إضافة مستخدم جديد")
            n = st.text_input("الاسم الكامل")
            u = st.text_input("يوزر")
            p = st.text_input("باسورد")
            if st.button("إنشاء حساب"):
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, 'rep', n))
                conn.commit(); st.success("تم"); st.rerun()
            st.divider()
            st.subheader("المستخدمين الحاليين")
            st.dataframe(pd.read_sql("SELECT username, real_name, role FROM users", conn), use_container_width=True)
        with t2:
            u_list = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
            u_sel = st.selectbox("اختر المستخدم", u_list)
            new_p = st.text_input("كلمة مرور جديدة")
            if st.button("تحديث"):
                conn.execute("UPDATE users SET password=? WHERE username=?", (new_p, u_sel)); conn.commit(); st.success("تم")
        with t3:
            u_del = st.selectbox("حذف مستخدم", [x for x in u_list if x != 'admin'])
            if st.button("تأكيد الحذف النهائي"):
                conn.execute("DELETE FROM users WHERE username=?", (u_del,)); conn.commit(); st.success("تم"); st.rerun()

    # --- استيراد ملف (مفعل بالكامل الآن) ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف Excel", type=['xlsx', 'csv'])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            st.dataframe(df.head())
            if st.button("بدء الاستيراد"):
                df.to_sql('customers', conn, if_exists='append', index=False)
                st.success("تم الاستيراد بنجاح")

    # --- إضافة عميل (مفاتيح الدول) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_c"):
            comp = st.text_input("اسم الشركة *")
            code = st.selectbox("الدولة *", list(COUNTRY_CODES.keys()))
            mob = st.text_input("الجوال *")
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            if st.form_submit_button("حفظ"):
                f_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                conn.execute("INSERT INTO customers (company_name, mobile, sales_rep) VALUES (?,?,?)", (comp, f_mob, rep))
                conn.commit(); st.success("تم الحفظ")

    # --- لوحة المدير (إنجازات) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إنجازات المناديب")
        d1 = st.date_input("من", date(2025, 1, 1))
        d2 = st.date_input("إلى", date.today())
        hist = pd.read_sql("SELECT * FROM status_history", conn)
        if not hist.empty:
            hist['timestamp'] = pd.to_datetime(hist['timestamp'])
            filtered = hist[(hist['timestamp'].dt.date >= d1) & (hist['timestamp'].dt.date <= d2)]
            if not filtered.empty:
                # 
                st.dataframe(filtered.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0), use_container_width=True)

    # --- البحث الشامل ---
    elif nav == "بحث شامل":
        st.header("🔍 بحث")
        q = st.text_input("ابحث عن أي معلومة:")
        if q:
            all_data = pd.read_sql("SELECT * FROM customers", conn)
            res = all_data[all_data.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            st.dataframe(res, use_container_width=True, hide_index=True)
