import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
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
    # إضافة أعمدة المبالغ والتواريخ
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد',
        quote_value REAL DEFAULT 0, contract_value REAL DEFAULT 0, quote_date TEXT)''')
    
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
#              دوال النظام
# ==========================================
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

    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المتابعة الذكية")
        rep_name = st.session_state['real_name']
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_name,))
        
        # --- 1. نظام التنبيهات (3 أيام على العرض) ---
        if not my_data.empty:
            st.subheader("🔔 تنبيهات عاجلة")
            overdue_found = False
            for _, row in my_data.iterrows():
                if row['status'] == "تم تقديم عرض مالي" and row['quote_date']:
                    q_date = datetime.strptime(row['quote_date'], "%Y-%m-%d")
                    if (datetime.now() - q_date).days >= 3:
                        st.error(f"⚠️ **{row['company_name']}**: مر 3 أيام على عرض السعر. تنتهي الصلاحية اليوم!")
                        overdue_found = True
            if not overdue_found: st.success("لا توجد تنبيهات متأخرة.")

        # --- 2. إحصائيات المندوب الشهرية ---
        st.divider()
        st.subheader("📊 إنجازك لهذا الشهر")
        if not my_data.empty:
            m_now = datetime.now().month
            # محاكاة لفلترة الشهر من التاريخ (للبساطة نستخدم البيانات الحالية)
            c1, c2, c3 = st.columns(3)
            c1.metric("عروض قُدمت", len(my_data[my_data['status']=="تم تقديم عرض مالي"]))
            c2.metric("عروض عُمّدت", len(my_data[my_data['status']=="تم التعميد"]))
            c3.metric("عروض رُفضت", len(my_data[my_data['status']=="تم الرفض"]))
        
        st.divider()

        # --- 3. تحديث الحالة والحقول المالية ---
        if not my_data.empty:
            client_list = {row['id']: row['company_name'] for _, row in my_data.iterrows()}
            sid = st.selectbox("اختر العميل للتحديث:", options=list(client_list.keys()), format_func=lambda x: client_list[x])
            client_row = my_data[my_data['id'] == sid].iloc[0]
            
            with st.form("advanced_update"):
                new_status = st.selectbox("الحالة الجديدة:", TRIP_STAGES, index=TRIP_STAGES.index(client_row['status']))
                
                # إظهار الحقول المالية بناءً على الاختيار
                q_val, c_val = 0.0, 0.0
                if new_status == "تم تقديم عرض مالي":
                    q_val = st.number_input("قيمة عرض السعر (ريال):", min_value=0.0, value=float(client_row['quote_value'] or 0))
                elif new_status == "تم التعميد":
                    c_val = st.number_input("قيمة التعميد النهائية (ريال):", min_value=0.0, value=float(client_row['contract_value'] or 0))
                
                note = st.text_area("ملاحظات المتابعة:")
                if st.form_submit_button("حفظ التحديث"):
                    update_status_advanced(sid, client_row['company_name'], new_status, st.session_state['real_name'], note, q_val, c_val)
                    st.success("تم التحديث بنجاح!")
                    st.rerun()
        else:
            st.info("لا يوجد عملاء مسجلين باسمك حالياً.")

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_c"):
            name = st.text_input("اسم الشركة")
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            if st.form_submit_button("حفظ"):
                c = conn.cursor()
                c.execute("INSERT INTO customers (company_name, sales_rep, status) VALUES (?,?,'جديد')", (name, rep))
                conn.commit()
                st.success("تمت الإضافة")

    elif nav == "لوحة المدير" and st.session_state['user_role'] == 'admin':
        st.header("📊 إحصائيات الإدارة")
        all_df = pd.read_sql("SELECT * FROM customers", conn)
        if not all_df.empty:
            st.plotly_chart(px.pie(all_df, names='status', title="توزيع الحالات إجمالاً"))
            st.dataframe(all_df[['company_name', 'sales_rep', 'status', 'quote_value', 'contract_value']])
