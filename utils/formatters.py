"""
Formatting utilities for strings, numbers, and phone numbers.
"""
import pandas as pd
from typing import Union, Optional


def clean_value(val: any, default: str = "") -> str:
    """
    Clean a value by removing NaN, None, and converting to string.
    This replaces the repeated pattern: str(x).replace('nan', '').replace('None', '')
    """
    if val is None or pd.isna(val):
        return default
    s = str(val)
    if s.lower() in ('nan', 'none', ''):
        return default
    return s


def clean_int_str(val: any) -> str:
    """
    Clean string values that might be read as floats from Excel.
    E.g., '123.0' -> '123', 'nan' -> ''
    """
    s = str(val)
    if s.lower() in ('nan', 'none', ''):
        return ""
    if s.endswith(".0"):
        return s[:-2]
    return s


def safe_int(val: any, default: int = 0) -> int:
    """
    Safely convert value to int, returning default on failure.
    """
    try:
        if pd.isna(val) or str(val).lower() in ('nan', 'none', ''):
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


def format_phone_string(phone_str: str) -> str:
    """
    Format a phone string to +7 XXX XXX XX XX format.
    """
    if not phone_str:
        return ""
    
    # Remove all non-digits
    clean = ''.join(c for c in str(phone_str) if c.isdigit())
    
    if not clean:
        return ""
    
    # Normalize: handle 11-digit numbers starting with 8 or 7
    if len(clean) == 11:
        if clean.startswith('8'):
            clean = '7' + clean[1:]
        elif not clean.startswith('7'):
            pass  # Keep as is for non-Russian numbers
    elif len(clean) == 10:
        clean = '7' + clean
    
    # Format: +7 XXX XXX XX XX
    if len(clean) >= 11 and clean.startswith('7'):
        digits = clean[:11]
        return f"+7 {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"
    
    # Fallback: return original or cleaned
    return phone_str if phone_str else ""


def format_number_with_spaces(num: Union[int, float], allow_float: bool = False) -> str:
    """
    Format a number with space as thousands separator.
    E.g., 1234567 -> '1 234 567'
    """
    try:
        if allow_float:
            return f"{float(num):,.2f}".replace(",", " ").replace(".", ",")
        return f"{int(num):,}".replace(",", " ")
    except (ValueError, TypeError):
        return "0"
