import streamlit as st
import pandas as pd
import requests
import os
import database as db
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# --- Configuration ---
YANDEX_TOKEN = "y0__xCF7vSyBhj0hTwg2oaewBUWNr9rdgvFpxw2k559OGkSU4o9VA"
FONTS_DIR = 'fonts'
TEMPLATES_DIR = 'templates'

# Helper function for formatted number input
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


# --- Sidebar ---
db.init_db()

# --- Yandex Disk Integration ---
def create_yandex_folder(folder_name):
    headers = {'Authorization': f'OAuth {YANDEX_TOKEN}'}
    base_path = '/Clients'
    path = f'{base_path}/{folder_name}'
    
    # Ensure base folder exists
    requests.put(f'https://cloud-api.yandex.net/v1/disk/resources?path={base_path}', headers=headers)
    
    # Create target folder
    requests.put(f'https://cloud-api.yandex.net/v1/disk/resources?path={path}', headers=headers)
    
    # Publish and get link
    requests.put(f'https://cloud-api.yandex.net/v1/disk/resources/publish?path={path}', headers=headers)
    meta = requests.get(f'https://cloud-api.yandex.net/v1/disk/resources?path={path}', headers=headers).json()
    
    return meta.get('public_url', 'Ссылка не создана')

def upload_to_yandex(file_obj, folder_name, filename):
    headers = {'Authorization': f'OAuth {YANDEX_TOKEN}'}
    path = f'/Clients/{folder_name}/{filename}'
    
    # Check if folder exists, if not - create it (robustness)
    # We do a quick check by trying to get meta info about folder
    folder_path = f'/Clients/{folder_name}'
    check = requests.get(f'https://cloud-api.yandex.net/v1/disk/resources?path={folder_path}', headers=headers)
    if check.status_code != 200:
        # Folder missing, try to create it
        create_yandex_folder(folder_name)
        
    # Get upload URL
    res = requests.get(f'https://cloud-api.yandex.net/v1/disk/resources/upload?path={path}&overwrite=true', headers=headers).json()
    upload_url = res.get('href')
    
    if upload_url:
        try:
            requests.put(upload_url, files={'file': file_obj})
            return True
        except Exception as e:
            st.error(f"Ошибка при отправке файла: {e}")
            return False
    else:
        # If we can't get upload URL, maybe path is wrong or token invalid
        st.error(f"Не удалось получить ссылку для загрузки. Ответ Яндекса: {res}")
        return False

# --- CSS Styles ---
# --- CSS Styles ---
hide_uploader_text = """
<style>
/* Hide the "Drag and drop..." text */
[data-testid='stFileUploader'] section > div:first-child > span {
    display: none;
}
/* Hide the "Limit 200MB..." text */
[data-testid='stFileUploader'] section > div:first-child > small {
    display: none;
}
/* Style the Browse button */
/* We target the button INSIDE the section (dropzone) to avoid targeting delete buttons in the file list */
[data-testid='stFileUploader'] section button {
    border: 1px solid #4CAF50;
    color: white;
    background-color: #4CAF50; 
    border-radius: 5px;
    visibility: hidden; /* Hide original text */
    position: relative;
    width: 150px;
}
/* Hack to change button text */
[data-testid='stFileUploader'] section button::after {
    content: "Выбрать файлы";
    visibility: visible;
    display: block;
    position: absolute;
    background-color: #4CAF50;
    padding: 5px 10px;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
}
</style>
"""

# --- UI Layout ---
st.set_page_config(page_title="Mortgage CRM", layout="wide", page_icon="🏦")
st.markdown(hide_uploader_text, unsafe_allow_html=True) # ПРИМЕНЯЕМ СТИЛИ

st.sidebar.title("СОКОЛ")
page = st.sidebar.radio("Меню", ["Рабочий стол", "Новый клиент", "Карточка Клиента", "База Банков"])

if st.sidebar.button("Обновить данные"):
    st.cache_data.clear()
    st.rerun()

# --- Page: Рабочий стол ---
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

# --- Page: Новый клиент ---
elif page == "Новый клиент":
    # Layout: Header + File Upload
    nc_c1, nc_c2 = st.columns([3, 1])
    with nc_c1:
        st.title("👤 Новый Клиент")
    with nc_c2:
        # Mini uploader - MULTIPLE FILES
        new_client_uploads = st.file_uploader("Загрузить документы", label_visibility="collapsed", accept_multiple_files=True)
        
    # Header Info - Status & Loan Type
    st.subheader("Основная информация")
    c1, c2, c3 = st.columns(3)
    fio = c1.text_input("ФИО")
    
    # Handle upload immediately if FIO exists
    if new_client_uploads:
        if fio:
            folder_name = f"{fio}_{datetime.now().strftime('%Y-%m-%d')}"
            with st.spinner(f"⏳ Загрузка {len(new_client_uploads)} файлов..."):
                # Ensure folder exists once
                create_yandex_folder(folder_name) 
                
                success_count = 0
                for uploaded_file in new_client_uploads:
                    if upload_to_yandex(uploaded_file, folder_name, uploaded_file.name):
                        success_count += 1
                
                if success_count == len(new_client_uploads):
                    st.toast(f"✅ Все файлы ({success_count}) загружены!", icon=None)
                else:
                    st.warning(f"⚠️ Загружено {success_count} из {len(new_client_uploads)} файлов.")
        else:
            st.warning("⚠️ Введите ФИО, чтобы загрузить файлы.")

    status = c2.selectbox("Статус", ["Новый", "В работе", "Одобрен", "Сделка", "Отказ"], index=None, placeholder="Выберите статус...")
    loan_type = c3.selectbox("Тип заявки", ["Ипотека", "Залог"], index=None, placeholder="Выберите тип...")
    
    c4, c5, c6 = st.columns(3)
    with c4:
        credit_sum = formatted_number_input("Требуемая сумма кредита", "credit_sum_input")
    
    with c5:
        op_cols = st.columns([0.85, 0.15])
        with op_cols[0]:
            obj_price = formatted_number_input("Стоимость объекта", "obj_price_input")
        op_cols[1].markdown("<br>", unsafe_allow_html=True)
        op_cols[1].link_button("🧮", "https://www.cian.ru/kalkulator-nedvizhimosti/", help="Калькулятор недвижимости")
        
    first_pay = 0.0
    if loan_type == "Ипотека":
        with c6:
            first_pay = formatted_number_input("Первоначальный взнос", "first_pay_input")
            
    # LTV and CIAN Report Row
    # LTV left, CIAN right (same row)
    ltv_val = 0.0
    if obj_price > 0:
        ltv_val = (credit_sum / obj_price) * 100
        
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    with r2_c1:
        st.text_input("КЗ (Коэффициент Залога)", value=f"{ltv_val:.1f}%", disabled=True)
    with r2_c2:
        cian_report_link = st.text_input("Отчет об оценке ЦИАН")
    
    # Pledge Logic
    # Inline: Is Pledged? | Bank | Amount
    p_c1, p_c2, p_c3 = st.columns([1, 1, 1])
    
    with p_c1:
        is_pledged_val = st.radio("Объект сейчас в залоге?", ["Да", "Нет"], horizontal=True, index=None)
    is_pledged = is_pledged_val == "Да"
    
    pledge_bank = ""
    pledge_amount = 0.0
    
    if is_pledged:
        with p_c2:
            pledge_bank = st.text_input("Где заложен (Банк)")
        with p_c3:
            pledge_amount = formatted_number_input("Сумма текущего долга", "pledge_amount_input")
    
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["Личные данные", "Финансы", "Залог"])
    
    with tab1:
        min_date = datetime(1930, 1, 1).date()
        max_date = datetime.now().date()
        
        # Row 1: Gender, DOB, Birth Place
        pd_r1_1, pd_r1_2, pd_r1_3 = st.columns(3)
        gender = pd_r1_1.radio("Пол", ["Мужской", "Женский"], horizontal=True, index=None)
        dob = pd_r1_2.date_input("Дата рождения", min_value=min_date, max_value=max_date, value=None)
        birth_place = pd_r1_3.text_input("Место рождения")
        
        # Row 2: Phone, Email
        pd_r2_1, pd_r2_2 = st.columns(2)
        with pd_r2_1:
            phone = formatted_phone_input("Телефон", "phone_input")
        with pd_r2_2:
            em_c1, em_c2 = st.columns([2, 1])
            email_user = em_c1.text_input("Email")
            email_domain = em_c2.selectbox("Домен", ["@gmail.com", "@ya.ru", "@mail.ru", "Вручную"], label_visibility="hidden", index=None, placeholder="@...")
            
            if email_domain and email_domain != "Вручную":
                email = email_user + email_domain
            else:
                email = email_user
        
        # Row 3: Marital Status, Children, Marriage Contract
        pd_r3_1, pd_r3_2, pd_r3_3 = st.columns(3)
        family = pd_r3_1.selectbox("Семейное положение", ["Холост/Не замужем", "Женат/Замужем", "Разведен(а)", "Вдовец/Вдова"], index=None, placeholder="Выберите...")
        children_count = pd_r3_2.number_input("Кол-во несовершеннолетних детей", 0, 10, 0)
        marriage_contract = pd_r3_3.radio("Наличие брачного договора / нотариального согласия", ["Брачный контракт", "Нотариальное согласие", "Нет"], horizontal=True, index=None)
        
        children_dates = []
        if children_count > 0:
            st.caption("Даты рождения детей:")
            cols = st.columns(min(children_count, 4))
            for i in range(children_count):
                with cols[i % 4]:
                    d = st.date_input(f"Ребенок {i+1}", min_value=datetime(2000,1,1).date(), max_value=max_date, key=f"child_{i}", value=None)
                    children_dates.append(str(d) if d else "")
        
        st.divider()
        st.subheader("Паспорт")
        p1, p2, p3, p4 = st.columns(4)
        pass_ser = p1.text_input("Серия")
        pass_num = p2.text_input("Номер")
        pass_code = p3.text_input("Код подразделения")
        pass_date = p4.date_input("Дата выдачи", min_value=datetime(1990, 1, 1).date(), max_value=max_date, value=None)
        
        pass_issued = st.text_input("Кем выдан")
        
        st.subheader("Адрес регистрации")
        a1, a2, a3, a4 = st.columns([1, 0.2, 1, 1])
        addr_index = a1.text_input("Индекс")
        a2.markdown("<div style='padding-top: 28px;'><a href='https://xn--80a1acny.ru.com/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
        addr_region = a3.text_input("Регион")
        addr_city = a4.text_input("Город")
        
        a5, a6, a7, a8, a9 = st.columns(5)
        addr_street = a5.text_input("Улица")
        addr_house = a6.text_input("Дом")
        addr_korpus = a7.text_input("Корпус")
        addr_structure = a8.text_input("Строение")
        addr_flat = a9.text_input("Квартира")
        
        st.divider()
        d1, d2 = st.columns(2)
        snils = d1.text_input("СНИЛС")
        
        with d2:
            inn_cols = st.columns([0.85, 0.15])
            inn = inn_cols[0].text_input("ИНН")
            inn_cols[1].markdown("<br>", unsafe_allow_html=True) # Spacer to align with input
            inn_cols[1].link_button("🔍", "https://service.nalog.ru/inn.do", help="Узнать/Проверить ИНН")
        
    with tab2:
        st.subheader("Работа")
        
        jr1_1, jr1_2 = st.columns(2)
        job_type = jr1_1.selectbox("Тип занятости", ["Найм", "ИП", "Собственник бизнеса", "Самозанятый", "Пенсионер"], index=None, placeholder="Выберите...")
        job_official_val = jr1_2.radio("Официально трудоустроен", ["Да", "Нет"], horizontal=True, index=None)
        job_official = job_official_val == "Да"
        
        if job_type and job_type != "Не работаю":
            # Compact fields: 4 cols per row
            jr1_1, jr1_2, jr1_3, jr1_4 = st.columns(4)
            job_company = jr1_1.text_input("Название компании")
            job_industry = jr1_2.text_input("Сфера деятельности")
            
            with jr1_3:
                inn_c1, inn_c2 = st.columns([4, 1])
                job_inn = inn_c1.text_input("ИНН Компании")
                inn_c2.markdown("<div style='padding-top: 28px;'><a href='https://www.rusprofile.ru/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
                
            job_date = jr1_4.date_input("Дата основания компании", min_value=min_date, max_value=max_date, value=None)
            
            jr2_1, jr2_2, jr2_3, jr2_4 = st.columns(4)
            job_position = jr2_1.text_input("Должность")
            with jr2_2:
                job_income = formatted_number_input("Доход", "job_income_input")
            job_start_date = jr2_3.date_input("Дата трудоустройства", min_value=min_date, max_value=max_date, value=None)
            
            # Calculate experience
            if job_start_date:
                today = datetime.now().date()
                delta = relativedelta(today, job_start_date)
                exp_str = f"{delta.years} лет {delta.months} мес."
            else:
                exp_str = ""
            
            jr2_4.text_input("Текущий стаж", value=exp_str, disabled=True)
            
            jr3_1, jr3_2 = st.columns(2)
            job_ceo = jr3_1.text_input("ФИО Гендиректора")
            with jr3_2:
                job_phone = formatted_phone_input("Рабочий телефон", "job_phone_input")
        else:
            # Defaults for no job
            job_company = ""
            job_industry = ""
            job_inn = ""
            job_date = None
            job_ceo = ""
            job_phone = ""
            job_position = ""
            job_income = 0
            job_start_date = None
            exp_str = ""
        
        st.subheader("Финансы")
        
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            loan_term_years = formatted_number_input("Срок кредита (лет)", "loan_term_input")
        
        loan_term_months = loan_term_years * 12
        with f2:
            st.text_input("Срок в месяцах", value=str(loan_term_months), disabled=True)
        
        has_coborrower_val = f3.radio("Будет ли созаемщик?", ["Да", "Нет"], horizontal=True, index=None)
        has_coborrower = has_coborrower_val == "Да"
        
        # Layout: Debts | Mos Comment | Mos Link | FSSP Comment | FSSP Link | Block Comment | Block Link
        f3_cols = st.columns([3, 2, 1.2, 2, 1.2, 2, 1.2])
        
        with f3_cols[0]:
            current_debts = formatted_number_input("Текущие платежи по кредитам", "current_debts_input")
            
        with f3_cols[1]:
            mosgorsud_comment = st.text_input("МосГорСуд")
        with f3_cols[2]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://www.mos-gorsud.ru/search?_cb=1764799069.0607' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>⚖️</a></div>", unsafe_allow_html=True)

        with f3_cols[3]:
            fssp_comment = st.text_input("ФССП")
        with f3_cols[4]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://fssp.gov.ru/' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>👮‍♂️</a></div>", unsafe_allow_html=True)

        with f3_cols[5]:
            block_comment = st.text_input("Блок Счета")
        with f3_cols[6]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://service.nalog.ru/bi.html' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>🚫</a></div>", unsafe_allow_html=True)
        
        assets_list = st.multiselect("Доп. активы", ["Машина", "Квартира", "Дом с ЗУ", "Коммерция", "Другое"])
        assets_str = ", ".join(assets_list)
        if "Другое" in assets_list:
            other_asset = st.text_input("Укажите другое имущество")
            assets_str += f" ({other_asset})"
        

        
    with tab3:
        st.subheader("Объект")
        
        o_row1_1, o_row1_2, o_row1_3 = st.columns(3)
        obj_type = o_row1_1.selectbox("Тип объекта", ["Квартира", "Дом", "Земельный участок", "Коммерция", "Комната", "Апартаменты", "Таунхаус"], index=None, placeholder="Выберите...")
        
        own_doc_type = o_row1_2.selectbox("Правоустановка", [
            "Договор купли-продажи", 
            "Договор дарения", 
            "Наследство", 
            "Приватизация", 
            "ДДУ", 
            "Договор мены",
            "Договор ренты",
            "Договор уступки права требования",
            "Справка ЖСК о полной выплате пая",
            "Решение суда",
            "Другое"
        ], index=None, placeholder="Выберите...")
        
        gift_donor_consent = "Нет"
        gift_donor_registered = "Нет"
        gift_donor_deregister = "Нет"
        
        if own_doc_type == "Другое":
            own_doc_type = o_row1_2.text_input("Впишите документ")
        elif own_doc_type == "Договор дарения":
            st.info("Дополнительные вопросы по дарению:")
            g1, g2 = st.columns(2)
            gift_donor_consent = g1.radio("Есть ли согласие дарителя?", ["Да", "Нет"], horizontal=True, index=None)
            gift_donor_registered = g2.radio("Прописан ли даритель?", ["Да", "Нет"], horizontal=True, index=None)
            if gift_donor_registered == "Да":
                gift_donor_deregister = st.radio("Готов ли он выписаться?", ["Да", "Нет"], horizontal=True, index=None)
            
        obj_date = o_row1_3.date_input("Дата правоустановки", min_value=min_date, max_value=max_date, value=None)
        
        o1, o2, o3, o4, o5 = st.columns(5)
        with o1:
            obj_area = formatted_number_input("Площадь (м2)", "obj_area_input", allow_float=True)
        with o2:
            obj_floor = formatted_number_input("Этаж", "obj_floor_input")
        with o3:
            obj_total_floors = formatted_number_input("Этажность", "obj_total_floors_input")
        with o4:
            obj_walls = st.selectbox("Материал стен", ["Кирпич", "Панель", "Монолит", "Блоки", "Дерево", "Смешанные"], index=None, placeholder="Выберите...")
        with o5:
            obj_renovation_val = st.radio("Реновация", ["Да", "Нет"], horizontal=True, index=None)
        obj_renovation = "Да" if obj_renovation_val == "Да" else "Нет"
        
        st.subheader("Адрес объекта")
        copy_addr_val = st.radio("Совпадает с адресом регистрации", ["Да", "Нет"], horizontal=True, index=None)
        copy_addr = copy_addr_val == "Да"
        
        if copy_addr:
            # Fields hidden, will copy on save
            st.info("Адрес объекта будет скопирован из адреса регистрации.")
            obj_index = ""
            obj_region = ""
            obj_city = ""
            obj_street = ""
            obj_house = ""
            obj_korpus = ""
            obj_structure = ""
            obj_flat = ""
        else:
            oa1, oa2, oa3, oa4 = st.columns([1, 0.2, 1, 1])
            obj_index = oa1.text_input("Индекс", key="obj_index")
            oa2.markdown("<div style='padding-top: 28px;'><a href='https://xn--80a1acny.ru.com/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
            obj_region = oa3.text_input("Регион", key="obj_region")
            obj_city = oa4.text_input("Город", key="obj_city")
            
            oa5, oa6, oa7, oa8, oa9 = st.columns(5)
            obj_street = oa5.text_input("Улица", key="obj_street")
            obj_house = oa6.text_input("Дом", key="obj_house")
            obj_korpus = oa7.text_input("Корпус", key="obj_korpus")
            obj_structure = oa8.text_input("Строение", key="obj_structure")
            obj_flat = oa9.text_input("Квартира", key="obj_flat")
            
        # cian_link removed from here as it moved to top
        
    submitted = st.button("Сохранить клиента")
        
    if submitted:
        if not fio:
            st.error("ФИО обязательно для заполнения!")
        else:
            # Copy address if needed
            if copy_addr:
                obj_index = addr_index
                obj_region = addr_region
                obj_city = addr_city
                obj_street = addr_street
                obj_house = addr_house
                obj_korpus = addr_korpus
                obj_structure = addr_structure
                obj_flat = addr_flat
                
            with st.spinner("Сохранение..."):
                folder_name = f"{fio}_{datetime.now().strftime('%Y-%m-%d')}"
                yandex_link = create_yandex_folder(folder_name)
                client_id = str(hash(fio + str(datetime.now())))
                
                data = {
                    "id": client_id,
                    "created_at": datetime.now().strftime('%Y-%m-%d'),
                    "status": status,
                    "loan_type": loan_type,
                    "fio": fio,
                    "gender": gender,
                    "dob": str(dob),
                    "birth_place": birth_place,
                    "phone": phone,
                    "email": email,
                    "passport_ser": pass_ser,
                    "passport_num": pass_num,
                    "passport_issued": pass_issued,
                    "passport_date": str(pass_date),
                    "kpp": pass_code,  # В базе это kpp, в форме pass_code - ОК
                    "inn": inn,
                    "snils": snils,
                    "addr_index": addr_index,
                    "addr_region": addr_region,
                    "addr_city": addr_city,
                    "addr_street": addr_street,
                    "addr_house": addr_house,
                    "addr_korpus": addr_korpus,
                    "addr_structure": addr_structure,
                    "addr_flat": addr_flat,
                    "obj_type": obj_type,
                    "obj_index": obj_index,
                    "obj_region": obj_region,
                    "obj_city": obj_city,
                    "obj_street": obj_street,
                    "obj_house": obj_house,
                    "obj_korpus": obj_korpus,
                    "obj_structure": obj_structure,
                    "obj_flat": obj_flat,
                    "obj_area": obj_area,
                    "obj_price": obj_price,
                    "obj_doc_type": own_doc_type,
                    "obj_date": str(obj_date),
                    "obj_renovation": obj_renovation, # Исправил переменную (была пустая строка "")
                    "obj_floor": obj_floor,
                    "obj_total_floors": obj_total_floors,
                    "obj_walls": obj_walls,
                    "gift_donor_consent": gift_donor_consent,
                    "gift_donor_registered": gift_donor_registered,
                    "gift_donor_deregister": gift_donor_deregister,
                    "cian_report_link": cian_report_link,
                    "family_status": family,
                    "marriage_contract": marriage_contract,
                    "children_count": children_count,
                    "children_dates": "; ".join(children_dates),
                    "job_type": job_type,
                    "job_official": job_official,
                    "job_company": job_company,
                    "job_sphere": job_industry,          # ИСПРАВЛЕНО (было job_sphere)
                    "job_found_date": str(job_date) if job_date else "", # ИСПРАВЛЕНО (было job_found_date)
                    "job_ceo": job_ceo,
                    "job_phone": job_phone,
                    "job_inn": job_inn,
                    "job_pos": job_position,             # ИСПРАВЛЕНО (было job_pos)
                    "job_income": job_income,
                    "job_start_date": str(job_start_date) if job_start_date else "",
                    "job_exp": exp_str,                  # ИСПРАВЛЕНО (было experience_str)
                    "credit_sum": credit_sum,
                    "loan_term": loan_term_years,
                    "has_coborrower": "Да" if has_coborrower else "Нет",
                    "first_pay": first_pay,
                    "current_debts": current_debts,
                    "assets": assets_str,
                    "is_pledged": "Да" if is_pledged else "Нет",
                    "pledge_bank": pledge_bank,
                    "pledge_amount": pledge_amount,
                    # Убрал дубликаты pledge_bank/amount
                    "yandex_link": yandex_link,
                    "mosgorsud_comment": mosgorsud_comment,
                    "fssp_comment": fssp_comment,
                    "block_comment": block_comment
                }
                db.save_client(data)
                st.success(f"Клиент {fio} сохранен!")

# --- Page: Карточка Клиента ---
elif page == "Карточка Клиента":
    st.title("🗂 Карточка Клиента")
    df = db.load_clients()
    if not df.empty:
        selected_name = st.selectbox("Выберите клиента", df["fio"].tolist())
        if selected_name:
            client = df[df["fio"] == selected_name].iloc[0]
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(client['fio'])
                st.write(f"**Статус:** {client['status']}")
                st.write(f"**Телефон:** {client['phone']}")
                st.write(f"**Яндекс Диск:** {client['yandex_link']}")
                with st.expander("Все данные"):
                    st.write(client.to_dict())
            
            with c2:
                st.write("Документы")
                # MULTIPLE FILES
                uploaded_files = st.file_uploader("Загрузить файл", accept_multiple_files=True, label_visibility="collapsed")
                
                if uploaded_files and st.button("Отправить в облако"):
                    # Check if yandex link is broken or missing
                    folder_name = f"{client['fio']}_{client['created_at']}"
                    
                    # If link is missing or broken, try to recreate folder
                    if not client['yandex_link'] or client['yandex_link'] == 'Ссылка не создана':
                        new_link = create_yandex_folder(folder_name)
                        # Update DB with new link
                        client_dict = client.to_dict()
                        client_dict['yandex_link'] = new_link
                        db.save_client(client_dict)
                        st.info("Папка на Яндекс Диске была пересоздана.")
                    
                    with st.spinner(f"⏳ Загрузка {len(uploaded_files)} файлов..."):
                        success_count = 0
                        for f in uploaded_files:
                            if upload_to_yandex(f, folder_name, f.name):
                                success_count += 1
                        
                        if success_count == len(uploaded_files):
                            st.success("✅ Все файлы загружены!")
                        else:
                            st.warning(f"⚠️ Загружено {success_count} из {len(uploaded_files)} файлов.")

# --- Page: База Банков ---
elif page == "База Банков":
    st.title("🏦 Банки")
    df = db.load_banks()
    st.dataframe(df)
    
    with st.form("new_bank"):
        b_name = st.text_input("Название")
        b_addr = st.text_input("Адрес")
        b_man = st.text_input("Менеджер")
        b_mail = st.text_input("Email")
        b_tel = st.text_input("Телефон")
        if st.form_submit_button("Добавить"):
            db.save_bank({
                "name": b_name, "address": b_addr, 
                "manager_fio": b_man, "manager_email": b_mail, 
                "manager_phone": b_tel
            })
            st.success("Банк добавлен")
            st.rerun()