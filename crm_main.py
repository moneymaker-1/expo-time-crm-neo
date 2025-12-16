import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import re 

# ==========================================
#              إعدادات النظام
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢")

# قاموس ترجمة الأعمدة للعرض (لتحويل الواجهة للعربية)
COLUMN_MAP = {
    "id": "المعرف",
    "company_name": "اسم الشركة",
    "sector": "القطاع",
    "contact_person": "الشخص المسؤول",
    "position": "المنصب",
    "mobile": "رقم الجوال",
    "email": "البريد الإلكتروني",
    "event_name": "الفعالية",
    "sales_rep": "المندوب",
    "status": "الحالة",
    "contract_amount": "مبلغ التعميد"
}

# قائمة الـ 22 دولة عربية ومفاتيحها
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "العراق (+964)": "964",
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
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد', contract_amount REAL DEFAULT 0)''')
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
            st.session_state.update({'logged_in': True, 'user_role': acc[2], 'real_name': acc[3], 'username': acc[0]})
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
                search_q = st.text_input("🔎 ابحث بالاسم:")
                df_f = df[df['company_name'].str.contains(search_q, case=False)]
                
                # عرض الجدول معرباً
                st.dataframe(df_f.rename(columns=COLUMN_MAP), use_container_width=True, hide_index=True)
                
                st.divider()
                selected_id = st.selectbox("اختر شركة للتعديل أو التواصل:", df_f['id'].tolist(), format_func=lambda x: df_f[df_f['id']==x]['company_name'].values[0])
                row = df[df['id']==selected_id].iloc[0]
                
                with st.form("edit_area"):
                    c1, c2 = st.columns(2)
                    with c1:
                        # المدير فقط يعدل اسم الشركة
                        new_name = st.text_input("اسم الشركة", value=row['company_name'], disabled=(role != 'admin'))
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                        wa_url = f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}"
                        st.link_button("💬 واتساب مباشر", wa_url)
                    with c2:
                        new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                        note = st.text_area("ملاحظات المتابعة")
                    
                    if st.form_submit_button("حفظ التعديلات"):
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, status=? WHERE id=?", (new_name, new_mob, new_st, selected_id))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", 
                                     (selected_id, new_name, new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم الحفظ"); st.rerun()
            else: st.info("لا توجد بيانات.")

        with t2:
            all_df = pd.read_sql("SELECT * FROM customers", conn)
            st.dataframe(all_df.rename(columns=COLUMN_MAP), use_container_width=True, hide_index=True)

    # --- إضافة عميل ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("الشركة *"), st.selectbox("القطاع", ["تقنية", "عقارات", "تجارة", "صناعة"])
                cont, pos = st.text_input("المسؤول"), st.text_input("المنصب")
            with c2:
                code = st.selectbox("الدولة *", list(COUNTRY_CODES.keys()))
                mob = st.text_input("الجوال *")
                em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
            
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                dup = check_duplicate(comp, full_mob)
                if dup: st.error(dup)
                elif comp and mob:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)",
                                 (comp, sec, cont, pos, full_mob, em, evt, rep))
                    conn.commit(); st.success("تم الحفظ")

    # --- استيراد ملف ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف", type=['xlsx', 'csv'])
        if f and st.button("🚀 بدء الاستيراد والربط"):
            df_in = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            # محاولة تعريب الأعمدة برمجياً لربطها
            inv_map = {v: k for k, v in COLUMN_MAP.items()}
            df_in.rename(columns=inv_map, inplace=True)
            df_in.to_sql('customers', conn, if_exists='append', index=False)
            st.success("تم الاستيراد والربط بنجاح!")

    # --- بحث شامل ---
    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث")
        q = st.text_input("ابحث عن شركة أو جوال:")
        if q:
            res = pd.read_sql(f"SELECT * FROM customers WHERE company_name LIKE '%{q}%' OR mobile LIKE '%{q}%'", conn)
            st.dataframe(res.rename(columns=COLUMN_MAP), use_container_width=True, hide_index=True)

    # --- المستخدمين ولوحة المدير ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t_add, t_pass, t_del = st.tabs(["إضافة", "تعديل كلمة مرور", "حذف"])
        with t_add:
            n, u, p = st.text_input("الاسم"), st.text_input("يوزر"), st.text_input("باس")
            if st.button("تأكيد الإضافة"):
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, 'rep', n))
                conn.commit(); st.success("تم")
        with t_pass:
            users = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
            u_sel = st.selectbox("اختر المستخدم", users)
            new_p = st.text_input("كلمة مرور جديدة")
            if st.button("تحديث الباسورد"):
                conn.execute("UPDATE users SET password=? WHERE username=?", (new_p, u_sel))
                conn.commit(); st.success("تم")
        with t_del:
            u_del = st.selectbox("حذف مستخدم", [x for x in users if x != 'admin'])
            if st.button("حذف نهائي"):
                conn.execute("DELETE FROM users WHERE username=?", (u_del,))
                conn.commit(); st.success("تم"); st.rerun()

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 الإحصائيات")
        df_all = pd.read_sql("SELECT * FROM customers", conn)
        if not df_all.empty:
            st.plotly_chart(px.bar(df_all, x='sales_rep', color='status', title="توزيع الحالات حسب المناديب"), use_container_width=True)
            st.dataframe(pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn).rename(columns=COLUMN_MAP), use_container_width=True)
