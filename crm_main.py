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
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "المغرب (+212)": "212"
}

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

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
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# ==========================================
#           دوال التحقق والمنطق
# ==========================================

def check_duplicate_info(comp_name, mob, em):
    c = conn.cursor()
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة|للتجارة', '', comp_name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"اسم مشابه لـ ({res[0]}) مع المندوب: {res[1]}"
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"رقم الجوال ({mob}) مكرر مع المندوب: {res[1]}"
    return None

def validate_intl_mobile(country_code, number):
    cleaned_num = re.sub(r'\D', '', number)
    if country_code == "966":
        if cleaned_num.startswith('0'): cleaned_num = cleaned_num[1:]
        return len(cleaned_num) == 9 and cleaned_num.startswith('5'), cleaned_num
    return len(cleaned_num) >= 7, cleaned_num

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Expo Time CRM")
        user = st.text_input("اسم المستخدم")
        pw = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
            acc = c.fetchone()
            if acc:
                st.session_state.update({'logged_in': True, 'user_role': acc[2], 'real_name': acc[3]})
                st.rerun()
            else: st.error("بيانات خاطئة")
else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (تعديل كامل للمدير والمندوب) ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        tab_my, tab_all = st.tabs(["📂 إدارة العمليات", "🌍 قاعدة البيانات الشاملة"])
        
        with tab_my:
            rep_name = st.session_state['real_name']
            reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
            if role == 'admin':
                rep_name = st.selectbox("اختر المندوب لإدارة عملائه:", reps) if reps else rep_name
            
            my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_name,))
            if not my_data.empty:
                search_q = st.text_input("🔎 ابحث بالاسم أو الجوال:")
                df_view = my_data[my_data.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)] if search_q else my_data
                
                client_opts = {row['id']: f"{row['company_name']} - {row['mobile']}" for i, row in df_view.iterrows()}
                sid = st.selectbox("👇 اختر العميل للتعديل:", list(client_opts.keys()), format_func=lambda x: client_opts[x])
                row = my_data[my_data['id'] == sid].iloc[0]
                
                with st.form("edit_full"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_cname = st.text_input("اسم الشركة", value=row['company_name'])
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                    with c2:
                        new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']) if row['status'] in TRIP_STAGES else 0)
                        note = st.text_area("ملاحظات المتابعة")
                    
                    if st.form_submit_button("💾 حفظ التعديلات"):
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, status=? WHERE id=?", (new_cname, new_mob, new_st, sid))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)",
                                     (sid, new_cname, new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم التحديث بنجاح"); st.rerun()

        with tab_all:
            st.subheader("🌍 تعديل الداتا الرئيسية")
            all_data = pd.read_sql("SELECT * FROM customers", conn)
            # تمكين التعديل المباشر في الجدول للمدير فقط
            if role == 'admin':
                st.write("💡 يمكنك التعديل مباشرة من الجدول أدناه ثم ضغط 'حفظ' (للمدير فقط)")
                edited_df = st.data_editor(all_data, use_container_width=True, hide_index=True, column_config={"id": None})
                if st.button("💾 حفظ تغييرات الجدول"):
                    for i, r in edited_df.iterrows():
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, sales_rep=?, status=? WHERE id=?", 
                                     (r['company_name'], r['mobile'], r['sales_rep'], r['status'], r['id']))
                    conn.commit(); st.success("تم حفظ تغييرات قاعدة البيانات الرئيسية")
            else:
                st.dataframe(all_data, use_container_width=True, hide_index=True, column_config={"id": None})

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            col1, col2 = st.columns(2)
            with col1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont = st.text_input("الشخص المسؤول")
            with col2:
                c_key = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_in = st.text_input("رقم الجوال *")
                em = st.text_input("الإيميل")
            
            reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
            rep = st.selectbox("المندوب", reps) if role == 'admin' and reps else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            
            if st.form_submit_button("حفظ"):
                is_v, f_mob = validate_intl_mobile(COUNTRY_CODES[c_key], mob_in)
                full_mob = f"+{COUNTRY_CODES[c_key]}{f_mob}"
                dup = check_duplicate_info(comp, full_mob, em)
                if dup: st.error(f"❌ مكرر: {dup}")
                elif comp and is_v:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, mobile, email, sales_rep) VALUES (?,?,?,?,?,?)",
                                 (comp, sec, cont, full_mob, em, rep))
                    conn.commit(); st.success("تم الحفظ")

    # (بقية خيارات المدير: لوحة المدير، المستخدمين، استيراد ملف، تظل كما هي في كودك الأصلي)
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف Excel", type=['xlsx', 'csv'])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            st.dataframe(df.head())
            if st.button("بدء الاستيراد"):
                df.to_sql('customers', conn, if_exists='append', index=False)
                st.success("تم الاستيراد بنجاح")
