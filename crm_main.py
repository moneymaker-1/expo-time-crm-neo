import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
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

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    # إضافة أعمدة المبالغ والتواريخ للتحديث الجديد
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, 
        status TEXT DEFAULT 'جديد',
        quote_value REAL DEFAULT 0, 
        contract_value REAL DEFAULT 0, 
        quote_date TEXT)''')
    
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
#              دوال النظام المحدثة
# ==========================================

def update_customer_status_advanced(cid, cname, new_status, user, notes="", q_val=0, c_val=0):
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    if new_status == "تم تقديم عرض مالي":
        c.execute("UPDATE customers SET status=?, quote_value=?, quote_date=? WHERE id=?", (new_status, q_val, today_date, cid))
    elif new_status == "تم التعميد":
        c.execute("UPDATE customers SET status=?, contract_value=? WHERE id=?", (new_status, c_val, cid))
    else:
        c.execute("UPDATE customers SET status=? WHERE id=?", (new_status, cid))
    
    c.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)",
              (cid, cname, new_status, user, notes, now_str))
    conn.commit()

def validate_mobile(mobile):
    cleaned_mobile = mobile.replace(" ", "").strip()
    return len(cleaned_mobile) == 10 and cleaned_mobile.isdigit()

def validate_email(email):
    regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(regex, email) is not None

def login_user(username, password):
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (username, password))
    return c.fetchone()

def create_user(username, password, real_name, role='rep'):
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, password, role, real_name))
        conn.commit()
        return True
    except: return False

def get_all_users(): return pd.read_sql("SELECT username, role, real_name FROM users", conn)
def get_all_reps(): return pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
def get_all_data(): return pd.read_sql("SELECT * FROM customers", conn)
def get_my_data(rep): return pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep,))
def get_client_history(cid): return pd.read_sql("SELECT * FROM status_history WHERE customer_id = ? ORDER BY id DESC", conn, params=(cid,))
def get_history_log(): return pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn)

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
                account = login_user(user, pw)
                if account:
                    st.session_state['logged_in'], st.session_state['user_role'], st.session_state['real_name'] = True, account[2], account[3]
                    st.rerun()
                else: st.error("بيانات خاطئة")
        else:
            name, user, pw = st.text_input("الاسم الكامل"), st.text_input("اسم المستخدم"), st.text_input("كلمة المرور", type="password")
            if st.button("تسجيل"):
                if create_user(user, pw, name): st.success("تم التسجيل")
                else: st.error("المستخدم موجود")
else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        rep_name = st.session_state['real_name']
        my_data = get_my_data(rep_name)

        # --- 1. نظام التنبيهات (3 أيام) ---
        if not my_data.empty:
            overdue_alerts = []
            for _, row in my_data.iterrows():
                if row['status'] == "تم تقديم عرض مالي" and row['quote_date']:
                    q_date = datetime.strptime(row['quote_date'], "%Y-%m-%d")
                    if (datetime.now() - q_date).days >= 3:
                        overdue_alerts.append(row['company_name'])
            if overdue_alerts:
                st.error(f"⚠️ تنبيه متابعة: عروض أسعار الشركات التالية مضى عليها 3 أيام: {', '.join(overdue_alerts)}")

        # --- 2. إحصائيات المندوب الشهرية ---
        st.subheader("📊 إنجازك لهذا الشهر")
        c1, c2, c3 = st.columns(3)
        c1.metric("عروض قُدمت", len(my_data[my_data['status']=="تم تقديم عرض مالي"]) if not my_data.empty else 0)
        c2.metric("عروض عُمّدت", len(my_data[my_data['status']=="تم التعميد"]) if not my_data.empty else 0)
        c3.metric("عروض رُفضت", len(my_data[my_data['status']=="تم الرفض"]) if not my_data.empty else 0)

        st.divider()

        if not my_data.empty:
            search_q = st.text_input("🔎 ابحث في عملائك (اسم، جوال...):", key="search_my")
            filter_status = st.selectbox("فلترة بالمرحلة:", ["الكل"] + TRIP_STAGES)
            
            df_view = my_data.copy()
            if search_q: df_view = df_view[df_view.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
            if filter_status != "الكل": df_view = df_view[df_view['status'] == filter_status]
            
            client_options = {row['id']: f"{row['company_name']} - {row['contact_person']}" for i, row in df_view.iterrows()}
            if client_options:
                sid = st.selectbox("👇 اختر العميل لإدارة ملفه:", options=list(client_options.keys()), format_func=lambda x: client_options[x])
                client_row = df_view[df_view['id'] == sid].iloc[0]
                
                col_info, col_action = st.columns([1, 1.5])
                with col_info:
                    st.subheader("📋 بيانات العميل")
                    st.info(f"**الشركة:** {client_row['company_name']}\n\n**الجوال:** {client_row['mobile']}\n\n**القطاع:** {client_row['sector']}")
                
                with col_action:
                    st.subheader("🚀 تحديث المرحلة والمبالغ")
                    with st.form("status_update"):
                        new_stage = st.selectbox("المرحلة الجديدة:", TRIP_STAGES, index=TRIP_STAGES.index(client_row['status']))
                        q_val = st.number_input("قيمة عرض السعر:", value=float(client_row['quote_value'] or 0)) if new_stage == "تم تقديم عرض مالي" else 0
                        c_val = st.number_input("قيمة التعميد:", value=float(client_row['contract_value'] or 0)) if new_stage == "تم التعميد" else 0
                        note = st.text_area("ملاحظات المتابعة:")
                        if st.form_submit_button("✅ حفظ التحديث"):
                            update_customer_status_advanced(sid, client_row['company_name'], new_stage, st.session_state['real_name'], note, q_val, c_val)
                            st.success("تم الحفظ!")
                            st.rerun()
        else: st.info("ليس لديك عملاء مسجلين بعد.")

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب (اختياري)") 
            with c2:
                mob, em, evt = st.text_input("الجوال *"), st.text_input("الإيميل *"), st.text_input("الفعالية")
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            if st.form_submit_button("حفظ"):
                if comp and validate_mobile(mob) and validate_email(em):
                    c = conn.cursor()
                    c.execute('''INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep, status)
                                 VALUES (?,?,?,?,?,?,?,?,'جديد')''', (comp, sec, cont, pos, mob, em, evt, rep))
                    conn.commit()
                    st.success("تم الحفظ!")
                else: st.error("تأكد من صحة البيانات الإلزامية")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 الإحصائيات العامة")
        df = get_all_data()
        if not df.empty:
            st.metric("إجمالي التعميدات", f"{df['contract_value'].sum()} ريال")
            st.plotly_chart(px.bar(df, x='sales_rep', y='contract_value', color='status', title="أداء المناديب المالي"))
            st.dataframe(df)

    elif nav == "بحث شامل":
        st.header("🔍 بحث في كل النظام")
        s = st.text_input("بحث...")
        if s:
            df = get_all_data()
            st.dataframe(df[df.astype(str).apply(lambda x: x.str.contains(s, case=False)).any(axis=1)])
