import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import re 

# تم إلغاء استيراد مكتبة openai 

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
    # إنشاء جدول العملاء
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد')''')
    
    # إنشاء جدول السجل (مع عمود notes الضروري)
    c.execute('''CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer_name TEXT, 
        updated_status TEXT, changed_by TEXT, notes TEXT, timestamp TEXT)''')
    
    # إنشاء جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, real_name TEXT)''')
    
    # التأكد من وجود المدير (Admin)
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '1234', 'admin', 'المدير العام'))
        conn.commit()
    conn.commit()
    return conn

conn = init_db()
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]

# --- مراحل رحلة العميل (المراحل الكاملة) ---
TRIP_STAGES = [
    "جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", 
    "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"
]

# ==========================================
#           دوال التحقق والذكاء البرمجي
# ==========================================

def check_duplicate_info(comp_name, mob, em):
    """فحص التكرار وإرجاع السبب والمندوب المسؤول"""
    c = conn.cursor()
    # تنظيف الاسم للمقارنة الذكية
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة|للتجارة', '', comp_name).strip()
    
    # فحص الاسم (بحث جزئي)
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"اسم الشركة مكرر أو مشابه لـ ({res[0]}) والمندوب المسؤول هو: {res[1]}"
    
    # فحص الجوال
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"رقم الجوال ({mob}) مسجل مسبقاً مع المندوب: {res[1]}"
    
    # فحص الإيميل
    c.execute("SELECT email, sales_rep FROM customers WHERE email = ?", (em,))
    res = c.fetchone()
    if res: return f"البريد الإلكتروني ({em}) مسجل مسبقاً مع المندوب: {res[1]}"
    
    return None

def validate_mobile(mobile):
    cleaned_mobile = mobile.replace(" ", "").strip()
    return len(cleaned_mobile) == 10 and cleaned_mobile.isdigit()

def validate_email(email):
    regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(regex, email) is not None

# ==========================================
#              دوال النظام الأصلية
# ==========================================

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

def update_customer_info(cid, new_mobile, new_email):
    c = conn.cursor()
    c.execute("UPDATE customers SET mobile = ?, email = ? WHERE id = ?", (new_mobile, new_email, cid))
    conn.commit()

def update_customer_status(cid, cname, new_status, user, notes=""):
    c = conn.cursor()
    c.execute("UPDATE customers SET status = ? WHERE id = ?", (new_status, cid))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (cid, cname, new_status, user, notes, now))
    conn.commit()

def update_user_password(user, pwd):
    conn.execute("UPDATE users SET password = ? WHERE username = ?", (pwd, user))
    conn.commit()

def delete_user(user):
    conn.execute("DELETE FROM users WHERE username = ?", (user,))
    conn.commit()

def get_all_users(): return pd.read_sql("SELECT username, role, real_name FROM users", conn)
def get_all_reps(): return pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
def get_all_data(): return pd.read_sql("SELECT * FROM customers", conn)
def get_my_data(rep): return pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep,))
def get_client_history(cid): return pd.read_sql("SELECT * FROM status_history WHERE customer_id = ? ORDER BY id DESC", conn, params=(cid,))
def get_history_log(): return pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn)

def add_customer(data):
    c = conn.cursor()
    c.execute('''INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
    conn.commit()

def bulk_import(df, reps):
    c = conn.cursor()
    count = 0
    df.rename(columns={'contact_name': 'contact_person', 'mobile_clean': 'mobile', 'suitable_exhibitions': 'event_name', 'salesrep': 'sales_rep'}, inplace=True)
    df.columns = df.columns.str.lower()
    if 'company_name' not in df.columns: return 0
    for _, row in df.iterrows():
        rep = row.get('sales_rep', 'غير معين')
        if rep not in reps: rep = 'غير معين'
        try:
            data = (row.get('company_name'), row.get('sector', ''), row.get('contact_person', ''), row.get('position', ''), 
                    row.get('mobile', ''), row.get('email', ''), row.get('event_name', ''), rep, "جديد")
            if data[0]:
                add_customer(data)
                count += 1
        except: continue
    return count

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
                    st.session_state['logged_in'] = True
                    st.session_state['user_role'] = account[2]
                    st.session_state['real_name'] = account[3]
                    st.success("تم الدخول")
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
        menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        tab_my, tab_all = st.tabs(["📂 عملائي (بحث وإدارة)", "🌍 قاعدة البيانات الشاملة"])
        
        with tab_my:
            rep_name = st.session_state['real_name']
            if role == 'admin':
                reps = get_all_reps()
                rep_name = st.selectbox("اختر المندوب للعرض:", reps) if reps else rep_name
                
            my_data = get_my_data(rep_name)
            
            if not my_data.empty:
                col_search, col_filter = st.columns([2,1])
                with col_search:
                    search_q = st.text_input("🔎 ابحث (بدء الكتابة يفعل الإكمال التلقائي):", key="search_my")
                with col_filter:
                    filter_status = st.selectbox("فلترة بالمرحلة:", ["الكل"] + TRIP_STAGES)
                
                df_view = my_data.copy()
                if search_q:
                    df_view = df_view[df_view.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)]
                if filter_status != "الكل":
                    df_view = df_view[df_view['status'] == filter_status]
                
                # إكمال تلقائي باختيار من القائمة المفلترة
                client_options = {row['id']: f"{row['company_name']} - {row['contact_person']}" for i, row in df_view.iterrows()}
                if client_options:
                    selected_id = st.selectbox("👇 اختر العميل من الاقتراحات:", options=list(client_options.keys()), format_func=lambda x: client_options[x])
                    client_row = df_view[df_view['id'] == selected_id].iloc[0]
                    
                    st.divider()
                    c1, c2 = st.columns([1, 1.5])
                    with c1:
                        st.subheader("📋 بيانات العميل")
                        with st.form("update_info"):
                            st.text_input("الشركة", value=client_row['company_name'], disabled=True)
                            new_mob = st.text_input("الجوال", value=client_row['mobile'])
                            new_email = st.text_input("الإيميل", value=client_row['email'])
                            if st.form_submit_button("تحديث البيانات"):
                                update_customer_info(client_row['id'], new_mob, new_email)
                                st.success("تم تحديث البيانات!"); st.rerun()
                        st.info(f"**المنصب:** {client_row['position']} | **الفعالية:** {client_row['event_name']} | **القطاع:** {client_row['sector']}")
                    with c2:
                        st.subheader("🚀 تحديث رحلة العميل")
                        with st.form("status_update"):
                            new_stage = st.selectbox("انقل العميل للمرحلة التالية:", TRIP_STAGES, index=TRIP_STAGES.index(client_row['status']) if client_row['status'] in TRIP_STAGES else 0)
                            note = st.text_area("ملاحظات المتابعة:")
                            if st.form_submit_button("✅ تسجيل العملية"):
                                update_customer_status(client_row['id'], client_row['company_name'], new_stage, st.session_state['real_name'], note)
                                st.success(f"تم النقل إلى {new_stage}"); st.rerun()
                        
                        history = get_client_history(client_row['id'])
                        if not history.empty:
                            for i, h in history.iterrows():
                                with st.chat_message("user"):
                                    st.write(f"**{h['updated_status']}** - {h['timestamp']} (بواسطة: {h['changed_by']})")
                                    if h['notes']: st.info(f"📝 {h['notes']}")
            else: st.info("لا توجد بيانات.")

        with tab_all:
            st.subheader("🌍 البحث في جميع العملاء")
            search_all = st.text_input("🔎 ابحث في الداتا كاملة:", key="search_global")
            all_df = get_all_data()
            if search_all:
                all_df = all_df[all_df.astype(str).apply(lambda x: x.str.contains(search_all, case=False)).any(axis=1)]
            # تحسين العرض لكل الشاشات وإخفاء الأعمدة غير الضرورية
            st.dataframe(all_df, use_container_width=True, hide_index=True, column_config={"id": None})

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب (اختياري)") 
            with c2:
                mob, em, evt = st.text_input("الجوال *"), st.text_input("الإيميل *"), st.text_input("الفعالية")
            rep = st.selectbox("المندوب", get_all_reps()) if role == 'admin' else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            
            if st.form_submit_button("حفظ"):
                # ميزة منع التكرار مع إظهار السبب
                dup_reason = check_duplicate_info(comp, mob, em)
                if dup_reason:
                    st.error(f"❌ تم رفض الإضافة للسبب التالي: {dup_reason}")
                elif comp and validate_mobile(mob) and validate_email(em):
                    add_customer((comp, sec, cont, pos, mob, em, evt, rep, "جديد"))
                    st.success("تم الحفظ بنجاح!")
                else: st.error("تأكد من ملء الحقول الإلزامية وصحة البيانات.")

    # (بقية خيارات المدير تظل كما هي في الأصل المرفق)
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 الإحصائيات")
        df = get_all_data()
        if not df.empty:
            c1, c2 = st.columns(2)
            c1.metric("العملاء", len(df))
            c2.metric("تم التعميد", len(df[df['status'] == "تم التعميد"]))
            st.plotly_chart(px.bar(df, x='sales_rep', color='status', category_orders={"status": TRIP_STAGES}), use_container_width=True)
            st.dataframe(get_history_log(), use_container_width=True, hide_index=True)

    elif nav == "المستخدمين" and role == 'admin':
        st.header("إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة", "تعديل كلمة مرور", "حذف"])
        with t1:
            n, u, p = st.text_input("الاسم"), st.text_input("يوزر"), st.text_input("باس")
            if st.button("إنشاء"):
                if create_user(u,p,n): st.success("تم")
                else: st.error("موجود")
        users = get_all_users()
        with t2:
            u_sel, np = st.selectbox("المستخدم", users['username']), st.text_input("كلمة مرور جديدة")
            if st.button("تحديث"): update_user_password(u_sel, np); st.success("تم")
        with t3:
            u_del = st.selectbox("حذف مستخدم", users[users['username']!='admin']['username'])
            if st.button("حذف"): delete_user(u_del); st.success("تم"); st.rerun()

    elif nav == "بحث شامل":
        st.header("🔍 بحث في كل النظام")
        s = st.text_input("بحث...")
        if s:
            df = get_all_data()
            st.dataframe(df[df.astype(str).apply(lambda x: x.str.contains(s, case=False)).any(axis=1)], use_container_width=True, hide_index=True, column_config={"id": None})
