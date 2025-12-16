import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import re 

# ==========================================
#              إعدادات النظام
# ==========================================
st.set_page_config(page_title="Expotime CRM", layout="wide", page_icon="🏢")

# قائمة الـ 22 دولة عربية
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

TRIP_STAGES = ["جديد", "تم الاتصال", "تم الاجتماع", "تم تقديم التصميم", "تم تقديم عرض مالي", "تم التعديل", "تم التعميد", "تم الرفض"]

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('company_crm.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, sector TEXT, contact_person TEXT, position TEXT, 
        mobile TEXT, email TEXT, event_name TEXT, sales_rep TEXT, status TEXT DEFAULT 'جديد', contract_amount REAL DEFAULT 0)''')
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

# ==========================================
#              واجهة التطبيق
# ==========================================

if not st.session_state.get('logged_in'):
    st.title("🔐 Expo Time CRM")
    choice = st.selectbox("القائمة", ["تسجيل دخول", "تسجيل مندوب جديد"])
    user = st.text_input("اسم المستخدم")
    pw = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?) AND password=?", (user, pw))
        acc = c.fetchone()
        if acc:
            st.session_state.update({'logged_in': True, 'user_role': acc[2], 'real_name': acc[3]})
            st.rerun()
        else: st.error("خطأ في البيانات")
else:
    role = st.session_state['user_role']
    with st.sidebar:
        st.title(f"مرحباً {st.session_state['real_name']}")
        menu = ["بوابة المبيعات", "إضافة عميل", "لوحة المدير", "المستخدمين", "استيراد ملف", "بحث شامل", "خروج"] if role == 'admin' else ["بوابة المبيعات", "إضافة عميل", "خروج"]
        nav = st.radio("التنقل", menu)
        if nav == "خروج": st.session_state.clear(); st.rerun()

    # --- بوابة المبيعات ---
    if nav == "بوابة المبيعات":
        st.header("💼 إدارة العملاء")
        rep_n = st.session_state['real_name']
        if role == 'admin':
            reps = pd.read_sql("SELECT real_name FROM users WHERE role='rep'", conn)['real_name'].tolist()
            rep_n = st.selectbox("اختر المندوب للعرض:", reps) if reps else rep_n
        
        my_data = pd.read_sql("SELECT * FROM customers WHERE sales_rep=?", conn, params=(rep_n,))
        if not my_data.empty:
            search_q = st.text_input("🔎 ابحث بالاسم:")
            df_view = my_data[my_data['company_name'].str.contains(search_q, case=False)]
            
            if not df_view.empty:
                selected_id = st.selectbox("👇 اختر العميل:", df_view['id'].tolist(), format_func=lambda x: df_view[df_view['id']==x]['company_name'].values[0])
                row = my_data[my_data['id'] == selected_id].iloc[0]
                
                with st.form("status_update_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        # المدير يستطيع تعديل البيانات، المندوب يشاهد فقط
                        new_cname = st.text_input("اسم الشركة", value=row['company_name'], disabled=(role != 'admin'))
                        new_mob = st.text_input("رقم الجوال", value=row['mobile'], disabled=(role != 'admin'))
                        st.link_button("💬 مراسلة واتساب", f"https://wa.me/{row['mobile'].replace('+', '').replace(' ', '')}")
                        new_st = st.selectbox("تحديث الحالة", TRIP_STAGES, index=TRIP_STAGES.index(row['status']) if row['status'] in TRIP_STAGES else 0)
                    with c2:
                        amt = st.number_input("مبلغ التعميد (SAR)", value=float(row.get('contract_amount', 0)) if new_st == "تم التعميد" else 0.0)
                        note = st.text_area("ملاحظات المتابعة")
                    
                    if st.form_submit_button("💾 حفظ التعديلات"):
                        conn.execute("UPDATE customers SET company_name=?, mobile=?, status=?, contract_amount=? WHERE id=?", (new_cname, new_mob, new_st, amt, selected_id))
                        conn.execute("INSERT INTO status_history (customer_id, customer_name, updated_status, changed_by, notes, timestamp) VALUES (?,?,?,?,?,?)", 
                                     (selected_id, new_cname, new_st, st.session_state['real_name'], note, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit(); st.success("تم التحديث"); st.rerun()
            else: st.warning("لا توجد نتائج.")

    # --- إضافة عميل ---
    elif nav == "إضافة عميل":
        st.header("➕ إضافة عميل")
        with st.form("add_client"):
            c1, c2 = st.columns(2)
            with c1:
                comp = st.text_input("اسم الشركة *")
                code = st.selectbox("الدولة", list(COUNTRY_CODES.keys()))
            with c2:
                mob = st.text_input("رقم الجوال *")
                rep = st.text_input("المندوب المسجل", value=st.session_state['real_name'], disabled=(role != 'admin'))
            
            if st.form_submit_button("تأكيد الحفظ"):
                full_mob = f"+{COUNTRY_CODES[code]}{mob.strip()}"
                # منع التكرار
                dup = conn.execute("SELECT sales_rep, company_name FROM customers WHERE mobile=? OR (company_name=? AND sales_rep=?)", (full_mob, comp, rep)).fetchone()
                if dup: st.error(f"⚠️ مكرر! العميل مسجل مسبقاً مع المندوب: {dup[0]}")
                elif comp and mob:
                    conn.execute("INSERT INTO customers (company_name, mobile, sales_rep) VALUES (?,?,?)", (comp, full_mob, rep))
                    conn.commit(); st.success("تم الحفظ بنجاح")

    # --- لوحة المدير ---
    elif nav == "لوحة المدير" and role == 'admin':
        st.header("📊 إحصائيات الأداء المجمعة")
        c1, c2 = st.columns(2)
        with c1: d_start = st.date_input("من تاريخ", date(2025, 1, 1))
        with c2: d_end = st.date_input("إلى تاريخ", date.today())
        
        hist_df = pd.read_sql("SELECT * FROM status_history", conn)
        if not hist_df.empty:
            hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
            filtered = hist_df[(hist_df['timestamp'].dt.date >= d_start) & (hist_df['timestamp'].dt.date <= d_end)]
            if not filtered.empty:
                # 
                summary = filtered.groupby(['changed_by', 'updated_status']).size().unstack(fill_value=0)
                st.subheader("📈 ملخص العمليات لكل مندوب")
                st.dataframe(summary, use_container_width=True)
                st.plotly_chart(px.bar(filtered, x='changed_by', color='updated_status', barmode='group'))
            else: st.warning("لا توجد بيانات للفترة المختارة.")

    # --- المستخدمين ---
    elif nav == "المستخدمين" and role == 'admin':
        st.header("👥 إدارة المستخدمين")
        t1, t2, t3 = st.tabs(["إضافة", "تعديل باسورد", "حذف"])
        with t1:
            n, u, p = st.text_input("الاسم"), st.text_input("اليوزر"), st.text_input("الباس")
            if st.button("إنشاء"):
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, 'rep', n))
                conn.commit(); st.success("تم")
        with t2:
            u_list = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
            u_sel = st.selectbox("اختر مستخدم", u_list)
            np = st.text_input("كلمة مرور جديدة")
            if st.button("تحديث الباسورد"):
                conn.execute("UPDATE users SET password=? WHERE username=?", (np, u_sel)); conn.commit(); st.success("تم")
        with t3:
            u_del = st.selectbox("حذف مستخدم", [x for x in u_list if x != 'admin'])
            if st.button("تأكيد الحذف"):
                conn.execute("DELETE FROM users WHERE username=?", (u_del,)); conn.commit(); st.success("تم"); st.rerun()

    # --- استيراد ملف ---
    elif nav == "استيراد ملف" and role == 'admin':
        st.header("📤 استيراد داتا")
        f = st.file_uploader("اختر ملف", type=['xlsx', 'csv'])
        if f and st.button("بدء الاستيراد"):
            df_in = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df_in.to_sql('customers', conn, if_exists='append', index=False)
            st.success("تم استيراد الداتا بنجاح")

    # --- بحث شامل ---
    elif nav == "بحث شامل":
        st.header("🔍 محرك البحث الشامل")
        q = st.text_input("🔎 ابحث عن أي معلومة (شركة، جوال، مندوب):")
        if q:
            all_c = pd.read_sql("SELECT * FROM customers", conn)
            res = all_c[all_c.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            st.dataframe(res, use_container_width=True, hide_index=True)
