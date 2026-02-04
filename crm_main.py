import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, date, timedelta

# ==========================================
#              إعدادات النظام
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢")

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    return conn

conn = init_db()
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم عرض مالي", "تم التعميد", "تم الرفض", "مؤجل"]

def get_reps_list():
    df = pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)
    return df['real_name'].tolist()

# ==========================================
#              واجهة التطبيق
# ==========================================
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        st.title("🔐 Expotime CRM")
        with st.form("login"):
            u = st.text_input("اسم المستخدم")
            p = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول"):
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (u, p))
                acc = c.fetchone()
                if acc:
                    st.session_state.update({'logged_in': True, 'user_role': acc[2], 'real_name': acc[3]})
                    st.rerun()
                else: st.error("خطأ في البيانات")
else:
    role = st.session_state['user_role']
    real_name = st.session_state['real_name']
    all_reps = get_reps_list()
    
    with st.sidebar:
        st.header(f"👋 {real_name}")
        menu = ["لوحة المدير", "بوابة المبيعات", "الفعاليات", "إضافة عميل", "المستخدمين", "استيراد ملفات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "الفعاليات", "إضافة عميل", "بحث شامل", "خروج"]
        nav = st.radio("القائمة الرئيسية", menu)

    if nav == "خروج":
        st.session_state.clear()
        st.rerun()

    # --- لوحة المدير (المترابطة) ---
    elif nav == "لوحة المدير":
        st.header("📊 تقرير أداء المناديب")
        c_f1, c_f2 = st.columns(2)
        with c_f1: s_rep = st.selectbox("المندوب:", ["الكل"] + all_reps)
        with c_f2: d_range = st.date_input("الفترة:", [date.today() - timedelta(days=1), date.today()])
        
        query = "SELECT customer_name as 'العميل', updated_status as 'الحالة', notes as 'الملاحظات', changed_by as 'المندوب', timestamp as 'الوقت' FROM status_history WHERE 1=1"
        params = []
        if s_rep != "الكل": query += " AND changed_by = ?"; params.append(s_rep)
        if len(d_range) == 2: query += " AND date(timestamp) BETWEEN ? AND ?"; params.append(d_range[0]); params.append(d_range[1])
        df_perf = pd.read_sql(query, conn, params=params)
        st.dataframe(df_perf, use_container_width=True)

    # --- بوابة المبيعات (مع الفلترة) ---
    elif nav == "بوابة المبيعات":
        st.header("💼 إدارة العملاء")
        
        # أسطر الفلترة الجديدة
        f1, f2 = st.columns(2)
        with f1: 
            f_status = st.selectbox("فلترة حسب الحالة:", ["الكل"] + TRIP_STAGES)
        with f2:
            target = real_name if role != 'admin' else st.selectbox("عرض مندوب:", ["الكل"] + all_reps)
        
        q_sales = "SELECT * FROM customers WHERE 1=1"
        params = []
        if target != "الكل": q_sales += " AND sales_rep = ?"; params.append(target)
        if f_status != "الكل": q_sales += " AND status = ?"; params.append(f_status)
        
        sales_df = pd.read_sql(q_sales, conn, params=params)
        
        if not sales_df.empty:
            sel_id = st.selectbox("اختر العميل:", sales_df['id'].tolist(), format_func=lambda x: sales_df[sales_df['id']==x]['company_name'].values[0])
            row = sales_df[sales_df['id']==sel_id].iloc[0]
            
            c_info, c_action = st.columns(2)
            with c_info:
                with st.form("edit_c"):
                    n_comp = st.text_input("الشركة", row['company_name'], disabled=(role!='admin'))
                    n_mob = st.text_input("الجوال", row['mobile'], disabled=(role!='admin'))
                    if role == 'admin' and st.form_submit_button("تحديث"):
                        conn.execute("UPDATE customers SET company_name=?, mobile=? WHERE id=?", (n_comp, n_mob, sel_id))
                        conn.commit(); st.rerun()
                st.link_button("💬 واتساب", f"https://wa.me/{re.sub(r'\D','',str(row['mobile']))}")
            with c_action:
                with st.form("status_up"):
                    new_s = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']) if row['status'] in TRIP_STAGES else 0)
                    note = st.text_area("الملاحظة")
                    if st.form_submit_button("حفظ"):
                        conn.execute("UPDATE customers SET status=? WHERE id=?", (new_s, sel_id))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)",
                                     (sel_id, row['company_name'], new_s, real_name, note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.rerun()
        else: st.info("لا توجد بيانات تطابق الفلتر.")

    # --- الفعاليات (مع الفلترة) ---
    elif nav == "الفعاليات":
        st.header("📅 إدارة الفعاليات")
        
        # أسطر الفلترة للفعاليات
        fe1, fe2 = st.columns(2)
        with fe1: f_loc = st.text_input("بحث بالموقع (المدينة):")
        with fe2: f_assign = st.selectbox("حالة الاستلام:", ["الكل", "متاحة", "مستلمة"])
        
        ev_query = "SELECT * FROM events WHERE 1=1"
        if f_loc: ev_query += f" AND location LIKE '%{f_loc}%'"
        if f_assign == "متاحة": ev_query += " AND (assigned_rep IS NULL OR assigned_rep = '')"
        elif f_assign == "مستلمة": ev_query += " AND (assigned_rep IS NOT NULL AND assigned_rep != '')"
        
        ev_df = pd.read_sql(ev_query, conn)
        
        for _, r_ev in ev_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2,1,1])
                with c1: st.subheader(r_ev['event_name']); st.write(f"📍 {r_ev['location']} | 📅 {r_ev['event_date']}")
                with c2: st.write(f"المسؤول: {r_ev['assigned_rep'] if r_ev['assigned_rep'] else 'متاح'}")
                with c3:
                    if not r_ev['assigned_rep'] and st.button("➕ استلام", key=f"g_{r_ev['id']}"):
                        conn.execute("UPDATE events SET assigned_rep = ? WHERE id = ?", (real_name, r_ev['id']))
                        conn.commit(); st.rerun()
                    if role == 'admin' and r_ev['assigned_rep'] and st.button("🔓 سحب", key=f"r_{r_ev['id']}"):
                        conn.execute("UPDATE events SET assigned_rep = NULL WHERE id = ?", (r_ev['id'],))
                        conn.commit(); st.rerun()

    # --- بقية النوافذ كما هي ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_f"):
            ca, cb = st.columns(2)
            with ca: cp=st.text_input("الشركة *"); sc=st.selectbox("القطاع", ["تقنية", "عقارات", "صناعة", "عام"]); ct=st.text_input("المسؤول")
            with cb: mb=st.text_input("الجوال *"); ml=st.text_input("الإيميل"); ev=st.text_input("الفعالية")
            if st.form_submit_button("حفظ"):
                if cp and mb:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, mobile, email, event_name, sales_rep, created_at) VALUES (?,?,?,?,?,?,?,?)", 
                                 (cp, sc, ct, mb, ml, ev, real_name, date.today()))
                    conn.commit(); st.success("تم الحفظ")
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        u_df = pd.read_sql("SELECT real_name, username FROM users", conn)
        st.dataframe(u_df, use_container_width=True)
        with st.expander("إضافة/حذف"):
            un = st.text_input("يوزر"); ps = st.text_input("باسورد"); nm = st.text_input("الاسم")
            if st.button("حفظ"):
                conn.execute("INSERT INTO users VALUES (?,?,'rep',?)", (un, ps, nm))
                conn.commit(); st.rerun()
    elif nav == "استيراد ملفات":
        st.header("📤 الاستيراد")
        st.tabs(["📁 عملاء", "📅 فعاليات"])
    elif nav == "بحث شامل":
        st.header("🔍 البحث")
        query = st.text_input("ابحث هنا...")
        if query: st.dataframe(pd.read_sql(f"SELECT * FROM customers WHERE company_name LIKE '%{query}%' OR mobile LIKE '%{query}%'", conn), use_container_width=True)
