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

# --- قائمة جميع الدول العربية (22 دولة) ---
COUNTRY_CODES = {
    "السعودية (+966)": "966",
    "الإمارات (+971)": "971",
    "مصر (+20)": "20",
    "الكويت (+965)": "965",
    "قطر (+974)": "974",
    "عمان (+968)": "968",
    "البحرين (+973)": "973",
    "الأردن (+962)": "962",
    "العراق (+964)": "964",
    "اليمن (+967)": "967",
    "فلسطين (+970)": "970",
    "لبنان (+961)": "961",
    "سوريا (+963)": "963",
    "المغرب (+212)": "212",
    "الجزائر (+213)": "213",
    "تونس (+216)": "216",
    "ليبيا (+218)": "218",
    "السودان (+249)": "249",
    "موريتانيا (+222)": "222",
    "الصومال (+252)": "252",
    "جيبوتي (+253)": "253",
    "جزر القمر (+269)": "269"
}

# --- إدارة الجلسة وقاعدة البيانات ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = None
if 'real_name' not in st.session_state: st.session_state['real_name'] = None

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

def is_duplicate_company(new_name):
    existing_companies = pd.read_sql("SELECT company_name FROM customers", conn)['company_name'].tolist()
    stop_words = ["شركة", "مؤسسة", "المحدودة", "للتجارة", "والمقاولات", "مصنع"]
    def clean(name):
        name = name.lower().strip()
        for word in stop_words: name = name.replace(word, "")
        return set(re.findall(r'\w+', name))
    new_tokens = clean(new_name)
    for existing in existing_companies:
        existing_tokens = clean(existing)
        if new_tokens.issubset(existing_tokens) or existing_tokens.issubset(new_tokens):
            return True, existing
    return False, None

def validate_international_mobile(country_code, number):
    cleaned_num = re.sub(r'\D', '', number) # إزالة أي رموز غير الأرقام
    if country_code == "966": # تحقق خاص للسعودية
        if cleaned_num.startswith('0'): cleaned_num = cleaned_num[1:]
        return len(cleaned_num) == 9 and cleaned_num.startswith('5'), cleaned_num
    # تحقق عام لباقي الدول العربية (بين 7 إلى 12 رقم)
    return len(cleaned_num) >= 7 and len(cleaned_num) <= 12, cleaned_num

def update_customer_status(cid, cname, new_status, user, notes=""):
    c = conn.cursor()
    c.execute("UPDATE customers SET status = ? WHERE id = ?", (new_status, cid))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)",
              (cid, cname, new_status, user, notes, now))
    conn.commit()

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🔐 Expo Time CRM</h1>", unsafe_allow_html=True)
        user = st.text_input("اسم المستخدم")
        pw = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
            account = c.fetchone()
            if account:
                st.session_state['logged_in'], st.session_state['user_role'], st.session_state['real_name'] = True, account[2], account[3]
                st.rerun()
            else: st.error("بيانات خاطئة")

else:
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        role = st.session_state['user_role']
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات ---
    if nav == "بوابة المبيعات":
        st.header("💼 بوابة المتابعة الذكية")
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(st.session_state['real_name'],))
        
        if not my_data.empty:
            search_input = st.text_input("🔎 ابحث في عملائك (اسم، جوال...):")
            df_filtered = my_data[my_data.astype(str).apply(lambda x: x.str.contains(search_input, case=False)).any(axis=1)] if search_input else my_data
            client_options = {row['id']: f"{row['company_name']} - {row['mobile']}" for i, row in df_filtered.iterrows()}
            
            if client_options:
                sid = st.selectbox("👇 اختر العميل:", options=list(client_options.keys()), format_func=lambda x: client_options[x])
                client_row = my_data[my_data['id'] == sid].iloc[0]
                
                c1, c2 = st.columns([1, 1.5])
                with c1:
                    st.subheader("📋 بيانات العميل")
                    st.info(f"**الشركة:** {client_row['company_name']}\n\n**الجوال:** {client_row['mobile']}")
                    
                    # زر واتساب المباشر المحدث
                    wa_number = client_row['mobile'].replace("+", "").replace(" ", "")
                    whatsapp_link = f"https://wa.me/{wa_number}"
                    st.link_button("💬 مراسلة عبر واتساب", whatsapp_link, use_container_width=True)
                
                with c2:
                    st.subheader("🚀 تحديث الحالة")
                    with st.form("status_up"):
                        new_st = st.selectbox("الحالة:", TRIP_STAGES, index=TRIP_STAGES.index(client_row['status']) if client_row['status'] in TRIP_STAGES else 0)
                        note = st.text_area("ملاحظات المتابعة:")
                        if st.form_submit_button("✅ حفظ العملية"):
                            update_customer_status(sid, client_row['company_name'], new_st, st.session_state['real_name'], note)
                            st.success("تم التحديث بنجاح!"); st.rerun()

    # --- إضافة عميل ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل عربي جديد")
        with st.form("add_intl"):
            col1, col2 = st.columns(2)
            with col1:
                comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
                cont = st.text_input("الشخص المسؤول")
            with col2:
                # القائمة المنسدلة لجميع الدول العربية
                country_key = st.selectbox("دولة العميل (المفتاح الدولي) *", list(COUNTRY_CODES.keys()))
                mob_input = st.text_input("رقم الجوال (بدون مفتاح الدولة) *")
                em = st.text_input("الإيميل")
            
            if st.form_submit_button("حفظ وإضافة"):
                is_dup, dup_name = is_duplicate_company(comp)
                country_val = COUNTRY_CODES[country_key]
                is_v, f_mob = validate_international_mobile(country_val, mob_input)
                full_mob = f"+{country_val}{f_mob}"
                
                if is_dup: st.error(f"❌ العميل موجود مسبقاً باسم مشابه: {dup_name}")
                elif not comp or not is_v: st.error("يرجى التأكد من كتابة اسم الشركة وصحة رقم الجوال لهذه الدولة")
                else:
                    c = conn.cursor()
                    c.execute("INSERT INTO customers (company_name, sector, contact_person, mobile, email, sales_rep) VALUES (?,?,?,?,?,?)",
                              (comp, sec, cont, full_mob, em, st.session_state['real_name']))
                    conn.commit()
                    st.success(f"✅ تمت الإضافة! الرقم المسجل دولياً: {full_mob}")
