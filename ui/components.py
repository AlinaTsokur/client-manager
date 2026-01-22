"""
Reusable UI components for Streamlit.
"""
import streamlit as st
from typing import Optional, Callable, List
import urllib.parse

from utils.formatters import safe_int


def formatted_number_input(
    label: str, 
    key: str, 
    allow_float: bool = False, 
    value: Optional[float] = None
) -> float:
    """
    Number input with space-separated formatting.
    
    Args:
        label: Input label
        key: Streamlit key
        allow_float: Allow decimal values
        value: Initial value
        
    Returns:
        Numeric value
    """
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
            val = val.replace(",", ".")
            clean = "".join(c for c in val if c.isdigit() or c == ".")
            if clean.count(".") > 1:
                clean = clean.replace(".", "", clean.count(".") - 1)
            
            if clean:
                parts = clean.split(".")
                int_part = "{:,}".format(int(parts[0])).replace(",", " ")
                formatted = f"{int_part}.{parts[1]}" if len(parts) > 1 else int_part
                st.session_state[key] = formatted
            else:
                st.session_state[key] = ""
        else:
            clean = "".join(c for c in val if c.isdigit())
            if clean:
                formatted = "{:,}".format(int(clean)).replace(",", " ")
                st.session_state[key] = formatted
            else:
                st.session_state[key] = ""
    
    st.text_input(label, key=key, on_change=on_change)
    
    val = st.session_state[key]
    if allow_float:
        clean = val.replace(" ", "")
        try:
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0
    else:
        clean = "".join(c for c in val if c.isdigit())
        return int(clean) if clean else 0


def formatted_phone_input(
    label: str, 
    key: str, 
    value: Optional[str] = None
) -> str:
    """
    Phone input with Russian format (+7 XXX XXX XX XX).
    
    Args:
        label: Input label
        key: Streamlit key
        value: Initial value
        
    Returns:
        Formatted phone string
    """
    if key not in st.session_state:
        st.session_state[key] = value if value else ""
    
    def on_change():
        val = st.session_state[key]
        clean = "".join(c for c in val if c.isdigit())
        
        if not clean:
            st.session_state[key] = ""
            return
        
        # Ensure starts with 7
        if clean.startswith("8"):
            clean = "7" + clean[1:]
        elif not clean.startswith("7"):
            clean = "7" + clean
        
        # Limit to 11 digits
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


def generate_yandex_mail_link(client: dict, bank: dict) -> Optional[str]:
    """
    Generate Yandex Mail compose link with pre-filled data.
    
    Args:
        client: Client data dictionary
        bank: Bank data dictionary
        
    Returns:
        Yandex Mail URL or None
    """
    from utils.formatters import clean_int_str, clean_value
    
    emails_to = []
    manager_email = clean_value(bank.get("manager_email"))
    if manager_email:
        emails_to.append(manager_email)
    
    emails_cc = []
    for field in ["email2", "email3"]:
        email = clean_value(bank.get(field))
        if email:
            emails_cc.append(email)
    
    if not emails_to and emails_cc:
        emails_to.append(emails_cc.pop(0))
    
    if not emails_to:
        return None
    
    # Build subject
    c_surname = client.get("surname", "") or (client.get("fio", "").split()[0] if client.get("fio") else "")
    c_name = client.get("name", "")
    if not c_name and client.get("fio") and len(client.get("fio", "").split()) > 1:
        c_name = client.get("fio", "").split()[1]
    
    subj_parts = [
        f"{c_surname} {c_name}",
        f"{client.get('obj_type', '')} {client.get('loan_type', '')} {client.get('obj_city', '')}",
        f"{safe_int(client.get('credit_sum', 0)):,} руб."
    ]
    subj = " / ".join(filter(None, subj_parts))
    
    # Build body
    lines = [
        "Добрый день!",
        f"Прошу рассмотреть заявку по клиенту: {client.get('fio')}",
        "",
        "--- ПАРАМЕТРЫ СДЕЛКИ ---",
        f"Программа: {client.get('loan_type')}",
        f"Сумма кредита: {safe_int(client.get('credit_sum', 0)):,} руб.",
        "",
        "--- ПОРТРЕТ КЛИЕНТА ---",
        f"Возраст: {safe_int(client.get('age', 0))} лет",
        f"Доход: {client.get('job_type')}",
    ]
    
    if client.get("has_coborrower") == "Да":
        lines.append("Созаемщик: ЕСТЬ")
    
    assets = clean_value(client.get("assets"))
    if assets:
        lines.append(f"Доп. активы: {assets}")
    
    lines.extend([
        "",
        "--- ОБЪЕКТ ЗАЛОГА ---",
        f"Тип: {client.get('obj_type')}",
    ])
    
    # Build address
    addr_parts = [
        clean_int_str(client.get("obj_index", "")),
        clean_value(client.get("obj_region")),
        clean_value(client.get("obj_city")),
        clean_value(client.get("obj_street")),
        f"д. {clean_int_str(client.get('obj_house', ''))}" if client.get("obj_house") else "",
        f"корп. {clean_int_str(client.get('obj_korpus', ''))}" if client.get("obj_korpus") else "",
        f"стр. {clean_int_str(client.get('obj_structure', ''))}" if client.get("obj_structure") else "",
        f"кв. {clean_int_str(client.get('obj_flat', ''))}" if client.get("obj_flat") else "",
    ]
    full_addr = ", ".join([p for p in addr_parts if p])
    lines.append(f"Адрес: {full_addr}")
    lines.append(f"Стоимость: {safe_int(client.get('obj_price', 0)):,} руб.")
    
    if client.get("is_pledged") == "Да":
        lines.append(f"Обременение: ЕСТЬ ({client.get('pledge_bank')}, остаток {safe_int(client.get('pledge_amount', 0)):,} руб.)")
    else:
        lines.append("Обременение: НЕТ")
    
    body_text = "\n".join(lines)
    
    # Build URL
    to_str = ",".join(emails_to)
    cc_str = ",".join(emails_cc)
    
    params = f"to={to_str}"
    if cc_str:
        params += f"&cc={cc_str}"
    params += f"&subj={urllib.parse.quote(subj)}&body={urllib.parse.quote(body_text)}"
    
    return f"https://mail.yandex.ru/compose?{params}"
