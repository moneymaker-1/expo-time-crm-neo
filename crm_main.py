import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import re 

# قائمة الدول العربية المضافة
COUNTRY_CODES = {
    "السعودية (+966)": "966", "الإمارات (+971)": "971", "مصر (+20)": "20",
    "الكويت (+965)": "965", "قطر (+974)": "974", "عمان (+968)": "968",
    "الأردن (+962)": "962", "المغرب (+212)": "212"
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

def get_all_reps(): return pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
def get_all_data(): return pd.read_sql("SELECT * FROM customers", conn)
def get_my_data(rep): return pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep,))
def get_client_history(cid): return pd.read_sql("SELECT * FROM status_history WHERE customer_id = ? ORDER BY id DESC", conn, params=(cid,))
def get_history_log(): return pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn)

def add_customer(data):
   c = conn.cursor()
   # ميزة منع التكرار المضافة هنا
   c.execute("SELECT sales_rep FROM customers WHERE mobile = ? OR company_name = ?", (data[4], data[0]))
   exists = c.fetchone()
   if exists:
       st.error(f"⚠️ هذا العميل مسجل مسبقاً مع المندوب: {exists[0]}")
       return False
   c.execute('''INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
   conn.commit()
   return True

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
               selected_id = st.selectbox("👇 اختر العميل:", df_view['id'].tolist(), format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
               row = my_data[my_data['id'] == selected_id].iloc[0]
               
               c1, c2 = st.columns([1, 1.5])
               with c1:
                   st.subheader("📋 بيانات العميل")
                   # ميزة الواتساب المضافة
                   st.link_button("💬 مراسلة واتساب فورية", f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}")
                   with st.form("update_info"):
                       st.text_input("الشركة", value=row['company_name'], disabled=True)
                       new_mob = st.text_input("الجوال", value=row['mobile'])
                       new_em = st.text_input("الإيميل", value=row['email'])
                       if st.form_submit_button("تحديث البيانات"):
                           update_customer_info(selected_id, new_mob, new_em)
                           st.success("تم التحديث")

               with c2:
                   with st.form("status_update"):
                       new_stage = st.selectbox("الحالة الجديدة:", TRIP_STAGES, index=TRIP_STAGES.index(row['status']))
                       note = st.text_area("ملاحظات المتابعة:")
                       if st.form_submit_button("✅ تسجيل العملية"):
                           update_customer_status(selected_id, row['company_name'], new_stage, st.session_state['real_name'], note)
                           st.success("تم الحفظ")
                           st.rerun()

   elif nav == "إضافة عميل":
       st.header("➕ إضافة عميل جديد")
       with st.form("new_c"):
           c1, c2 = st.columns(2)
           with c1:
               comp, sec = st.text_input("اسم الشركة *"), st.selectbox("القطاع", SECTORS)
               cont, pos = st.text_input("الشخص المسؤول"), st.text_input("المنصب")
           with c2:
               # ميزة مفاتيح الدول المضافة
               c_key = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
               mob_num = st.text_input("رقم الجوال *")
               em, evt = st.text_input("الإيميل"), st.text_input("الفعالية")
           
           rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
           if st.form_submit_button("حفظ"):
               full_mob = f"+{COUNTRY_CODES[c_key]}{mob_num.strip()}"
               if add_customer((comp, sec, cont, pos, full_mob, em, evt, rep, "جديد")):
                   st.success("تم الحفظ بنجاح")

   elif nav == "بحث شامل":
       st.header("🔍 محرك البحث الشامل")
       q = st.text_input("🔎 ابحث عن أي معلومة (اسم شركة، رقم، مندوب...):")
       if q:
           all_df = get_all_data()
           res = all_df[all_df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
           st.dataframe(res, use_container_width=True, hide_index=True)
