import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import re 

# ==========================================
#             إعدادات النظام والدول
# ==========================================

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

# ==========================================
#             قاعدة البيانات
# ==========================================
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
    
    # إنشاء حساب المدير الافتراضي إذا لم يوجد
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '1234', 'admin', 'المدير العام'))
        conn.commit()
    conn.commit()
    return conn

conn = init_db()

SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات", "مقاولات", "أغذية", "طبية", "سياحة", "تعليم"]
TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض", "مؤجل"]

# ==========================================
#             دوال النظام
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
    # التحقق من التكرار برقم الجوال أو اسم الشركة
    c.execute("SELECT sales_rep FROM customers WHERE mobile = ? OR company_name = ?", (data[4], data[0]))
    exists = c.fetchone()
    if exists:
        st.error(f"⚠️ العميل مكرر وموجود مسبقاً مع المندوب: {exists[0]}")
        return False
    c.execute('''INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
    conn.commit()
    return True

def bulk_import(df, reps):
    count = 0
    # توحيد أسماء الأعمدة لتجنب المشاكل
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # رسم خرائط للأعمدة المتوقعة
    column_map = {
        'company_name': 'company_name', 'اسم الشركة': 'company_name',
        'sector': 'sector', 'القطاع': 'sector',
        'contact_person': 'contact_person', 'المسؤول': 'contact_person', 'contact': 'contact_person',
        'position': 'position', 'المنصب': 'position',
        'mobile': 'mobile', 'الجوال': 'mobile', 'phone': 'mobile', 'رقم الهاتف': 'mobile',
        'email': 'email', 'البريد': 'email', 'الايميل': 'email',
        'event_name': 'event_name', 'الفعالية': 'event_name', 'event': 'event_name',
        'sales_rep': 'sales_rep', 'المندوب': 'sales_rep', 'rep': 'sales_rep'
    }
    
    # إعادة تسمية الأعمدة في الداتا فريم
    df = df.rename(columns=column_map)
    
    for _, row in df.iterrows():
        rep = row.get('sales_rep', 'غير معين')
        # إذا كان المندوب فارغاً أو غير موجود
        if pd.isna(rep) or str(rep).strip() == "": rep = 'غير معين'
        
        # تجهيز البيانات
        comp = row.get('company_name', '')
        if pd.isna(comp): continue # تخطي الصفوف الفارغة
        
        mob = str(row.get('mobile', ''))
        # تنظيف بسيط للجوال
        if mob.endswith('.0'): mob = mob[:-2]
        
        data = (
            str(comp).strip(),
            str(row.get('sector', 'عام')),
            str(row.get('contact_person', '')),
            str(row.get('position', '')), 
            mob,
            str(row.get('email', '')),
            str(row.get('event_name', '')),
            str(rep).strip(),
            "جديد"
        )
        
        if data[0]: # إذا وجد اسم شركة
            if add_customer(data):
                count += 1
    return count

# ==========================================
#             واجهة التطبيق الرئيسية
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
                if create_user(user, pw, name): st.success("تم التسجيل! يمكنك الدخول الآن.")
                else: st.error("المستخدم موجود مسبقاً")
else:
    role = st.session_state['user_role']
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        if role == 'admin':
            menu = ["لوحة المدير", "المستخدمين", "استيراد ملف", "بوابة المبيعات", "إضافة عميل", "بحث شامل", "خروج"]
        else:
            menu = ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)

    # ------------------------------------------------------------------
    #                           منطق التنقل
    # ------------------------------------------------------------------

    if nav == "خروج":
        st.session_state.clear()
        st.rerun()

    elif nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        rep_name = st.session_state['real_name']
        
        if role == 'admin':
            reps = get_all_reps()
            if reps:
                col_r1, col_r2 = st.columns([1, 2])
                with col_r1:
                    rep_name = st.selectbox("اختر المندوب للعرض:", reps)
        
        my_data = get_my_data(rep_name)
        
        if not my_data.empty:
            search_q = st.text_input("🔎 ابحث بالاسم:")
            # فلترة البيانات
            df_view = my_data[my_data['company_name'].astype(str).str.contains(search_q, case=False)]
            
            if not df_view.empty:
                # اختيار العميل
                selected_id = st.selectbox(
                    "👇 اختر العميل:", 
                    df_view['id'].tolist(), 
                    format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0]
                )
                
                # جلب بيانات العميل المختار
                row = df_view[df_view['id'] == selected_id].iloc[0]
                
                st.markdown("---")
                col1, col2 = st.columns([1, 1.5])
                
                # --- العمود الأول: المعلومات الأساسية ---
                with col1:
                    st.subheader("📋 بيانات العميل")
                    # زر واتساب
                    clean_mob = re.sub(r'\D', '', str(row['mobile']))
                    st.link_button("💬 واتساب فوراً", f"https://wa.me/{clean_mob}")
                    
                    # نموذج تعديل البيانات (مع مفتاح فريد)
                    with st.form(key=f"update_info_{selected_id}"):
                        new_name = st.text_input("اسم الشركة", value=row['company_name'], disabled=(role != 'admin'))
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                        new_email = st.text_input("الإيميل", value=row['email'])
                        if st.form_submit_button("تعديل البيانات"):
                            update_customer_info(selected_id, new_name, new_mob, new_email)
                            st.success("تم التعديل!")
                            st.rerun()

                # --- العمود الثاني: رحلة العميل ---
                with col2:
                    st.subheader("🚀 تحديث الحالة (الرحلة)")
                    
                    # معالجة الحالة الحالية
                    current_status = row['status']
                    if current_status not in TRIP_STAGES:
                        st.warning(f"الحالة الحالية '{current_status}' غير قياسية. سيتم اعتبارها 'جديد'.")
                        current_index = 0
                    else:
                        current_index = TRIP_STAGES.index(current_status)

                    # نموذج تحديث الحالة (مع مفتاح فريد)
                    with st.form(key=f"status_up_{selected_id}"):
                        new_st = st.selectbox("الحالة الجديدة", TRIP_STAGES, index=current_index)
                        note = st.text_area("ملاحظات المتابعة", placeholder="اكتب تفاصيل الاجتماع أو الاتصال...")
                        
                        if st.form_submit_button("حفظ التحديث"):
                            update_customer_status(selected_id, row['company_name'], new_st, st.session_state['real_name'], note)
                            st.toast("✅ تم تحديث الرحلة!")
                            st.rerun()

                    st.markdown("### 🕒 سجل المتابعات")
                    history = get_client_history(selected_id)
                    
                    if not history.empty:
                        with st.container(height=300):
                            for _, h in history.iterrows():
                                st.markdown(f"""
                                **{h['updated_status']}** <span style='color:grey; font-size:0.8em;'>👤 {h['changed_by']} | 📅 {h['timestamp']}</span>
                                """, unsafe_allow_html=True)
                                if h['notes']:
                                    st.info(f"{h['notes']}")
                                st.divider()
                    else:
                        st.info("لا يوجد سجل متابعات بعد.")
            else:
                st.warning("لا يوجد عملاء مطابقين للبحث.")
        else:
            st.info("لا توجد بيانات لهذا المندوب.")

    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("new_c"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                sec = st.selectbox("القطاع", SECTORS)
                cont = st.text_input("المسؤول")
                pos = st.text_input("المنصب")
            with c2:
                code = st.selectbox("مفتاح الدولة *", list(COUNTRY_CODES.keys()))
                mob = st.text_input("الجوال *")
                em = st.text_input("الإيميل")
                evt = st.text_input("الفعالية المهتم بها")
            
            rep = st.text_input("المندوب", value=st.session_state['real_name'], disabled=(role != 'admin'))
            
            if st.form_submit_button("حفظ العميل"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                if comp and mob:
                    if add_customer((comp, sec, cont, pos, full_mob, em, evt, rep, "جديد")):
                        st.success("تم إضافة العميل بنجاح!")
                else:
                    st.error("الرجاء تعبئة اسم الشركة والجوال.")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات النظام")
        
        all_data = get_all_data()
        total_customers = len(all_data)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي العملاء", total_customers)
        col2.metric("عدد المناديب", len(get_all_reps()))
        col3.metric("المستخدمين", len(get_all_users()))
        
        st.divider()
        st.subheader("📈 أداء المناديب (حسب الحالات)")
        
        d1 = st.date_input("من تاريخ", date(2025, 1, 1))
        d2 = st.date_input("إلى تاريخ", date.today())
        
        hist = get_history_log()
        if not hist.empty:
            hist['timestamp'] = pd.to_datetime(hist['timestamp'])
            filt = hist[(hist['timestamp'].dt.date >= d1) & (hist['timestamp'].dt.date <= d2)]
            
            if not filt.empty:
                summary = filt.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
                st.dataframe(summary, use_container_width=True)
                
                # رسم بياني بسيط
                st.bar_chart(summary)
            else:
                st.warning("لا توجد عمليات في هذه الفترة.")

    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة", "تعديل", "حذف"])
        with t1:
            n = st.text_input("الاسم الحقيقي")
            u = st.text_input("اسم المستخدم للدخول")
            p = st.text_input("كلمة المرور")
            if st.button("حفظ المستخدم"): 
                if create_user(u,p,n): st.success("تم!")
        with t2:
            u_sel = st.selectbox("اختر المستخدم", pd.read_sql("SELECT username FROM users", conn)['username'].tolist())
            np = st.text_input("كلمة المرور الجديدة")
            if st.button("تحديث كلمة المرور"): update_user_password(u_sel, np); st.success("تم!")
        with t3:
            u_del = st.selectbox("حذف مستخدم", [x for x in pd.read_sql("SELECT username FROM users", conn)['username'].tolist() if x != 'admin'])
            if st.button("تأكيد الحذف النهائي"): delete_user(u_del); st.rerun()

    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد العملاء (Excel/CSV)")
        st.info("تأكد أن الملف يحتوي على أعمدة: company_name, mobile, sales_rep")
        f = st.file_uploader("اختر الملف", type=['xlsx', 'csv'])
        if f and st.button("بدء الاستيراد"):
            try:
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                num = bulk_import(df, get_all_reps())
                st.success(f"تم استيراد {num} عميل بنجاح!")
            except Exception as e:
                st.error(f"حدث خطأ في الملف: {e}")

    elif nav == "بحث شامل":
        st.header("🔍 بحث في كل الداتا")
        q = st.text_input("اكتب اسم الشركة، الرقم، أو المندوب:")
        if q:
            all_c = get_all_data()
            # البحث في جميع الأعمدة
            res = all_c[all_c.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            st.dataframe(res, use_container_width=True)
