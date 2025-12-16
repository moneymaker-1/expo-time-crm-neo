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

# قائمة الدول العربية للتحديث الجديد
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "العراق (+964)": "964",
    "المغرب (+212)": "212", "تونس (+216)": "216"
}

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

# --- قاعدة البيانات (مطابقة لهيكلك الأصلي لضمان عدم ضياع الداتا) ---
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

# --- دوال التحقق المتقدمة ---
def check_duplicate_info(comp_name, mob):
    c = conn.cursor()
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة', '', comp_name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"تنبيه: الشركة مسجلة مسبقاً باسم مشابه ({res[0]}) مع المندوب: {res[1]}"
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"تنبيه: رقم الجوال ({mob}) مسجل مسبقاً مع المندوب: {res[1]}"
    return None

# ==========================================
#              واجهة التطبيق
# ==========================================

# صفحة الدخول الأصلية
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

    # --- بوابة المبيعات (مع الإكمال التلقائي وصلاحية التعديل) ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        tab_my, tab_all = st.tabs(["📂 عملائي (بحث وإدارة)", "🌍 قاعدة البيانات الشاملة"])
        
        with tab_my:
            rep_name = st.session_state['real_name']
            if role == 'admin':
                reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
                rep_name = st.selectbox("اختر المندوب للعرض:", reps) if reps else rep_name
            
            my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_name,))
            if not my_data.empty:
                # ميزة الإكمال التلقائي هنا
                search_q = st.text_input("🔎 ابحث بالاسم (الاقتراحات ستظهر أدناه):")
                df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)] if search_q else my_data
                
                client_opts = {row['id']: row['company_name'] for i, row in df_view.iterrows()}
                if client_opts:
                    sid = st.selectbox("👇 اختر العميل من القائمة المفلترة:", list(client_opts.keys()), format_func=lambda x: client_opts[x])
                    row = my_data[my_data['id'] == sid].iloc[0]
                    
                    with st.form("edit_form"):
                        c1, c2 = st.columns(2)
                        with c1:
                            new_cname = st.text_input("اسم الشركة", value=row['company_name'])
                            new_mob = st.text_input("الجوال", value=row['mobile'])
                            st.link_button("💬 مراسلة واتساب", f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}")
                        with c2:
                            new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']) if row['status'] in TRIP_STAGES else 0)
                            note = st.text_area("ملاحظات المتابعة")
                        
                        if st.form_submit_button("💾 حفظ التعديلات"):
                            conn.execute("UPDATE customers SET company_name=?, mobile=?, status=? WHERE id=?", (new_cname, new_mob, new_st, sid))
                            conn.commit(); st.success("تم التحديث"); st.rerun()
            else: st.info("لا يوجد عملاء لهذا المندوب.")

        with tab_all:
            st.subheader("🌍 البحث في جميع العملاء")
            all_df = pd.read_sql("SELECT * FROM customers", conn)
            # إخفاء الـ id وتوسيع الجدول للعرض الكامل
            st.dataframe(all_df, use_container_width=True, hide_index=True, column_config={"id": None})

    # --- إضافة عميل (استعادة كافة الحقول الأصلية) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            col1, col2 = st.columns(2)
            with col1:
                comp = st.text_input("اسم الشركة *")
                sec = st.selectbox("القطاع", SECTORS)
                cont = st.text_input("الشخص المسؤول")
                pos = st.text_input("المنصب")
            with col2:
                c_key = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_in = st.text_input("رقم الجوال *")
                em = st.text_input("الإيميل *")
                evt = st.text_input("الفعالية")
            
            reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
            rep = st.selectbox("المندوب", reps) if role == 'admin' and reps else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[c_key]}{mob_in.strip()}"
                dup_reason = check_duplicate_info(comp, full_mob)
                if dup_reason: st.error(dup_reason)
                elif comp and mob_in:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)",
                                 (comp, sec, cont, pos, full_mob, em, evt, rep))
                    conn.commit(); st.success("تم الحفظ بنجاح")

    # --- استيراد ملف (استعادة الميزة الأصلية) ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد Excel/CSV")
        f = st.file_uploader("اختر الملف", type=['csv', 'xlsx'])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            st.dataframe(df.head())
            if st.button("بدء الاستيراد"):
                df.to_sql('customers', conn, if_exists='append', index=False)
                st.success("تم الاستيراد بنجاح")
