import streamlit as st
import pandas as pd
import requests
import os
import database as db
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- КОНФИГУРАЦИЯ ---
YANDEX_TOKEN = "y0__xCF7vSyBhj0hTwg2oaewBUWNr9rdgvFpxw2k559OGkSU4o9VA"

FONTS_DIR = 'fonts'
TEMPLATES_DIR = 'templates'

# --- CSS ХАК ДЛЯ УДАЛЕНИЯ НАДПИСЕЙ В ЗАГРУЗЧИКЕ ---
hide_uploader_text = """
<style>
    /* Скрываем текст "Limit 200MB per file" */
    [data-testid="stFileUploader"] section > div > small {
        display: none;
    }
    /* Скрываем иконку и текст "Drag and drop file here" */
    [data-testid="stFileUploader"] section > div > div > span {
        display: none; 
    }
    /* Делаем зону компактнее */
    [data-testid="stFileUploader"] section {
        padding: 0px;
    }
    [data-testid="stFileUploader"] section > div {
        padding-top: 15px;
        padding-bottom: 15px;
    }
</style>
"""

# --- ИНТЕГРАЦИЯ С ЯНДЕКС ДИСКОМ ---
def create_yandex_folder(folder_name):
    headers = {'Authorization': f'OAuth {YANDEX_TOKEN}'}
    requests.put('https://cloud-api.yandex.net/v1/disk/resources?path=/Clients', headers=headers)
    client_path = f'/Clients/{folder_name}'
    requests.put(f'https://cloud-api.yandex.net/v1/disk/resources?path={client_path}', headers=headers)
    requests.put(f'https://cloud-api.yandex.net/v1/disk/resources/publish?path={client_path}', headers=headers)
    meta_res = requests.get(f'https://cloud-api.yandex.net/v1/disk/resources?path={client_path}', headers=headers)
    if meta_res.status_code == 200:
        return meta_res.json().get('public_url', 'Нет ссылки')
    return "Ошибка создания"

def upload_to_yandex(file_obj, folder_name, filename):
    headers = {'Authorization': f'OAuth {YANDEX_TOKEN}'}
    path = f'/Clients/{folder_name}/{filename}'
    res = requests.get(f'https://cloud-api.yandex.net/v1/disk/resources/upload?path={path}&overwrite=true', headers=headers)
    if res.status_code == 200:
        upload_url = res.json().get('href')
        requests.put(upload_url, files={'file': file_obj})
        return True
    return False

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def formatted_number_input(label, key, allow_float=False):
    if key not in st.session_state:
        st.session_state[key] = ""
        
    def on_change():
        val = st.session_state[key]
        if allow_float:
            # allow digits and one dot/comma
            val = val.replace(',', '.')
            clean = ''.join(c for c in val if c.isdigit() or c == '.')
            if clean.count('.') > 1:
                clean = clean.replace('.', '', clean.count('.') - 1)
            
            if clean:
                parts = clean.split('.')
                int_part = "{:,}".format(int(parts[0])).replace(",", " ")
                if len(parts) > 1:
                    formatted = f"{int_part}.{parts[1]}"
                else:
                    formatted = int_part
                st.session_state[key] = formatted
            else:
                st.session_state[key] = ""
        else:
            # remove non-digits
            clean = ''.join(c for c in val if c.isdigit())
            if clean:
                # format with spaces
                formatted = "{:,}".format(int(clean)).replace(",", " ")
                st.session_state[key] = formatted
            else:
                st.session_state[key] = ""
            
    st.text_input(label, key=key, on_change=on_change)
    
    val = st.session_state[key]
    if allow_float:
        clean = val.replace(' ', '')
        try:
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0
    else:
        clean = ''.join(c for c in val if c.isdigit())
        return int(clean) if clean else 0

def formatted_phone_input(label, key):
    if key not in st.session_state:
        st.session_state[key] = ""
        
    def on_change():
        val = st.session_state[key]
        # keep only digits
        clean = ''.join(c for c in val if c.isdigit())
        
        if not clean:
            st.session_state[key] = ""
            return

        # Ensure starts with 7
        if clean.startswith('8'):
            clean = '7' + clean[1:]
        elif not clean.startswith('7'):
            clean = '7' + clean
            
        # Limit length to 11 digits (7 + 10 digits)
        clean = clean[:11]
        
        # Format: +7 999 999 99 99
        formatted = "+7"
        if len(clean) > 1:
            formatted += " " + clean[1:4]
        if len(clean) > 4:
            formatted += " " + clean[4:7]
        if len(clean) > 7:
            formatted += " " + clean[7:9]
        if len(clean) > 9:
            formatted += " " + clean[9:11]
            
        st.session_state[key] = formatted

    st.text_input(label, key=key, on_change=on_change)
    return st.session_state[key]

# --- ИНИЦИАЛИЗАЦИЯ ---
db.init_db()
st.set_page_config(page_title="Mortgage CRM", layout="wide", page_icon="🏦")
st.markdown(hide_uploader_text, unsafe_allow_html=True) # ПРИМЕНЯЕМ СТИЛИ

st.sidebar.title("СОКОЛ")
page = st.sidebar.radio("Меню", ["Рабочий стол", "Новый клиент", "Карточка Клиента", "База Банков"])

if st.sidebar.button("Обновить данные"):
    st.cache_data.clear()
    st.rerun()

# --- СТРАНИЦА: РАБОЧИЙ СТОЛ ---
if page == "Рабочий стол":
    st.title("📋 База Клиентов")
    
    df = db.load_clients()
    
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.multiselect("Фильтр по статусу", options=df["status"].unique())
        with col2:
            search = st.text_input("Поиск по ФИО")
            
        if status_filter:
            df = df[df["status"].isin(status_filter)]
            
        if search:
            df = df[df["fio"].str.contains(search, case=False)]
            
        # Add Select column for deletion
        df.insert(0, "Select", False)
        
        # Use data_editor to allow checkbox selection
        edited_df = st.data_editor(
            df,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Выбрать",
                    help="Выберите для удаления",
                    default=False,
                )
            },
            disabled=df.columns[1:], # Disable editing for other columns
            hide_index=True,
            key="client_editor"
        )
        
        if st.button("Удалить выбранные"):
            # Find selected rows
            selected_rows = edited_df[edited_df["Select"]]
            if not selected_rows.empty:
                for index, row in selected_rows.iterrows():
                    db.delete_client(row["id"])
                st.success(f"Удалено {len(selected_rows)} клиентов.")
                st.rerun()
            else:
                st.warning("Выберите клиентов для удаления.")
    else:
        st.info("База данных пуста.")

# --- СТРАНИЦА: НОВЫЙ КЛИЕНТ ---
elif page == "Новый клиент":
    st.title("👤 Новый Клиент")
    
    st.subheader("Основная информация")
    c1, c2, c3 = st.columns(3)
    with c1:
        fio = st.text_input("ФИО Клиента")
    with c2:
        status = st.selectbox("Статус", ["Новый", "В работе", "Одобрен", "Сделка", "Отказ"])
    with c3:
        loan_type = st.selectbox("Тип сделки", ["Ипотека", "Залог", "Рефинансирование", "Покупка"])
        
    c4, c5 = st.columns(2)
    with c4:
        credit_sum = formatted_number_input("Сумма кредита", "credit_sum_input")
    with c5:
        obj_price = formatted_number_input("Стоимость объекта", "obj_price_input")

    tab1, tab2, tab3 = st.tabs(["Личные данные", "Финансы", "Залог"])
    
    with tab1:
        pd1, pd2 = st.columns(2)
        with pd1:
            phone = formatted_phone_input("Телефон", "phone_input")
        with pd2:
            email_user = st.text_input("Email (имя)", placeholder="example")
            email_domain = st.selectbox("Домен", ["@gmail.com", "@mail.ru", "@yandex.ru", "@bk.ru", "@list.ru", "@inbox.ru", "@icloud.com", "Другое"], label_visibility="collapsed")
            if email_domain == "Другое":
                email_full_domain = st.text_input("Введите домен", placeholder="@domain.com")
                email = f"{email_user}{email_full_domain}" if email_user and email_full_domain else ""
            else:
                email = f"{email_user}{email_domain}" if email_user else ""
            st.caption(f"Итоговый Email: {email}")

        st.divider()
        st.markdown("##### Паспортные данные")
        p1, p2, p3 = st.columns(3)
        with p1:
            passport_series = formatted_number_input("Серия", "pass_series")
            passport_num = formatted_number_input("Номер", "pass_num")
        with p2:
            passport_code = formatted_number_input("Код подразделения", "pass_code")
            passport_date = st.date_input("Дата выдачи", value=None)
        with p3:
            passport_issued = st.text_input("Кем выдан")
            
        gender = st.radio("Пол", ["Мужской", "Женский"], horizontal=True)
        dob = st.date_input("Дата рождения", value=datetime(1990, 1, 1))
        birth_place = st.text_input("Место рождения")
        
        st.divider()
        st.markdown("##### Семья")
        f1, f2 = st.columns(2)
        with f1:
            family_status = st.selectbox("Семейное положение", ["Холост/Не замужем", "Женат/Замужем", "Разведен/а", "Вдовец/Вдова"])
        with f2:
            children = st.number_input("Количество детей", min_value=0, step=1)
            
        st.divider()
        st.markdown("##### Адрес регистрации")
        ar1, ar2, ar3 = st.columns([1, 2, 2])
        with ar1: addr_index = formatted_number_input("Индекс", "addr_index")
        with ar2: addr_city = st.text_input("Город/Населенный пункт", key="addr_city")
        with ar3: addr_street = st.text_input("Улица", key="addr_street")
        
        ar4, ar5, ar6, ar7, ar8 = st.columns(5)
        with ar4: addr_house = st.text_input("Дом", key="addr_house")
        with ar5: addr_korpus = st.text_input("Корпус", key="addr_korpus")
        with ar6: addr_structure = st.text_input("Строение", key="addr_structure")
        with ar7: addr_flat = st.text_input("Квартира", key="addr_flat")
        with ar8: 
            st.markdown("<div style='padding-top: 28px;'><a href='https://pochta.ru/indexes' target='_blank' style='text-decoration: none; font-size: 24px;'>🔍</a></div>", unsafe_allow_html=True)

        st.divider()
        st.markdown("##### Адрес объекта (если отличается)")
        copy_addr = st.checkbox("Совпадает с адресом регистрации")
        
        if not copy_addr:
            ao1, ao2, ao3 = st.columns([1, 2, 2])
            with ao1: obj_index = formatted_number_input("Индекс (Объект)", "obj_index")
            with ao2: obj_city = st.text_input("Город (Объект)", key="obj_city")
            with ao3: obj_street = st.text_input("Улица (Объект)", key="obj_street")
            
            ao4, ao5, ao6, ao7 = st.columns(4)
            with ao4: obj_house = st.text_input("Дом (Объект)", key="obj_house")
            with ao5: obj_korpus = st.text_input("Корпус (Объект)", key="obj_korpus")
            with ao6: obj_structure = st.text_input("Строение (Объект)", key="obj_structure")
            with ao7: obj_flat = st.text_input("Квартира (Объект)", key="obj_flat")
        else:
            # Placeholder values if copied
            obj_index = addr_index
            obj_city = addr_city
            obj_street = addr_street
            obj_house = addr_house
            obj_korpus = addr_korpus
            obj_structure = addr_structure
            obj_flat = addr_flat

    with tab2:
        st.subheader("Работа и Финансы")
        job_type = st.selectbox("Тип занятости", ["Найм", "ИП", "Самозанятый", "Бизнес", "Пенсионер"])
        
        j1, j2 = st.columns(2)
        with j1:
            job_sphere = st.text_input("Сфера деятельности")
            job_company = st.text_input("Название компании")
            job_phone = formatted_phone_input("Телефон организации", "job_phone")
            job_site = st.text_input("Сайт компании")
        with j2:
            job_inn = formatted_number_input("ИНН Организации", "job_inn")
            job_ceo = st.text_input("ФИО Ген. директора")
            job_pos = st.text_input("Должность")
            
        st.divider()
        f1, f2, f3 = st.columns(3)
        with f1:
            job_income = formatted_number_input("Доход в месяц", "job_income")
        with f2:
            job_start_date = st.date_input("Дата трудоустройства", value=None)
        with f3:
            if job_start_date:
                delta = relativedelta(datetime.now().date(), job_start_date)
                st.info(f"Стаж: {delta.years} лет {delta.months} мес.")
                job_exp = f"{delta.years} лет {delta.months} мес."
            else:
                job_exp = "0"

        st.divider()
        
        # Layout: Debts | Mos Comment | Mos Link | FSSP Comment | FSSP Link | Block Comment | Block Link
        f3_cols = st.columns([3, 2, 1.2, 2, 1.2, 2, 1.2])
        
        with f3_cols[0]:
            current_debts = formatted_number_input("Текущие платежи по кредитам", "current_debts_input")
            
        with f3_cols[1]:
            mosgorsud_comment = st.text_input("Суд", placeholder="Коммент")
        with f3_cols[2]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://www.mos-gorsud.ru/search?_cb=1764799069.0607' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>⚖️</a></div>", unsafe_allow_html=True)

        with f3_cols[3]:
            fssp_comment = st.text_input("ФССП", placeholder="Коммент")
        with f3_cols[4]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://fssp.gov.ru/' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>👮‍♂️</a></div>", unsafe_allow_html=True)

        with f3_cols[5]:
            block_comment = st.text_input("Блок", placeholder="Коммент")
        with f3_cols[6]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://service.nalog.ru/bi.html' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>🚫</a></div>", unsafe_allow_html=True)
        
        assets_list = st.multiselect("Доп. активы", ["Машина", "Квартира", "Дом с ЗУ", "Коммерция", "Другое"])
        assets_str = ", ".join(assets_list)

    with tab3:
        st.subheader("Залог")
        is_pledged = st.checkbox("Есть обременение?")
        if is_pledged:
            pledge_bank = st.text_input("Банк залогодержатель")
            pledge_amount = formatted_number_input("Остаток долга", "pledge_amount")
        else:
            pledge_bank = ""
            pledge_amount = 0

    if st.button("Сохранить Клиента", type="primary"):
        if fio:
            client_id = str(hash(fio + str(datetime.now())))
            folder_name = f"{fio}_{datetime.now().strftime('%Y-%m-%d')}"
            yandex_link = create_yandex_folder(folder_name)
            
            # Prepare data
            data = {
                "id": client_id,
                "created_at": datetime.now().strftime('%Y-%m-%d'),
                "status": status,
                "loan_type": loan_type,
                "fio": fio,
                "credit_sum": credit_sum,
                "obj_price": obj_price,
                "phone": phone,
                "email": email,
                "passport_series": passport_series,
                "passport_num": passport_num,
                "passport_code": passport_code,
                "passport_date": str(passport_date) if passport_date else "",
                "passport_issued": passport_issued,
                "gender": gender,
                "dob": str(dob),
                "birth_place": birth_place,
                "family_status": family_status,
                "children": children,
                "addr_index": addr_index,
                "addr_city": addr_city,
                "addr_street": addr_street,
                "addr_house": addr_house,
                "addr_korpus": addr_korpus,
                "addr_structure": addr_structure,
                "addr_flat": addr_flat,
                "obj_index": obj_index,
                "obj_city": obj_city,
                "obj_street": obj_street,
                "obj_house": obj_house,
                "obj_korpus": obj_korpus,
                "obj_structure": obj_structure,
                "obj_flat": obj_flat,
                "job_type": job_type,
                "job_sphere": job_sphere,
                "job_company": job_company,
                "job_phone": job_phone,
                "job_site": job_site,
                "job_inn": job_inn,
                "job_ceo": job_ceo,
                "job_pos": job_pos,
                "job_income": job_income,
                "job_start_date": str(job_start_date) if job_start_date else "",
                "job_exp": job_exp,
                "current_debts": current_debts,
                "mosgorsud_comment": mosgorsud_comment,
                "fssp_comment": fssp_comment,
                "block_comment": block_comment,
                "assets": assets_str,
                "is_pledged": "Да" if is_pledged else "Нет",
                "pledge_bank": pledge_bank,
                "pledge_amount": pledge_amount,
                "yandex_link": yandex_link
            }
            
            db.save_client(data)
            st.success(f"Клиент {fio} сохранен!")
            st.balloons()
        else:
            st.error("Введите ФИО")

# --- СТРАНИЦА: КАРТОЧКА КЛИЕНТА ---
elif page == "Карточка Клиента":
    st.title("Карточка Клиента")
    
    df = db.load_clients()
    
    if not df.empty:
        client_list = sorted(df["fio"].tolist())
        selected_name = st.selectbox("Поиск клиента", client_list, index=None, placeholder="Выберите клиента...")
        
        if selected_name:
            client = df[df["fio"] == selected_name].iloc[0]
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(client['fio'])
                st.caption(f"Статус: {client['status']}")
                st.text(f"📞 {client.get('phone', 'Нет номера')}")
                
                st.divider()
                if client.get('yandex_link') and str(client['yandex_link']).startswith('http'):
                    st.link_button("📂 Папка на Яндекс Диске", client['yandex_link'])
                else:
                    st.caption("Нет папки в облаке")

                with st.expander("Анкетные данные"):
                    st.write(client.to_dict())
            
            with c2:
                # ЧИСТАЯ ЗАГРУЗКА БЕЗ НАДПИСЕЙ
                uploaded = st.file_uploader("Загрузить документы", label_visibility="visible", accept_multiple_files=False)
                
                if uploaded and st.button("Загрузить в облако"):
                    # Имя папки восстанавливаем по логике создания (ФИО + Дата)
                    # В идеале хранить имя папки в БД, но пока так
                    folder_name = f"{client['fio']}_{client['created_at']}"
                    with st.spinner("⏳ Загрузка..."):
                        if upload_to_yandex(uploaded, folder_name, uploaded.name):
                            st.toast(f"✅ Файл {uploaded.name} сохранен!", icon=None)
                        else:
                            st.error("Ошибка загрузки")

    else:
        st.info("Нет клиентов в базе")

# --- СТРАНИЦА: БАЗА БАНКОВ ---
elif page == "База Банков":
    st.title("🏦 База Банков")
    df = db.load_banks()
    st.dataframe(df, use_container_width=True)
    
    with st.expander("Добавить банк"):
        with st.form("new_bank"):
            n = st.text_input("Название банка")
            m = st.text_input("Email менеджера")
            if st.form_submit_button("Добавить"):
                db.save_bank({"name": n, "manager_email": m})
                st.rerun()