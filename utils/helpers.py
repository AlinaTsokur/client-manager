"""
Helper utilities for various operations.
"""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Tuple, Optional
import pandas as pd


def parse_fio(fio_str: str) -> Tuple[str, str, str]:
    """
    Split FIO string into surname, name, patronymic.
    
    Returns:
        Tuple of (surname, name, patronymic)
    """
    if not fio_str:
        return "", "", ""
    parts = str(fio_str).strip().split()
    surname = parts[0] if len(parts) > 0 else ""
    name = parts[1] if len(parts) > 1 else ""
    patronymic = " ".join(parts[2:]) if len(parts) > 2 else ""
    return surname, name, patronymic


def calculate_age(dob: object) -> Optional[int]:
    """
    Calculate age from date of birth.
    
    Args:
        dob: Date of birth (date, datetime, or string)
        
    Returns:
        Age in years or None if invalid
    """
    if not dob:
        return None
    try:
        if isinstance(dob, str):
            if dob.lower() in ('none', 'nan', ''):
                return None
            dob = pd.to_datetime(dob).date()
        elif isinstance(dob, datetime):
            dob = dob.date()
        elif not isinstance(dob, date):
            return None
        
        return relativedelta(datetime.now().date(), dob).years
    except Exception:
        return None


def transliterate(text: str) -> str:
    """
    Transliterate Russian text to Latin for folder names.
    """
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
    result = []
    for char in text:
        if char in mapping:
            result.append(mapping[char])
        elif char.isalnum():
            result.append(char)
    
    return "".join(result).strip('_')


def get_current_timestamp() -> str:
    """Get current datetime as formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_date_format(date_val, format_str: str = "%d.%m.%Y") -> str:
    """
    Safely format a date value to string.
    
    Args:
        date_val: Date value (date, datetime, pd.Timestamp, or string)
        format_str: Output format string
        
    Returns:
        Formatted date string or empty string if invalid
    """
    if not date_val:
        return ""
    try:
        if isinstance(date_val, str):
            if date_val.lower() in ('none', 'nan', ''):
                return ""
            date_val = pd.to_datetime(date_val)
        
        # Use hasattr to support datetime, date, and pd.Timestamp
        if hasattr(date_val, "strftime"):
            return date_val.strftime(format_str)
        
        return ""
    except Exception:
        return ""


def build_address(client: dict, prefix: str = "addr") -> str:
    """
    Build full address string from client data.
    
    Args:
        client: Client data dict
        prefix: Field prefix ('addr' for registration, 'obj' for property)
    
    Returns:
        Formatted address string
    """
    parts = []
    
    index_val = str(client.get(f"{prefix}_index", "") or "").strip()
    if index_val and index_val.lower() not in ("nan", "none", ""):
        parts.append(index_val)
    
    region = str(client.get(f"{prefix}_region", "") or "").strip()
    if region and region.lower() not in ("nan", "none", ""):
        parts.append(region)
    
    city = str(client.get(f"{prefix}_city", "") or "").strip()
    if city and city.lower() not in ("nan", "none", ""):
        parts.append(f"г. {city}")
    
    street = str(client.get(f"{prefix}_street", "") or "").strip()
    if street and street.lower() not in ("nan", "none", ""):
        parts.append(f"ул. {street}")
    
    house = str(client.get(f"{prefix}_house", "") or "").strip()
    if house and house.lower() not in ("nan", "none", ""):
        parts.append(f"д. {house}")
    
    korpus = str(client.get(f"{prefix}_korpus", "") or "").strip()
    if korpus and korpus.lower() not in ("nan", "none", ""):
        parts.append(f"корп. {korpus}")
    
    structure = str(client.get(f"{prefix}_structure", "") or "").strip()
    if structure and structure.lower() not in ("nan", "none", ""):
        parts.append(f"стр. {structure}")
    
    flat = str(client.get(f"{prefix}_flat", "") or "").strip()
    if flat and flat.lower() not in ("nan", "none", ""):
        parts.append(f"кв. {flat}")
    
    return ", ".join(parts)


def format_client_info(client: dict) -> str:
    """
    Format client info as compact text for easy copying.
    
    Args:
        client: Client data dict
    
    Returns:
        Formatted multi-line string
    """
    lines = []
    
    # FIO
    fio = str(client.get("fio", "") or "").strip()
    if fio:
        lines.append(f"ФИО: {fio}")
    
    # DOB + Birth Place
    dob = safe_date_format(client.get("dob"), "%d.%m.%Y")
    birth_place = str(client.get("birth_place", "") or "").strip()
    if dob:
        line = f"Дата рождения: {dob}"
        if birth_place and birth_place.lower() not in ("nan", "none", ""):
            line += f", {birth_place}"
        lines.append(line)
    
    # Passport
    pass_ser = str(client.get("passport_ser", "") or "").strip()
    pass_num = str(client.get("passport_num", "") or "").strip()
    pass_issued = str(client.get("passport_issued", "") or "").strip()
    pass_date = safe_date_format(client.get("passport_date"), "%d.%m.%Y")
    kpp = str(client.get("kpp", "") or "").strip()
    
    if pass_ser or pass_num:
        passport_line = f"Паспорт: {pass_ser} {pass_num}"
        if kpp and kpp.lower() not in ("nan", "none", ""):
            passport_line += f", код {kpp}"
        if pass_date:
            passport_line += f", выдан {pass_date}"
        if pass_issued and pass_issued.lower() not in ("nan", "none", ""):
            passport_line += f", {pass_issued}"
        lines.append(passport_line)
    
    # Phone
    phone = str(client.get("phone", "") or "").strip()
    if phone and phone.lower() not in ("nan", "none", ""):
        lines.append(f"Телефон: {phone}")
    
    # Registration address
    reg_addr = build_address(client, "addr")
    if reg_addr:
        lines.append(f"Адрес регистрации: {reg_addr}")
    
    # Object/Property info
    obj_type = str(client.get("obj_type", "") or "").strip()
    obj_area = client.get("obj_area", "")
    obj_addr = build_address(client, "obj")
    
    if obj_type and obj_type.lower() not in ("nan", "none", ""):
        prop_line = f"Объект: {obj_type}"
        if obj_area and str(obj_area).lower() not in ("nan", "none", "") and str(obj_area).strip() not in ("0", "0.0", "0.00", "0,0", "0,00"):
            prop_line += f", {obj_area} м²"
        lines.append(prop_line)
    
    if obj_addr:
        lines.append(f"Адрес объекта: {obj_addr}")
    
    # Document type + date
    obj_doc_type = str(client.get("obj_doc_type", "") or "").strip()
    obj_date = safe_date_format(client.get("obj_date"), "%d.%m.%Y")
    
    if obj_doc_type and obj_doc_type.lower() not in ("nan", "none", ""):
        doc_line = f"Правоустановка: {obj_doc_type}"
        if obj_date:
            doc_line += f" от {obj_date}"
        lines.append(doc_line)
    
    return "\n".join(lines)
