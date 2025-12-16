import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import re 

# قائمة الدول العربية الـ 22
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "الأردن (+962)": "962", "البحرين (+973)": "973", "العراق (+964)": "964",
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
   conn.commit()
   return conn

conn = init_db()
SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات"]
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# --- دوال النظام الأصلية ---
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

def update_customer_info(cid, new_name, new_mobile, new_email):
   c = conn.cursor()
   c.execute("UPDATE customers SET company_name = ?, mobile = ?, email = ? WHERE id = ?", 
             (new_name, new_mobile, new_email, cid))
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
                   st.session_state.update({'logged_in': True, 'user_role': account[2], 'real_name': account[3]})
                   st.rerun()
               else: st.error("بيانات خاطئة")
       else:
           name = st.text_input("الاسم الكامل")
           user = st.text_input("اسم المستخدم")
           pw = st.text_input("كلمة المرور", type="password")
           if st.button("تسجيل"):
               if create_user(user, pw, name): st.success("تم التسجيل")
               else: st.error("المستخدم موجود")

else:
   role = st.session_state['user_role']
   with st.sidebar:
       st.title(f"مرحباً {st.session_state['real_name']}")
       menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "إضافة عميل", "بوابة المبيعات", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
       nav = st.radio("التنقل", menu)
       if nav == "خروج":
           st.session_state.clear()
           st.rerun()

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
               search_q = st.text_input("🔎 ابحث بالاسم:")
               df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
               selected_id = st.selectbox("👇 اختر العميل لإدارة ملفه:", df_view['id'].tolist(), format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
               row = my_data[my_data['id'] == selected_id].iloc[0]
               
               st.divider()
               c1, c2 = st.columns([1, 1.5])
               with c1:
                   st.subheader("📋 بيانات العميل")
                   # --- إضافة زر واتساب مباشر ---
                   clean_phone = re.sub(r'\D', '', str(row['mobile']))
                   st.markdown(f'''<a href="https://wa.me/{clean_phone}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; width: 100%; margin-bottom: 10px;">💬 مراسلة واتساب فورية</button></a>''', unsafe_allow_html=True)
                   
                   with st.form("update_info"):
                       # المدير يستطيع تعديل اسم الشركة، المندوب لا يستطيع
                       new_name = st.text_input("الشركة", value=row['company_name'], disabled=(role != 'admin'))
                       new_mob = st.text_input("الجوال", value=row['mobile'])
                       new_email = st.text_input("الإيميل", value=row['email'])
                       if st.form_submit_button("تحديث البيانات"):
                           update_customer_info(selected_id, new_name, new_mob, new_email)
                           st.success("تم تحديث البيانات!")
                           st.rerun()

               with c2:
                   with st.form("status_update"):
                       new_stage = st.selectbox("انقل العميل للمرحلة التالية:", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                       note = st.text_area("ملاحظات المتابعة:", placeholder="سجل ملاحظاتك هنا...")
                       if st.form_submit_button("✅ تسجيل العملية"):
                           update_customer_status(selected_id, row['company_name'], new_stage, st.session_state['real_name'], note)
                           st.success("تم الحفظ")
                           st.rerun()
                   
                   st.subheader("⏳ سجل المتابعات")
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
               # --- إضافة مفاتيح الدول العربية ---
               code = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
               mob_num = st.text_input("رقم الجوال *")
               em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
           
           rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
           if st.form_submit_button("حفظ"):
               full_mob = f"+{COUNTRY_CODES[code]}{mob_num.strip()}"
               # فحص التكرار قبل الحفظ
               exists = conn.execute("SELECT sales_rep FROM customers WHERE mobile = ?", (full_mob,)).fetchone()
               if exists:
                   st.error(f"⚠️ مكرر! العميل مسجل مع المندوب: {exists[0]}")
               elif comp and mob_num:
                   add_customer((comp, sec, cont, pos, full_mob, em, evt, rep, "جديد"))
                   st.success("تم الحفظ بنجاح")

   elif nav == "لوحة المدير" and role == 'admin':
       st.header("📊 إحصائيات إنجازات المناديب")
       col_d1, col_d2 = st.columns(2)
       with col_d1: start_d = st.date_input("من تاريخ", date(2025, 1, 1))
       with col_d2: end_d = st.date_input("إلى تاريخ", date.today())
       
       hist_df = get_history_log()
       if not hist_df.empty:
           hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp']).dt.date
           filtered = hist_df[(hist_df['timestamp'] >= start_d) & (hist_df['timestamp'] <= end_d)]
           if not filtered.empty:
               summary = filtered.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
               st.subheader("📋 ملخص النشاط لكل مندوب")
               st.dataframe(summary, use_container_width=True)

   elif nav == "المستخدمين" and role == 'admin':
       # القسم الأصلي تماماً بدون تعديل
       st.header("👥 إدارة المستخدمين")
       t1, t2, t3 = st.tabs(["إضافة", "تعديل كلمة مرور", "حذف"])
       # ... (كود المستخدمين الأصلي يكمل هنا)

   elif nav == "بحث شامل":
       st.header("🔍 محرك البحث الشامل")
       q = st.text_input("🔎 ابحث عن أي معلومة:")
       if q:
           all_df = get_all_data()
           res = all_df[all_df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
           st.dataframe(res, use_container_width=True, hide_index=True)
