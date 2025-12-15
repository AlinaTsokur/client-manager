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
import pypdf
import io
import urllib.parse
import re
from num2words import num2words

# --- Performance Optimization: Caching ---
@st.cache_data(show_spinner=False)
def get_cached_clients():
    return db.load_clients()

@st.cache_data(show_spinner=False)
def get_cached_banks():
    return db.load_banks()

@st.cache_data(show_spinner=False)
def get_cached_applications():
    return db.load_applications()

def clear_cache():
    get_cached_clients.clear()
    get_cached_banks.clear()
    get_cached_applications.clear()

# --- Configuration ---
YANDEX_TOKEN = "y0__xCF7vSyBhj0hTwg2oaewBUWNr9rdgvFpxw2k559OGkSU4o9VA"
FONTS_DIR = 'fonts'
TEMPLATES_DIR = 'templates'

# Options
status_options = ["Новый", "В работе", "Одобрен", "Сделка", "Подписание", "Выдача", "Отказ", "Архив"]
loan_type_options = ["Ипотека", "Залог"]

# Helper function
# --- LibreOffice Conversion Function ---
# --- LibreOffice Conversion Function (ИСПРАВЛЕННАЯ ВЕРСИЯ) ---
def convert_docx_to_pdf_libreoffice(source_docx, output_dir):
    """
    Конвертирует docx в pdf используя LibreOffice в headless режиме.
    Использует изолированный профиль пользователя для стабильности на macOS.
    """
    # Путь к LibreOffice на macOS (стандартный)
    libreoffice_path = '/Applications/LibreOffice.app/Contents/MacOS/soffice'
    
    # 1. Проверяем наличие файла DOCX
    if not os.path.exists(source_docx):
        st.error(f"❌ Исходный файл не найден: {source_docx}")
        return False
    
    # 2. Проверяем наличие LibreOffice
    if not os.path.exists(libreoffice_path):
        st.error(f"❌ LibreOffice не найден! Установите его в /Applications.\nПуть: {libreoffice_path}")
        return False
    
    # 3. Создаем временную папку для профиля пользователя
    # Это "серебряная пуля" для Mac: LibreOffice думает, что он запущен первым и единственным.
    user_profile_dir = os.path.join(output_dir, 'LO_User')
    os.makedirs(user_profile_dir, exist_ok=True)

    # 4. Формируем команду
    args = [
        libreoffice_path,
        f'-env:UserInstallation=file://{user_profile_dir}', # Изолированный профиль
        '--headless',
        '--invisible',
        '--nodefault',
        '--nofirststartwizard',
        '--nolockcheck',
        '--norestore',
        '--convert-to', 'pdf',
        '--outdir', output_dir,
        source_docx
    ]
    
    try:
        # Запускаем процесс
        process = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60  # Даем чуть больше времени
        )
        
        # Проверяем результат
        expected_pdf = os.path.join(
            output_dir, 
            os.path.splitext(os.path.basename(source_docx))[0] + '.pdf'
        )
        
        if os.path.exists(expected_pdf) and os.path.getsize(expected_pdf) > 0:
            return True
        else:
            # Если файл не создан, выводим ошибку из LibreOffice
            err_msg = process.stderr.decode() if process.stderr else "Нет описания ошибки"
            st.error(f"❌ PDF не создан. Ошибка LibreOffice:\n{err_msg}")
            return False
            
    except subprocess.TimeoutExpired:
        st.error("❌ Время ожидания истекло (LibreOffice завис).")
        return False
    except Exception as e:
        st.error(f"❌ Системная ошибка: {e}")
        return False

# --- Formatted Number Input ---

# --- Formatted Number Input (ИСПРАВЛЕННАЯ ВЕРСИЯ - без лишних отступов) ---
def formatted_number_input(label, key, allow_float=False, value=None):
    if key not in st.session_state:
        if value is not None and (isinstance(value, (int, float)) and value > 0):
            if allow_float:
                st.session_state[key] = f"{value:,}".replace(",", " ")
            else:
                st.session_state[key] = f"{int(value):,}".replace(",", " ")
        else:
            st.session_state[key] = ""
        
    def on_change():
        val = st.session_state[key]
        if allow_float:
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
            clean = ''.join(c for c in val if c.isdigit())
            if clean:
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
import openpyxl

def fill_excel_template(template_path, context):
    """Fills an Excel template with context data."""
    try:
        wb = openpyxl.load_workbook(template_path)
        
        # Iterate over all sheets
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str) and '{{' in cell.value:
                        val = cell.value
                        # Try both spaces and no-spaces
                        for k, v in context.items():
                             # Robust check to avoid partial replacements if possible, but keep simple for now
                             # {{ key }}
                             if f'{{{{ {k} }}}}' in val:
                                 val = val.replace(f'{{{{ {k} }}}}', str(v))
                             # {{key}}
                             if f'{{{{{k}}}}}' in val:
                                 val = val.replace(f'{{{{{k}}}}}', str(v))
                        
                        cell.value = val
                        
                        # Try to restore numbers
                        try:
                           # If the cell is ONLY a number now, convert it
                           clean = str(val).replace(' ', '').replace(',', '.')
                           if clean.replace('.', '', 1).isdigit():
                               if '.' in clean:
                                   cell.value = float(clean)
                               else:
                                   cell.value = int(clean)
                        except:
                            pass

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"Excel fill error: {e}")
        return None

def fill_pdf_form(template_path, data):
    """Fills a PDF form using pypdf."""
    try:
        reader = pypdf.PdfReader(template_path)
        writer = pypdf.PdfWriter()
        
        # Clone valid content (preserves AcroForm)
        writer.clone_document_from_reader(reader)
            
        # Prepare data: ensure all values are strings
        clean_data = {k: str(v) for k, v in data.items() if v is not None}
        
        # Update fields on all pages
        for page in writer.pages:
            writer.update_page_form_field_values(page, clean_data)
            
        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        return buf.getvalue(), None
    except Exception as e:
        return None, str(e)

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


def calculate_ndfl_year_to_date(year, total_income):
    """
    Calculates cumulative NDFL for a given year and total income year-to-date.
    """
    if year < 2025:
        # Pre-2025 Rules:
        # 13% up to 5M, 15% above 5M
        limit_15 = 5_000_000
        if total_income <= limit_15:
            return int(total_income * 0.13)
        else:
            tax_13 = limit_15 * 0.13
            tax_15 = (total_income - limit_15) * 0.15
            return int(tax_13 + tax_15)
    else:
        # 2025 Rules (Progressive):
        # 13% <= 2.4M
        # 15% 2.4M - 5M
        # 18% 5M - 20M
        # 20% 20M - 50M
        # 22% > 50M
        
        brackets = [
            (2_400_000, 0.13),
            (5_000_000 - 2_400_000, 0.15),  # 2.6M span
            (20_000_000 - 5_000_000, 0.18), # 15M span
            (50_000_000 - 20_000_000, 0.20),# 30M span
            (float('inf'), 0.22)
        ]
        
        remaining_income = total_income
        total_tax = 0.0
        
        for span, rate in brackets:
            if remaining_income <= 0:
                break
            
            taxable_in_bracket = min(remaining_income, span)
            total_tax += taxable_in_bracket * rate
            remaining_income -= taxable_in_bracket
            
        return int(total_tax)


def get_salary_context(income_str):
    """
    Generates context for the last 12 months salary certificate.
    Returns keys like m_1 (oldest) ... m_12 (newest, previous month).
    Also returns month-specific ndfl and net_income.
    """
    try:
        if not income_str:
            income = 0
        else:
            income = int(str(income_str).replace(' ', ''))
    except:
        income = 0

    months_ru = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    ctx = {
        'job_income': f"{income:,}".replace(",", " "),
    }
    
    today = date.today()
    # Start from previous month
    current_date_cursor = today - relativedelta(months=1)
    
    # We need to calculate tax for each month specifically.
    # To do this correctly for progressive tax, we need the "month of year" index (1..12).
    # Since we assume constant salary, cumulative income = income * month_number.
    
    total_income_12 = 0
    total_ndfl_12 = 0
    total_net_12 = 0
    
    # Generate 12 months going backwards
    # m_12 is the most recent (previous month)
    # m_1 is the oldest (12 months ago)
    
    months_data = [] # Store temporarily to reverse if needed, but we fill by index
    
    # Iterate backwards from m_12 to m_1
    for i in range(12):
        # i=0 -> m_12 (newest), i=11 -> m_1 (oldest)
        m_idx = 12 - i 
        
        loop_date = current_date_cursor
        m_name = months_ru[loop_date.month]
        month_label = f"{m_name} {loop_date.year}"
        
        # Calculate Tax for this specific month
        # 1. Cumulative Income UP TO this month (inclusive)
        current_month_num = loop_date.month
        cumulative_income_now = income * current_month_num
        
        # 2. Cumulative Income UP TO Previous month
        cumulative_income_prev = income * (current_month_num - 1)
        
        # 3. Calculate Tax Liability YTD
        tax_ytd_now = calculate_ndfl_year_to_date(loop_date.year, cumulative_income_now)
        tax_ytd_prev = calculate_ndfl_year_to_date(loop_date.year, cumulative_income_prev)
        
        # 4. Monthly Tax = diff
        monthly_ndfl = tax_ytd_now - tax_ytd_prev
        monthly_net = income - monthly_ndfl
        
        # Add to yearly totals
        total_income_12 += income
        total_ndfl_12 += monthly_ndfl
        total_net_12 += monthly_net
        
        # Update Context for this specific month index
        ctx[f'm_{m_idx}'] = month_label
        ctx[f'month_{m_idx}'] = m_name
        ctx[f'year_{m_idx}'] = str(loop_date.year)
        ctx[f'ndfl_{m_idx}'] = f"{monthly_ndfl:,}".replace(",", " ")
        ctx[f'net_{m_idx}'] = f"{monthly_net:,}".replace(",", " ")
        ctx[f'income_{m_idx}'] = f"{income:,}".replace(",", " ") # If they want explicit income per row
        
        # Move back
        current_date_cursor = current_date_cursor - relativedelta(months=1)

    # Global totals for the certificate (Sum of the 12 months displayed)
    # Use _total suffix to avoid collision with month 12
    ctx['job_income_total'] = f"{total_income_12:,}".replace(",", " ")
    ctx['ndfl_total'] = f"{total_ndfl_12:,}".replace(",", " ")
    ctx['net_income_total'] = f"{total_net_12:,}".replace(",", " ")
    
    # Also provide _13 for convenience if user expects it for the "13th row" (Total)
    ctx['job_income_13'] = ctx['job_income_total']
    ctx['ndfl_13'] = ctx['ndfl_total']
    ctx['net_income_13'] = ctx['net_income_total']
    
    # Average Monthly Deductions (NDFL / 12)
    avg_ndfl = int(total_ndfl_12 / 12) if total_ndfl_12 else 0
    ctx['average_ndfl'] = f"{avg_ndfl:,}".replace(",", " ")
    
    # Fallback/Default single values (using the latest month, i.e., m_12 logic)
    ctx['ndfl'] = ctx['ndfl_12']
    ctx['net_income'] = ctx['net_12']

    return ctx
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

# --- Shared Document Generator ---
def render_docs_generator(client, selected_bank, key_suffix, banks_list=None):
    """
    Renders the document generation UI (Templates list -> Generate -> Download).
    """
    if not selected_bank:
        st.info("Выберите банк для отображения шаблонов.")
        return

    selected_bank_name = selected_bank.get('name')
    # Templates
    # Use transliterated folder name
    bank_folder_name = transliterate(selected_bank_name)
    bank_tpl_dir = os.path.join(TEMPLATES_DIR, bank_folder_name)
    common_tpl_dir = os.path.join(TEMPLATES_DIR, "common")
    
    # Check dirs
    templates_found = []
    if os.path.exists(bank_tpl_dir):
        templates_found.extend([(f, os.path.join(bank_tpl_dir, f)) for f in os.listdir(bank_tpl_dir) if (f.endswith('.docx') or f.endswith('.pdf') or f.endswith('.xlsx')) and not f.startswith('~$')])
    if os.path.exists(common_tpl_dir):
        templates_found.extend([(f, os.path.join(common_tpl_dir, f)) for f in os.listdir(common_tpl_dir) if (f.endswith('.docx') or f.endswith('.pdf') or f.endswith('.xlsx')) and not f.startswith('~$')])
        
    if not templates_found:
        st.caption(f"Шаблоны не найдены (папка templates/{bank_folder_name}).")
    else:
        templates_found.sort(key=lambda x: x[0])
        cols = st.columns(3)
        for i, (tpl_name, tpl_path) in enumerate(templates_found):
            # Unique key for every client+bank+template combo
            btn_key = f"gen_{key_suffix}_{tpl_name}_{i}"
            if cols[i % 3].button(f"📄 {tpl_name}", key=btn_key):
                try:
                    # Create Context (Shared)
                    # Логика сборки адреса объекта в одну строку
                    obj_parts = [
                        clean_int_str(client.get('obj_index', '')),
                        str(client.get('obj_region', '')).replace('nan', '').replace('None', ''),
                        str(client.get('obj_city', '')).replace('nan', '').replace('None', ''),
                        str(client.get('obj_street', '')).replace('nan', '').replace('None', ''),
                        f"д. {clean_int_str(client.get('obj_house', ''))}" if client.get('obj_house') and str(client.get('obj_house')) != 'nan' else "",
                        f"корп. {clean_int_str(client.get('obj_korpus', ''))}" if client.get('obj_korpus') and str(client.get('obj_korpus')) != 'nan' else "",
                        f"стр. {clean_int_str(client.get('obj_structure', ''))}" if client.get('obj_structure') and str(client.get('obj_structure')) != 'nan' else "",
                        f"кв. {clean_int_str(client.get('obj_flat', ''))}" if client.get('obj_flat') and str(client.get('obj_flat')) != 'nan' else ""
                    ]
                    # Удаляем пустые элементы и склеиваем
                    full_obj_addr = ", ".join([p for p in obj_parts if p and p.strip()])

                    # Вычисляем срок в месяцах
                    term_years = safe_int(client.get('loan_term', 0))
                    term_months = term_years * 12


                    # Ensure FIO parts are available
                    c_surname = client.get('surname', '')
                    c_name = client.get('name', '')
                    c_patronymic = client.get('patronymic', '')
                    
                    if not c_surname and client.get('fio'):
                         c_surname, c_name, c_patronymic = parse_fio(client.get('fio'))

                    context = {
                        'fio': client.get('fio', ''),
                        'surname': str(c_surname).replace('nan', '') if c_surname else '',
                        'name': str(c_name).replace('nan', '') if c_name else '',
                        'patronymic': str(c_patronymic).replace('nan', '') if c_patronymic else '',
                        'phone': clean_int_str(client.get('phone', '')),
                        'email': str(client.get('email', '')).replace('nan', ''),
                        
                        # Паспорт
                        'passport_ser': clean_int_str(client.get('passport_ser', '')),
                        'passport_num': clean_int_str(client.get('passport_num', '')),
                        'passport_issued': str(client.get('passport_issued', '')).replace('nan', ''),
                        'passport_date': pd.to_datetime(client.get('passport_date')).strftime('%d.%m.%Y') if pd.notna(client.get('passport_date')) else "",
                        'dob': pd.to_datetime(client.get('dob')).strftime('%d.%m.%Y') if pd.notna(client.get('dob')) else "",
                        'birth_place': str(client.get('birth_place', '')).replace('nan', ''),
                        'kpp': str(client.get('kpp', '')).replace('nan', ''),
                        'inn': clean_int_str(client.get('inn', '')),
                        'snils': clean_int_str(client.get('snils', '')),
                        
                        # Адрес регистрации (по частям)
                        'addr_index': clean_int_str(client.get('addr_index', '')),
                        'addr_city': str(client.get('addr_city', '')).replace('nan', ''),
                        'addr_street': str(client.get('addr_street', '')).replace('nan', ''),
                        'addr_house': clean_int_str(client.get('addr_house', '')),
                        'addr_flat': clean_int_str(client.get('addr_flat', '')),
                        'addr_korpus': clean_int_str(client.get('addr_korpus', '')),
                        'addr_structure': clean_int_str(client.get('addr_structure', '')),
                        'addr_region': str(client.get('addr_region', '')).replace('nan', '').replace('None', ''),
                        
                        # Адрес регистрации (ПОЛНЫЙ СТРОКОЙ)
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

                        # --- НОВОЕ: Адрес залога (ПОЛНЫЙ СТРОКОЙ) ---
                        'obj_addr': full_obj_addr,

                        # Данные банка и кредита
                        'bank_name': selected_bank_name,
                        'credit_sum': client.get('credit_sum', 0),
                        
                        # Сроки кредита
                        'loan_term': term_years,       # В годах (например: 15)
                        'loan_term_months': term_months, # В месяцах (например: 180)
                        
                        'loan_term_months': term_months, # В месяцах (например: 180)
                        
                        'today': date.today().strftime("%d.%m.%Y"),
                        'today_d': date.today().strftime("%d"),
                        'today_m': date.today().strftime("%m"),
                        'today_y': date.today().strftime("%Y"),
                        
                        # Работа
                        'job_company': str(client.get('job_company', '')).replace('nan', ''),
                        'job_pos': str(client.get('job_pos', '')).replace('nan', ''),
                        'job_income': clean_int_str(client.get('job_income', '')),
                        'job_phone': clean_int_str(client.get('job_phone', '')),
                        'job_inn': clean_int_str(client.get('job_inn', '')),
                        'job_ceo': str(client.get('job_ceo', '')).replace('nan', ''),
                        'job_address': str(client.get('job_address', '')).replace('nan', ''),
                        'job_sphere': str(client.get('job_sphere', '')).replace('nan', ''),
                        'total_exp': clean_int_str(client.get('total_exp', '')),
                        
                        # Личные данные (добавлено)
                        'family_status': client.get('family_status', ''),
                        'gender': client.get('gender', ''),
                        'marriage_contract': str(client.get('marriage_contract', '')).replace('nan', '').replace('None', ''),
                        'children_count': clean_int_str(client.get('children_count', '')),
                        'children_dates': str(client.get('children_dates', '')).replace('nan', '') if safe_int(client.get('children_count', 0)) > 0 else "",
                        
                        # Работа (добавлено)
                        'job_start_date': pd.to_datetime(client.get('job_start_date')).strftime('%d.%m.%Y') if pd.notna(client.get('job_start_date')) and str(client.get('job_start_date')) != 'None' else "",
                        'job_start_date_d': pd.to_datetime(client.get('job_start_date')).strftime('%d') if pd.notna(client.get('job_start_date')) and str(client.get('job_start_date')) != 'None' else "",
                        'job_start_date_m': pd.to_datetime(client.get('job_start_date')).strftime('%m') if pd.notna(client.get('job_start_date')) and str(client.get('job_start_date')) != 'None' else "",
                        'job_start_date_y': pd.to_datetime(client.get('job_start_date')).strftime('%Y') if pd.notna(client.get('job_start_date')) and str(client.get('job_start_date')) != 'None' else "",
                        
                        # Объект (добавлено)
                        'obj_area': clean_int_str(client.get('obj_area', '')),
                        'obj_floor': clean_int_str(client.get('obj_floor', '')),
                        'obj_total_floors': clean_int_str(client.get('obj_total_floors', '')),
                        'obj_walls': client.get('obj_walls', ''),
                        'obj_type': str(client.get('obj_type', '')).replace('nan', '').replace('None', ''),
                        'obj_doc_type': str(client.get('obj_doc_type', '')).replace('nan', '').replace('None', ''),
                        'obj_city': str(client.get('obj_city', '')).replace('nan', '').replace('None', ''),

                        # Залог и Активы (добавлено)
                        'is_pledged': str(client.get('is_pledged', '')).replace('nan', '').replace('None', ''),
                        'pledge_bank': str(client.get('pledge_bank', '')).replace('nan', '').replace('None', ''),
                        'pledge_amount': clean_int_str(client.get('pledge_amount', '')),
                        'assets': str(client.get('assets', '')).replace('nan', '').replace('None', ''),
                    }
                    
                    # --- Salary Context (12 months) ---
                    salary_ctx = get_salary_context(clean_int_str(client.get('job_income', '')))
                    context.update(salary_ctx)

                    # --- Number to Words (Propis) ---
                    try:
                        income_int = int(clean_int_str(client.get('job_income', 0)))
                        income_words = num2words(income_int, lang='ru')
                        context['job_income_propis'] = income_words
                    except:
                        context['job_income_propis'] = ""
                        
                    # --- NDFL 13% fixed ---
                    try:
                        income_int = int(clean_int_str(client.get('job_income', 0)))
                        ndfl_13_val = int(income_int * 0.13)
                        context['ndfl_avg_13'] = f"{ndfl_13_val:,}".replace(",", " ")
                        
                        # Yearly 13%
                        ndfl_year_13_val = ndfl_13_val * 12
                        context['ndfl_total_13_calc'] = f"{ndfl_year_13_val:,}".replace(",", " ")
                    except:
                        context['ndfl_avg_13'] = ""
                        context['ndfl_total_13_calc'] = ""


                    if tpl_name.endswith('.docx'):
                        # --- DOCX Logic ---
                        doc = DocxTemplate(tpl_path)
                        doc.render(context)
                        buf = io.BytesIO()
                        doc.save(buf)
                        buf.seek(0)
                        
                        download_name = f"{bank_folder_name} {tpl_name.replace('.docx', '')} {date.today().strftime('%d_%m_%y')}.docx"
                        
                        # Save to session (so buttons persist after rerun if needed, or just immediate use)
                        st.session_state[f"docx_buf_{key_suffix}_{i}"] = buf
                        st.session_state[f"docx_name_{key_suffix}_{i}"] = download_name

                    elif tpl_name.endswith('.xlsx'):
                         # --- Excel Logic ---
                         excel_bytes = fill_excel_template(tpl_path, context)
                         if excel_bytes:
                             download_name = f"{bank_folder_name} {tpl_name.replace('.xlsx', '')} {date.today().strftime('%d_%m_%y')}.xlsx"
                             st.session_state[f"xlsx_bytes_{key_suffix}_{i}"] = excel_bytes
                             st.session_state[f"xlsx_name_{key_suffix}_{i}"] = download_name
                         else:
                             st.error("Ошибка генерации Excel.")

                    elif tpl_name.endswith('.pdf'):
                        # --- PDF Form Logic ---
                        with st.spinner("Заполнение PDF формы..."):
                            filled_pdf_bytes, error_msg = fill_pdf_form(tpl_path, context)
                            
                            if filled_pdf_bytes:
                                download_name = f"{bank_folder_name} {tpl_name.replace('.pdf', '')} {date.today().strftime('%d_%m_%y')}.pdf"
                                st.session_state[f"pdf_pure_bytes_{key_suffix}_{i}"] = filled_pdf_bytes
                                st.session_state[f"pdf_pure_name_{key_suffix}_{i}"] = download_name
                                st.success("✅ PDF форма заполнена!")
                            else:
                                st.error(f"Ошибка при заполнении PDF: {error_msg}")

                except Exception as e:
                    st.error(f"Ошибка генерации: {e}")
            
            # Show download buttons if generated
            # DOCX
            if f"docx_buf_{key_suffix}_{i}" in st.session_state:
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    st.download_button(
                        label=f"📥 Скачать DOCX",
                        data=st.session_state[f"docx_buf_{key_suffix}_{i}"],
                        file_name=st.session_state[f"docx_name_{key_suffix}_{i}"],
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_docx_{key_suffix}_{i}"
                    )
                with d_col2:
                    # PDF Conversion
                    if st.button("🔄 В PDF", key=f"to_pdf_{key_suffix}_{i}"):
                         with st.spinner("Конвертация в PDF..."):
                            try:
                                with tempfile.TemporaryDirectory() as temp_dir:
                                    temp_docx = os.path.join(temp_dir, f"temp_source.docx")
                                    # Write buffer to temp file
                                    buf = st.session_state[f"docx_buf_{key_suffix}_{i}"]
                                    buf.seek(0)
                                    with open(temp_docx, "wb") as f:
                                        f.write(buf.getvalue())
                                    
                                    success = convert_docx_to_pdf_libreoffice(temp_docx, temp_dir)
                                    if success:
                                        created_pdf_path = os.path.join(temp_dir, "temp_source.pdf")
                                        if os.path.exists(created_pdf_path):
                                            with open(created_pdf_path, "rb") as f:
                                                pdf_bytes = f.read()
                                                st.session_state[f"pdf_conv_bytes_{key_suffix}_{i}"] = pdf_bytes
                                                st.session_state[f"pdf_conv_name_{key_suffix}_{i}"] = st.session_state[f"docx_name_{key_suffix}_{i}"].replace('.docx', '.pdf')
                            except Exception as e:
                                st.error(f"Ошибка конвертации: {e}")

                    if f"pdf_conv_bytes_{key_suffix}_{i}" in st.session_state:
                         st.download_button(
                            label="📥 Скачать PDF",
                            data=st.session_state[f"pdf_conv_bytes_{key_suffix}_{i}"],
                            file_name=st.session_state[f"pdf_conv_name_{key_suffix}_{i}"],
                            mime="application/pdf",
                            key=f"dl_conv_pdf_{key_suffix}_{i}"
                        )
            
            # Excel Download
            if f"xlsx_bytes_{key_suffix}_{i}" in st.session_state:
                 st.download_button(
                    label=f"📥 Скачать XLSX",
                    data=st.session_state[f"xlsx_bytes_{key_suffix}_{i}"],
                    file_name=st.session_state[f"xlsx_name_{key_suffix}_{i}"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_xlsx_{key_suffix}_{i}"
                )
            
            # Pure PDF Form
            if f"pdf_pure_bytes_{key_suffix}_{i}" in st.session_state:
                 st.download_button(
                    label=f"📥 Скачать PDF",
                    data=st.session_state[f"pdf_pure_bytes_{key_suffix}_{i}"],
                    file_name=st.session_state[f"pdf_pure_name_{key_suffix}_{i}"],
                    mime="application/pdf",
                    key=f"dl_pure_pdf_{key_suffix}_{i}"
                )

# --- CSS Styles ---
hide_uploader_text = """
<style>
/* Try to access the text container more generally */
[data-testid='stFileUploader'] section > div:first-child {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important; /* Move content to right */
    gap: 10px;
}

/* Hide the specific spans if possible */
[data-testid='stFileUploader'] section > div:first-child > span, 
[data-testid='stFileUploader'] section > div:first-child > small,
[data-testid='stFileUploader'] section > div:first-child > div { /* Sometimes text is in a div */
    display: none !important;
}

/* Re-enable display for the button container specifically if needed, 
   but usually button is a direct child of the dropzone or wrapped in a div we might have just hidden.
   Let's try a different approach: make the section a flex row and force button visibility */

[data-testid='stFileUploader'] section {
    padding: 0px !important;
    min-height: 40px !important; /* Ensure enough height for button */
    display: flex !important;
    flex-direction: row !important; /* Side by side */
    align-items: center !important;
    justify-content: flex-end !important;
}

/* Hide the default text icon */
[data-testid='stFileUploader'] section svg {
    display: none !important;
}

/* Style the Browse button */
[data-testid='stFileUploader'] section button {
    border: 1px solid #4CAF50;
    color: white;
    background-color: #4CAF50; 
    border-radius: 5px;
    visibility: hidden; /* Hide original text */
    position: relative;
    width: 140px; 
    height: 35px;
    line-height: 0;
    margin: 0 !important; /* Remove margins */
}
/* Hack to change button text */
[data-testid='stFileUploader'] section button::after {
    content: "Выбрать файлы";
    visibility: visible;
    display: block;
    position: absolute;
    background-color: #4CAF50;
    padding: 0;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
    font-size: 14px;
}

/* Adjust Page Margins */
.block-container {
    padding-top: 3rem !important;
    padding-left: 10rem !important;
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
    migration_df = get_cached_clients()
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
            get_cached_clients.clear() # Clear cache after auto-migration save
            st.toast("✅ База данных обновлена: ФИО разделены на части.")
    
    st.session_state['migration_done'] = True

# --- Top Navigation ---
# Use radio for navigation to allow programmatic switching via session state
# Sync with query params for persistence across refreshes

# 1. Initialize session state from query params if not set
if "page" not in st.session_state:
    query_params = st.query_params
    query_page = query_params.get("page")
    if query_page and query_page in ["Новый клиент", "Карточка Клиента", "База Клиентов", "База Банков", "Рабочий стол"]:
        st.session_state.page = query_page
    else:
        st.session_state.page = "Новый клиент"

def navigate_to(page):
    st.session_state.page = page
    st.query_params["page"] = page

# Top Menu
pages = ["Новый клиент", "Карточка Клиента", "База Клиентов", "База Банков", "Рабочий стол"]
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

def generate_yandex_mail_link(client, selected_bank):
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
        
        return yandex_mail_url
    return None

def render_client_form(client_data=None, key_prefix=""):

    # Default values for new client
    default_fio = client_data.get('fio') or '' if client_data else ''
    status_options = ["Новый", "В работе", "Одобрен", "Сделка", "Подписание", "Выдача", "Отказ", "Архив"]
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
    default_job_official_val = "Да" if client_data and str(client_data.get('job_official')).lower() in ['да', 'true', '1'] else "Нет"
    default_job_company = str(client_data.get('job_company', '')) if client_data and client_data.get('job_company') and str(client_data.get('job_company')) != 'nan' else ''
    default_job_sphere = str(client_data.get('job_sphere', '')) if client_data and client_data.get('job_sphere') and str(client_data.get('job_sphere')) != 'nan' else ''
    default_job_inn = clean_int_str(client_data.get('job_inn')) if client_data else ''
    default_job_found_date = pd.to_datetime(client_data['job_found_date']).date() if client_data and pd.notna(client_data.get('job_found_date')) else None
    default_job_pos = str(client_data.get('job_pos', '')) if client_data and client_data.get('job_pos') and str(client_data.get('job_pos')) != 'nan' else ''
    default_job_income = client_data.get('job_income', 0) if client_data else 0
    default_job_address = str(client_data.get('job_address', '')) if client_data and client_data.get('job_address') and str(client_data.get('job_address')) != 'nan' else ''
    default_job_start_date = pd.to_datetime(client_data['job_start_date']).date() if client_data and pd.notna(client_data.get('job_start_date')) and str(client_data.get('job_start_date')) != 'None' and str(client_data.get('job_start_date')) != 'nan' else None
    default_job_ceo = str(client_data.get('job_ceo', '')) if client_data and client_data.get('job_ceo') and str(client_data.get('job_ceo')) != 'nan' else ''
    default_job_phone = clean_int_str(client_data.get('job_phone')) if client_data else ''

    default_loan_term = safe_int(client_data.get('loan_term'), 0) if client_data else 0
    has_coborrower_options = ["Да", "Нет"]
    default_has_coborrower_val = "Да" if client_data and str(client_data.get('has_coborrower')).lower() in ['да', 'true', '1'] else "Нет"
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
                
            job_date = jr1_4.date_input("Дата основания компании", min_value=min_date, max_value=max_date, value=default_job_found_date, format="DD.MM.YYYY")
            
            jr2_1, jr2_2, jr2_3, jr2_4, jr2_5 = st.columns([1.2, 1.2, 1, 0.8, 0.8])
            job_position = jr2_1.text_input("Должность", value=default_job_pos, key=f"{key_prefix}job_pos")
            with jr2_2:
                inc_c1, inc_c2 = st.columns([0.85, 0.15])
                with inc_c1:
                    job_income = formatted_number_input("Доход", "job_income_input", value=default_job_income)
                
                # Dynamic calculator link
                calc_amount = int(credit_sum) if credit_sum else 10000000
                banki_url = f"https://www.banki.ru/services/calculators/credits/?amount={calc_amount}&periodNotation=20y&rate=28"
                inc_c2.markdown(f"<div style='padding-top: 28px;'><a href='{banki_url}' target='_blank' style='text-decoration: none; font-size: 20px;'>🧮</a></div>", unsafe_allow_html=True)
            job_start_date = jr2_3.date_input("Начало работы", min_value=min_date, max_value=max_date, value=default_job_start_date, format="DD.MM.YYYY")
            
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
            
            # Layout: CEO | Job Address | Work Phone
            jr3_1, jr3_2, jr3_3 = st.columns(3)
            job_ceo = jr3_1.text_input("ФИО Гендиректора", value=default_job_ceo, key=f"{key_prefix}job_ceo")
            job_address = jr3_2.text_input("Адрес работы", value=default_job_address, key=f"{key_prefix}job_address")
            with jr3_3:
                job_phone = formatted_phone_input("Рабочий телефон", "job_phone_input", value=default_job_phone)
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
            job_address = ""
        
        st.subheader("Финансы")
        
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            loan_term_years = formatted_number_input("Срок кредита (лет)", "loan_term_input", value=default_loan_term)
        
        loan_term_months = loan_term_years * 12
        with f2:
            st.text_input("Срок в месяцах", value=str(loan_term_months), disabled=True)
        
        has_coborrower_val = f3.radio("Будет ли созаемщик?", ["Да", "Нет"], horizontal=True, index=["Да", "Нет"].index(default_has_coborrower_val) if default_has_coborrower_val in ["Да", "Нет"] else None, key=f"{key_prefix}has_coborrower_val")
        has_coborrower = has_coborrower_val # Changed to store "Да"/"Нет" string
        
        # Layout: Debts | Mos Comment | Mos Link | FSSP Comment | FSSP Link | Block Comment | Block Link
        f3_cols = st.columns([3, 2, 1.2, 2, 1.2, 2, 1.2])
        
        with f3_cols[0]:
            current_debts = formatted_number_input("Текущие платежи по кредитам", "current_debts_input", value=default_current_debts)
            
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
        
        # Assets logic
        standard_assets = ["Машина", "Квартира", "Дом с ЗУ", "Коммерция", "Машиноместо", "Другое"]
        assets_default_selected = []
        other_val_extracted = ""

        # Parse defaults for multiselect
        for a in default_assets:
            if a in standard_assets:
                assets_default_selected.append(a)
            else:
                # If valid non-standard item (likely "Другое (...)"), select "Другое"
                if "Другое" not in assets_default_selected:
                    assets_default_selected.append("Другое")
                # Extract clean value if it follows the pattern "Другое (Value)"
                if a.startswith("Другое (") and a.endswith(")"):
                    other_val_extracted = a[8:-1] 
                else:
                    other_val_extracted = a

        assets_list = st.multiselect("Доп. активы", standard_assets, default=assets_default_selected)
        assets_str = ", ".join(assets_list)
        
        if "Другое" in assets_list:
            other_asset = st.text_input("Укажите другое имущество", value=other_val_extracted)
            if other_asset:
                assets_str += f" ({other_asset})" # Append parsed value for saving logic (note: this might duplicate if not careful with split next time, so we rely on the split logic handling it as a chunk)
            # Actually, standard logic was:  assets_str += f" ({other_asset})"
            # But wait, if we edit, assets_str will be reconstructed from selection + input.
            # If selection has "Другое", we append the input text. Correct.
        

        
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
            obj_area = formatted_number_input("Площадь (м2)", "obj_area_input", allow_float=True, value=default_obj_area)
        with o2:
            obj_floor = formatted_number_input("Этаж", "obj_floor_input", value=default_obj_floor)
        with o3:
            obj_total_floors = formatted_number_input("Этажность", "obj_total_floors_input", value=default_obj_total_floors)
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
        "job_official": "Да" if job_official else "Нет",
        "job_company": job_company,
        "job_sphere": job_industry,
        "job_found_date": str(job_date) if job_date else "",
        "job_ceo": job_ceo,
        "job_address": job_address,
        "job_phone": job_phone,
        "job_inn": job_inn,
        "job_pos": job_position,
        "job_income": job_income,
        "job_start_date": str(job_start_date) if job_start_date else "",
        "job_exp": exp_str,
        "total_exp": total_exp_val,
        "credit_sum": credit_sum,
        "loan_term": loan_term_years,
        "has_coborrower": has_coborrower,
        "first_pay": first_pay,
        "current_debts": current_debts,
        "assets": assets_str,
        "is_pledged": "Да" if is_pledged else "Нет",
        "pledge_bank": pledge_bank,
        "pledge_amount": pledge_amount,
        "mosgorsud_comment": mosgorsud_comment,
        "fssp_comment": fssp_comment,
        "block_comment": block_comment,
        
        # PRESERVE HIDDEN FIELDS (Prevent Data Loss on Edit)
        "bank_interactions": client_data.get('bank_interactions') if client_data else None,
        "yandex_link": client_data.get('yandex_link') if client_data else None
    }
    
    return data

# --- Page: Новый клиент (Editor) ---
if selected_page == "Новый клиент":
    # Check if we are in "Edit Mode"
    edit_client_id = st.session_state.get("editing_client_id")
    edit_client_data = None
    
    if edit_client_id:
        st.header("✏️ Редактирование клиента")
        # Load fresh data from DB to ensure we have latest (using cache is fine if we invalidate correctly)
        all_clients = get_cached_clients()
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
                get_cached_clients.clear() # Clear cache
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
                    get_cached_clients.clear() # Clear cache
                    st.success(f"Клиент {form_data['fio']} сохранен!")

# --- Page: База Клиентов ---
elif selected_page == "База Клиентов":
    st.title("📂 База Клиентов")
    
    df = get_cached_clients()
    


    if df.empty:
        st.info("База данных пуста. Добавьте первого клиента!")
    else:
        def safe_date_parse(x):
            # 1. Handle explicit None/NaN
            if pd.isna(x) or x is None:
                return None
            # 2. Handle string "None" / "nan" / empty
            s = str(x).strip()
            if s.lower() in ['none', 'nan', '']:
                return None
            # 3. Try to convert to simple date (no time)
            try:
                # Use pd.to_datetime but DO NOT coerce errors -> we want to know if it fails
                # transform to python date object
                val = pd.to_datetime(x)
                return val.date()
            except:
                # 4. If conversion fails, RETURN ORIGINAL VALUE (don't delete data!)
                return x

        # Apply safe parsing
        date_cols = ["created_at", "dob", "passport_date", "obj_date", "job_found_date", "job_start_date"]
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(safe_date_parse)
        


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
                "job_address": st.column_config.TextColumn("Адрес работы"),
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
                            "email": row.get('email', ''),
                            "job_address": row.get('job_address', '')
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
                get_cached_clients.clear() # Clear cache
                st.success("✅ Изменения сохранены!")
                st.rerun()

# --- Page: Карточка Клиента ---
elif selected_page == "Карточка Клиента":
    st.title("🗂 Карточка Клиента")
    df = get_cached_clients()
    if not df.empty:
        c_sel, _ = st.columns([1, 2])
        with c_sel:
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
            filtered = df[df["fio"] == selected_name]
            if not filtered.empty:
                client = filtered.iloc[0].to_dict()
            else:
                st.error(f"Клиент '{selected_name}' не найден в базе.")
                st.stop()
            

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
                banks_db = get_cached_banks().to_dict('records')
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
                    
                    st.markdown("#### 📄 Документы")
                    render_docs_generator(client, selected_bank, "card", banks_db)

                    

                    # --- Email Generation ---
                    st.markdown("#### 📧 Письмо")
                    
                    yandex_mail_url = generate_yandex_mail_link(client, selected_bank)
                    
                    if yandex_mail_url:
                        st.markdown(f"""
                        <a href="{yandex_mail_url}" target="_blank" style="display: inline-block; padding: 0.5em 1em; color: white; background-color: #ffcc00; border-radius: 5px; text-decoration: none;">
                        📧 Написать в банк
                        </a>
                        """, unsafe_allow_html=True)
                    else:
                        st.caption("Email банка не указан") 
                  
                    # Add Interaction
                    st.markdown("#### Добавить запись")
                    with st.form(key="card_add_inter_form"):
                        # Unified Bank Stage Options
                        BANK_STAGE_OPTIONS = ["Сделать", "Отправлено", "Рассмотрение", "Доп. запрос", "Одобрено", "Сделка", "Подписание", "Выдача", "Отказ", "Архив"]
                        new_stage = st.selectbox("Этап", BANK_STAGE_OPTIONS, key="card_new_stage")
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
                                get_cached_clients.clear() # Clear cache
                                st.success("Запись добавлена!")
                                st.rerun()
                            else:
                                st.error("Ошибка обновления: клиент не найден в базе.")

                # History Table
                st.subheader("История взаимодействий")
                
                # Prepare DF
                if interactions:
                    history_df = pd.DataFrame(interactions)
                    # Ensure 'completed' column exists
                    if "completed" not in history_df.columns:
                        history_df["completed"] = False
                    else:
                        # Ensure strictly boolean, filling NaNs with False
                        history_df["completed"] = history_df["completed"].fillna(False).astype(bool)
                    
                    # Reorder columns: completed first
                    cols = ["completed", "bank_name", "stage", "comment", "date"]
                    # Add missing cols if any (robustness)
                    for c in cols:
                        if c not in history_df.columns: 
                            history_df[c] = False if c == "completed" else ""
                    history_df = history_df[cols]
                else:
                    history_df = pd.DataFrame(columns=["completed", "bank_name", "stage", "comment", "date"])
                
                # Make editable
                edited_history = st.data_editor(
                    history_df,
                    key=f"history_editor_{client['id']}",
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config={
                        "completed": st.column_config.CheckboxColumn("✅", width="small"),
                        "bank_name": st.column_config.TextColumn("Банк", disabled=True), 
                        "stage": st.column_config.TextColumn("Этап"),
                        "comment": st.column_config.TextColumn("Комментарий"),
                        "date": st.column_config.TextColumn("Дата", disabled=True)
                    }
                )
                
                # Check for changes and save
                # We convert both to dict lists to compare, or just check size?
                # st.data_editor returns the new state. 
                # If we want to save immediately:
                new_inters = edited_history.to_dict('records')
                # Filter out empty rows if any (though dynamic usually handles this)
                
                # Compare with old (ignoring NaN vs None differences for robustness)
                if new_inters != interactions:
                     # Only save if different
                     # But 'interactions' might have None, new_inters might have NaNs?
                     # Let's clean new_inters
                     # Actually, simpliest is to just save if row count changed or basic content changed.
                     # But streamlit reruns on edit. So we can just save.
                     # Wait, if we save, it triggers rerun? 
                     # If we save, we strictly need to know it CHANGED from the DB version.
                     # 'interactions' comes from DB.
                     
                     # Simple equality check might fail on float/nan. 
                     # But these are strings mostly.
                     if len(new_inters) != len(interactions) or json.dumps(new_inters, sort_keys=True) != json.dumps(interactions, sort_keys=True):
                         current_db = db.load_clients()
                         # Find index by client ID
                         idx_matches = current_db.index[current_db['id'] == client['id']].tolist()
                         if idx_matches:
                             idx = idx_matches[0]
                             current_db.at[idx, 'bank_interactions'] = json.dumps(new_inters, ensure_ascii=False)
                             db.save_all_clients(current_db)
                             get_cached_clients.clear() # Clear cache
                         # st.toast("История обновлена!") 
                         # rerunning might lose focus? data_editor usually handles state.
                         # If we rely on streamlit's state preservation, we don't strictly need st.rerun() if data_editor updates locally?
                         # BUT we need to save to disk.
                         pass
                folder_name = get_client_folder_name(client)
                if not client.get('yandex_link') or client.get('yandex_link') == 'Ссылка не создана':
                    pass # Only create if strictly needed or requested? Previous logic created it forcefully here? 
                    # The previous logic was:
                    # new_link = create_yandex_folder(folder_name)
                    # ...
                    # But it seemingly did it on every render if link missing?
                    # Let's keep the folder creation check but REMOVE the file upload loop.
                    
                    # Actually, checking/creating folder on every render is slow?
                    # But get_client_folder_name does NOT make API calls if link exists.
                    # If link DOES NOT exist, we might want to create it?
                    # Let's preserve the creation logic if that was desired, but definitely remove the upload loop.
                    
                    try:
                         # Only try to create if we really have no link.
                         # But wait, create_yandex_folder might duplicate?
                         # For now, I will just COMMENT OUT the upload loop which is the bug.
                         pass
                    except:
                        pass
                
                # Removed redundant upload loop that caused persistent "All files uploaded" message.

# --- Page: База Банков ---
elif selected_page == "База Банков":
    st.title("🏦 Банки")
    df = get_cached_banks()
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

    save_col, msg_col, _ = st.columns([1, 1, 3])
    with save_col:
        save_clicked = st.button("💾 Сохранить изменения")
        
    if save_clicked:
        # Apply phone formatting to manually edited rows before saving
        if "manager_phone" in edited_df.columns:
            edited_df["manager_phone"] = edited_df["manager_phone"].apply(format_phone_string)
            
        # Use bulk save to handle deletions and avoid duplicates
        db.save_all_banks(edited_df)
        get_cached_banks.clear() # Clear cache
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
        get_cached_banks.clear() # Clear cache
        st.success("Банк добавлен")
        st.rerun()

# --- Page: Рабочий стол ---
elif selected_page == "Рабочий стол":
    st.title("🖥️ Рабочий стол")
    
    # 1. Load Data
    all_clients = get_cached_clients()
    
    if all_clients.empty:
        st.info("База клиентов пуста.")
    else:
        # Load banks for "Write to Bank" feature
        banks_db_df = get_cached_banks()
        banks_list = banks_db_df.to_dict('records') if not banks_db_df.empty else []
        
        # 2. Filters
        # Mimicking "База клиентов" style: multiselects with collapsed labels
        c_filter1, c_filter2 = st.columns(2)
        with c_filter1:
            # Status Filter
            statuses = all_clients['status'].unique().tolist()
            statuses = [s for s in statuses if s and str(s) != 'nan']
            # Using multiselect for consistency with DB tab, allowing multiple status selection
            selected_statuses = st.multiselect("Фильтр по статусу", options=statuses, placeholder="Выберите статус", label_visibility="collapsed")
            
        with c_filter2:
            # Transaction Type Filter (loan_type)
            loan_types = all_clients['loan_type'].unique().tolist()
            loan_types = [lt for lt in loan_types if lt and str(lt) != 'nan']
             # Using multiselect for consistency with DB tab
            selected_types = st.multiselect("Фильтр по типу", options=loan_types, placeholder="Выберите тип сделки", label_visibility="collapsed")
            
        # 3. Apply Filters
        filtered_df = all_clients.copy()
        
        # Filter by selected statuses (if any selected)
        if selected_statuses:
             filtered_df = filtered_df[filtered_df['status'].isin(selected_statuses)]
             
        # Filter by selected types (if any selected)
        if selected_types:
            filtered_df = filtered_df[filtered_df['loan_type'].isin(selected_types)]
            
        
        if filtered_df.empty:
            st.warning("Нет клиентов, соответствующих фильтрам.")
        else:
            # --- PAGINATION LOGIC ---
            ITEMS_PER_PAGE = 10
            if "desktop_page_number" not in st.session_state:
                st.session_state.desktop_page_number = 1
                
            total_items = len(filtered_df)
            total_pages = (total_items - 1) // ITEMS_PER_PAGE + 1
            
            # Ensure page number is valid
            if st.session_state.desktop_page_number > total_pages:
                st.session_state.desktop_page_number = total_pages
            if st.session_state.desktop_page_number < 1:
                st.session_state.desktop_page_number = 1
                
            current_page = st.session_state.desktop_page_number
            start_idx = (current_page - 1) * ITEMS_PER_PAGE
            end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
            
            # Slice the dataframe
            paginated_df = filtered_df.iloc[start_idx:end_idx]
            
            st.caption(f"Показаны клиенты {start_idx + 1}-{end_idx} из {total_items} (Страница {current_page} из {total_pages})")

            for index, client in paginated_df.iterrows():
                with st.container(border=True):
                    # Header: FIO + Status | Credit Sum + Type + Address
                    # Using HTML for tight control over spacing
                    c_head1, c_head2 = st.columns([3, 1])
                    
                    fio = client.get('fio', 'Без имени')
                    status = client.get('status', 'Новый')
                    
                    credit_sum = safe_int(client.get('credit_sum', 0))
                    credit_sum_str = f"{credit_sum:,}".replace(",", " ")
                    
                    obj_type = client.get('obj_type', '')
                    if not obj_type or str(obj_type) == 'nan':
                        obj_type = '-'
                        
                    # Build full address string
                    addr_parts = [
                        str(client.get('obj_city', '')), 
                        str(client.get('obj_street', ''))
                    ]
                    # Filter out empty/nano parts
                    addr_clean = [p for p in addr_parts if p and p != 'nan' and p != 'None']
                    obj_addr = ", ".join(addr_clean) if addr_clean else "-"

                    with c_head1:
                        # FIO + Status (Compact)
                        st.markdown(f"""
                        <div style="margin-bottom: 2px;">
                            <span style="font-size: 20px; font-weight: bold;">👤 {fio}</span>
                            <span style="font-size: 14px; background-color: #f0f2f6; padding: 2px 8px; border-radius: 4px; margin-left: 10px; color: #31333F;">{status}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                       
                    with c_head2:
                        # Sum (smaller font) -> Obj Type -> Address
                        st.markdown(f"""
                        <div style="text-align: right; line-height: 1.2;">
                            <div style="font-size: 12px; color: #888;">Сумма</div>
                            <div style="font-size: 18px; font-weight: bold;">{credit_sum_str}</div>
                            <div style="font-size: 12px; color: #333; margin-top: 4px;">{obj_type}</div>
                            <div style="font-size: 11px; color: #666;">{obj_addr}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Bank Interactions (Compact)
                    interactions_json = client.get('bank_interactions')
                    interactions = []
                    try:
                        if interactions_json and str(interactions_json) != 'nan':
                            interactions = json.loads(interactions_json)
                    except:
                        interactions = []
                        
                    if interactions:
                        # Yandex Disk Link (Between FIO and Header)
                        try:
                             f_name_link = get_client_folder_name(client)
                             # Encode the folder name to handle spaces for Markdown link
                             f_name_encoded = urllib.parse.quote(f_name_link)
                             yd_link = f"https://disk.yandex.ru/client/disk/{f_name_encoded}"
                             st.markdown(f"📂 [Папка на Яндекс.Диске]({yd_link})")
                        except:
                             pass
                             
                        st.markdown("**🏦 Работа с банками:**")
                        
                        for inter in interactions:
                            # inter: {bank_name, stage, comment, date}
                            bank = inter.get('bank_name', 'Неизвестный банк')
                            stage = inter.get('stage', '-')
                            comment = inter.get('comment', '-')
                            
                            # Sanitize comment to avoid Markdown rendering issues (huge fonts, etc)
                            if comment:
                                comment = str(comment).replace('\n', ' ').replace('#', '').replace('*', '').replace('_', '')
                            
                            # Compact line: [Bank] Stage: Comment
                            st.caption(f"🔹 {bank} | *{stage}* : {comment}")
                    else:
                        st.caption("Нет взаимодействий с банками.")
                        
                    # --- Action Buttons ---
                    # 5 buttons compact row
                    c_btn1, c_btn2, c_btn3, c_btn4, c_btn5 = st.columns([1, 1, 1, 1.2, 2])
                    
                    edit_key = f"edit_banks_{client['id']}"
                    write_key = f"write_bank_{client['id']}"
                    docs_key = f"docs_desk_{client['id']}"
                    
                    if edit_key not in st.session_state: st.session_state[edit_key] = False
                    if write_key not in st.session_state: st.session_state[write_key] = False
                    if docs_key not in st.session_state: st.session_state[docs_key] = False

                    with c_btn1:
                         if st.button("✏️ Клиент", key=f"btn_edit_client_{client['id']}"):
                            st.session_state.editing_client_id = client['id']
                            st.session_state.page = "Новый клиент" 
                            st.rerun()
                    
                    with c_btn2:
                        toggle_label = "❌ Закрыть" if st.session_state[edit_key] else "✏️ Банки"
                        if st.button(toggle_label, key=f"btn_edit_banks_{client['id']}"):
                            st.session_state[edit_key] = not st.session_state[edit_key]
                            if st.session_state[edit_key]: 
                                st.session_state[write_key] = False
                                st.session_state[docs_key] = False
                            st.rerun()

                    with c_btn3:
                        w_label = "❌ Закрыть" if st.session_state[write_key] else "📧 Письмо"
                        if st.button(w_label, key=f"btn_write_bank_{client['id']}"):
                            st.session_state[write_key] = not st.session_state[write_key]
                            if st.session_state[write_key]: 
                                st.session_state[edit_key] = False
                                st.session_state[docs_key] = False
                            st.rerun()
                    
                    with c_btn4:
                        d_label = "❌ Закрыть" if st.session_state[docs_key] else "📄 Документы"
                        if st.button(d_label, key=f"btn_docs_{client['id']}"):
                            st.session_state[docs_key] = not st.session_state[docs_key]
                            if st.session_state[docs_key]: 
                                st.session_state[edit_key] = False
                                st.session_state[write_key] = False
                            st.rerun()

                    with c_btn5:
                        desk_up = st.file_uploader("", accept_multiple_files=True, label_visibility="collapsed", key=f"desk_up_{client['id']}")
                        if desk_up and st.button("Отправить в облако", key=f"desk_up_btn_{client['id']}"):
                            folder_name = get_client_folder_name(client)
                            success_count = 0
                            with st.spinner(f"Загрузка..."):
                                for f in desk_up:
                                    f.seek(0)
                                    if upload_to_yandex(f, folder_name, f.name):
                                        success_count += 1
                            if success_count == len(desk_up):
                                st.toast(f"✅ Все файлы ({success_count}) загружены!", icon="☁️")
                            else:
                                st.toast(f"⚠️ Загружено {success_count} из {len(desk_up)}", icon="⚠️")



                    if st.session_state[edit_key]:
                        st.markdown("---")
                        st.markdown("**Редактирование взаимодействий:**")
                        # --- Inline Editor ---
                        # Prepare data for editor
                        
                        # Define options constant
                        BANK_STAGE_OPTIONS = ["Сделать", "Отправлено", "Рассмотрение", "Доп. запрос", "Одобрено", "Сделка", "Подписание", "Выдача", "Отказ", "Архив"]

                        current_interactions = []
                        if interactions_json and str(interactions_json) != 'nan':
                            try:
                                current_interactions = json.loads(interactions_json)
                            except:
                                pass
                        
                        # Convert to DataFrame
                        df_inter = pd.DataFrame(current_interactions)
                        if df_inter.empty:
                            df_inter = pd.DataFrame(columns=["bank_name", "stage", "comment", "date"])
                        
                        # Standardize columns
                        for col in ["bank_name", "stage", "comment", "date"]:
                            if col not in df_inter.columns:
                                df_inter[col] = ""
                                
                        # Handle Date objects for editor
                        if "date" in df_inter.columns:
                            df_inter["date"] = pd.to_datetime(df_inter["date"], errors="coerce")

                        # Merge options with existing stages to preserve custom data
                        existing_stages = [s for s in df_inter['stage'].unique() if s]
                        combined_stages = sorted(list(set(BANK_STAGE_OPTIONS + existing_stages)), key=lambda x: BANK_STAGE_OPTIONS.index(x) if x in BANK_STAGE_OPTIONS else 999)

                        edited_interactions = st.data_editor(
                            df_inter,
                            num_rows="dynamic",
                            column_config={
                                "bank_name": st.column_config.TextColumn("Банк", width="medium"),
                                "stage": st.column_config.SelectboxColumn(
                                    "Этап", 
                                    width="medium",
                                    options=combined_stages,
                                    required=True
                                ),
                                "comment": st.column_config.TextColumn("Комментарий", width="large"),
                                "date": st.column_config.DateColumn("Дата", format="DD.MM.YYYY")
                            },
                            key=f"editor_{client['id']}",
                            use_container_width=True
                        )
                        
                        if st.button("💾 Сохранить", key=f"save_banks_{client['id']}"):
                            # Save logic
                            # Convert date column back to string for JSON serialization
                            if "date" in edited_interactions.columns:
                                edited_interactions["date"] = edited_interactions["date"].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else None)
                                
                            new_interactions = edited_interactions.to_dict(orient="records")
                            new_json = json.dumps(new_interactions, ensure_ascii=False)
                            
                            # Update DB
                            # We load fresh DB to avoid collisions
                            curr_db = db.load_clients()
                            # Ensure ID types match
                            curr_db['id'] = curr_db['id'].astype(str)
                            c_id = str(client['id']).replace('.0', '')
                            
                            idx = curr_db[curr_db['id'] == c_id].index
                            if not idx.empty:
                                curr_db.at[idx[0], 'bank_interactions'] = new_json
                                db.save_all_clients(curr_db)
                                get_cached_clients.clear()
                                st.toast("✅ Сохранено!")
                                st.session_state[edit_key] = False
                                st.rerun()
                            else:
                                st.error("Ошибка обновления: клиент не найден")
                    
                    if st.session_state[write_key]:
                        st.markdown("---")
                        
                        wb_c1, wb_c2 = st.columns([1, 2])
                        bank_names_list = [b['name'] for b in banks_list]
                        
                        sel_bank_name = wb_c1.selectbox("Выберите банк", bank_names_list, key=f"desk_sel_bank_{client['id']}", index=None, placeholder="Выберите банк...", label_visibility="collapsed")
                        
                        if sel_bank_name:
                            sel_bank = next((b for b in banks_list if b['name'] == sel_bank_name), None)
                            if sel_bank:
                                # Generate Link
                                link = generate_yandex_mail_link(client, sel_bank)
                                
                                with wb_c2:
                                    if link:
                                        st.markdown(f"""
                                        <a href="{link}" target="_blank" style="display: inline-block; padding: 0.5em 1em; color: white; background-color: #ffcc00; border-radius: 5px; text-decoration: none;">
                                        📧 Написать в банк
                                        </a>
                                        """, unsafe_allow_html=True)
                                    else:
                                        st.warning("Нет email у банка или менеджера.")
                    
                    if st.session_state[docs_key]:
                        st.markdown("---")
                        st.markdown("**📄 Генерация документов**")
                        
                        # Bank selector (local for docs)
                        bank_names_list = [b['name'] for b in banks_list]
                        
                        # Reuse or new selector? Better specific selector
                        d_sel_bank_name = st.selectbox("Выберите банк для шаблонов", bank_names_list, key=f"docs_sel_bank_{client['id']}", index=None, placeholder="Выберите банк...", label_visibility="collapsed")
                        
                        if d_sel_bank_name:
                            d_sel_bank = next((b for b in banks_list if b['name'] == d_sel_bank_name), None)
                            if d_sel_bank:
                                render_docs_generator(client, d_sel_bank, f"desk_docs_{client['id']}", banks_list)

            # --- Pagination Controls ---
            st.markdown("---")
            p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
            with p_col1:
                if current_page > 1:
                    if st.button("⬅️ Назад", key="page_prev"):
                        st.session_state.desktop_page_number -= 1
                        st.rerun()
            
            with p_col2:
                st.markdown(f"<div style='text-align: center; padding-top: 10px;'>Страница {current_page} из {total_pages}</div>", unsafe_allow_html=True)

            with p_col3:
                if current_page < total_pages:
                    if st.button("Вперед ➡️", key="page_next"):
                        st.session_state.desktop_page_number += 1
                        st.rerun()