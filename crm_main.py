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

# قائمة الدول العربية المضافة حديثاً للتحديث
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "الأردن (+962)": "962", "المغرب (+212)": "212", "العراق (+964)": "964"
}

# --- إدارة الجلسة ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

# --- قاعدة البيانات الأصلية ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    # إنشاء جداولك الأصلية
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
#           دوال التحقق (الجديدة)
# ==========================================

def check_duplicate_info(comp_name, mob):
    """دالة منع تكرار البيانات"""
    c = conn.cursor()
    # تنظيف الاسم للمقارنة الذكية
    clean_name = re.sub(r'شركة|مؤسسة|المحدودة', '', comp_name).strip()
    c.execute("SELECT company_name, sales_rep FROM customers WHERE company_name LIKE ?", (f'%{clean_name}%',))
    res = c.fetchone()
    if res: return f"الشركة مسجلة باسم ({res[0]}) مع المندوب: {res[1]}"
    
    c.execute("SELECT mobile, sales_rep FROM customers WHERE mobile = ?", (mob,))
    res = c.fetchone()
    if res: return f"رقم الجوال ({mob}) مسجل مع المندوب: {res[1]}"
    return None

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
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
        # استعادة كامل القائمة الأصلية
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات (استعادة الملاحظات + إضافة زر الواتساب) ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        t_my, t_all = st.tabs(["📂 عملائي (بحث وإدارة)", "🌍 قاعدة البيانات الشاملة"])
        with t_my:
            rep_n = st.session_state['real_name']
            if role == 'admin':
                reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
                rep_n = st.selectbox("اختر المندوب:", reps) if reps else rep_n
            
            my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_n,))
            if not my_data.empty:
                search_q = st.text_input("🔎 ابحث بالاسم:")
                df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
                client_opts = {row['id']: row['company_name'] for i, row in df_view.iterrows()}
                
                if client_opts:
                    sid = st.selectbox("👇 اختر العميل:", list(client_opts.keys()), format_func=lambda x: client_opts[x])
                    row = my_data[my_data['id'] == sid].iloc[0]
                    
                    with st.form("edit_form"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.text_input("الشركة", value=row['company_name'], disabled=True)
                            new_mob = st.text_input("الجوال", value=row['mobile'])
                            # إضافة ميزة مراسلة الواتساب
                            wa_url = f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}"
                            st.link_button("💬 مراسلة واتساب فورية", wa_url)
                        with c2:
                            new_st = st.selectbox("الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                            note = st.text_area("ملاحظات المتابعة (سجل ما تم مع العميل)", placeholder="اكتب ملاحظاتك هنا...")
                        
                        if st.form_submit_button("💾 حفظ"):
                            conn.execute("UPDATE customers SET mobile=?, status=? WHERE id=?", (new_mob, new_st, sid))
                            conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", (sid, row['company_name'], new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit(); st.success("تم الحفظ"); st.rerun()

        with t_all: # قاعدة البيانات الشاملة الأصلية
            st.subheader("🌍 قاعدة البيانات الشاملة")
            all_df = pd.read_sql("SELECT * FROM customers", conn)
            st.dataframe(all_df, use_container_width=True, hide_index=True)

    # --- إضافة عميل (دمج مفاتيح الدول ومنع التكرار) ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل جديد")
        with st.form("new_c"):
            col1, col2 = st.columns(2)
            with col1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب")
            with col2:
                c_key = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob_in = st.text_input("رقم الجوال *")
                em, evt = st.text_input("الإيميل *"), st.text_input("الفعالية")
            
            reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
            rep = st.selectbox("المندوب", reps) if role == 'admin' and reps else st.text_input("المندوب", value=st.session_state['real_name'], disabled=True)
            
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[c_key]}{mob_in.strip()}"
                # تفعيل منع تكرار البيانات
                dup_reason = check_duplicate_info(comp, full_mob)
                if dup_reason:
                    st.error(f"❌ تم الرفض: {dup_reason}")
                elif comp and mob_in and em:
                    conn.execute("INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep) VALUES (?,?,?,?,?,?,?,?)", (comp, sec, cont, pos, full_mob, em, evt, rep))
                    conn.commit(); st.success("تم الحفظ بنجاح")
                else: st.error("تأكد من ملء الحقول الإلزامية")

    # --- استعادة باقي الشاشات الأصلية ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 الإحصائيات")
        df_stats = pd.read_sql("SELECT * FROM customers", conn)
        if not df_stats.empty:
            st.plotly_chart(px.bar(df_stats, x='sales_rep', color='status'), use_container_width=True)
            st.subheader("سجل المتابعات (Log)")
            st.dataframe(pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn), use_container_width=True)

    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة", "تعديل", "حذف"])
        with t1:
            n, u, p = st.text_input("الاسم"), st.text_input("يوزر"), st.text_input("باس")
            if st.button("إنشاء"):
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, 'rep', n))
                conn.commit(); st.success("تم")
        with t2:
            u_list = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
            u_sel = st.selectbox("المستخدم", u_list)
            np = st.text_input("باس جديد")
            if st.button("تحديث"):
                conn.execute("UPDATE users SET password=? WHERE username=?", (np, u_sel))
                conn.commit(); st.success("تم")
        with t3:
            u_del = st.selectbox("حذف مستخدم", [x for x in u_list if x != 'admin'])
            if st.button("❌ حذف"):
                conn.execute("DELETE FROM users WHERE username=?", (u_del,))
                conn.commit(); st.success("تم"); st.rerun()

    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف", type=['csv', 'xlsx'])
        if f and st.button("بدء الاستيراد"):
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df.to_sql('customers', conn, if_exists='append', index=False)
            st.success("تم الاستيراد")

    elif nav == "بحث شامل":
        st.header("🔍 بحث شامل")
        s = st.text_input("🔎 ابحث عن أي معلومة:")
        if s:
            df_full = pd.read_sql("SELECT * FROM customers", conn)
            st.dataframe(df_full[df_full.astype(str).apply(lambda x: x.str.contains(s, case=False)).any(axis=1)], use_container_width=True, hide_index=True)
