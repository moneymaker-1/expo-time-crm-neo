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

# قائمة كاملة بجميع الدول العربية الـ 22
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

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db')
    c = conn.cursor()
    # إضافة عمود مبلغ التعميد لجدول العملاء
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
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# ==========================================
#              دوال التحقق
# ==========================================

def check_duplicate_info(comp_name, mob):
    c = conn.cursor()
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة', '', comp_name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"الشركة مسجلة باسم مشابه ({res[0]}) مع المندوب: {res[1]}"
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"رقم الجوال ({mob}) مسجل مع المندوب: {res[1]}"
    return None

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Expo Time CRM")
        choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
        user = st.text_input("اسم المستخدم")
        pw = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
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
        if nav == "خروج":
            st.session_state.clear()
            st.rerun()

    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        rep_name = st.session_state['real_name']
        if role == 'admin':
            reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
            rep_name = st.selectbox("اختر المندوب:", reps) if reps else rep_name
        
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep_name,))
        if not my_data.empty:
            search_q = st.text_input("🔎 ابحث بالاسم:")
            df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
            selected_id = st.selectbox("👇 اختر العميل:", df_view['id'], format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
            row = my_data[my_data['id'] == selected_id].iloc[0]
            
            c1, c2 = st.columns([1, 1.5])
            with c1:
                st.subheader("📋 بيانات العميل")
                # زر الواتساب
                clean_phone = re.sub(r'\D', '', str(row['mobile']))
                wa_link = f"https://wa.me/{clean_phone}"
                st.markdown(f'<a href="{wa_link}" target="_blank"><button style="background-color:#25D366;color:white;border:none;padding:10px;border-radius:5px;width:100%;cursor:pointer;">💬 مراسلة واتساب</button></a>', unsafe_allow_html=True)
                st.info(f"الشركة: {row['company_name']}\n\nالجوال: {row['mobile']}")

            with c2:
                with st.form("status_update"):
                    new_stage = st.selectbox("الحالة الجديدة:", TRIP_STAGES, index=TRIP_STAGES.index(row['status']) if row['status'] in TRIP_STAGES else 0)
                    # خانة مبلغ التعميد
                    amt = st.number_input("مبلغ التعميد (في حال تم التعميد فقط)", value=float(row['contract_amount'])) if new_stage == "تم التعميد" else 0.0
                    note = st.text_area("ملاحظات المتابعة:")
                    if st.form_submit_button("✅ حفظ"):
                        conn.execute("UPDATE customers SET status = ?, contract_amount = ? WHERE id = ?", (new_stage, amt, selected_id))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                                     (selected_id, row['company_name'], new_stage, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم التحديث"); st.rerun()

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب")
            with c2:
                # مفتاح الدولة المباشر (22 دولة عربية)
                c_code = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_num = st.text_input("رقم الجوال *")
                em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
            
            reps = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
            rep = st.selectbox("المندوب", reps) if role == 'admin' and reps else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[c_code]}{mob_num.strip()}"
                dup = check_duplicate_info(comp, full_mob)
                if dup: st.error(f"❌ مكرر: {dup}")
                elif comp and mob_num:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)",
                                 (comp, sec, cont, pos, full_mob, em, evt, rep))
                    conn.commit(); st.success("تم الحفظ بنجاح")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 الإحصائيات المجمعة")
        df_hist = pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn)
        if not df_hist.empty:
            summary = df_hist.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
            st.dataframe(summary, use_container_width=True)
