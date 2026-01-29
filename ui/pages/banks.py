"""
Banks page - База Банков.
"""
import streamlit as st
import json
import uuid
import math
import pandas as pd

from config.constants import BANK_PROGRAM_OPTIONS, BANK_OBJECT_OPTIONS
from database.repository import BankRepository
from ui.components import formatted_phone_input


def _safe_float(value, default=None):
    """Safely convert value to float, handling None and nan."""
    if value is None:
        return default
    try:
        result = float(value)
        if math.isnan(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def _safe_int(value, default=None):
    """Safely convert value to int, handling None and nan."""
    if value is None:
        return default
    try:
        result = float(value)
        if math.isnan(result):
            return default
        return int(result)
    except (ValueError, TypeError):
        return default


def _parse_json_field(value, default):
    """Parse JSON field from string or return as-is if already parsed."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return default
    return value if value else default


def _format_list_for_display(value):
    """Convert list/JSON to comma-separated string."""
    parsed = _parse_json_field(value, [])
    if isinstance(parsed, list):
        return ", ".join(parsed) if parsed else "—"
    if isinstance(parsed, dict):
        return ", ".join(parsed.keys()) if parsed else "—"
    return "—"


def _get_programs_list(bank):
    """Get list of active programs based on objects."""
    programs = []
    ipoteka = _parse_json_field(bank.get("ipoteka_objects"), [])
    zalog = _parse_json_field(bank.get("zalog_objects"), [])
    lizing = _parse_json_field(bank.get("lizing_objects"), [])
    
    if ipoteka:
        programs.append("Ипотека")
    if zalog:
        programs.append("Залог")
    if lizing:
        programs.append("Лизинг")
    
    return ", ".join(programs) if programs else "—"


def _get_all_objects(bank):
    """Get combined list of all objects from all programs."""
    objects = set()
    
    ipoteka = _parse_json_field(bank.get("ipoteka_objects"), [])
    if isinstance(ipoteka, list):
        objects.update(ipoteka)
    elif isinstance(ipoteka, dict):
        objects.update(ipoteka.keys())
    
    zalog = _parse_json_field(bank.get("zalog_objects"), [])
    if isinstance(zalog, list):
        objects.update(zalog)
    
    lizing = _parse_json_field(bank.get("lizing_objects"), [])
    if isinstance(lizing, list):
        objects.update(lizing)
    
    return ", ".join(sorted(objects)) if objects else "—"


def render_banks_page(bank_repo: BankRepository, get_cached_banks, clear_cache):
    """Render the banks management page."""
    st.title("🏦 Банки")
    df = get_cached_banks()
    
    if not df.empty:
        df = df.sort_values("name", na_position="last")
        
        # Prepare display DataFrame
        display_df = pd.DataFrame()
        display_df["Название"] = df["name"].fillna("—")
        display_df["Менеджер"] = df["manager_fio"].fillna("—")
        display_df["Программы"] = df.apply(lambda r: _get_programs_list(r), axis=1)
        display_df["Объекты"] = df.apply(lambda r: _get_all_objects(r), axis=1)
        
        # Term and Amount - show only if set
        def format_range(row, min_col, max_col, suffix=""):
            min_val = _safe_int(row.get(min_col))
            max_val = _safe_int(row.get(max_col))
            if min_val is None and max_val is None:
                return "—"
            min_str = str(min_val) if min_val is not None else "?"
            max_str = str(max_val) if max_val is not None else "?"
            return f"{min_str}–{max_str}{suffix}"
        
        display_df["Срок"] = df.apply(lambda r: format_range(r, "term_min", "term_max"), axis=1)
        display_df["Сумма (млн)"] = df.apply(lambda r: format_range(r, "amount_min", "amount_max"), axis=1)
        display_df["ЛК"] = df["lk_link"] if "lk_link" in df.columns else None
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ЛК": st.column_config.LinkColumn(
                    "Личный кабинет",
                    display_text="🔗 Вход",
                    help="Ссылка на личный кабинет банка",
                    width="small"
                )
            }
        )
        
        # --- Edit section ---
        st.markdown("---")
        st.subheader("✏️ Редактирование банка")
        
        bank_names = df["name"].dropna().tolist()
        selected_bank_name = st.selectbox(
            "Выберите банк",
            options=[""] + bank_names,
            index=0,
            placeholder="Выберите банк для редактирования...",
            label_visibility="collapsed"
        )
        
        if selected_bank_name:
            bank_row = df[df["name"] == selected_bank_name].iloc[0]
            bank = bank_row.to_dict()
            bank_id = str(bank.get("id", ""))
            
            # Parse program-specific fields
            ipoteka_objects = _parse_json_field(bank.get("ipoteka_objects"), [])
            ipoteka_pv = _parse_json_field(bank.get("ipoteka_pv"), {})
            zalog_objects = _parse_json_field(bank.get("zalog_objects"), [])
            lizing_objects = _parse_json_field(bank.get("lizing_objects"), [])
            
            with st.container():
                st.markdown(f"**Редактирование: {selected_bank_name}**")
                
                # Basic info
                e_r1_c1, e_r1_c2, e_r1_c3 = st.columns(3)
                e_name = e_r1_c1.text_input("Название", value=bank.get("name", ""), key=f"e_name_{bank_id}")
                e_manager = e_r1_c2.text_input("Менеджер", value=bank.get("manager_fio", "") or "", key=f"e_manager_{bank_id}")
                with e_r1_c3:
                    e_phone = formatted_phone_input("Телефон", f"e_phone_{bank_id}", value=bank.get("manager_phone", "") or "")
                
                e_r2_c1, e_r2_c2, e_r2_c3, e_r2_c4 = st.columns(4)
                e_email = e_r2_c1.text_input("Email", value=bank.get("manager_email", "") or "", key=f"e_email_{bank_id}")
                e_email2 = e_r2_c2.text_input("Email 2", value=bank.get("email2", "") or "", key=f"e_email2_{bank_id}")
                e_email3 = e_r2_c3.text_input("Email 3", value=bank.get("email3", "") or "", key=f"e_email3_{bank_id}")
                e_lk = e_r2_c4.text_input("ЛК", value=bank.get("lk_link", "") or "", key=f"e_lk_{bank_id}")
                
                e_address = st.text_input("Адрес", value=bank.get("address", "") or "", key=f"e_addr_{bank_id}")
                
                # === ИПОТЕКА ===
                st.markdown("---")
                st.markdown("### 🏠 Ипотека")
                
                e_ipoteka_objects = st.multiselect(
                    "Объекты (Ипотека)",
                    options=BANK_OBJECT_OPTIONS,
                    default=[o for o in ipoteka_objects if o in BANK_OBJECT_OPTIONS],
                    key=f"e_ipoteka_obj_{bank_id}"
                )
                
                # PV for selected ipoteka objects
                e_ipoteka_pv = {}
                if e_ipoteka_objects:
                    st.markdown("**ПВ (%):** *(оставьте пустым если неизвестно)*")
                    pv_cols = st.columns(4)
                    for i, obj in enumerate(e_ipoteka_objects):
                        with pv_cols[i % 4]:
                            current_pv = ipoteka_pv.get(obj)
                            pv_val = st.number_input(
                                obj,
                                min_value=0,
                                max_value=100,
                                value=_safe_int(current_pv, 0),
                                step=5,
                                key=f"e_pv_{bank_id}_{obj}"
                            )
                            if pv_val > 0:
                                e_ipoteka_pv[obj] = pv_val
                
                # === ЗАЛОГ ===
                st.markdown("---")
                st.markdown("### 🏦 Залог")
                
                e_zalog_objects = st.multiselect(
                    "Объекты (Залог)",
                    options=BANK_OBJECT_OPTIONS,
                    default=[o for o in zalog_objects if o in BANK_OBJECT_OPTIONS],
                    key=f"e_zalog_obj_{bank_id}"
                )
                
                e_zalog_kz = None
                if e_zalog_objects:
                    current_kz = _safe_int(bank.get("zalog_kz"))
                    e_zalog_kz = st.number_input(
                        "КЗ max (%)",
                        min_value=0,
                        max_value=100,
                        value=current_kz if current_kz else 0,
                        key=f"e_zalog_kz_{bank_id}"
                    )
                    if e_zalog_kz == 0:
                        e_zalog_kz = None
                
                # === ЛИЗИНГ ===
                st.markdown("---")
                st.markdown("### 🚗 Лизинг")
                
                e_lizing_objects = st.multiselect(
                    "Объекты (Лизинг)",
                    options=BANK_OBJECT_OPTIONS,
                    default=[o for o in lizing_objects if o in BANK_OBJECT_OPTIONS],
                    key=f"e_lizing_obj_{bank_id}"
                )
                
                e_lizing_kz = None
                if e_lizing_objects:
                    current_kz = _safe_int(bank.get("lizing_kz"))
                    e_lizing_kz = st.number_input(
                        "КЗ max (%)",
                        min_value=0,
                        max_value=100,
                        value=current_kz if current_kz else 0,
                        key=f"e_lizing_kz_{bank_id}"
                    )
                    if e_lizing_kz == 0:
                        e_lizing_kz = None
                
                # === Common fields ===
                st.markdown("---")
                st.markdown("### ⚙️ Общие условия")
                
                range_cols = st.columns(4)
                with range_cols[0]:
                    e_term_min = st.number_input("Срок от (мес)", value=_safe_int(bank.get("term_min"), 0), min_value=0, key=f"e_term_min_{bank_id}")
                    e_term_max = st.number_input("Срок до (мес)", value=_safe_int(bank.get("term_max"), 0), min_value=0, key=f"e_term_max_{bank_id}")
                with range_cols[1]:
                    e_amount_min = st.number_input("Сумма от (млн)", value=_safe_float(bank.get("amount_min"), 0.0), min_value=0.0, step=0.1, key=f"e_amt_min_{bank_id}")
                    e_amount_max = st.number_input("Сумма до (млн)", value=_safe_float(bank.get("amount_max"), 0.0), min_value=0.0, step=1.0, key=f"e_amt_max_{bank_id}")
                with range_cols[2]:
                    e_age_min = st.number_input("Возраст от", value=_safe_int(bank.get("age_min"), 0), min_value=0, key=f"e_age_min_{bank_id}")
                    e_age_max = st.number_input("Возраст до", value=_safe_int(bank.get("age_max"), 0), min_value=0, key=f"e_age_max_{bank_id}")
                with range_cols[3]:
                    e_encumbrance = st.checkbox("Обременение", value=bool(bank.get("allows_encumbrance", False)), key=f"e_enc_{bank_id}")
                    e_renovation = st.checkbox("Реновация", value=bool(bank.get("allows_renovation", False)), key=f"e_ren_{bank_id}")
                
                # Save/Delete buttons
                btn_cols = st.columns([1, 1, 4])
                with btn_cols[0]:
                    if st.button("💾 Сохранить", key=f"save_{bank_id}", type="primary"):
                        if not e_name.strip():
                            st.error("Название банка обязательно!")
                        else:
                            updated_bank = {
                                "id": bank_id,
                                "name": e_name.strip(),
                                "manager_fio": e_manager or None,
                                "manager_phone": e_phone or None,
                                "manager_email": e_email or None,
                                "email2": e_email2 or None,
                                "email3": e_email3 or None,
                                "lk_link": e_lk or None,
                                "address": e_address or None,
                                # Program-specific
                                "ipoteka_objects": e_ipoteka_objects if e_ipoteka_objects else [],
                                "ipoteka_pv": e_ipoteka_pv if e_ipoteka_pv else {},
                                "zalog_objects": e_zalog_objects if e_zalog_objects else [],
                                "zalog_kz": e_zalog_kz,
                                "lizing_objects": e_lizing_objects if e_lizing_objects else [],
                                "lizing_kz": e_lizing_kz,
                                # Common - save None if 0
                                "term_min": e_term_min if e_term_min else None,
                                "term_max": e_term_max if e_term_max else None,
                                "amount_min": e_amount_min if e_amount_min else None,
                                "amount_max": e_amount_max if e_amount_max else None,
                                "age_min": e_age_min if e_age_min else None,
                                "age_max": e_age_max if e_age_max else None,
                                "allows_encumbrance": e_encumbrance,
                                "allows_renovation": e_renovation
                            }
                            if bank_repo.save(updated_bank):
                                clear_cache()
                                st.toast("✅ Банк обновлён!")
                                st.rerun()
                            else:
                                st.error("Ошибка сохранения")
                with btn_cols[1]:
                    if st.button("🗑️ Удалить", key=f"delete_{bank_id}"):
                        if bank_repo.delete(bank_id):
                            clear_cache()
                            st.toast("🗑️ Банк удалён!")
                            st.rerun()
                        else:
                            st.error("Ошибка удаления")
    
    # --- Add new bank ---
    st.markdown("---")
    st.subheader("➕ Добавить банк")
    
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    b_name = r1_c1.text_input("Название", key="new_bank_name")
    b_address = r1_c2.text_input("Адрес", key="new_bank_addr")
    b_manager = r1_c3.text_input("Менеджер", key="new_bank_manager")
    with r1_c4:
        b_phone = formatted_phone_input("Телефон", "bank_new_phone")
    
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
    b_email = r2_c1.text_input("Email", key="new_bank_email")
    b_email2 = r2_c2.text_input("Email 2", key="new_bank_email2")
    b_email3 = r2_c3.text_input("Email 3", key="new_bank_email3")
    b_lk = r2_c4.text_input("Ссылка на ЛК", placeholder="https://...", key="new_bank_lk")
    
    if st.button("Добавить", type="primary", key="add_new_bank"):
        if not b_name.strip():
            st.error("Название банка обязательно!")
        else:
            bank_data = {
                "id": str(uuid.uuid4()),
                "name": b_name.strip(),
                "address": b_address or None,
                "manager_fio": b_manager or None,
                "manager_phone": b_phone or None,
                "manager_email": b_email or None,
                "email2": b_email2 or None,
                "email3": b_email3 or None,
                "lk_link": b_lk or None,
                "ipoteka_objects": [],
                "ipoteka_pv": {},
                "zalog_objects": [],
                "zalog_kz": None,
                "lizing_objects": [],
                "lizing_kz": None,
                "term_min": None,
                "term_max": None,
                "amount_min": None,
                "amount_max": None,
                "age_min": None,
                "age_max": None,
                "allows_encumbrance": False,
                "allows_renovation": False
            }
            if bank_repo.save(bank_data):
                clear_cache()
                st.success("Банк добавлен!")
                st.rerun()
