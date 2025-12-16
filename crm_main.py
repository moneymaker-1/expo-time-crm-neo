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

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    # الجدول الشامل بجميع الخانات السابقة والجديدة
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        company_name TEXT, 
        sector TEXT, 
        contact_person TEXT, 
        position TEXT, 
        mobile TEXT, 
        email TEXT, 
        event_name TEXT, 
        sales_rep TEXT, 
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
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]

# --- دالة تحديث الحالة مع المبالغ ---
def update_status_advanced(cid, cname, new_status, user, notes="", q_val=0, c_val=0):
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

# ==========================================
#              واجهة التطبيق
# ==========================================
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Expo Time CRM")
        u = st.text_input("اسم المستخدم")
        p = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
            acc = c.fetchone()
            if acc:
                st.session_state['logged_in'], st.session_state['user_role'], st.session_state['real_name'] = True, acc[2], acc[3]
                st.rerun()
            else: st.error("بيانات خاطئة")
else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "خروج"] if st.session_state['user_role'] == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات ---
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المتابعة الذكية")
        rep_name = st.session_state['real_name']
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_name,))
        
        # 1. التنبيهات (3 أيام على عرض السعر)
        if not my_data.empty:
            overdue = []
            for _, row in my_data.iterrows():
                if row['status'] == "تم تقديم عرض مالي" and row['quote_date']:
                    q_date = datetime.strptime(row['quote_date'], "%Y-%m-%d")
                    if (datetime.now() - q_date).days >= 3:
                        overdue.append(row['company_name'])
            if overdue:
                st.error(f"⚠️ تنبيه: العروض المالية للشركات التالية مر عليها 3 أيام: {', '.join(overdue)}")

        # 2. إحصائيات المندوب الشهرية
        st.subheader("📊 إنجازك لهذا الشهر")
        c1, c2, c3 = st.columns(3)
        c1.metric("عروض قُدمت", len(my_data[my_data['status']=="تم تقديم عرض مالي"]) if not my_data.empty else 0)
        c2.metric("عروض عُمّدت", len(my_data[my_data['status']=="تم التعميد"]) if not my_data.empty else 0)
        c3.metric("عروض رُفضت", len(my_data[my_data['status']=="تم الرفض"]) if not my_data.empty else 0)

        st.divider()

        # 3. إدارة الملفات وتحديثها
        if not my_data.empty:
            client_options = {row['id']: f"{row['company_name']}" for _, row in my_data.iterrows()}
            sid = st.selectbox("اختر العميل للإدارة:", options=list(client_options.keys()), format_func=lambda x: client_options[x])
            client_row = my_data[my_data['id'] == sid].iloc[0]
            
            c_info, c_action = st.columns([1, 1.5])
            with c_info:
                st.info(f"**بيانات العميل:**\n\n**المسؤول:** {client_row['contact_person']}\n\n**الجوال:** {client_row['mobile']}\n\n**الإيميل:** {client_row['email']}\n\n**الفعالية:** {client_row['event_name']}")
            
            with c_action:
                with st.form("status_update"):
                    new_status = st.selectbox("تحديث الحالة إلى:", TRIP_STAGES, index=TRIP_STAGES.index(client_row['status']))
                    
                    q_val = 0.0
                    c_val = 0.0
                    if new_status == "تم تقديم عرض مالي":
                        q_val = st.number_input("قيمة عرض السعر (ريال):", value=float(client_row['quote_value'] or 0))
                    elif new_status == "تم التعميد":
                        c_val = st.number_input("قيمة التعميد النهائية (ريال):", value=float(client_row['contract_value'] or 0))
                    
                    note = st.text_area("ملاحظات المتابعة:")
                    if st.form_submit_button("حفظ التحديث"):
                        update_status_advanced(sid, client_row['company_name'], new_status, st.session_state['real_name'], note, q_val, c_val)
                        st.success("تم الحفظ!")
                        st.rerun()

    # --- إضافة عميل (كامل الخانات) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_full_client"):
            col1, col2 = st.columns(2)
            with col1:
                comp = st.text_input("اسم الشركة *")
                sec = st.selectbox("القطاع", SECTORS)
                cont = st.text_input("الشخص المسؤول")
                pos = st.text_input("المنصب الوظيفي")
            with col2:
                mob = st.text_input("رقم الجوال")
                em = st.text_input("البريد الإلكتروني")
                evt = st.text_input("اسم الفعالية / المعرض")
            
            rep = st.text_input("المندوب المسؤول", value=st.session_state['real_name'], disabled=True)
            
            if st.form_submit_button("إضافة العميل للنظام"):
                if comp:
                    c = conn.cursor()
                    c.execute('''INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep, status) 
                                 VALUES (?,?,?,?,?,?,?,?,'جديد')''', (comp, sec, cont, pos, mob, em, evt, rep))
                    conn.commit()
                    st.success(f"تمت إضافة {comp} بنجاح")
                else: st.error("اسم الشركة حقل إلزامي")

    # --- لوحة المدير ---
    elif nav == "لوحة المدير" and st.session_state['user_role'] == 'admin':
        st.header("📊 إحصائيات الإدارة الشاملة")
        all_df = pd.read_sql("SELECT * FROM customers", conn)
        if not all_df.empty:
            st.write("إجمالي العقود المتعمدة:", all_df['contract_value'].sum(), "ريال")
            st.dataframe(all_df)
