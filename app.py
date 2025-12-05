import streamlit as st
import pandas as pd
import requests
import os
import database as db
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import time

# --- Configuration ---
YANDEX_TOKEN = "y0__xCF7vSyBhj0hTwg2oaewBUWNr9rdgvFpxw2k559OGkSU4o9VA"
FONTS_DIR = 'fonts'
TEMPLATES_DIR = 'templates'

# Helper function for formatted number input
def formatted_number_input(label, key, allow_float=False, value=None):
    if key not in st.session_state:
        if value is not None:
            # Initialize with provided value
            if allow_float:
                st.session_state[key] = f"{value:,}".replace(",", " ")
            else:
                st.session_state[key] = f"{int(value):,}".replace(",", " ")
        else:
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

def formatted_phone_input(label, key, value=None):
    if key not in st.session_state:
        if value:
            st.session_state[key] = value
        else:
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


# Helper function to parse FIO
def parse_fio(fio_str):
    """Splits FIO string into surname, name, patronymic."""
    if not fio_str:
        return "", "", ""
    parts = fio_str.strip().split()
    surname = parts[0] if len(parts) > 0 else ""
    name = parts[1] if len(parts) > 1 else ""
    patronymic = " ".join(parts[2:]) if len(parts) > 2 else ""
    return surname, name, patronymic


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

/* Adjust Page Margins */
.block-container {
    padding-top: 3rem !important; /* Reduced by ~50% (default is usually ~6rem) */
    padding-left: 10rem !important; /* Increased side margins (default is usually ~5rem) */
    padding-right: 10rem !important;
    max-width: 100% !important;
}
</style>
"""

# --- UI Layout ---
st.set_page_config(page_title="Mortgage CRM", layout="wide", page_icon="🏦")
st.markdown(hide_uploader_text, unsafe_allow_html=True) # ПРИМЕНЯЕМ СТИЛИ

st.title("СОКОЛ")

# --- MIGRATION: Auto-parse FIO for existing clients ---
# This runs once per rerun, but we can optimize to run only if needed.
# For simplicity, we check if any client has empty surname but present FIO.
if 'migration_done' not in st.session_state:
    migration_df = db.load_clients()
    if not migration_df.empty and 'fio' in migration_df.columns:
        changed = False
        for index, row in migration_df.iterrows():
            # Check if surname is missing but FIO exists
            if pd.notna(row['fio']) and row['fio'] and (pd.isna(row.get('surname')) or row['surname'] == ""):
                s, n, p = parse_fio(str(row['fio']))
                migration_df.at[index, 'surname'] = s
                migration_df.at[index, 'name'] = n
                migration_df.at[index, 'patronymic'] = p
                changed = True
        
        if changed:
            db.save_all_clients(migration_df)
            st.toast("✅ База данных обновлена: ФИО разделены на части.")
    
    st.session_state['migration_done'] = True

# --- Top Navigation ---
# Use radio for navigation to allow programmatic switching via session state
if "page" not in st.session_state:
    st.session_state.page = "Новый клиент"

def navigate_to(page):
    st.session_state.page = page

# Top Menu
pages = ["Новый клиент", "Карточка Клиента", "База Клиентов", "База Банков"]
if st.session_state.page not in pages:
    st.session_state.page = "Новый клиент"

current_index = pages.index(st.session_state.page)

selected_page = st.radio(
    "Меню", 
    pages, 
    horizontal=True,
    label_visibility="collapsed",
    index=current_index
)

if selected_page != st.session_state.page:
    st.session_state.page = selected_page
    st.rerun()

# Helper function to render the client form (for both new and edit)
def render_client_form(client_data=None, key_prefix=""):
    # Default values for new client
    default_fio = client_data.get('fio') or '' if client_data else ''
    default_status = client_data.get('status', None) if client_data else None
    default_loan_type = client_data.get('loan_type', None) if client_data else None
    default_credit_sum = client_data.get('credit_sum', 0) if client_data else 0
    default_obj_price = client_data.get('obj_price', 0) if client_data else 0
    default_first_pay = client_data.get('first_pay', 0) if client_data else 0
    default_cian_report_link = client_data.get('cian_report_link', '') if client_data else ''
    default_is_pledged_val = "Да" if client_data and client_data.get('is_pledged') else "Нет"
    default_pledge_bank = client_data.get('pledge_bank', '') if client_data else ''
    default_pledge_amount = client_data.get('pledge_amount', 0) if client_data else 0
    
    default_gender = client_data.get('gender', None) if client_data else None
    default_dob = pd.to_datetime(client_data['dob']).date() if client_data and client_data.get('dob') else None
    default_birth_place = client_data.get('birth_place') or '' if client_data else ''
    default_phone = client_data.get('phone') or '' if client_data else ''
    default_email = client_data.get('email') or '' if client_data else ''
    default_family = client_data.get('family_status', None) if client_data else None
    default_children_count = client_data.get('children_count', 0) if client_data else 0
    default_marriage_contract = client_data.get('marriage_contract', None) if client_data else None
    default_children_dates = client_data.get('children_dates', '').split(', ') if client_data and client_data.get('children_dates') else []

    default_pass_ser = client_data.get('passport_ser', '') if client_data else ''
    default_pass_num = client_data.get('passport_num', '') if client_data else ''
    default_pass_code = client_data.get('kpp', '') if client_data else ''
    default_pass_date = pd.to_datetime(client_data['passport_date']).date() if client_data and client_data.get('passport_date') else None
    default_pass_issued = client_data.get('passport_issued', '') if client_data else ''

    default_addr_index = client_data.get('addr_index', '') if client_data else ''
    default_addr_region = client_data.get('addr_region', '') if client_data else ''
    default_addr_city = client_data.get('addr_city', '') if client_data else ''
    default_addr_street = client_data.get('addr_street', '') if client_data else ''
    default_addr_house = client_data.get('addr_house', '') if client_data else ''
    default_addr_korpus = client_data.get('addr_korpus', '') if client_data else ''
    default_addr_structure = client_data.get('addr_structure', '') if client_data else ''
    default_addr_flat = client_data.get('addr_flat', '') if client_data else ''

    default_snils = client_data.get('snils', '') if client_data else ''
    default_inn = client_data.get('inn', '') if client_data else ''

    default_job_type = client_data.get('job_type', None) if client_data else None
    default_job_official_val = "Да" if client_data and client_data.get('job_official') else "Нет"
    default_job_company = client_data.get('job_company', '') if client_data else ''
    default_job_sphere = client_data.get('job_sphere', '') if client_data else ''
    default_job_inn = client_data.get('job_inn', '') if client_data else ''
    default_job_found_date = pd.to_datetime(client_data['job_found_date']).date() if client_data and client_data.get('job_found_date') else None
    default_job_pos = client_data.get('job_pos', '') if client_data else ''
    default_job_income = client_data.get('job_income', 0) if client_data else 0
    default_job_start_date = pd.to_datetime(client_data['job_start_date']).date() if client_data and client_data.get('job_start_date') else None
    default_job_ceo = client_data.get('job_ceo', '') if client_data else ''
    default_job_phone = client_data.get('job_phone', '') if client_data else ''

    default_loan_term = client_data.get('loan_term', 0) if client_data else 0
    default_has_coborrower_val = "Да" if client_data and client_data.get('has_coborrower') else "Нет"
    default_current_debts = client_data.get('current_debts', 0) if client_data else 0
    default_mosgorsud_comment = client_data.get('mosgorsud_comment', '') if client_data else ''
    default_fssp_comment = client_data.get('fssp_comment', '') if client_data else ''
    default_block_comment = client_data.get('block_comment', '') if client_data else ''
    default_assets = str(client_data.get('assets', '')).split(', ') if client_data and client_data.get('assets') and str(client_data.get('assets')) != 'nan' else []

    default_obj_type = client_data.get('obj_type', None) if client_data else None
    default_obj_doc_type = client_data.get('obj_doc_type', None) if client_data else None
    default_obj_date = pd.to_datetime(client_data['obj_date']).date() if client_data and client_data.get('obj_date') else None
    default_obj_area = client_data.get('obj_area', 0.0) if client_data else 0.0
    default_obj_floor = client_data.get('obj_floor', 0) if client_data else 0
    default_obj_total_floors = client_data.get('obj_total_floors', 0) if client_data else 0
    default_obj_walls = client_data.get('obj_walls', None) if client_data else None
    default_obj_renovation_val = "Да" if client_data and client_data.get('obj_renovation') == "Да" else "Нет"
    
    default_gift_donor_consent = client_data.get('gift_donor_consent', None) if client_data else None
    default_gift_donor_registered = client_data.get('gift_donor_registered', None) if client_data else None
    default_gift_donor_deregister = client_data.get('gift_donor_deregister', None) if client_data else None

    default_obj_index = client_data.get('obj_index', '') if client_data else ''
    default_obj_region = client_data.get('obj_region', '') if client_data else ''
    default_obj_city = client_data.get('obj_city', '') if client_data else ''
    default_obj_street = client_data.get('obj_street', '') if client_data else ''
    default_obj_house = client_data.get('obj_house', '') if client_data else ''
    default_obj_korpus = client_data.get('obj_korpus', '') if client_data else ''
    default_obj_structure = client_data.get('obj_structure', '') if client_data else ''
    default_obj_flat = client_data.get('obj_flat', '') if client_data else ''
    
    # Determine if obj address should be copied
    copy_addr_val = "Нет"
    if client_data:
        # If any obj_addr field is different from reg_addr, then it's not copied
        if not (client_data.get('obj_index') == client_data.get('addr_index') and
                client_data.get('obj_region') == client_data.get('addr_region') and
                client_data.get('obj_city') == client_data.get('addr_city') and
                client_data.get('obj_street') == client_data.get('addr_street') and
                client_data.get('obj_house') == client_data.get('addr_house') and
                client_data.get('obj_korpus') == client_data.get('addr_korpus') and
                client_data.get('obj_structure') == client_data.get('addr_structure') and
                client_data.get('obj_flat') == client_data.get('addr_flat')):
            copy_addr_val = "Нет"
        else:
            copy_addr_val = "Да"
    
    c1, c2, c3 = st.columns([2, 1, 1])
    fio = c1.text_input("ФИО", value=default_fio, key=f"{key_prefix}fio")
    status = c2.selectbox("Статус", ["Новый", "В работе", "Одобрен", "Сделка", "Отказ", "Архив"], index=["Новый", "В работе", "Одобрен", "Сделка", "Отказ", "Архив"].index(default_status) if default_status else None, placeholder="Выберите статус...", key=f"{key_prefix}status")
    loan_type = c3.selectbox("Тип заявки", ["Ипотека", "Залог"], index=["Ипотека", "Залог"].index(default_loan_type) if default_loan_type else None, placeholder="Выберите тип...", key=f"{key_prefix}loan_type")
    
    c4, c5, c6 = st.columns(3)
    with c4:
        credit_sum = formatted_number_input("Требуемая сумма кредита", f"{key_prefix}credit_sum_input", value=default_credit_sum)
    
    with c5:
        op_cols = st.columns([0.85, 0.15])
        with op_cols[0]:
            obj_price = formatted_number_input("Стоимость объекта", f"{key_prefix}obj_price_input", value=default_obj_price)
        op_cols[1].markdown("<br>", unsafe_allow_html=True)
        op_cols[1].link_button("🧮", "https://www.cian.ru/kalkulator-nedvizhimosti/", help="Калькулятор недвижимости")
        
    first_pay = 0.0
    if loan_type == "Ипотека":
        with c6:
            first_pay = formatted_number_input("Первоначальный взнос", f"{key_prefix}first_pay_input", value=default_first_pay)
            
    # LTV and CIAN Report Row
    # LTV left, CIAN right (same row)
    ltv_val = 0.0
    if obj_price > 0:
        ltv_val = (credit_sum / obj_price) * 100
        
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    with r2_c1:
        st.text_input("КЗ (Коэффициент Залога)", value=f"{ltv_val:.1f}%", disabled=True, key=f"{key_prefix}ltv_display")
    with r2_c2:
        cian_report_link = st.text_input("Отчет об оценке ЦИАН", value=default_cian_report_link, key=f"{key_prefix}cian_report_link")
    
    # Pledge Logic
    # Inline: Is Pledged? | Bank | Amount
    p_c1, p_c2, p_c3 = st.columns([1, 1, 1])
    
    with p_c1:
        is_pledged_val = st.radio("Объект сейчас в залоге?", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_is_pledged_val) if default_is_pledged_val else None, key=f"{key_prefix}is_pledged_val")
    is_pledged = is_pledged_val == "Да"
    
    pledge_bank = ""
    pledge_amount = 0.0
    
    if is_pledged:
        with p_c2:
            pledge_bank = st.text_input("Где заложен (Банк)", value=default_pledge_bank, key=f"{key_prefix}pledge_bank")
        with p_c3:
            pledge_amount = formatted_number_input("Сумма текущего долга", f"{key_prefix}pledge_amount_input", value=default_pledge_amount)
    
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["Личные данные", "Финансы", "Залог"])
    
    with tab1:
        min_date = datetime(1930, 1, 1).date()
        max_date = datetime.now().date()
        
        # Row 1: Gender, DOB, Birth Place
        pd_r1_1, pd_r1_2, pd_r1_3 = st.columns(3)
        gender = pd_r1_1.radio("Пол", ["Мужской", "Женский"], horizontal=True, index=["Мужской", "Женский"].index(default_gender) if default_gender else None, key=f"{key_prefix}gender")
        dob = pd_r1_2.date_input("Дата рождения", min_value=min_date, max_value=max_date, value=default_dob, key=f"{key_prefix}dob")
        birth_place = pd_r1_3.text_input("Место рождения", value=default_birth_place, key=f"{key_prefix}birth_place")
        
        # Row 2: Phone, Email
        pd_r2_1, pd_r2_2 = st.columns(2)
        with pd_r2_1:

            phone = formatted_phone_input("Телефон", f"{key_prefix}phone_input", value=default_phone)
        with pd_r2_2:
            em_c1, em_c2 = st.columns([2, 1])
            email_user_part = default_email.split('@')[0] if '@' in default_email else default_email
            email_domain_part = '@' + default_email.split('@')[1] if '@' in default_email else None
            
            email_user = em_c1.text_input("Email", value=email_user_part, key=f"{key_prefix}email_user")
            
            domain_options = ["@gmail.com", "@ya.ru", "@mail.ru", "Вручную"]
            default_domain_index = domain_options.index(email_domain_part) if email_domain_part in domain_options else (len(domain_options) - 1 if email_domain_part else None)
            
            email_domain = em_c2.selectbox("Домен", domain_options, label_visibility="hidden", index=default_domain_index, placeholder="@...", key=f"{key_prefix}email_domain")
            
            if email_domain and email_domain != "Вручную":
                email = email_user + email_domain
            else:
                email = email_user
        
        # Row 3: Marital Status, Children, Marriage Contract
        pd_r3_1, pd_r3_2, pd_r3_3 = st.columns(3)
        family = pd_r3_1.selectbox("Семейное положение", ["Холост/Не замужем", "Женат/Замужем", "Разведен(а)", "Вдовец/Вдова"], index=["Холост/Не замужем", "Женат/Замужем", "Разведен(a)", "Вдовец/Вдова"].index(default_family) if default_family else None, placeholder="Выберите...", key=f"{key_prefix}family")
        children_count = pd_r3_2.number_input("Кол-во несовершеннолетних детей", 0, 10, value=default_children_count, key=f"{key_prefix}children_count")
        marriage_contract = pd_r3_3.radio("Наличие брачного договора / нотариального согласия", ["Брачный контракт", "Нотариальное согласие", "Нет"], horizontal=True, index=["Брачный контракт", "Нотариальное согласие", "Нет"].index(default_marriage_contract) if default_marriage_contract else None, key=f"{key_prefix}marriage_contract")
        
        children_dates = []
        if children_count > 0:
            st.caption("Даты рождения детей:")
            cols = st.columns(min(children_count, 4))
            for i in range(children_count):
                default_child_date = pd.to_datetime(default_children_dates[i]).date() if i < len(default_children_dates) and default_children_dates[i] else None
                d = st.date_input(f"Ребенок {i+1}", min_value=datetime(2000,1,1).date(), max_value=max_date, key=f"{key_prefix}child_{i}", value=default_child_date)
                children_dates.append(str(d) if d else "")
        
        st.divider()
        st.subheader("Паспорт")
        p1, p2, p3, p4 = st.columns(4)
        pass_ser = p1.text_input("Серия", value=default_pass_ser, key=f"{key_prefix}pass_ser")
        pass_num = p2.text_input("Номер", value=default_pass_num, key=f"{key_prefix}pass_num")
        pass_code = p3.text_input("Код подразделения", value=default_pass_code, key=f"{key_prefix}pass_code")
        pass_date = p4.date_input("Дата выдачи", min_value=datetime(1990, 1, 1).date(), max_value=max_date, value=default_pass_date, key=f"{key_prefix}pass_date")
        
        pass_issued = st.text_input("Кем выдан", value=default_pass_issued, key=f"{key_prefix}pass_issued")
        
        st.subheader("Адрес регистрации")
        a1, a2, a3, a4 = st.columns([1, 0.2, 1, 1])
        addr_index = a1.text_input("Индекс", value=default_addr_index, key=f"{key_prefix}addr_index")
        a2.markdown("<div style='padding-top: 28px;'><a href='https://xn--80a1acny.ru.com/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
        addr_region = a3.text_input("Регион", value=default_addr_region, key=f"{key_prefix}addr_region")
        addr_city = a4.text_input("Город", value=default_addr_city, key=f"{key_prefix}addr_city")
        
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
        
    # Parse FIO for return data
    surname, name, patronymic = parse_fio(fio)
    
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

    data = {
        "status": status,
        "loan_type": loan_type,
        "fio": fio,
        "surname": surname,
        "name": name,
        "patronymic": patronymic,
        "gender": gender,
        "dob": str(dob),
        "birth_place": birth_place,
        "phone": phone,
        "email": email,
        "passport_ser": pass_ser,
        "passport_num": pass_num,
        "passport_issued": pass_issued,
        "passport_date": str(pass_date),
        "kpp": pass_code,
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
        "obj_renovation": obj_renovation,
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
        "job_sphere": job_industry,
        "job_found_date": str(job_date) if job_date else "",
        "job_ceo": job_ceo,
        "job_phone": job_phone,
        "job_inn": job_inn,
        "job_pos": job_position,
        "job_income": job_income,
        "job_start_date": str(job_start_date) if job_start_date else "",
        "job_exp": exp_str,
        "credit_sum": credit_sum,
        "loan_term": loan_term_years,
        "has_coborrower": "Да" if has_coborrower else "Нет",
        "first_pay": first_pay,
        "current_debts": current_debts,
        "assets": assets_str,
        "is_pledged": "Да" if is_pledged else "Нет",
        "pledge_bank": pledge_bank,
        "pledge_amount": pledge_amount,
        "mosgorsud_comment": mosgorsud_comment,
        "fssp_comment": fssp_comment,
        "block_comment": block_comment
    }
    
    return data

# --- Page: Новый клиент (Editor) ---
if selected_page == "Новый клиент":
    # Check if we are in "Edit Mode"
    edit_client_id = st.session_state.get("editing_client_id")
    edit_client_data = None
    
    if edit_client_id:
        st.header("✏️ Редактирование клиента")
        # Load fresh data from DB to ensure we have latest
        all_clients = db.load_clients()
        if not all_clients.empty and edit_client_id in all_clients['id'].values:
            edit_client_data = all_clients[all_clients['id'] == edit_client_id].iloc[0].to_dict()
        else:
            st.error("Клиент не найден!")
            st.session_state.editing_client_id = None
            st.rerun()
            
        if st.button("❌ Отмена редактирования"):
            st.session_state.editing_client_id = None
            st.rerun()
            
        form_data = render_client_form(client_data=edit_client_data, key_prefix="edit_")
        
        if st.button("💾 Сохранить изменения"):
            with st.spinner("Сохранение..."):
                # Update data
                data = form_data.copy()
                data["id"] = edit_client_data["id"]
                data["created_at"] = edit_client_data["created_at"]
                data["yandex_link"] = edit_client_data.get("yandex_link", "")
                
                # Parse FIO if changed
                if data["fio"] != edit_client_data["fio"]:
                    surname, name, patronymic = parse_fio(data["fio"])
                    data["surname"] = surname
                    data["name"] = name
                    data["patronymic"] = patronymic
                else:
                    data["surname"] = edit_client_data.get("surname", "")
                    data["name"] = edit_client_data.get("name", "")
                    data["patronymic"] = edit_client_data.get("patronymic", "")

                # Convert date objects to strings
                for key, val in data.items():
                    if isinstance(val, (date, datetime)):
                        data[key] = str(val)
                
                db.save_client(data)
                st.success(f"Данные клиента {data['fio']} обновлены!")
                st.session_state.editing_client_id = None # Exit edit mode
                time.sleep(1)
                st.rerun()
                
    else:
        st.header("🆕 Новый клиент")
        form_data = render_client_form(key_prefix="new_")
        
        if st.button("✨ Создать клиента"):
            if not form_data["fio"]:
                st.error("ФИО обязательно для заполнения!")
            else:
                with st.spinner("Сохранение..."):
                    # Generate ID and basic fields
                    client_id = str(hash(form_data["fio"] + str(datetime.now())))
                    
                    # Parse FIO
                    surname, name, patronymic = parse_fio(form_data["fio"])
                    
                    # Create Yandex folder
                    folder_name = f"{form_data['fio']}_{datetime.now().strftime('%Y-%m-%d')}"
                    yandex_link = create_yandex_folder(folder_name)
                    
                    # Prepare data for saving
                    data = form_data.copy()
                    data["id"] = client_id
                    data["created_at"] = datetime.now().strftime('%Y-%m-%d')
                    data["surname"] = surname
                    data["name"] = name
                    data["patronymic"] = patronymic
                    data["yandex_link"] = yandex_link
                    
                    # Convert date objects to strings
                    for key, val in data.items():
                        if isinstance(val, (date, datetime)):
                            data[key] = str(val)
                            
                    db.save_client(data)
                    st.success(f"Клиент {form_data['fio']} сохранен!")

# --- Page: База Клиентов ---
elif selected_page == "База Клиентов":
    st.title("📂 База Клиентов")
    
    df = db.load_clients()
    
    if df.empty:
        st.info("База данных пуста. Добавьте первого клиента!")
    else:
        # Pre-process dates for editor
        date_cols = ["created_at", "dob", "passport_date", "obj_date", "job_found_date", "job_start_date"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # Replace NaT with None (Streamlit requires None for empty dates, not NaT)
                df[col] = df[col].astype(object).where(df[col].notnull(), None)

        # Force all other columns to string if they are not numeric/date, to avoid float inference for empty cols
        numeric_cols = ["credit_sum", "obj_price", "first_pay", "current_debts", "pledge_amount", "job_income", "obj_area", "obj_floor", "obj_total_floors", "children_count", "loan_term"]
        
        for col in df.columns:
            if col not in date_cols and col not in numeric_cols and col != "Select":
                # Treat as text
                val = df[col].astype(str).replace("nan", "").replace("None", "")
                df[col] = val.apply(lambda x: x[:-2] if x.endswith(".0") else x)
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.multiselect("Фильтр по статусу", options=df["status"].unique() if not df.empty else [])
        with col2:
            search = st.text_input("Поиск по ФИО")
            
        filtered_df = df.copy()
        if status_filter:
            filtered_df = filtered_df[filtered_df["status"].isin(status_filter)]
        if search:
            filtered_df = filtered_df[filtered_df["fio"].str.contains(search, case=False, na=False)]
            
        # Data Editor
        edited_df = st.data_editor(
            filtered_df,
            num_rows="dynamic",
            disabled=["id", "created_at", "surname", "name", "patronymic"],
            key="client_editor_main",
            use_container_width=True,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "created_at": st.column_config.DateColumn("Создан", format="YYYY-MM-DD", disabled=True),
                "status": st.column_config.SelectboxColumn("Статус", options=["Новый", "В работе", "Одобрен", "Сделка", "Отказ", "Архив"]),
                "loan_type": st.column_config.SelectboxColumn("Тип", options=["Ипотека", "Залог"]),
                "fio": st.column_config.TextColumn("ФИО"),
                "credit_sum": st.column_config.NumberColumn("Сумма", format="%d"),
                "phone": st.column_config.TextColumn("Телефон"),
            }
        )
        
        if st.button("💾 Сохранить изменения таблицы"):
            with st.spinner("Сохранение..."):
                current_db = db.load_clients()
                
                # Handle Deletions
                original_ids = set(filtered_df['id'].dropna())
                current_ids = set(edited_df['id'].dropna())
                deleted_ids = original_ids - current_ids
                
                if deleted_ids:
                    current_db = current_db[~current_db['id'].isin(deleted_ids)]
                    
                # Handle Updates
                for index, row in edited_df.iterrows():
                    row_id = row.get('id')
                    fio = str(row.get('fio', ''))
                    surname, name, patronymic = parse_fio(fio)
                    
                    if pd.isna(row_id) or row_id == "":
                        new_id = str(hash(fio + str(datetime.now())))
                        new_row = row.to_dict()
                        new_row['id'] = new_id
                        new_row['surname'] = surname
                        new_row['name'] = name
                        new_row['patronymic'] = patronymic
                        if pd.isna(new_row.get('created_at')):
                            new_row['created_at'] = datetime.now().strftime('%Y-%m-%d')
                        current_db = pd.concat([current_db, pd.DataFrame([new_row])], ignore_index=True)
                    else:
                        mask = current_db['id'] == row_id
                        if mask.any():
                            for col in edited_df.columns:
                                current_db.loc[mask, col] = row[col]
                            current_db.loc[mask, 'surname'] = surname
                            current_db.loc[mask, 'name'] = name
                            current_db.loc[mask, 'patronymic'] = patronymic
                
                db.save_all_clients(current_db)
                st.success("✅ Изменения сохранены!")
                st.rerun()

# --- Page: Карточка Клиента ---
elif selected_page == "Карточка Клиента":
    st.title("🗂 Карточка Клиента")
    df = db.load_clients()
    if not df.empty:
        selected_name = st.selectbox("Выберите клиента", df["fio"].tolist())
        if selected_name:
            client = df[df["fio"] == selected_name].iloc[0].to_dict()
            
            st.subheader(f"Редактирование: {client['fio']}")
            st.write(f"**Яндекс Диск:** {client.get('yandex_link', 'Нет ссылки')}")
            
            # EDIT BUTTON
            if st.button("✏️ Редактировать клиента"):
                st.session_state.editing_client_id = client['id']
                st.session_state.page = "Новый клиент" # Switch tab
                st.rerun()
            
            with st.expander("Все данные", expanded=True):
                st.json(client)
            
            st.divider()
            st.write("Документы")
            uploaded_files = st.file_uploader("Загрузить файл", accept_multiple_files=True, label_visibility="collapsed", key="card_uploader")
            
            if uploaded_files and st.button("Отправить в облако", key="card_upload_btn"):
                folder_name = f"{client['fio']}_{client['created_at']}"
                if not client.get('yandex_link') or client.get('yandex_link') == 'Ссылка не создана':
                    new_link = create_yandex_folder(folder_name)
                    client_dict = client.copy()
                    client_dict['yandex_link'] = new_link
                    db.save_client(client_dict)
                    st.info("Папка на Яндекс Диске была пересоздана.")
                    client['yandex_link'] = new_link
                
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
elif selected_page == "База Банков":
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