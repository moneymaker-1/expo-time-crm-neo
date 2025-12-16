import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import re 

# ==========================================
#              إعدادات النظام
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢")

# قائمة الـ 22 دولة عربية
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

TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

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

# --- دوال التحقق ---
def check_duplicate(name, mob):
    c = conn.cursor()
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة', '', name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"الشركة مكررة مع المندوب: {res[1]}"
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"الجوال مكرر مع المندوب: {res[1]}"
    return None

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state.get('logged_in'):
    st.title("🔐 Expo Time CRM")
    choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
    user = st.text_input("اسم المستخدم")
    pw = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?) AND password=?", (user, pw))
        acc = c.fetchone()
        if acc:
            st.session_state.update({'logged_in': True, 'user_role': acc[2], 'real_name': acc[3]})
            st.rerun()
        else: st.error("خطأ في البيانات")
else:
    role = st.session_state['user_role']
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة العملاء")
        t1, t2 = st.tabs(["📂 عملائي", "🌍 قاعدة البيانات الشاملة"])
        with t1:
            my_name = st.session_state['real_name']
            if role == 'admin':
                reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
                my_name = st.selectbox("اختر المندوب:", reps) if reps else my_name
            
            df = pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(my_name,))
            if not df.empty:
                search_q = st.text_input("🔎 ابحث بالاسم (إكمال تلقائي):")
                df_f = df[df['company_name'].str.contains(search_q, case=False)]
                selected_id = st.selectbox("اختر شركة للتعديل:", df_f['id'].tolist(), format_func=lambda x: df_f[df_f['id']==x]['company_name'].values[0])
                row = df[df['id']==selected_id].iloc[0]
                
                with st.form("edit_area"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_name = st.text_input("اسم الشركة", value=row['company_name'], disabled=(role != 'admin'))
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                        st.link_button("💬 واتساب مباشر", f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}")
                    with c2:
                        new_st = st.selectbox("الحالة الحالية", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                        note = st.text_area("ملاحظات المتابعة")
                    if st.form_submit_button("حفظ"):
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, status=? WHERE id=?", (new_name, new_mob, new_st, selected_id))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (selected_id, new_name, new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم التحديث"); st.rerun()
            else: st.info("لا توجد بيانات.")

    # --- إضافة عميل ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("الشركة *"), st.selectbox("القطاع", ["تقنية", "عقارات", "تجارة", "صناعة"])
                cont, pos = st.text_input("المسؤول"), st.text_input("المنصب")
            with c2:
                code = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob = st.text_input("الجوال *")
                em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                dup = check_duplicate(comp, full_mob)
                if dup: st.error(dup)
                elif comp and mob:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)", (comp, sec, cont, pos, full_mob, em, evt, rep))
                    conn.commit(); st.success("تم الحفظ")

    # --- لوحة المدير (الفلتر والإحصائيات المجمعة) ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات أداء المناديب")
        
        # فلتر التاريخ
        c_d1, c_d2 = st.columns(2)
        with c_d1: d_start = st.date_input("من تاريخ", date(2023, 1, 1))
        with c_d2: d_end = st.date_input("إلى تاريخ", date.today())
        
        # جلب البيانات المفلترة من السجل
        history = pd.read_sql("SELECT * FROM status_history", conn)
        if not history.empty:
            history['timestamp'] = pd.to_datetime(history['timestamp'])
            history = history[(history['timestamp'].dt.date >= d_start) & (history['timestamp'].dt.date <= d_end)]
            
            if not history.empty:
                # إنشاء الجدول المجمع
                summary = history.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0).reset_index()
                summary.columns.name = None
                summary.rename(columns={'changed_by': 'اسم المندوب'}, inplace=True)
                
                st.subheader("📈 ملخص العمليات لكل مندوب")
                st.dataframe(summary, use_container_width=True, hide_index=True)
                
                # رسم بياني
                st.plotly_chart(px.bar(history, x='changed_by', color='updated_status', title="توزيع الحالات"), use_container_width=True)
            else: st.warning("لا توجد عمليات في هذه الفترة.")
        
    # --- المستخدمين (إدارة كاملة) ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة", "تغيير باسورد", "حذف"])
        with t1:
            n, u, p = st.text_input("الاسم"), st.text_input("اليوزر"), st.text_input("الباسورد")
            if st.button("إنشاء"):
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, 'rep', n))
                conn.commit(); st.success("تم")
        with t2:
            u_list = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
            u_sel = st.selectbox("اختر المستخدم", u_list)
            np = st.text_input("باسورد جديد")
            if st.button("تحديث"):
                conn.execute("UPDATE users SET password=? WHERE username=?", (np, u_sel))
                conn.commit(); st.success("تم")
        with t3:
            u_del = st.selectbox("حذف مستخدم", [x for x in u_list if x != 'admin'])
            if st.button("حذف نهائي"):
                conn.execute("DELETE FROM users WHERE username=?", (u_del,)); conn.commit(); st.success("تم"); st.rerun()

    # --- استيراد ملف وبحث شامل ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف", type=['xlsx', 'csv'])
        if f and st.button("بدء الاستيراد"):
            df_in = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df_in.to_sql('customers', conn, if_exists='append', index=False)
            st.success("تم الاستيراد")

    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث")
        q = st.text_input("ابحث عن شركة، جوال، أو مندوب:")
        if q:
            all_data = pd.read_sql("SELECT * FROM customers", conn)
            res = all_data[all_data.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            st.dataframe(res, use_container_width=True, hide_index=True)
