import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import re 

# قائمة الدول العربية
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
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'real_name' not in st.session_state:
    st.session_state['real_name'] = None

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db')
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
#              دوال النظام
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
            account = login_user(user, pw)
            if account:
                st.session_state.update({'logged_in': True, 'user_role': account[2], 'real_name': account[3]})
                st.rerun()
            else: st.error("بيانات خاطئة")
else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        tab_my, tab_all = st.tabs(["📂 عملائي", "🌍 قاعدة البيانات الشاملة"])
        
        with tab_my:
            rep_name = st.session_state['real_name']
            if role == 'admin':
                reps = get_all_reps()
                rep_name = st.selectbox("اختر المندوب:", reps) if reps else rep_name
            
            my_data = get_my_data(rep_name)
            if not my_data.empty:
                search_q = st.text_input("🔎 ابحث بالاسم:")
                df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
                selected_id = st.selectbox("👇 اختر العميل:", df_view['id'].tolist(), format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
                row = my_data[my_data['id'] == selected_id].iloc[0]
                
                c1, c2 = st.columns([1, 1.5])
                with c1:
                    st.subheader("📋 بيانات العميل")
                    # ميزة الواتساب
                    clean_phone = re.sub(r'\D', '', str(row['mobile']))
                    st.markdown(f'''<a href="https://wa.me/{clean_phone}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; width: 100%;">💬 مراسلة واتساب</button></a>''', unsafe_allow_html=True)
                    
                    with st.form("update_info"):
                        st.text_input("الشركة", value=row['company_name'], disabled=True)
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                        new_em = st.text_input("الإيميل", value=row['email'])
                        if st.form_submit_button("تحديث"):
                            update_customer_info(selected_id, new_mob, new_em)
                            st.success("تم التحديث"); st.rerun()

                with c2:
                    with st.form("status_update"):
                        new_stage = st.selectbox("الحالة الجديدة:", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                        note = st.text_area("ملاحظات المتابعة:")
                        if st.form_submit_button("✅ حفظ"):
                            update_customer_status(selected_id, row['company_name'], new_stage, st.session_state['real_name'], note)
                            st.success("تم"); st.rerun()
                    
                    st.subheader("⏳ السجل")
                    history = get_client_history(selected_id)
                    for i, h in history.iterrows():
                        st.caption(f"{h['timestamp']} - {h['updated_status']} ({h['changed_by']})")
                        if h['notes']: st.info(h['notes'])

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp, sec = st.text_input("الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("المسؤول"), st.text_input("المنصب")
            with c2:
                # ميزة مفاتيح الدول
                c_code = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_num = st.text_input("رقم الجوال *")
                em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
            
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[c_code]}{mob_num.strip()}"
                # ميزة منع التكرار
                dup = conn.execute("SELECT sales_rep FROM customers WHERE mobile=? OR company_name=?", (full_mob, comp)).fetchone()
                if dup:
                    st.error(f"⚠️ مكرر! العميل مسجل مع المندوب: {dup[0]}")
                elif comp and mob_num:
                    add_customer((comp, sec, cont, pos, full_mob, em, evt, rep, "جديد"))
                    st.success("تم الحفظ")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات الأداء المجمعة")
        # فلتر التاريخ
        col_d1, col_d2 = st.columns(2)
        with col_d1: start_d = st.date_input("من تاريخ", date(2025, 1, 1))
        with col_d2: end_d = st.date_input("إلى تاريخ", date.today())
        
        hist_df = get_history_log()
        if not hist_df.empty:
            hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp']).dt.date
            filtered = hist_df[(hist_df['timestamp'] >= start_d) & (hist_df['timestamp'] <= end_d)]
            
            if not filtered.empty:
                # الجدول المجمع المطلوب
                summary = filtered.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
                st.subheader("📈 إجمالي الحالات لكل مندوب")
                st.dataframe(summary, use_container_width=True)
                
                # الرسم البياني الأصلي
                st.plotly_chart(px.bar(filtered, x='changed_by', color='updated_status', barmode='group'), use_container_width=True)
            else: st.warning("لا توجد بيانات للفترة المختارة")

    elif nav == "المستخدمين" and role == 'admin':
        # قسم المستخدمين الأصلي تماماً
        st.header("إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة", "تعديل كلمة مرور", "حذف"])
        with t1:
            n, u, p = st.text_input("الاسم"), st.text_input("يوزر"), st.text_input("باس")
            if st.button("إنشاء"):
                if create_user(u,p,n): st.success("تم")
        # (بقية كود المستخدمين الأصلي...)
