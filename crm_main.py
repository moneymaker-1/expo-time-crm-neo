import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import re
import time

# ==========================================
#              إعدادات النظام
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢", initial_sidebar_state="expanded")

# قائمة الدول العربية
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "البحرين (+973)": "973", "الأردن (+962)": "962", "العراق (+964)": "964",
    "اليمن (+967)": "967", "فلسطين (+970)": "970", "لبنان (+961)": "961",
    "سوريا (+963)": "963", "المغرب (+212)": "212", "الجزائر (+213)": "213",
    "تونس (+216)": "216", "ليبيا (+218)": "218", "السودان (+249)": "249",
    "موريتانيا (+222)": "222", "الصومال (+252)": "252", "جيبوتي (+253)": "253", "جزر القمر (+269)": "269"
}

# إدارة الجلسة
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'login_time' not in st.session_state: st.session_state['login_time'] = None

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
    # جدول جديد لسجل الاستخدام
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, login_time TEXT, logout_time TEXT, duration_mins REAL)''')
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '1234', 'admin', 'المدير العام'))
    conn.commit()
    return conn

conn = init_db()

# ==========================================
#           دوال التحقق المتقدمة
# ==========================================

def is_duplicate_company(new_name):
    existing = pd.read_sql("SELECT company_name FROM customers", conn)['company_name'].tolist()
    stop_words = ["شركة", "مؤسسة", "المحدودة", "للتجارة", "والمقاولات"]
    def clean(n):
        n = n.lower().strip()
        for w in stop_words: n = n.replace(w, "")
        return set(re.findall(r'\w+', n))
    new_t = clean(new_name)
    for ex in existing:
        ex_t = clean(ex)
        if new_t.issubset(ex_t) or ex_t.issubset(new_t): return True, ex
    return False, None

def validate_intl_mobile(country_code, number):
    clean_n = re.sub(r'\D', '', number)
    if country_code == "966":
        if clean_n.startswith('0'): clean_n = clean_n[1:]
        return len(clean_n) == 9 and clean_n.startswith('5'), clean_n
    return len(clean_n) >= 7 and len(clean_n) <= 12, clean_n

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
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
            acc = c.fetchone()
            if acc:
                st.session_state.update({'logged_in': True, 'user_role': acc[2], 'real_name': acc[3], 'username': user, 'login_time': datetime.now()})
                # تسجيل وقت الدخول في القاعدة
                conn.execute("INSERT INTO user_sessions (username, login_time) VALUES (?,?)", (user, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                st.rerun()
            else: st.error("بيانات خاطئة")
else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج":
            # تحديث وقت الخروج والمدة
            if st.session_state['login_time']:
                duration = (datetime.now() - st.session_state['login_time']).seconds / 60
                conn.execute("UPDATE user_sessions SET logout_time=?, duration_mins=? WHERE username=? AND logout_time IS NULL", 
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(duration, 2), st.session_state['username']))
                conn.commit()
            st.session_state.clear(); st.rerun()

    if nav == "بوابة المبيعات":
        st.header("💼 إدارة المتابعات والواتساب")
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(st.session_state['real_name'],))
        if not my_data.empty:
            search = st.text_input("🔎 ابحث (اسم، جوال...):")
            df_f = my_data[my_data.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)] if search else my_data
            
            opts = {row['id']: f"{row['company_name']}" for i, row in df_f.iterrows()}
            if opts:
                sid = st.selectbox("اختر العميل:", options=list(opts.keys()), format_func=lambda x: opts[x])
                row = my_data[my_data['id']==sid].iloc[0]
                
                c1, c2 = st.columns([1, 1.5])
                with c1:
                    st.info(f"**الشركة:** {row['company_name']}\n\n**الجوال:** {row['mobile']}")
                    wa_url = f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}"
                    st.link_button("💬 مراسلة واتساب", wa_url, use_container_width=True)
                with c2:
                    with st.form("up"):
                        ns = st.selectbox("المرحلة", ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"], index=0)
                        note = st.text_area("ملاحظات")
                        if st.form_submit_button("حفظ"):
                            conn.execute("UPDATE customers SET status=? WHERE id=?", (ns, sid))
                            conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)",
                                         (sid, row['company_name'], ns, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit(); st.success("تم"); st.rerun()

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل (تحقق دولي ومنع تكرار)")
        with st.form("add_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                sec = st.selectbox("القطاع", ["تقنية", "عقارات", "صناعة", "خدمات"])
            with c2:
                ckey = st.selectbox("الدولة *", list(COUNTRY_CODES.keys()))
                mob_i = st.text_input("الجوال (بدون الصفر الأول) *")
                em = st.text_input("الإيميل")
            
            if st.form_submit_button("حفظ"):
                is_dup, dup_n = is_duplicate_company(comp)
                is_v, f_mob = validate_intl_mobile(COUNTRY_CODES[ckey], mob_i)
                full_mob = f"+{COUNTRY_CODES[ckey]}{f_mob}"
                
                if is_dup: st.error(f"❌ العميل موجود مسبقاً: {dup_n}")
                elif not comp or not is_v: st.error("تأكد من البيانات وصحة الجوال")
                else:
                    conn.execute("INSERT INTO customers (company_name, sector, mobile, email, sales_rep) VALUES (?,?,?,?,?)",
                                 (comp, sec, full_mob, em, st.session_state['real_name']))
                    conn.commit(); st.success(f"تم الحفظ: {full_mob}")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 تقارير الإدارة")
        t1, t2 = st.tabs(["إحصائيات المبيعات", "⏱️ سجل استخدام الموظفين"])
        with t1:
            df = pd.read_sql("SELECT * FROM customers", conn)
            if not df.empty:
                st.plotly_chart(px.bar(df, x='sales_rep', color='status', title="أداء المناديب"))
        with t2:
            st.subheader("سجل دخول وخروج الموظفين")
            sessions_df = pd.read_sql("SELECT username as 'الموظف', login_time as 'وقت الدخول', logout_time as 'وقت الخروج', duration_mins as 'المدة (دقائق)' FROM user_sessions ORDER BY id DESC", conn)
            st.dataframe(sessions_df, use_container_width=True)
