elif nav == "بوابة المبيعات":
        st.header("💼 إدارة رحلة العملاء")
        rep_name = st.session_state['real_name']
        if role == 'admin':
            reps = get_all_reps()
            rep_name = st.selectbox("اختر المندوب للعرض:", reps) if reps else rep_name
        
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
                
                col1, col2 = st.columns([1, 1.5])
                
                # --- العمود الأول: المعلومات الأساسية ---
                with col1:
                    st.subheader("📋 بيانات العميل")
                    # زر الواتساب
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

                # --- العمود الثاني: رحلة العميل (الحالة والسجل) ---
                with col2:
                    st.subheader("🚀 تحديث الحالة (الرحلة)")
                    
                    # التأكد من أن الحالة الحالية موجودة في القائمة لتجنب الأخطاء
                    current_status = row['status']
                    if current_status not in TRIP_STAGES:
                        st.warning(f"الحالة الحالية '{current_status}' غير موجودة في القائمة القياسية، سيتم تعيينها إلى 'جديد'")
                        current_index = 0
                    else:
                        current_index = TRIP_STAGES.index(current_status)

                    # استخدام مفتاح فريد للنموذج (key) يعتمد على ID العميل
                    with st.form(key=f"status_up_{selected_id}"):
                        new_st = st.selectbox("الحالة الجديدة", TRIP_STAGES, index=current_index)
                        note = st.text_area("ملاحظات المتابعة", placeholder="اكتب تفاصيل الاجتماع أو الاتصال هنا...")
                        
                        if st.form_submit_button("حفظ التحديث"):
                            update_customer_status(selected_id, row['company_name'], new_st, st.session_state['real_name'], note)
                            st.toast("✅ تم تحديث الرحلة بنجاح!")
                            st.rerun()

                    st.divider()
                    st.subheader("🕒 سجل المتابعات (Timeline)")
                    
                    # جلب وعرض السجل
                    history = get_client_history(selected_id)
                    
                    if not history.empty:
                        for _, h in history.iterrows():
                            # تصميم البطاقة للسجل
                            with st.container():
                                st.markdown(f"""
                                **{h['updated_status']}** <span style='color:grey; font-size:0.8em;'>👤 {h['changed_by']} | 📅 {h['timestamp']}</span>
                                """, unsafe_allow_html=True)
                                if h['notes']:
                                    st.info(f"📝 {h['notes']}")
                                st.markdown("---")
                    else:
                        st.info("لا يوجد سجل متابعات لهذا العميل بعد.")
