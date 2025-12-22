import streamlit as st
import sqlite3
import pandas as pd
import re
import quopri 
from datetime import datetime, date

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
    
    # جدول العملاء
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد', created_at DATE)''')
    
    try:
        c.execute("ALTER TABLE customers ADD COLUMN created_at DATE")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer_name TEXT, 
        updated_status TEXT, changed_by TEXT, notes TEXT, timestamp TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, role TEXT, real_name TEXT)''')
    
    # جدول الفعاليات
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_name TEXT, event_date TEXT, location TEXT, assigned_rep TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '1234', 'admin', 'المدير العام'))
        conn.commit()
    conn.commit()
    return conn

conn = init_db()

SECTORS = ["تقنية", "عقارات", "تجارة تجزئة", "صناعة", "خدمات", "مقاولات", "أغذية", "طبية", "سياحة", "تعليم", "عام"]
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

def add_new_event(name, date, location):
    c = conn.cursor()
    c.execute("INSERT INTO events (event_name, event_date, location, assigned_rep) VALUES (?, ?, ?, ?)", 
              (name, date, location, 'غير محدد'))
    conn.commit()

def get_all_events():
    # تعديل لجلب الفعاليات كنص في حال كان التاريخ نصاً
    return pd.read_sql("SELECT * FROM events", conn)

def assign_event_to_rep(event_id, rep_name):
    c = conn.cursor()
    c.execute("UPDATE events SET assigned_rep = ? WHERE id = ?", (rep_name, event_id))
    conn.commit()

def get_all_users(): return pd.read_sql("SELECT username, role, real_name FROM users", conn)
def get_all_reps(): return pd.read_sql("SELECT real_name FROM users WHERE role = 'rep'", conn)['real_name'].tolist()
def get_all_data(): return pd.read_sql("SELECT * FROM customers", conn)
def get_my_data(rep): return pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep,))
def get_client_history(cid): return pd.read_sql("SELECT * FROM status_history WHERE customer_id = ? ORDER BY id DESC", conn, params=(cid,))
def get_history_log(): return pd.read_sql("SELECT * FROM status_history ORDER BY id DESC", conn)

def add_customer(data):
    c = conn.cursor()
    c.execute("SELECT sales_rep FROM customers WHERE mobile = ? OR company_name = ?", (data[4], data[0]))
    exists = c.fetchone()
    if exists: return False
    today = date.today()
    data_with_date = data + (today,)
    c.execute('''INSERT INTO customers (company_name, sector, contact_person, position, mobile, email, event_name, sales_rep, status, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data_with_date)
    conn.commit()
    return True

# --- دوال التقارير ---
def generate_rep_report(rep_name):
    c = conn.cursor()
    customers = pd.read_sql("SELECT * FROM customers WHERE sales_rep = ?", conn, params=(rep_name,))
    if customers.empty:
        return pd.DataFrame(), pd.DataFrame()
    customers['created_at'] = pd.to_datetime(customers['created_at'], errors='coerce').dt.date
    history = pd.read_sql("SELECT * FROM status_history WHERE changed_by = ?", conn, params=(rep_name,))
    history['timestamp'] = pd.to_datetime(history['timestamp'])
    return customers, history

# --- معالجة VCF ---
def parse_vcf_content(content):
    contacts_list = []
    cards = content.split(b'BEGIN:VCARD')
    for card in cards:
        if not card.strip(): continue
        try: card_str = card.decode('utf-8', errors='ignore')
        except: continue
        if '=D' in card_str or 'ENCODING=QUOTED-PRINTABLE' in card_str:
            try: card_decoded = quopri.decodestring(card).decode('utf-8', errors='ignore')
            except: card_decoded = card_str
        else: card_decoded = card_str
        fn_match = re.search(r'FN(?:;.*)?:(.*)', card_decoded)
        name = fn_match.group(1).replace(';', ' ').strip() if fn_match else ""
        org_match = re.search(r'ORG(?:;.*)?:(.*)', card_decoded)
        company = org_match.group(1).replace(';', ' ').strip() if org_match else ""
        email_match = re.search(r'EMAIL(?:;.*)?:(.*)', card_decoded)
        email = email_match.group(1).strip() if email_match else ""
        tel_matches = re.findall(r'TEL(?:;.*)?:([+\d\s-]+)', card_decoded)
        if tel_matches:
            for tel in tel_matches:
                mob = re.sub(r'[^\d]', '', str(tel))
                if len(mob) < 5: continue
                if mob.startswith('00'): mob = mob[2:]
                if mob.startswith('05'): mob = '966' + mob[1:]
                final_comp = company if company else name
                if not final_comp: final_comp = "عميل غير معروف"
                contacts_list.append({
                    'company_name': final_comp, 'sector': 'عام', 'contact_person': name, 'position': '', 
                    'mobile': mob, 'email': email, 'event_name': 'استيراد VCF', 'sales_rep': 'غير معين'
                })
    return pd.DataFrame(contacts_list).drop_duplicates(subset=['mobile'])

def bulk_import_clients(df, reps):
    count = 0
    df.columns = [str(c).lower().strip() for c in df.columns]
    column_map = {
        'company_name': 'company_name', 'اسم الشركة': 'company_name',
        'sector': 'sector', 'القطاع': 'sector',
        'contact_person': 'contact_person', 'المسؤول': 'contact_person',
        'mobile': 'mobile', 'الجوال': 'mobile', 'phone': 'mobile',
        'email': 'email', 'البريد': 'email',
        'event_name': 'event_name', 'الفعالية': 'event_name',
        'sales_rep': 'sales_rep', 'المندوب': 'sales_rep'
    }
    df = df.rename(columns=column_map)
    for _, row in df.iterrows():
        rep = row.get('sales_rep', 'غير معين')
        if pd.isna(rep) or str(rep).strip() == "": rep = 'غير معين'
        comp = row.get('company_name', '')
        if pd.isna(comp): continue
        mob = str(row.get('mobile', ''))
        if mob.endswith('.0'): mob = mob[:-2]
        data = (str(comp).strip(), str(row.get('sector', 'عام')), str(row.get('contact_person', '')), str(row.get('position', '')), 
                mob, str(row.get('email', '')), str(row.get('event_name', '')), str(rep).strip(), "جديد")
        if data[0] and len(mob) > 5:
            if add_customer(data): count += 1
    return count

def bulk_import_events(df):
    count = 0
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # تحديث الخريطة لتقبل ملفك (events.csv)
    column_map = {
        'event_name': 'event_name', 'اسم الفعالية': 'event_name', 'الفعالية': 'event_name',
        'date': 'event_date', 'التاريخ': 'event_date', 'event_date': 'event_date',
        'location': 'location', 'المكان': 'location', 'المدينة': 'location', 'المكان / القاعة': 'location'
    }
    df = df.rename(columns=column_map)
    
    for _, row in df.iterrows():
        name = row.get('event_name')
        date_val = row.get('event_date')
        loc = row.get('location')
        
        # التأكد من وجود البيانات الأساسية
        if pd.notna(name) and pd.notna(date_val):
            add_new_event(str(name), str(date_val), str(loc) if pd.notna(loc) else "")
            count += 1
    return count

# ==========================================
#             واجهة التطبيق الرئيسية
# ==========================================

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Expotime CRM")
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
    real_name = st.session_state['real_name']
    
    with st.sidebar:
        st.title(f"مرحباً {real_name}")
        if role == 'admin':
            menu = ["لوحة المدير", "التقارير", "الفعاليات", "المستخدمين", "استيراد ملف", "بوابة المبيعات", "إضافة عميل", "بحث شامل", "خروج"]
        else:
            menu = ["بوابة المبيعات", "التقارير", "الفعاليات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)

    if nav == "خروج":
        st.session_state.clear()
        st.rerun()

    # ==========================
    #      قسم التقارير
    # ==========================
    elif nav == "التقارير":
        st.header("📑 تقارير الأداء المفصلة")
        if role == 'admin':
            reps_list = get_all_reps()
            selected_rep = st.selectbox("اختر المندوب لاستخراج التقرير:", reps_list)
        else:
            selected_rep = real_name
            st.info(f"تقرير الأداء الخاص بـ: {selected_rep}")

        if selected_rep:
            customers_df, history_df = generate_rep_report(selected_rep)
            if not customers_df.empty:
                st.subheader("📊 ملخص الأداء")
                c1, c2, c3 = st.columns(3)
                c1.metric("إجمالي العملاء المسندين", len(customers_df))
                current_month = datetime.now().month
                this_month_customers = customers_df[pd.to_datetime(customers_df['created_at']).dt.month == current_month]
                c2.metric("عملاء جدد (هذا الشهر)", len(this_month_customers))
                top_status = customers_df['status'].mode()[0] if not customers_df.empty else "لا يوجد"
                c3.metric("الحالة الأكثر شيوعاً", top_status)
                st.divider()
                st.subheader("📋 تفاصيل العملاء والحالة الحالية")
                st.dataframe(customers_df[['company_name', 'mobile', 'status', 'created_at', 'event_name']], use_container_width=True)
                csv_cust = customers_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 تحميل قائمة العملاء (Excel/CSV)", data=csv_cust, file_name=f"Customers_{selected_rep}.csv", mime="text/csv")
                st.divider()
                st.subheader("📝 سجل المتابعات والتحديثات")
                if not history_df.empty:
                    st.dataframe(history_df[['customer_name', 'updated_status', 'notes', 'timestamp']], use_container_width=True)
                    csv_hist = history_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 تحميل سجل المتابعات كامل (Excel/CSV)", data=csv_hist, file_name=f"History_{selected_rep}.csv", mime="text/csv")
                else: st.warning("لا يوجد سجل متابعات مسجل لهذا المندوب حتى الآن.")
            else: st.warning("لا يوجد عملاء مسندين لهذا المندوب.")

    # ==========================
    #      قسم الفعاليات
    # ==========================
    elif nav == "الفعاليات":
        st.header("📅 إدارة الفعاليات القادمة")
        
        # إضافة فعالية يدوية للمدير
        if role == 'admin':
            with st.expander("➕ إضافة فعالية يدوياً"):
                with st.form("add_event_form"):
                    e_name = st.text_input("اسم الفعالية")
                    e_date = st.text_input("تاريخ الفعالية (مثال: 2025-10-10)")
                    e_loc = st.text_input("المكان / المدينة")
                    if st.form_submit_button("حفظ الفعالية"):
                        add_new_event(e_name, e_date, e_loc)
                        st.success("تمت الإضافة بنجاح!")
                        st.rerun()
        
        st.divider()
        st.subheader("📌 قائمة الفعاليات المتاحة")
        events = get_all_events()
        
        if not events.empty:
            for index, event in events.iterrows():
                is_taken = event['assigned_rep'] != 'غير محدد'
                with st.container():
                    c1, c2, c3 = st.columns([2, 2, 1.5])
                    with c1:
                        st.markdown(f"### 🎉 {event['event_name']}")
                        st.caption(f"📅 {event['event_date']} | 📍 {event['location']}")
                    with c2:
                        if is_taken:
                            st.markdown(f"🔒 **المسؤول:** :red[{event['assigned_rep']}]")
                            if event['assigned_rep'] == st.session_state['real_name']:
                                st.success("✅ هذه الفعالية بعهدتك")
                        else: st.markdown("🟢 **متاحة للاستلام**")
                    with c3:
                        if not is_taken:
                            if st.button("✋ استلام الفعالية", key=f"evt_{event['id']}"):
                                assign_event_to_rep(event['id'], st.session_state['real_name'])
                                st.toast(f"مبروك! أصبحت مسؤولاً عن {event['event_name']}")
                                st.rerun()
                    st.divider()
        else: st.info("لا توجد فعاليات قادمة مسجلة حالياً.")

    elif nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        rep_name = st.session_state['real_name']
        if role == 'admin':
            reps = get_all_reps()
            if reps: rep_name = st.selectbox("اختر المندوب للعرض:", reps)
        my_data = get_my_data(rep_name)
        if not my_data.empty:
            search_q = st.text_input("🔎 ابحث بالاسم:")
            df_view = my_data[my_data['company_name'].astype(str).str.contains(search_q, case=False)]
            if not df_view.empty:
                selected_id = st.selectbox("👇 اختر العميل:", df_view['id'].tolist(), format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
                row = df_view[df_view['id'] == selected_id].iloc[0]
                st.markdown("---")
                col1, col2 = st.columns([1, 1.5])
                with col1:
                    st.subheader("📋 بيانات العميل")
                    clean_mob = re.sub(r'\D', '', str(row['mobile']))
                    st.link_button("💬 واتساب فوراً", f"https://wa.me/{clean_mob}")
                    with st.form(key=f"update_info_{selected_id}"):
                        new_name = st.text_input("اسم الشركة", value=row['company_name'], disabled=(role != 'admin'))
                        new_mob = st.text_input("الجوال", value=row['mobile'])
                        new_email = st.text_input("الإيميل", value=row['email'])
                        if st.form_submit_button("تعديل البيانات"):
                            update_customer_info(selected_id, new_name, new_mob, new_email)
                            st.success("تم التعديل!")
                            st.rerun()
                with col2:
                    st.subheader("🚀 تحديث الحالة")
                    current_status = row['status']
                    idx = TRIP_STAGES.index(current_status) if current_status in TRIP_STAGES else 0
                    with st.form(key=f"status_up_{selected_id}"):
                        new_st = st.selectbox("الحالة الجديدة", TRIP_STAGES, index=idx)
                        note = st.text_area("ملاحظات المتابعة")
                        if st.form_submit_button("حفظ التحديث"):
                            update_customer_status(selected_id, row['company_name'], new_st, st.session_state['real_name'], note)
                            st.toast("✅ تم تحديث الرحلة!")
                            st.rerun()
                    st.markdown("### 🕒 سجل المتابعات")
                    history = get_client_history(selected_id)
                    if not history.empty:
                        with st.container(height=300):
                            for _, h in history.iterrows():
                                st.markdown(f"**{h['updated_status']}** | 👤 {h['changed_by']} | 📅 {h['timestamp']}")
                                if h['notes']: st.info(h['notes'])
                                st.divider()
                    else: st.info("لا يوجد سجل متابعات بعد.")
            else: st.warning("لا يوجد نتائج.")
        else: st.info("لا توجد بيانات لهذا المندوب.")

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
            if st.form_submit_button("حفظ"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                if comp and mob:
                    if add_customer((comp, sec, cont, pos, full_mob, em, evt, rep, "جديد")):
                        st.success("تمت الإضافة!")
                else: st.error("البيانات ناقصة")

    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات النظام")
        all_data = get_all_data()
        col1, col2, col3 = st.columns(3)
        col1.metric("العملاء", len(all_data))
        col2.metric("المناديب", len(get_all_reps()))
        col3.metric("المستخدمين", len(get_all_users()))
        st.divider()
        hist = get_history_log()
        if not hist.empty:
            st.subheader("📈 النشاط الأخير")
            st.dataframe(hist.head(10), use_container_width=True)

    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة", "تعديل", "حذف"])
        with t1:
            n, u, p = st.text_input("الاسم"), st.text_input("يوزر"), st.text_input("باسورد")
            if st.button("حفظ"): create_user(u,p,n); st.success("تم")
        with t2:
            u_sel = st.selectbox("المستخدم", pd.read_sql("SELECT username FROM users", conn)['username'].tolist())
            np = st.text_input("كلمة المرور الجديدة")
            if st.button("تحديث"): update_user_password(u_sel, np); st.success("تم")
        with t3:
            u_del = st.selectbox("حذف", [x for x in pd.read_sql("SELECT username FROM users", conn)['username'].tolist() if x != 'admin'])
            if st.button("حذف نهائي"): delete_user(u_del); st.rerun()

    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد (عملاء / فعاليات)")
        
        # اختيار نوع الملف
        upload_type = st.radio("ماذا تريد أن تستورد؟", ["👥 بيانات عملاء", "📅 جدول فعاليات"])
        
        f = st.file_uploader("اختر الملف", type=['xlsx', 'csv', 'vcf'])
        
        if f and st.button("بدء الاستيراد"):
            try:
                if upload_type == "👥 بيانات عملاء":
                    if f.name.endswith('.vcf'):
                        df = parse_vcf_content(f.read())
                        st.write(f"تم قراءة {len(df)} جهة اتصال من ملف VCF. جاري الحفظ...")
                    else:
                        df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                    
                    num = bulk_import_clients(df, get_all_reps())
                    st.success(f"✅ تم استيراد وتخزين {num} عميل بنجاح!")
                
                else: # استيراد فعاليات
                    if f.name.endswith('.vcf'):
                        st.error("عفواً، لا يمكن استيراد الفعاليات من ملف VCF.")
                    else:
                        df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                        num = bulk_import_events(df)
                        st.success(f"✅ تم إضافة {num} فعالية جديدة للجدول!")

            except Exception as e:
                st.error(f"حدث خطأ: {e}")

    elif nav == "بحث شامل":
        st.header("🔍 بحث شامل + استحواذ العملاء")
        q = st.text_input("بحث بالاسم، الرقم، أو المندوب:")
        if q:
            all_c = get_all_data()
            res = all_c[all_c.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            if not res.empty:
                for index, row in res.iterrows():
                    is_assigned = (row['sales_rep'] != 'غير معين') and (row['sales_rep'] is not None) and (str(row['sales_rep']).strip() != '')
                    with st.container():
                        c1, c2, c3 = st.columns([2, 2, 1])
                        with c1:
                            st.markdown(f"**🏢 {row['company_name']}**")
                            st.caption(f"📱 {row['mobile']}")
                        with c2:
                            if is_assigned:
                                st.markdown(f"🔒 **محجوز:** :red[{row['sales_rep']}]")
                            else: st.markdown("🔓 **متاح**")
                        with c3:
                            if not is_assigned:
                                if st.button("➕ لي", key=f"clm_{row['id']}"):
                                    c = conn.cursor()
                                    c.execute("UPDATE customers SET sales_rep = ? WHERE id = ?", (st.session_state['real_name'], row['id']))
                                    conn.commit()
                                    st.toast("تمت الإضافة لقائمتك!")
                                    st.rerun()
                        st.divider()
            else: st.info("لا توجد نتائج")
