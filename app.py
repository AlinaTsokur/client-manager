import streamlit as st
import pandas as pd
import requests
import os
import database as db
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import time
from streamlit_searchbox import st_searchbox
from docxtpl import DocxTemplate
import tempfile
import uuid
import subprocess
import sys
import json
import io
import urllib.parse
# --- Configuration ---
YANDEX_TOKEN = "y0__xCF7vSyBhj0hTwg2oaewBUWNr9rdgvFpxw2k559OGkSU4o9VA"
FONTS_DIR = 'fonts'
TEMPLATES_DIR = 'templates'

# Options
status_options = ["Новый", "В работе", "Сделка", "Отказ", "Архив"]
loan_type_options = ["Ипотека", "Кредит под залог", "Потреб", "Рефинансирование"]

# Helper function for formatted number input
def formatted_number_input(label, key, allow_float=False, value=None):
    if key not in st.session_state:
        if value is not None and (isinstance(value, (int, float)) and value > 0):
            # Initialize with provided value
            if allow_float:
                st.session_state[key] = f"{value:,}".replace(",", " ")
            else:
                st.session_state[key] = f"{int(value):,}".replace(",", " ")
        else:
            st.session_state[key] = ""
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

# --- LibreOffice Conversion Function ---
def convert_docx_to_pdf_libreoffice(source_docx, output_dir):
    """
    Конвертирует docx в pdf используя LibreOffice в headless режиме.
    Требует установленного LibreOffice.
    """
    # Попытка найти путь к LibreOffice в зависимости от ОС
    if sys.platform == 'darwin':  # macOS
        libreoffice_path = '/Applications/LibreOffice.app/Contents/MacOS/soffice'
    elif sys.platform == 'win32': # Windows
        libreoffice_path = r'C:\Program Files\LibreOffice\program\soffice.exe'
    else: # Linux
        libreoffice_path = 'libreoffice'

    # Команда запуска
    args = [
        libreoffice_path,
        '--headless',
        '--convert-to', 'pdf',
        '--outdir', output_dir,
        source_docx
    ]
    
    # Запуск процесса
    try:
        subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        st.error("❌ LibreOffice не найден! Установите LibreOffice или проверьте путь в коде.")
        return False
    except subprocess.CalledProcessError as e:
        st.error(f"❌ Ошибка конвертации LibreOffice: {e}")
        return False
    except Exception as e:
        st.error(f"❌ Неизвестная ошибка: {e}")
        return False

def clean_int_str(val):
    """Cleans string values that might be read as floats from Excel (e.g. '123.0' -> '123')."""
    s = str(val)
    if s == 'nan' or s == 'None': return ""
    if s.endswith(".0"): return s[:-2]
    return s

def safe_int(val, default=0):
    try:
        if pd.isna(val) or str(val).lower() == 'nan':
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

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



def format_phone_string(phone_str):
    """Formats a phone string to +7 XXX XXX XX XX"""
    if not phone_str:
        return ""
    
    # Remove all non-digits
    clean = ''.join(c for c in str(phone_str) if c.isdigit())
    
    # Handle empty
    if not clean:
        return ""
        
    # Сначала нормализуем длину и префикс
    if len(clean) == 11:
        if clean.startswith('8'):
            clean = '7' + clean[1:]
        elif not clean.startswith('7'):
            # Если 11 цифр и не начинается на 7 или 8 (редкий кейс, но все же)
            pass 
    elif len(clean) == 10:
        clean = '7' + clean
    
    # Formatting
    # Expected: 79998887766 -> +7 999 888 77 66
    if len(clean) >= 11 and clean.startswith('7'):
        # Take first 11 only
        digits = clean[:11]
        return f"+7 {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"
    
    # Fallback for weird numbers (like short ones or other countries if any)
    # But try to add + if missing
    return phone_str if phone_str else ""

def transliterate(text):
    """Simple transliteration for folder names."""
    if not isinstance(text, str):
        return str(text)
        
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        ' ': '_', '-': '_', '.': '', ',': ''
    }
    
    text = text.strip().lower()
    res = []
    for char in text:
        if char in mapping:
            res.append(mapping[char])
        elif char.isalnum():
            res.append(char)
            
    # Join and strip underscores from ends (in case of leading/trailing weird chars)
    return "".join(res).strip('_')


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

def calculate_age(dob):
    if not dob:
        return None
    try:
        if isinstance(dob, str):
            dob = pd.to_datetime(dob).date()
        elif isinstance(dob, datetime):
            dob = dob.date()
        return relativedelta(datetime.now().date(), dob).years
    except:
        return None


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

def get_client_folder_name(client):
    """
    Robustly determine client folder name.
    1. Try to resolve via Yandex Public API if link exists (Best for consistency).
    2. Fallback to constructing from FIO + Created Date.
    """
    # 1. Try public API
    link = client.get('yandex_link')
    if link and link != 'Ссылка не создана' and 'yadi.sk' in link:
        try:
            api_url = 'https://cloud-api.yandex.net/v1/disk/public/resources'
            params = {'public_key': link}
            # Public resources don't technically require Auth, but safer to include if we have token, 
            # though sometimes public API with token behaves differently. Let's try without token first as it's a public link.
            resp = requests.get(api_url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                name = data.get('name')
                if name:
                    return name
        except Exception as e:
            print(f"Error resolving Yandex link: {e}")

    # 2. Fallback Logic
    c_created = client.get('created_at', '')
    
    # Handle various date formats/types
    if not c_created or str(c_created) == 'nan' or str(c_created) == 'None':
         # Last resort: If we really can't find date, we might create a new folder.
         # But usually created_at should be there. If it's broken, we use today?
         # Or we rely on FIO only? No, FIO is not unique enough.
         # Let's use Today to at least ensure we have a valid suffix.
         c_created = datetime.now().strftime('%Y-%m-%d')
    elif isinstance(c_created, (date, datetime)):
         c_created = c_created.strftime('%Y-%m-%d')
    
    # Clean up formatting
    folder_name = f"{client.get('fio', 'Client')}_{c_created}".strip('_')
    return folder_name

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
# Sync with query params for persistence across refreshes

# 1. Initialize session state from query params if not set
if "page" not in st.session_state:
    query_params = st.query_params
    query_page = query_params.get("page")
    if query_page and query_page in ["Новый клиент", "Карточка Клиента", "База Клиентов", "База Банков"]:
        st.session_state.page = query_page
    else:
        st.session_state.page = "Новый клиент"

def navigate_to(page):
    st.session_state.page = page
    st.query_params["page"] = page

# Top Menu
pages = ["Новый клиент", "Карточка Клиента", "База Клиентов", "База Банков"]
if st.session_state.page not in pages:
    st.session_state.page = "Новый клиент"

current_index = pages.index(st.session_state.page)

# Update query param initially (if just started)
if st.query_params.get("page") != st.session_state.page:
    st.query_params["page"] = st.session_state.page

selected_page = st.radio(
    "Меню", 
    pages, 
    horizontal=True,
    label_visibility="collapsed",
    index=current_index
)

if selected_page != st.session_state.page:
    st.session_state.page = selected_page
    st.query_params["page"] = selected_page
    st.rerun()

# Helper function to render the client form (for both new and edit)
def render_client_form(client_data=None, key_prefix=""):
    # Default values for new client
    default_fio = client_data.get('fio') or '' if client_data else ''
    status_options = ["Новый", "В работе", "Одобрен", "Сделка", "Отказ", "Архив"]
    default_status = client_data.get('status', None) if client_data else None
    loan_type_options = ["Ипотека", "Залог"]
    default_loan_type = client_data.get('loan_type', None) if client_data else None
    default_credit_sum = client_data.get('credit_sum', 0) if client_data else 0
    default_obj_price = client_data.get('obj_price', 0) if client_data else 0
    default_first_pay = client_data.get('first_pay', 0) if client_data else 0
    default_cian_report_link = str(client_data.get('cian_report_link', '')) if client_data and client_data.get('cian_report_link') and str(client_data.get('cian_report_link')) != 'nan' else ''
    is_pledged_options = ["Да", "Нет"]
    default_is_pledged_val = "Да" if client_data and client_data.get('is_pledged') else "Нет"
    default_pledge_bank = str(client_data.get('pledge_bank', '')) if client_data and client_data.get('pledge_bank') and str(client_data.get('pledge_bank')) != 'nan' else ''
    default_pledge_amount = client_data.get('pledge_amount', 0) if client_data else 0
    
    gender_options = ["Мужской", "Женский"]
    default_gender = client_data.get('gender', None) if client_data else None
    default_dob = pd.to_datetime(client_data['dob']).date() if client_data and pd.notna(client_data.get('dob')) else None
    default_birth_place = clean_int_str(client_data.get('birth_place')) if client_data else ''
    default_phone = clean_int_str(client_data.get('phone')) if client_data else ''
    default_email = str(client_data.get('email', '')) if client_data and client_data.get('email') and str(client_data.get('email')) != 'nan' else ''
    family_options = ["Холост/Не замужем", "Женат/Замужем", "Разведен(а)", "Вдовец/Вдова"]
    default_family = client_data.get('family_status', None) if client_data else None
    default_children_count = safe_int(client_data.get('children_count'), 0) if client_data else 0
    marriage_contract_options = ["Брачный контракт", "Нотариальное согласие", "Нет"]
    default_marriage_contract = client_data.get('marriage_contract', None) if client_data else None
    default_children_dates = str(client_data.get('children_dates', '')).split('; ') if client_data and client_data.get('children_dates') and str(client_data.get('children_dates')) != 'nan' else []

    default_pass_ser = clean_int_str(client_data.get('passport_ser')) if client_data else ''
    default_pass_num = clean_int_str(client_data.get('passport_num')) if client_data else ''
    default_pass_code = clean_int_str(client_data.get('kpp')) if client_data else ''
    default_pass_date = pd.to_datetime(client_data['passport_date']).date() if client_data and pd.notna(client_data.get('passport_date')) else None
    default_pass_issued = str(client_data.get('passport_issued', '')) if client_data and client_data.get('passport_issued') and str(client_data.get('passport_issued')) != 'nan' else ''

    default_addr_index = clean_int_str(client_data.get('addr_index')) if client_data else ''
    default_addr_region = str(client_data.get('addr_region', '')) if client_data and client_data.get('addr_region') and str(client_data.get('addr_region')) != 'nan' else ''
    default_addr_city = str(client_data.get('addr_city', '')) if client_data and client_data.get('addr_city') and str(client_data.get('addr_city')) != 'nan' else ''
    default_addr_street = clean_int_str(client_data.get('addr_street')) if client_data else ''
    default_addr_house = clean_int_str(client_data.get('addr_house')) if client_data else ''
    default_addr_korpus = clean_int_str(client_data.get('addr_korpus')) if client_data else ''
    default_addr_structure = clean_int_str(client_data.get('addr_structure')) if client_data else ''
    default_addr_flat = clean_int_str(client_data.get('addr_flat')) if client_data else ''

    default_snils = clean_int_str(client_data.get('snils')) if client_data else ''
    default_inn = clean_int_str(client_data.get('inn')) if client_data else ''

    job_type_options = ["Найм", "ИП", "Собственник бизнеса", "Самозанятый", "Пенсионер", "Не работаю"]
    default_job_type = client_data.get('job_type', None) if client_data else None
    job_official_options = ["Да", "Нет"]
    default_job_official_val = "Да" if client_data and client_data.get('job_official') else "Нет"
    default_job_company = str(client_data.get('job_company', '')) if client_data and client_data.get('job_company') and str(client_data.get('job_company')) != 'nan' else ''
    default_job_sphere = str(client_data.get('job_sphere', '')) if client_data and client_data.get('job_sphere') and str(client_data.get('job_sphere')) != 'nan' else ''
    default_job_inn = clean_int_str(client_data.get('job_inn')) if client_data else ''
    default_job_found_date = pd.to_datetime(client_data['job_found_date']).date() if client_data and pd.notna(client_data.get('job_found_date')) else None
    default_job_pos = str(client_data.get('job_pos', '')) if client_data and client_data.get('job_pos') and str(client_data.get('job_pos')) != 'nan' else ''
    default_job_income = client_data.get('job_income', 0) if client_data else 0
    default_job_start_date = pd.to_datetime(client_data['job_start_date']).date() if client_data and pd.notna(client_data.get('job_start_date')) and str(client_data.get('job_start_date')) != 'None' and str(client_data.get('job_start_date')) != 'nan' else None
    default_job_ceo = str(client_data.get('job_ceo', '')) if client_data and client_data.get('job_ceo') and str(client_data.get('job_ceo')) != 'nan' else ''
    default_job_phone = clean_int_str(client_data.get('job_phone')) if client_data else ''

    default_loan_term = safe_int(client_data.get('loan_term'), 0) if client_data else 0
    has_coborrower_options = ["Да", "Нет"]
    default_has_coborrower_val = "Да" if client_data and client_data.get('has_coborrower') else "Нет"
    default_current_debts = client_data.get('current_debts', 0) if client_data else 0
    default_mosgorsud_comment = str(client_data.get('mosgorsud_comment', '')) if client_data and client_data.get('mosgorsud_comment') and str(client_data.get('mosgorsud_comment')) != 'nan' else ''
    default_fssp_comment = str(client_data.get('fssp_comment', '')) if client_data and client_data.get('fssp_comment') and str(client_data.get('fssp_comment')) != 'nan' else ''
    default_block_comment = str(client_data.get('block_comment', '')) if client_data and client_data.get('block_comment') and str(client_data.get('block_comment')) != 'nan' else ''
    default_assets = str(client_data.get('assets', '')).split(', ') if client_data and client_data.get('assets') and str(client_data.get('assets')) != 'nan' else []

    obj_type_options = ["Квартира", "Дом", "Земельный участок", "Коммерция", "Комната", "Апартаменты", "Таунхаус"]
    default_obj_type = client_data.get('obj_type', None) if client_data else None
    obj_doc_type_options = [
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
    ]
    default_obj_doc_type = client_data.get('obj_doc_type', None) if client_data else None
    default_obj_date = pd.to_datetime(client_data['obj_date']).date() if client_data and pd.notna(client_data.get('obj_date')) and str(client_data.get('obj_date')) != 'None' and str(client_data.get('obj_date')) != 'nan' else None
    default_obj_area = client_data.get('obj_area', 0.0) if client_data else 0.0
    default_obj_floor = safe_int(client_data.get('obj_floor'), 0) if client_data else 0
    default_obj_total_floors = safe_int(client_data.get('obj_total_floors'), 0) if client_data else 0
    obj_walls_options = ["Кирпич", "Панель", "Монолит", "Блоки", "Дерево", "Смешанные"]
    default_obj_walls = client_data.get('obj_walls', None) if client_data else None
    obj_renovation_options = ["Да", "Нет"]
    default_obj_renovation_val = "Да" if client_data and client_data.get('obj_renovation') == "Да" else "Нет"
    
    gift_consent_options = ["Да", "Нет"]
    default_gift_donor_consent = client_data.get('gift_donor_consent', None) if client_data else None
    gift_registered_options = ["Да", "Нет"]
    default_gift_donor_registered = client_data.get('gift_donor_registered', None) if client_data else None
    gift_deregister_options = ["Да", "Нет"]
    default_gift_donor_deregister = client_data.get('gift_donor_deregister', None) if client_data else None

    default_obj_index = clean_int_str(client_data.get('obj_index')) if client_data else ''
    default_obj_region = str(client_data.get('obj_region', '')) if client_data and client_data.get('obj_region') and str(client_data.get('obj_region')) != 'nan' else ''
    default_obj_city = str(client_data.get('obj_city', '')) if client_data and client_data.get('obj_city') and str(client_data.get('obj_city')) != 'nan' else ''
    default_obj_street = clean_int_str(client_data.get('obj_street')) if client_data else ''
    default_obj_house = clean_int_str(client_data.get('obj_house')) if client_data else ''
    default_obj_korpus = clean_int_str(client_data.get('obj_korpus')) if client_data else ''
    default_obj_structure = clean_int_str(client_data.get('obj_structure')) if client_data else ''
    default_obj_flat = clean_int_str(client_data.get('obj_flat')) if client_data else ''
    
    # Determine if obj address should be copied
    copy_addr_val = "Нет"
    if client_data:
        # If any obj_addr field is different from reg_addr, then it's not copied
        if not (clean_int_str(client_data.get('obj_index')) == clean_int_str(client_data.get('addr_index')) and
                str(client_data.get('obj_region', '')) == str(client_data.get('addr_region', '')) and
                str(client_data.get('obj_city', '')) == str(client_data.get('addr_city', '')) and
                clean_int_str(client_data.get('obj_street')) == clean_int_str(client_data.get('addr_street')) and
                clean_int_str(client_data.get('obj_house')) == clean_int_str(client_data.get('addr_house')) and
                clean_int_str(client_data.get('obj_korpus')) == clean_int_str(client_data.get('addr_korpus')) and
                clean_int_str(client_data.get('obj_structure')) == clean_int_str(client_data.get('addr_structure')) and
                clean_int_str(client_data.get('obj_flat')) == clean_int_str(client_data.get('addr_flat'))):
            copy_addr_val = "Нет"
        else:
            copy_addr_val = "Да"
    
    # Row 1: FIO, Status, Loan Type, Credit Sum
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    fio = c1.text_input("ФИО", value=default_fio, key=f"{key_prefix}fio")
    status = c2.selectbox("Статус", status_options, index=status_options.index(default_status) if default_status in status_options else None, placeholder="Выберите статус...", key=f"{key_prefix}status")
    loan_type = c3.selectbox("Тип заявки", loan_type_options, index=loan_type_options.index(default_loan_type) if default_loan_type in loan_type_options else None, placeholder="Выберите тип...", key=f"{key_prefix}loan_type")
    
    with c4:
        credit_sum = formatted_number_input("Требуемая сумма кредита", f"{key_prefix}credit_sum_input", value=default_credit_sum)

    # Row 2: Object Price (with button), LTV, CIAN Report, First Pay
    # We need to get obj_price first to calculate LTV, but LTV is displayed in the same row.
    # Streamlit runs top-to-bottom. We can render inputs, get their values, and then calculate LTV.
    # But LTV display depends on obj_price and credit_sum which are inputs.
    # In Streamlit, values from current run are available.
    
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns([1.2, 1, 1, 1])
    
    with r2_c1:
        op_cols = st.columns([0.85, 0.15])
        with op_cols[0]:
            obj_price = formatted_number_input("Стоимость объекта", f"{key_prefix}obj_price_input", value=default_obj_price)
        op_cols[1].markdown("<div style='padding-top: 28px;'><a href='https://www.cian.ru/kalkulator-nedvizhimosti/' target='_blank' style='text-decoration: none; font-size: 20px;'>🧮</a></div>", unsafe_allow_html=True)

    ltv_val = 0.0
    # print(f"DEBUG: credit_sum={credit_sum}, obj_price={obj_price}")
    if obj_price and obj_price > 0:
        ltv_val = (credit_sum / obj_price) * 100
    # print(f"DEBUG: ltv_val={ltv_val}")
        
    with r2_c2:
        st.text_input("КЗ (Коэффициент Залога)", value=f"{ltv_val:.1f}%", disabled=True)
        
    with r2_c3:
        cian_report_link = st.text_input("Отчет об оценке ЦИАН", value=default_cian_report_link, key=f"{key_prefix}cian_report_link")
        
    first_pay = 0.0
    if loan_type == "Ипотека":
        with r2_c4:
            first_pay = formatted_number_input("Первоначальный взнос", f"{key_prefix}first_pay_input", value=default_first_pay)
    
    # Pledge Logic
    # Inline: Is Pledged? | Bank | Amount
    p_c1, p_c2, p_c3 = st.columns([1, 1, 1])
    
    with p_c1:
        is_pledged_val = st.radio("Объект сейчас в залоге?", is_pledged_options, horizontal=True, index=is_pledged_options.index(default_is_pledged_val) if default_is_pledged_val in is_pledged_options else None, key=f"{key_prefix}is_pledged_val")
    is_pledged = is_pledged_val == "Да"
    
    pledge_bank = ""
    pledge_amount = 0.0
    
    if is_pledged:
        with p_c2:
            pledge_bank = st.text_input("Где заложен (Банк)", value=default_pledge_bank, key=f"{key_prefix}pledge_bank")
        with p_c3:
            pledge_amount = formatted_number_input("Сумма текущего долга", f"{key_prefix}pledge_amount_input", value=default_pledge_amount)
    

    
    tab1, tab2, tab3 = st.tabs(["Личные данные", "Финансы", "Залог"])
    
    with tab1:
        min_date = datetime(1930, 1, 1).date()
        max_date = datetime.now().date()
        
        # Row 1: Gender, DOB, Age, Birth Place
        pd_r1_1, pd_r1_2, pd_r1_3, pd_r1_4 = st.columns([1, 1.2, 0.4, 2])
        gender = pd_r1_1.radio("Пол", gender_options, horizontal=True, index=gender_options.index(default_gender) if default_gender in gender_options else None, key=f"{key_prefix}gender")
        dob = pd_r1_2.date_input("Дата рождения", min_value=min_date, max_value=max_date, value=default_dob, key=f"{key_prefix}dob", format="DD.MM.YYYY")
        
        # Calculate Age
        age_val = ""
        if dob:
            age_val = relativedelta(datetime.now().date(), dob).years
        
        pd_r1_3.text_input("Возраст", value=str(age_val), disabled=True)
        birth_place = pd_r1_4.text_input("Место рождения", value=default_birth_place, key=f"{key_prefix}birth_place")
        
        # Row 2: Phone, Email
        # Row 2: Phone, Email, SNILS, INN
        pd_r2_1, pd_r2_2, pd_r2_3, pd_r2_4, pd_r2_5 = st.columns([1, 2, 0.7, 0.7, 0.2])
        with pd_r2_1:
            phone = formatted_phone_input("Телефон", f"{key_prefix}phone_input", value=default_phone)
        with pd_r2_2:
            em_c1, em_c2 = st.columns([1.5, 1])
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
        
        snils = pd_r2_3.text_input("СНИЛС", value=default_snils, key=f"{key_prefix}snils")
        inn = pd_r2_4.text_input("ИНН", value=default_inn, key=f"{key_prefix}inn")
        pd_r2_5.markdown("<div style='padding-top: 28px;'><a href='https://service.nalog.ru/inn.do' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
        
        # Row 3: Marital Status, Children, Marriage Contract
        pd_r3_1, pd_r3_2, pd_r3_3 = st.columns([0.9, 1.1, 2.2])
        family = pd_r3_1.selectbox("Семейное положение", family_options, index=family_options.index(default_family) if default_family in family_options else None, placeholder="Выберите...", key=f"{key_prefix}family")
        children_count = pd_r3_2.number_input("Кол-во несовершеннолетних детей", 0, 10, value=int(default_children_count) if default_children_count else 0, key=f"{key_prefix}children_count")
        marriage_contract = pd_r3_3.radio("Наличие брачного договора / нотариального согласия", marriage_contract_options, horizontal=True, index=marriage_contract_options.index(default_marriage_contract) if default_marriage_contract in marriage_contract_options else None, key=f"{key_prefix}marriage_contract")
        
        children_dates = []
        if children_count > 0:
            st.caption("Даты рождения детей:")
            cols = st.columns(5) # Initialize first row
            for i in range(children_count):
                if i > 0 and i % 5 == 0:
                    cols = st.columns(5) # New row every 5 items
                
                with cols[i % 5]:
                    default_child_date = pd.to_datetime(default_children_dates[i]).date() if i < len(default_children_dates) and default_children_dates[i] else None
                    d = st.date_input(f"Ребенок {i+1}", min_value=datetime(2000,1,1).date(), max_value=max_date, key=f"{key_prefix}child_{i}", value=default_child_date, format="DD.MM.YYYY")
                    children_dates.append(str(d) if d else "")
        
        st.subheader("Паспорт")
        p1, p2, p3, p4, p5 = st.columns([1, 1, 1, 3, 1])
        pass_ser = p1.text_input("Серия", value=default_pass_ser, key=f"{key_prefix}pass_ser")
        pass_num = p2.text_input("Номер", value=default_pass_num, key=f"{key_prefix}pass_num")
        pass_code = p3.text_input("Код подразделения", value=default_pass_code, key=f"{key_prefix}pass_code")
        pass_issued = p4.text_input("Кем выдан", value=default_pass_issued, key=f"{key_prefix}pass_issued")
        pass_date = p5.date_input("Дата выдачи", min_value=datetime(1990, 1, 1).date(), max_value=max_date, value=default_pass_date, key=f"{key_prefix}pass_date", format="DD.MM.YYYY")
        
        st.subheader("Адрес регистрации")
        a1, a2, a3, a4 = st.columns([1, 0.2, 1, 1])
        addr_index = a1.text_input("Индекс", value=default_addr_index, key=f"{key_prefix}addr_index")
        a2.markdown("<div style='padding-top: 28px;'><a href='https://xn--80a1acny.ru.com/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
        addr_region = a3.text_input("Регион", value=default_addr_region, key=f"{key_prefix}addr_region")
        addr_city = a4.text_input("Город", value=default_addr_city, key=f"{key_prefix}addr_city")
        
        a5, a6, a7, a8, a9 = st.columns(5)
        addr_street = a5.text_input("Улица", value=default_addr_street, key=f"{key_prefix}addr_street")
        addr_house = a6.text_input("Дом", value=default_addr_house, key=f"{key_prefix}addr_house")
        addr_korpus = a7.text_input("Корпус", value=default_addr_korpus, key=f"{key_prefix}addr_korpus")
        addr_structure = a8.text_input("Строение", value=default_addr_structure, key=f"{key_prefix}addr_structure")
        addr_flat = a9.text_input("Квартира", value=default_addr_flat, key=f"{key_prefix}addr_flat")
        

        
    with tab2:
        st.subheader("Работа")
        
        jr1_1, jr1_2 = st.columns(2)
        job_type = jr1_1.selectbox("Тип занятости", ["Найм", "ИП", "Собственник бизнеса", "Самозанятый", "Пенсионер"], index=["Найм", "ИП", "Собственник бизнеса", "Самозанятый", "Пенсионер"].index(default_job_type) if default_job_type in ["Найм", "ИП", "Собственник бизнеса", "Самозанятый", "Пенсионер"] else None, placeholder="Выберите...", key=f"{key_prefix}job_type")
        job_official_val = jr1_2.radio("Официально трудоустроен", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_job_official_val) if default_job_official_val in ["Да", "Нет"] else None, key=f"{key_prefix}job_official_val")
        job_official = job_official_val == "Да"
        
        if job_type and job_type != "Не работаю":
            # Compact fields: 4 cols per row
            jr1_1, jr1_2, jr1_3, jr1_4 = st.columns(4)
            job_company = jr1_1.text_input("Название компании", value=default_job_company, key=f"{key_prefix}job_company")
            job_industry = jr1_2.text_input("Сфера деятельности", value=default_job_sphere, key=f"{key_prefix}job_industry")
            
            with jr1_3:
                inn_c1, inn_c2 = st.columns([4, 1])
                job_inn = inn_c1.text_input("ИНН Компании", value=default_job_inn, key=f"{key_prefix}job_inn")
                inn_c2.markdown("<div style='padding-top: 28px;'><a href='https://www.rusprofile.ru/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
                
            job_date = jr1_4.date_input("Дата основания компании", min_value=min_date, max_value=max_date, value=None, format="DD.MM.YYYY")
            
            jr2_1, jr2_2, jr2_3, jr2_4, jr2_5 = st.columns([1.2, 1.2, 1, 0.8, 0.8])
            job_position = jr2_1.text_input("Должность", value=default_job_pos, key=f"{key_prefix}job_pos")
            with jr2_2:
                inc_c1, inc_c2 = st.columns([0.85, 0.15])
                with inc_c1:
                    job_income = formatted_number_input("Доход", "job_income_input")
                
                # Dynamic calculator link
                calc_amount = int(credit_sum) if credit_sum else 10000000
                banki_url = f"https://www.banki.ru/services/calculators/credits/?amount={calc_amount}&periodNotation=20y&rate=28"
                inc_c2.markdown(f"<div style='padding-top: 28px;'><a href='{banki_url}' target='_blank' style='text-decoration: none; font-size: 20px;'>🧮</a></div>", unsafe_allow_html=True)
            job_start_date = jr2_3.date_input("Начало работы", min_value=min_date, max_value=max_date, value=None, format="DD.MM.YYYY")
            
            # Calculate experience
            if job_start_date:
                today = datetime.now().date()
                delta = relativedelta(today, job_start_date)
                exp_str = f"{delta.years} г. {delta.months} м."
            else:
                exp_str = ""
            
            # Calculate Total Experience
            total_exp_val = 0
            if isinstance(age_val, int):
                total_exp_val = max(0, age_val - 18)
            
            jr2_4.text_input("Тек. стаж", value=exp_str, disabled=True)
            jr2_5.text_input("Общ. стаж", value=str(total_exp_val), disabled=True)
            
            jr3_1, jr3_2 = st.columns(2)
            job_ceo = jr3_1.text_input("ФИО Гендиректора", value=default_job_ceo, key=f"{key_prefix}job_ceo")
            with jr3_2:
                job_phone = formatted_phone_input("Рабочий телефон", "job_phone_input")
        else:
            # Defaults for no job
            job_company = ""
            job_industry = ""
            job_inn = ""
            job_date = None
            job_position = ""
            job_income = 0
            job_start_date = None
            exp_str = ""
            total_exp_val = 0
            if isinstance(age_val, int):
                total_exp_val = max(0, age_val - 18)
            
            # Don't render inputs, just return empty values
            job_ceo = ""
            job_phone = ""
        
        st.subheader("Финансы")
        
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            loan_term_years = formatted_number_input("Срок кредита (лет)", "loan_term_input")
        
        loan_term_months = loan_term_years * 12
        with f2:
            st.text_input("Срок в месяцах", value=str(loan_term_months), disabled=True)
        
        has_coborrower_val = f3.radio("Будет ли созаемщик?", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_has_coborrower_val) if default_has_coborrower_val in ["Да", "Нет"] else None, key=f"{key_prefix}has_coborrower_val")
        has_coborrower = has_coborrower_val == "Да"
        
        # Layout: Debts | Mos Comment | Mos Link | FSSP Comment | FSSP Link | Block Comment | Block Link
        f3_cols = st.columns([3, 2, 1.2, 2, 1.2, 2, 1.2])
        
        with f3_cols[0]:
            current_debts = formatted_number_input("Текущие платежи по кредитам", "current_debts_input")
            
        with f3_cols[1]:
            mosgorsud_comment = st.text_input("МосГорСуд", value=default_mosgorsud_comment, key=f"{key_prefix}mosgorsud_comment")
        with f3_cols[2]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://www.mos-gorsud.ru/search?_cb=1764799069.0607' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>⚖️</a></div>", unsafe_allow_html=True)

        with f3_cols[3]:
            fssp_comment = st.text_input("ФССП", value=default_fssp_comment, key=f"{key_prefix}fssp_comment")
        with f3_cols[4]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://fssp.gov.ru/' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>👮‍♂️</a></div>", unsafe_allow_html=True)

        with f3_cols[5]:
            block_comment = st.text_input("Блок Счета", value=default_block_comment, key=f"{key_prefix}block_comment")
        with f3_cols[6]:
            st.markdown("<div style='padding-top: 28px;'><a href='https://service.nalog.ru/bi.html' target='_blank' style='text-decoration: none; font-size: 16px; color: white;'>🚫</a></div>", unsafe_allow_html=True)
        
        assets_list = st.multiselect("Доп. активы", ["Машина", "Квартира", "Дом с ЗУ", "Коммерция", "Другое"])
        assets_str = ", ".join(assets_list)
        if "Другое" in assets_list:
            # Try to find the component that isn't in the standard list
            standard_assets = ["Машина", "Квартира", "Дом с ЗУ", "Коммерция", "Другое"]
            other_val = ""
            for a in default_assets:
                if a not in standard_assets:
                    other_val = a
                    break
            other_asset = st.text_input("Укажите другое имущество", value=other_val)
            assets_str += f" ({other_asset})"
        

        
    with tab3:
        st.subheader("Объект")
        
        o_row1_1, o_row1_2, o_row1_3 = st.columns(3)
        obj_type = o_row1_1.selectbox("Тип объекта", ["Квартира", "Дом", "Земельный участок", "Коммерция", "Комната", "Апартаменты", "Таунхаус"], index=["Квартира", "Дом", "Земельный участок", "Коммерция", "Комната", "Апартаменты", "Таунхаус"].index(default_obj_type) if default_obj_type in ["Квартира", "Дом", "Земельный участок", "Коммерция", "Комната", "Апартаменты", "Таунхаус"] else None, placeholder="Выберите...", key=f"{key_prefix}obj_type")
        
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
        ], index=[
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
        ].index(default_obj_doc_type) if default_obj_doc_type in [
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
        ] else None, placeholder="Выберите...", key=f"{key_prefix}obj_doc_type")
        
        gift_donor_consent = "Нет"
        gift_donor_registered = "Нет"
        gift_donor_deregister = "Нет"
        
        if own_doc_type == "Другое":
            # If current doc type is not in list, use it as value
            custom_doc_val = default_obj_doc_type if default_obj_doc_type not in [
                "Договор купли-продажи", "Договор дарения", "Наследство", "Приватизация", "ДДУ", 
                "Договор мены", "Договор ренты", "Договор уступки права требования", 
                "Справка ЖСК о полной выплате пая", "Решение суда", "Другое", None
            ] else ""
            own_doc_type = o_row1_2.text_input("Впишите документ", value=custom_doc_val)
        elif own_doc_type == "Договор дарения":
            g1, g2, g3 = st.columns(3)
            gift_donor_consent = g1.radio("Есть ли согласие дарителя?", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_gift_donor_consent) if default_gift_donor_consent in ["Да", "Нет"] else None, key=f"{key_prefix}gift_donor_consent")
            gift_donor_registered = g2.radio("Прописан ли даритель?", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_gift_donor_registered) if default_gift_donor_registered in ["Да", "Нет"] else None, key=f"{key_prefix}gift_donor_registered")
            
            if gift_donor_registered == "Да":
                gift_donor_deregister = g3.radio("Готов ли он выписаться?", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_gift_donor_deregister) if default_gift_donor_deregister in ["Да", "Нет"] else None, key=f"{key_prefix}gift_donor_deregister")
            
        obj_date = o_row1_3.date_input("Дата правоустановки", min_value=min_date, max_value=max_date, value=default_obj_date, key=f"{key_prefix}obj_date", format="DD.MM.YYYY")
        
        o1, o2, o3, o4, o5 = st.columns(5)
        with o1:
            obj_area = formatted_number_input("Площадь (м2)", "obj_area_input", allow_float=True)
        with o2:
            obj_floor = formatted_number_input("Этаж", "obj_floor_input")
        with o3:
            obj_total_floors = formatted_number_input("Этажность", "obj_total_floors_input")
        with o4:
            obj_walls = st.selectbox("Материал стен", ["Кирпич", "Панель", "Монолит", "Блоки", "Дерево", "Смешанные"], index=["Кирпич", "Панель", "Монолит", "Блоки", "Дерево", "Смешанные"].index(default_obj_walls) if default_obj_walls in ["Кирпич", "Панель", "Монолит", "Блоки", "Дерево", "Смешанные"] else None, placeholder="Выберите...", key=f"{key_prefix}obj_walls")
        with o5:
            obj_renovation_val = st.radio("Реновация", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_obj_renovation_val) if default_obj_renovation_val in ["Да", "Нет"] else None, key=f"{key_prefix}obj_renovation_val")
        obj_renovation = "Да" if obj_renovation_val == "Да" else "Нет"
        
        st.subheader("Адрес объекта")
        copy_addr_val = st.radio("Совпадает с адресом регистрации", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(copy_addr_val) if copy_addr_val in ["Да", "Нет"] else None, key=f"{key_prefix}copy_addr_val")
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
            obj_index = oa1.text_input("Индекс", value=default_obj_index, key="obj_index")
            oa2.markdown("<div style='padding-top: 28px;'><a href='https://xn--80a1acny.ru.com/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
            obj_region = oa3.text_input("Регион", value=default_obj_region, key="obj_region")
            obj_city = oa4.text_input("Город", value=default_obj_city, key="obj_city")
            
            oa5, oa6, oa7, oa8, oa9 = st.columns(5)
            obj_street = oa5.text_input("Улица", value=default_obj_street, key="obj_street")
            obj_house = oa6.text_input("Дом", value=default_obj_house, key="obj_house")
            obj_korpus = oa7.text_input("Корпус", value=default_obj_korpus, key="obj_korpus")
            obj_structure = oa8.text_input("Строение", value=default_obj_structure, key="obj_structure")
            obj_flat = oa9.text_input("Квартира", value=default_obj_flat, key="obj_flat")
            
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
        "age": age_val,
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
        "total_exp": total_exp_val,
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
                    client_id = str(abs(hash(form_data["fio"] + str(datetime.now()))))
                    
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
        
    # Calculate Age for display
    if not df.empty and "dob" in df.columns:
        df["age"] = df["dob"].apply(calculate_age)
        # Calculate Total Exp for display
        df["total_exp"] = df["age"].apply(lambda x: max(0, x - 18) if isinstance(x, (int, float)) else 0)

    # --- Filters ---
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect("Фильтр по статусу", options=df["status"].unique() if not df.empty else [], placeholder="Выберите статус", label_visibility="collapsed")
        with col2:
            loan_type_filter = st.multiselect("Фильтр по типу", options=["Ипотека", "Залог"], placeholder="Выберите тип сделки", label_visibility="collapsed")
        with col3:
            search = st.text_input("Поиск по ФИО", placeholder="Введите ФИО", label_visibility="collapsed")
            
        filtered_df = df.copy()
        if status_filter:
            filtered_df = filtered_df[filtered_df["status"].isin(status_filter)]
        if loan_type_filter:
            filtered_df = filtered_df[filtered_df["loan_type"].isin(loan_type_filter)]
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
                "created_at": st.column_config.DateColumn("Создан", format="DD.MM.YYYY", disabled=True),
                "status": st.column_config.SelectboxColumn("Статус", options=status_options, required=True),
                # "manager": st.column_config.TextColumn("Менеджер"),
                "loan_type": st.column_config.SelectboxColumn("Тип", options=loan_type_options),
                "fio": st.column_config.TextColumn("ФИО"),
                "credit_sum": st.column_config.NumberColumn("Сумма", format="%d"),
                "phone": st.column_config.TextColumn("Телефон"),
                "dob": st.column_config.DateColumn("Дата рождения", format="DD.MM.YYYY"),
                "age": st.column_config.NumberColumn("Возраст"),
                "total_exp": st.column_config.NumberColumn("Общ. стаж"),
                "passport_date": st.column_config.DateColumn("Дата выдачи паспорта", format="DD.MM.YYYY"),
                "obj_date": st.column_config.DateColumn("Дата собственности", format="DD.MM.YYYY"),
                "job_found_date": st.column_config.DateColumn("Дата основания", format="DD.MM.YYYY"),
                "job_start_date": st.column_config.DateColumn("Дата начала работы", format="DD.MM.YYYY"),
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
                    # Ensure current_db IDs are strings for comparison
                    current_db['id'] = current_db['id'].astype(str)
                    # Also ensure deleted_ids are strings (they should be, but to be safe)
                    deleted_ids = set(str(uid) for uid in deleted_ids)
                    current_db = current_db[~current_db['id'].isin(deleted_ids)]
                    
                # Handle Updates
                for index, row in edited_df.iterrows():
                    # Recalculate age based on DOB (in case DOB was edited or Age is missing)
                    row_dob = row.get('dob')
                    new_age = calculate_age(row_dob)
                    new_total_exp = max(0, new_age - 18) if isinstance(new_age, int) else 0
                    
                    # Ensure ID is handled as string for consistent comparison
                    row_id = str(row.get('id')).split('.')[0] if pd.notnull(row.get('id')) and row.get('id') != '' else None
                    if row_id == "None" or row_id == "nan": 
                        row_id = None
                        
                    fio = str(row.get('fio', ''))
                    surname, name, patronymic = parse_fio(fio)
                    
                    row_exists = False
                    if row_id:
                        # Normalize DB IDs to string for check
                        current_db['id'] = current_db['id'].astype(str).str.replace(r'\.0$', '', regex=True)
                        if row_id in current_db['id'].values:
                            row_exists = True

                    if not row_exists:
                        # Add new row with basic fields
                        new_client_data = {
                            "id": str(row_id) if row_id else str(abs(hash(datetime.now()))),
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "fio": fio,
                            "surname": surname,
                            "name": name,
                            "patronymic": patronymic,
                            "status": row.get('status', 'Новый'),
                            "loan_type": row.get('loan_type', 'Ипотека'),
                            "phone": row.get('phone', ''),
                            "dob": str(row.get('dob')) if row.get('dob') else None,
                            "age": new_age,
                            "total_exp": new_total_exp,
                            "credit_sum": row.get('credit_sum', 0),
                            "email": row.get('email', '')
                        }
                        current_db = pd.concat([current_db, pd.DataFrame([new_client_data])], ignore_index=True)
                    else:
                        # Update existing row
                        curr_idx = current_db[current_db['id'] == row_id].index[0]
                        # Update fields from the edited dataframe
                        for col in edited_df.columns:
                            val = row[col]
                            # Handle dates
                            if isinstance(val, (date, datetime)):
                                val = str(val)
                            current_db.at[curr_idx, col] = val
                        
                        # Update derived fields
                        current_db.at[curr_idx, 'surname'] = surname
                        current_db.at[curr_idx, 'name'] = name
                        current_db.at[curr_idx, 'patronymic'] = patronymic
                        current_db.at[curr_idx, 'age'] = new_age
                        current_db.at[curr_idx, 'total_exp'] = new_total_exp
                
                db.save_all_clients(current_db)
                st.success("✅ Изменения сохранены!")
                st.rerun()

# --- Page: Карточка Клиента ---
elif selected_page == "Карточка Клиента":
    st.title("🗂 Карточка Клиента")
    df = db.load_clients()
    if not df.empty:
        c_sel, _ = st.columns([1, 2])
        with c_sel:
            # st_searchbox for autocomplete
            # st_searchbox for autocomplete
            all_clients_list = sorted([str(x) for x in df["fio"].unique().tolist() if x is not None and str(x) != 'nan'])
            
            def search_clients(searchterm: str):
                if not searchterm:
                    return []
                return [
                    name for name in all_clients_list
                    if str(name).lower().startswith(searchterm.lower())
                ]

            selected_name = st_searchbox(
                search_clients,
                key="client_searchbox",
                placeholder="Начните вводить ФИО...",
                label="Поиск клиента",
                style_overrides={"noOptionsMessage": {"display": "none"}}
            )
        if selected_name:
            client = df[df["fio"] == selected_name].iloc[0].to_dict()
            

            st.write(f"**Яндекс Диск:** {client.get('yandex_link', 'Нет ссылки')}")
            
            # EDIT BUTTON
            if st.button("✏️ Редактировать клиента"):
                st.session_state.editing_client_id = client['id']
                st.session_state.page = "Новый клиент" # Switch tab
                st.rerun()
            
            with st.expander("Все данные", expanded=False):
                st.json(client)
            
            st.write("Документы")
            uploaded_files = st.file_uploader("Загрузить файл", accept_multiple_files=True, label_visibility="collapsed", key="card_uploader")
            
            if uploaded_files and st.button("Отправить в облако", key="card_upload_btn"):
                folder_name = get_client_folder_name(client)
                
                success_count = 0
                with st.spinner(f"Загрузка {len(uploaded_files)} файлов на Яндекс.Диск (папка: {folder_name})..."):
                    for f in uploaded_files:
                        # Reset pointer just in case
                        f.seek(0)
                        if upload_to_yandex(f, folder_name, f.name):
                            success_count += 1
                
                if success_count == len(uploaded_files):
                    st.success(f"✅ Все файлы ({success_count}) успешно загружены в папку '{folder_name}'!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning(f"⚠️ Загружено {success_count} из {len(uploaded_files)} файлов. Проверьте ошибки.")

            st.divider()
            
            # --- Work with Banks Module (View Mode) ---
            with st.expander("🏦 Работа с банками", expanded=True):
                # Load banks
                banks_db = db.load_banks().to_dict('records')
                bank_names = [b['name'] for b in banks_db]
                
                # Parse existing interactions
                interactions_json = client.get('bank_interactions', '[]')
                try:
                    interactions = json.loads(interactions_json)
                    if not isinstance(interactions, list): interactions = []
                except:
                    interactions = []
                
                c_bank, c_act = st.columns([1, 2])
                selected_bank_name = c_bank.selectbox("Выберите банк", bank_names, index=None, placeholder="Выберите банк...", key="card_sel_bank")
                
                selected_bank = next((b for b in banks_db if b['name'] == selected_bank_name), None) if selected_bank_name else None
                
                if selected_bank:
                    manager_phone = str(selected_bank.get('manager_phone', '')).replace('nan', '')
                    import re
                    # Remove all non-digit characters
                    digits = re.sub(r'\D', '', manager_phone)
                    
                    # Fix Russian formatting 89... -> 79...
                    if len(digits) == 11 and digits.startswith('8'):
                        digits = '7' + digits[1:]
                    elif len(digits) == 10 and digits.startswith('9'):
                        digits = '7' + digits
                        
                    wa_url = f"https://wa.me/{digits}" if digits else ""
                    
                    lk_link = str(selected_bank.get('lk_link', '')).replace('nan', '').replace('None', '')
                    lk_display = f" | [Личный кабинет]({lk_link})" if lk_link else ""
                    
                    st.info(f"Менеджер: {selected_bank.get('manager_fio', '')} ([WhatsApp]({wa_url})){lk_display}" if wa_url else f"Менеджер: {selected_bank.get('manager_fio', '')}{lk_display}")
                    
                    # Templates
                    st.markdown("#### 📄 Документы")
                    # Use transliterated folder name
                    bank_folder_name = transliterate(selected_bank_name)
                    bank_tpl_dir = os.path.join(TEMPLATES_DIR, bank_folder_name)
                    common_tpl_dir = os.path.join(TEMPLATES_DIR, "common")
                    
                    # Check dirs
                    templates_found = []
                    if os.path.exists(bank_tpl_dir):
                        templates_found.extend([(f, os.path.join(bank_tpl_dir, f)) for f in os.listdir(bank_tpl_dir) if f.endswith('.docx') and not f.startswith('~$')])
                    if os.path.exists(common_tpl_dir):
                        templates_found.extend([(f, os.path.join(common_tpl_dir, f)) for f in os.listdir(common_tpl_dir) if f.endswith('.docx') and not f.startswith('~$')])
                        
                    if not templates_found:
                        st.caption(f"Шаблоны не найдены (папка templates/{bank_folder_name}).")
                    else:
                        templates_found.sort(key=lambda x: x[0])
                        cols = st.columns(3)
                        for i, (tpl_name, tpl_path) in enumerate(templates_found):
                            if cols[i % 3].button(f"Сформировать {tpl_name}", key=f"card_gen_{tpl_name}_{i}"):
                                try:
                                    doc = DocxTemplate(tpl_path)
                                    # Safe context building from client dict
                                    context = {
                                        'fio': client.get('fio', ''),
                                        'phone': clean_int_str(client.get('phone', '')),
                                        'email': str(client.get('email', '')).replace('nan', ''),
                                        'passport_ser': clean_int_str(client.get('passport_ser', '')),
                                        'passport_num': clean_int_str(client.get('passport_num', '')),
                                        'passport_issued': str(client.get('passport_issued', '')).replace('nan', ''),
                                        'passport_date': pd.to_datetime(client.get('passport_date')).strftime('%d.%m.%Y') if pd.notna(client.get('passport_date')) else "",
                                        'dob': pd.to_datetime(client.get('dob')).strftime('%d.%m.%Y') if pd.notna(client.get('dob')) else "",
                                        'birth_place': str(client.get('birth_place', '')).replace('nan', ''),
                                        'kpp': str(client.get('kpp', '')).replace('nan', ''),
                                        'inn': str(client.get('inn', '')).replace('nan', ''),
                                        'snils': str(client.get('snils', '')).replace('nan', ''),
                                        'addr_index': clean_int_str(client.get('addr_index', '')),
                                        'addr_city': str(client.get('addr_city', '')).replace('nan', ''),
                                        'addr_street': str(client.get('addr_street', '')).replace('nan', ''),
                                        'addr_house': clean_int_str(client.get('addr_house', '')),
                                        'addr_house': clean_int_str(client.get('addr_house', '')),
                                        'addr_flat': clean_int_str(client.get('addr_flat', '')),
                                        'addr_korpus': clean_int_str(client.get('addr_korpus', '')),
                                        'addr_structure': clean_int_str(client.get('addr_structure', '')),
                                        'addr_region': str(client.get('addr_region', '')).replace('nan', '').replace('None', ''),
                                        'addr_reg': ", ".join(filter(None, [
                                            clean_int_str(client.get('addr_index', '')),
                                            str(client.get('addr_region', '')).replace('nan', '').replace('None', ''),
                                            str(client.get('addr_city', '')).replace('nan', '').replace('None', ''),
                                            str(client.get('addr_street', '')).replace('nan', '').replace('None', ''),
                                            f"д. {clean_int_str(client.get('addr_house', ''))}" if client.get('addr_house') and str(client.get('addr_house')) != 'nan' else "",
                                            f"корп. {clean_int_str(client.get('addr_korpus', ''))}" if client.get('addr_korpus') and str(client.get('addr_korpus')) != 'nan' else "",
                                            f"стр. {clean_int_str(client.get('addr_structure', ''))}" if client.get('addr_structure') and str(client.get('addr_structure')) != 'nan' else "",
                                            f"кв. {clean_int_str(client.get('addr_flat', ''))}" if client.get('addr_flat') and str(client.get('addr_flat')) != 'nan' else ""
                                        ])),
                                        'bank_name': selected_bank_name,
                                        'credit_sum': client.get('credit_sum', 0),
                                        'loan_term': client.get('loan_term', 0),
                                        'today': date.today().strftime("%d.%m.%Y")
                                    }
                                    doc.render(context)
                                    buf = io.BytesIO()
                                    doc.save(buf)
                                    buf.seek(0)
                                    tpl_basename = tpl_name.replace('.docx', '')
                                    # Finalize DOCX
                                    doc.save(buf)
                                    buf.seek(0)
                                    
                                    # --- Auto-upload to Yandex Disk (DOCX) ---
                                    with st.spinner("Загрузка DOCX на Яндекс.Диск..."):
                                        target_folder = get_client_folder_name(client)
                                        download_name = f"{bank_folder_name} {tpl_name.replace('.docx', '')} {date.today().strftime('%d_%m_%y')}.docx"
                                        
                                        # Upload
                                        buf.seek(0)
                                        if upload_to_yandex(buf, target_folder, download_name):
                                            st.toast(f"✅ {download_name} загружен в '{target_folder}'!", icon="☁️")
                                        else:
                                            st.toast(f"❌ Не удалось загрузить {download_name}", icon="⚠️")
                                            
                                        buf.seek(0) # Reset for download button

                                    d_col1, d_col2 = st.columns(2)
                                    with d_col1:
                                        st.download_button(
                                            label=f"Скачать DOCX",
                                            data=buf,
                                            file_name=download_name,
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            key=f"dl_btn_docx_{tpl_name}_{i}"
                                        )
                                    
                                    with d_col2:
                                        pdf_key = f"pdf_data_{tpl_name}_{i}"
                                        
                                        if st.button(f"Сформировать PDF", key=f"gen_pdf_{tpl_name}_{i}"):
                                            with st.spinner("Конвертация в PDF через LibreOffice..."):
                                                try:
                                                    # 1. Создаем временную папку и пути
                                                    with tempfile.TemporaryDirectory() as temp_dir:
                                                        temp_docx = os.path.join(temp_dir, f"temp_source.docx")
                                                        # LibreOffice сохраняет файл с тем же именем, но .pdf, в папку outdir
                                                        
                                                        # 2. Сохраняем DOCX из памяти (buf) во временный файл
                                                        with open(temp_docx, "wb") as f:
                                                            f.write(buf.getvalue())
                                                        
                                                        # 3. Конвертируем
                                                        success = convert_docx_to_pdf_libreoffice(temp_docx, temp_dir)
                                                        
                                                        if success:
                                                            # Имя созданного PDF файла будет таким же как у docx, но .pdf
                                                            created_pdf_path = os.path.join(temp_dir, "temp_source.pdf")
                                                            
                                                            if os.path.exists(created_pdf_path):
                                                                # 4. Читаем PDF обратно в память
                                                                with open(created_pdf_path, "rb") as f:
                                                                    pdf_bytes = f.read()
                                                                    st.session_state[pdf_key] = pdf_bytes
                                                                
                                                                st.success("✅ PDF сформирован!")
                                                                
                                                                # --- Auto-upload to Yandex Disk (PDF) ---
                                                                target_folder = get_client_folder_name(client)
                                                                pdf_name_upload = download_name.replace('.docx', '.pdf')
                                                                
                                                                with st.spinner("Загрузка PDF на Яндекс.Диск..."):
                                                                     # Wrap bytes in IO for upload
                                                                     pdf_io = io.BytesIO(pdf_bytes)
                                                                     if upload_to_yandex(pdf_io, target_folder, pdf_name_upload):
                                                                         st.toast(f"✅ PDF загружен в '{target_folder}'!", icon="☁️")
                                                                     else:
                                                                         st.error("Не удалось загрузить PDF в облако.")

                                                            else:
                                                                st.error("Файл PDF не был создан, хотя LibreOffice не вернул ошибок.")
                                                
                                                except Exception as e:
                                                    st.error(f"Ошибка процесса: {e}")
                                        
                                        # Render download button if data exists in session state
                                        if pdf_key in st.session_state:
                                            pdf_name = download_name.replace('.docx', '.pdf')
                                            st.download_button(
                                                label="Скачать PDF",
                                                data=st.session_state[pdf_key],
                                                file_name=pdf_name,
                                                mime="application/pdf",
                                                key=f"dl_btn_pdf_{pdf_key}"
                                            )

                                except Exception as e:
                                    st.error(f"Ошибка генерации: {e}")

                    
                    # --- Email Generation ---
                    
                    st.markdown("#### 📧 Письмо")
                    
                    emails_to = []
                    # Prefer manager email, otherwise use first available
                    if selected_bank.get('manager_email') and str(selected_bank.get('manager_email')) != "nan":
                        emails_to.append(str(selected_bank.get('manager_email')))
                    
                    emails_cc = []
                    if selected_bank.get('email2') and str(selected_bank.get('email2')) != "nan":
                        emails_cc.append(str(selected_bank.get('email2')))
                    if selected_bank.get('email3') and str(selected_bank.get('email3')) != "nan":
                        emails_cc.append(str(selected_bank.get('email3')))
                    
                    # If no manager email, use first CC as TO
                    if not emails_to and emails_cc:
                        emails_to.append(emails_cc.pop(0))
                        
                    # SUBJECT: Surname Name / ObjType Program City / CreditSum
                    c_surname = client.get('surname', '') or client.get('fio', '').split()[0]
                    c_name = client.get('name', '')
                    if not c_name and len(client.get('fio', '').split()) > 1:
                        c_name = client.get('fio', '').split()[1]
                    
                    subj_parts = [
                        f"{c_surname} {c_name}",
                        f"{client.get('obj_type', '')} {client.get('loan_type', '')} {client.get('obj_city', '')}",
                        f"{safe_int(client.get('credit_sum', 0)):,} руб."
                    ]
                    subj = " / ".join(filter(None, subj_parts))
                    subj = urllib.parse.quote(subj)
                    
                    # BODY Construction
                    lines = []
                    lines.append("Добрый день!")
                    lines.append(f"Прошу рассмотреть заявку по клиенту: {client.get('fio')}")
                    lines.append("")
                    lines.append("--- ПАРАМЕТРЫ СДЕЛКИ ---")
                    lines.append(f"Программа: {client.get('loan_type')}")
                    lines.append(f"Сумма кредита: {safe_int(client.get('credit_sum', 0)):,} руб.")
                    
                    lines.append("")
                    lines.append("--- ПОРТРЕТ КЛИЕНТА ---")
                    lines.append(f"Возраст: {safe_int(client.get('age', 0))} лет")
                    lines.append(f"Доход: {client.get('job_type')}")
                    
                    if client.get('has_coborrower') == 'Да':
                        lines.append("Созаемщик: ЕСТЬ")
                    
                    if client.get('assets') and str(client.get('assets')) != 'nan' and str(client.get('assets')) != 'None':
                         lines.append(f"Доп. активы: {client.get('assets')}")

                    lines.append("")
                    lines.append("--- ОБЪЕКТ ЗАЛОГА ---")
                    lines.append(f"Тип: {client.get('obj_type')}")
                    
                    addr_parts = [
                        clean_int_str(client.get('obj_index', '')), 
                        str(client.get('obj_region', '')),
                        str(client.get('obj_city', '')), 
                        str(client.get('obj_street', '')), 
                        f"д. {clean_int_str(client.get('obj_house', ''))}" if client.get('obj_house') and str(client.get('obj_house')) != 'nan' else "",
                        f"корп. {clean_int_str(client.get('obj_korpus', ''))}" if client.get('obj_korpus') and str(client.get('obj_korpus')) != 'nan' else "",
                        f"стр. {clean_int_str(client.get('obj_structure', ''))}" if client.get('obj_structure') and str(client.get('obj_structure')) != 'nan' else "",
                        f"кв. {clean_int_str(client.get('obj_flat', ''))}" if client.get('obj_flat') and str(client.get('obj_flat')) != 'nan' else ""
                    ]
                    full_addr = ", ".join([p for p in addr_parts if p and p != "nan" and p != "None" and p != ""])
                    lines.append(f"Адрес: {full_addr}")
                    
                    lines.append(f"Стоимость: {safe_int(client.get('obj_price', 0)):,} руб.")
                    
                    if client.get('is_pledged') == 'Да':
                        lines.append(f"Обременение: ЕСТЬ ({client.get('pledge_bank')}, остаток {safe_int(client.get('pledge_amount', 0)):,} руб.)")
                    else:
                        lines.append("Обременение: НЕТ")
                        
                    lines.append(f"Правоустановка: {client.get('obj_doc_type')} от {pd.to_datetime(client.get('obj_date')).strftime('%d.%m.%Y') if pd.notna(client.get('obj_date')) else ''}")
                    
                    if client.get('obj_renovation') == 'Да':
                         lines.append("Реновация: ДА")

                    lines.append("")
                    lines.append("Отчет об оценке (ЦИАН):")
                    lines.append(str(client.get('cian_report_link', '')).replace('nan', '').replace('None', ''))

                    body_text = "\n".join(lines)
                    body = urllib.parse.quote(body_text)
                    
                    if emails_to:
                        to_str = ",".join(emails_to)
                        cc_str = ",".join(emails_cc)
                        
                        yandex_params = f"to={to_str}"
                        if cc_str:
                            yandex_params += f"&cc={cc_str}"
                        
                        yandex_params += f"&subj={subj}&body={body}"
                        yandex_mail_url = f"https://mail.yandex.ru/compose?{yandex_params}"
                        
                        st.markdown(f"""
                        <a href="{yandex_mail_url}" target="_blank" style="display: inline-block; padding: 0.5em 1em; color: white; background-color: #ffcc00; border-radius: 5px; text-decoration: none;">
                        📧 Написать в банк (Яндекс.Почта)
                        </a>
                        """, unsafe_allow_html=True)
                    else:
                        st.caption("Email банка не указан")                  
                    # Add Interaction
                    st.markdown("#### Добавить запись")
                    with st.form(key="card_add_inter_form"):
                        new_stage = st.selectbox("Этап", ["Отправлено", "Рассмотрение", "Доп. запрос", "Одобрено", "Отказ", "Сделка"], key="card_new_stage")
                        new_comment = st.text_area("Комментарий", key="card_new_comment")
                        
                        if st.form_submit_button("Добавить"):
                            # Load fresh DB to safely update
                            current_db = db.load_clients()
                            # Find client index
                            # Ensure ID is string
                            client_id_str = str(client['id']).split('.')[0]
                            # Normalize DB IDs for search
                            current_db['id'] = current_db['id'].astype(str).str.replace(r'\.0$', '', regex=True)
                            
                            idx = current_db[current_db['id'] == client_id_str].index
                            if not idx.empty:
                                idx = idx[0]
                                # Get existing interactions again to be safe
                                curr_inters_json = current_db.at[idx, 'bank_interactions']
                                try:
                                    curr_inters = json.loads(curr_inters_json) if pd.notna(curr_inters_json) and curr_inters_json != "nan" else []
                                    if not isinstance(curr_inters, list): curr_inters = []
                                except:
                                    curr_inters = []
                                
                                new_rec = {
                                    "bank_name": selected_bank_name,
                                    "stage": new_stage,
                                    "comment": new_comment,
                                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                                }
                                curr_inters.insert(0, new_rec)
                                
                                current_db.at[idx, 'bank_interactions'] = json.dumps(curr_inters, ensure_ascii=False)
                                db.save_all_clients(current_db)
                                st.success("Запись добавлена!")
                                st.rerun()
                            else:
                                st.error("Ошибка обновления: клиент не найден в базе.")

                # History Table
                st.subheader("История взаимодействий")
                if interactions:
                    st.dataframe(pd.DataFrame(interactions))
                else:
                    st.caption("История пуста")
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
    if not df.empty:
        # Pre-process: ensure text columns are strings (not float/NaN) to satisfy st.data_editor
        # Also ensure new columns exist if DB migration didn't happen yet
        for new_col in ["email2", "email3"]:
            if new_col not in df.columns:
                df[new_col] = ""

        for col in df.columns:
            if col != "id": # Keep ID as is or also str
                 val = df[col].astype(str).replace("nan", "").replace("None", "")
                 df[col] = val.apply(lambda x: x[:-2] if x.endswith(".0") else x)
        
        # Reorder columns: Name, Manager, Phone, Email, Email2, Email3, Address, ID
        desired_order = ["name", "manager_fio", "manager_phone", "manager_email", "email2", "email3", "address", "id"]
        # Ensure all cols exist (just in case)
        existing_cols = [c for c in desired_order if c in df.columns]
        # Append any other cols that might be there
        remaining_cols = [c for c in df.columns if c not in existing_cols]
        df = df[existing_cols + remaining_cols]

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        name_filter = st.multiselect("Фильтр по названию", options=df["name"].unique() if not df.empty else [], placeholder="Введите название банка", label_visibility="collapsed")
    
    filtered_df = df.copy()
    if name_filter:
        filtered_df = filtered_df[filtered_df["name"].isin(name_filter)]

    # Use Data Editor for Banks too
    edited_df = st.data_editor(
        filtered_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "name": st.column_config.TextColumn("Название"),
            "address": st.column_config.TextColumn("Адрес"),
            "manager_fio": st.column_config.TextColumn("Менеджер"),
            "manager_email": st.column_config.TextColumn("Email"),
            "email2": st.column_config.TextColumn("Email 2"),
            "email3": st.column_config.TextColumn("Email 3"),
            "manager_phone": st.column_config.TextColumn("Телефон"),
            "lk_link": st.column_config.LinkColumn("Ссылка на ЛК", display_text="Перейти"),
        },
        key="bank_editor"
    )
    
    # Save button row
    # Save button row
    save_col, msg_col, _ = st.columns([1, 1, 3])
    with save_col:
        save_clicked = st.button("💾 Сохранить изменения")
        
    if save_clicked:
        # Apply phone formatting to manually edited rows before saving
        if "manager_phone" in edited_df.columns:
            edited_df["manager_phone"] = edited_df["manager_phone"].apply(format_phone_string)
            
        # Use bulk save to handle deletions and avoid duplicates
        db.save_all_banks(edited_df)
        with msg_col:
            st.markdown(
                """
                <div style="
                    color: #0f5132;
                    padding: 0.1rem 0;
                    text-align: left;
                    font-size: 1rem;
                    line-height: 1.6;
                    margin-top: 0.2rem;
                ">
                    ✅ Банки сохранены
                </div>
                """,
                unsafe_allow_html=True
            )
    
    # st.divider() - Removed by user request
    st.subheader("Добавить новый банк")
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    with r1_c1:
        b_name = st.text_input("Название")
    with r1_c2:
        b_addr = st.text_input("Адрес")
    with r1_c3:
        b_man = st.text_input("Менеджер")
    with r1_c4:
        b_tel = formatted_phone_input("Телефон", "bank_new_phone")
        
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    with r2_c1:
        b_mail = st.text_input("Email")
    with r2_c2:
        b_mail2 = st.text_input("Email 2")
    with r2_c3:
        b_mail3 = st.text_input("Email 3")
    
    # New row for Link
    r3_c1, r3_c2 = st.columns([2, 1])
    with r3_c1:
        b_lk = st.text_input("Ссылка на ЛК", placeholder="https://...")

    if st.button("Добавить", type="primary"):
        new_id = str(abs(hash(b_name + str(datetime.now()))))
        db.save_bank({
            "id": new_id,
            "name": b_name, "address": b_addr, 
            "manager_fio": b_man, "manager_email": b_mail,
            "email2": b_mail2, "email3": b_mail3, 
            "manager_phone": b_tel, "lk_link": b_lk
        })
        st.success("Банк добавлен")
        st.rerun()