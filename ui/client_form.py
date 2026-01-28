"""
Complete client form renderer with all fields.
"""
import streamlit as st
import pandas as pd
import json
import streamlit.components.v1 as components
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from config.constants import (
    STATUS_OPTIONS, LOAN_TYPE_OPTIONS, GENDER_OPTIONS, FAMILY_STATUS_OPTIONS,
    MARRIAGE_CONTRACT_OPTIONS, JOB_TYPE_OPTIONS, JOB_OFFICIAL_OPTIONS,
    OBJ_TYPE_OPTIONS, OBJ_DOC_TYPE_OPTIONS, OBJ_WALLS_OPTIONS, ASSET_OPTIONS, YES_NO_OPTIONS
)
from utils.formatters import clean_value, clean_int_str, safe_int
from utils.helpers import parse_fio
from ui.components import formatted_number_input, formatted_phone_input


def render_client_form(client_data=None, key_prefix=""):
    """
    Render the complete client form for new/edit operations.
    
    Args:
        client_data: Existing client data dict for edit mode, or None for new client
        key_prefix: Prefix for Streamlit widget keys to avoid duplicates
    
    Returns:
        dict: Form data collected from user input
    """
    
    # === Default Values ===
    default_fio = clean_value(client_data.get("fio")) if client_data else ""
    default_status = client_data.get("status") if client_data else None
    default_loan_type = client_data.get("loan_type") if client_data else None
    default_credit_sum = client_data.get("credit_sum", 0) if client_data else 0
    default_obj_price = client_data.get("obj_price", 0) if client_data else 0
    default_first_pay = client_data.get("first_pay", 0) if client_data else 0
    default_cian_report_link = clean_value(client_data.get("cian_report_link")) if client_data else ""
    
    # Pledge defaults
    default_is_pledged = "Да" if client_data and client_data.get("is_pledged") == "Да" else "Нет"
    default_pledge_bank = clean_value(client_data.get("pledge_bank")) if client_data else ""
    default_pledge_amount = client_data.get("pledge_amount", 0) if client_data else 0
    
    # Personal data defaults
    default_gender = client_data.get("gender") if client_data else None
    default_dob = pd.to_datetime(client_data["dob"]).date() if client_data and pd.notna(client_data.get("dob")) else None
    default_birth_place = clean_value(client_data.get("birth_place")) if client_data else ""
    default_phone = clean_int_str(client_data.get("phone")) if client_data else ""
    default_email = clean_value(client_data.get("email")) if client_data else ""
    default_family = client_data.get("family_status") if client_data else None
    default_children_count = safe_int(client_data.get("children_count"), 0) if client_data else 0
    default_marriage_contract = client_data.get("marriage_contract") if client_data else None
    default_children_dates = str(client_data.get("children_dates", "")).split("; ") if client_data and client_data.get("children_dates") and str(client_data.get("children_dates")) != "nan" else []
    
    # Passport defaults
    default_pass_ser = clean_int_str(client_data.get("passport_ser")) if client_data else ""
    default_pass_num = clean_int_str(client_data.get("passport_num")) if client_data else ""
    default_pass_code = clean_int_str(client_data.get("kpp")) if client_data else ""
    default_pass_date = pd.to_datetime(client_data["passport_date"]).date() if client_data and pd.notna(client_data.get("passport_date")) else None
    default_pass_issued = clean_value(client_data.get("passport_issued")) if client_data else ""
    
    # Address defaults
    default_addr_index = clean_int_str(client_data.get("addr_index")) if client_data else ""
    default_addr_region = clean_value(client_data.get("addr_region")) if client_data else ""
    default_addr_city = clean_value(client_data.get("addr_city")) if client_data else ""
    default_addr_street = clean_value(client_data.get("addr_street")) if client_data else ""
    default_addr_house = clean_int_str(client_data.get("addr_house")) if client_data else ""
    default_addr_korpus = clean_int_str(client_data.get("addr_korpus")) if client_data else ""
    default_addr_structure = clean_int_str(client_data.get("addr_structure")) if client_data else ""
    default_addr_flat = clean_int_str(client_data.get("addr_flat")) if client_data else ""
    
    default_snils = clean_int_str(client_data.get("snils")) if client_data else ""
    default_inn = clean_int_str(client_data.get("inn")) if client_data else ""
    
    # Job defaults
    default_job_type = client_data.get("job_type") if client_data else None
    default_job_official = "Да" if client_data and str(client_data.get("job_official")).lower() in ["да", "true", "1"] else "Нет"
    default_job_company = clean_value(client_data.get("job_company")) if client_data else ""
    default_job_sphere = clean_value(client_data.get("job_sphere")) if client_data else ""
    default_job_inn = clean_int_str(client_data.get("job_inn")) if client_data else ""
    default_job_found_date = pd.to_datetime(client_data["job_found_date"]).date() if client_data and pd.notna(client_data.get("job_found_date")) else None
    default_job_pos = clean_value(client_data.get("job_pos")) if client_data else ""
    default_job_income = client_data.get("job_income", 0) if client_data else 0
    default_job_start_date = pd.to_datetime(client_data["job_start_date"]).date() if client_data and pd.notna(client_data.get("job_start_date")) and str(client_data.get("job_start_date")) not in ["None", "nan"] else None
    default_job_ceo = clean_value(client_data.get("job_ceo")) if client_data else ""
    default_job_phone = clean_int_str(client_data.get("job_phone")) if client_data else ""
    default_job_address = clean_value(client_data.get("job_address")) if client_data else ""
    
    # Finance defaults
    default_loan_term = safe_int(client_data.get("loan_term"), 0) if client_data else 0
    default_has_coborrower = "Да" if client_data and str(client_data.get("has_coborrower")).lower() in ["да", "true", "1"] else "Нет"
    default_current_debts = client_data.get("current_debts", 0) if client_data else 0
    default_mosgorsud_comment = clean_value(client_data.get("mosgorsud_comment")) if client_data else ""
    default_fssp_comment = clean_value(client_data.get("fssp_comment")) if client_data else ""
    default_block_comment = clean_value(client_data.get("block_comment")) if client_data else ""
    # Parse assets with smart handling of "Другое (...)"
    default_assets = []
    default_other_asset = ""
    if client_data and client_data.get("assets") and str(client_data.get("assets")) != "nan":
        raw_assets = str(client_data.get("assets", ""))
        parts = [p.strip() for p in raw_assets.split(",") if p.strip()]
        for p in parts:
            if p.strip().lower().startswith("другое"):
                default_assets.append("Другое")
                if "(" in p and ")" in p:
                    default_other_asset = p.split("(", 1)[1].rsplit(")", 1)[0].strip()
            else:
                default_assets.append(p)
    
    # Object defaults
    default_obj_type = client_data.get("obj_type") if client_data else None
    default_obj_doc_type = client_data.get("obj_doc_type") if client_data else None
    default_obj_date = pd.to_datetime(client_data["obj_date"]).date() if client_data and pd.notna(client_data.get("obj_date")) and str(client_data.get("obj_date")) not in ["None", "nan"] else None
    default_obj_area = client_data.get("obj_area", 0.0) if client_data else 0.0
    default_obj_floor = safe_int(client_data.get("obj_floor"), 0) if client_data else 0
    default_obj_total_floors = safe_int(client_data.get("obj_total_floors"), 0) if client_data else 0
    default_obj_walls = client_data.get("obj_walls") if client_data else None
    default_obj_renovation = "Да" if client_data and client_data.get("obj_renovation") == "Да" else "Нет"
    
    # Gift donor defaults (for "Договор дарения")
    default_gift_donor_consent = client_data.get("gift_donor_consent") if client_data else None
    default_gift_donor_registered = client_data.get("gift_donor_registered") if client_data else None
    default_gift_donor_deregister = client_data.get("gift_donor_deregister") if client_data else None
    
    # Object address defaults
    default_obj_index = clean_int_str(client_data.get("obj_index")) if client_data else ""
    default_obj_region = clean_value(client_data.get("obj_region")) if client_data else ""
    default_obj_city = clean_value(client_data.get("obj_city")) if client_data else ""
    default_obj_street = clean_value(client_data.get("obj_street")) if client_data else ""
    default_obj_house = clean_int_str(client_data.get("obj_house")) if client_data else ""
    default_obj_korpus = clean_int_str(client_data.get("obj_korpus")) if client_data else ""
    default_obj_structure = clean_int_str(client_data.get("obj_structure")) if client_data else ""
    default_obj_flat = clean_int_str(client_data.get("obj_flat")) if client_data else ""
    
    # Determine if obj address matches reg address
    copy_addr_val = "Нет"
    if client_data:
        if (clean_int_str(client_data.get("obj_index")) == clean_int_str(client_data.get("addr_index")) and
            clean_value(client_data.get("obj_region")) == clean_value(client_data.get("addr_region")) and
            clean_value(client_data.get("obj_city")) == clean_value(client_data.get("addr_city")) and
            clean_value(client_data.get("obj_street")) == clean_value(client_data.get("addr_street")) and
            clean_int_str(client_data.get("obj_house")) == clean_int_str(client_data.get("addr_house"))):
            copy_addr_val = "Да"
    
    min_date = datetime(1930, 1, 1).date()
    max_date = datetime.now().date()
    
    # =========================================
    # ROW 1: FIO, Status, Loan Type, Credit Sum
    # =========================================
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    fio = c1.text_input("ФИО", value=default_fio, key=f"{key_prefix}fio")
    status = c2.selectbox("Статус", STATUS_OPTIONS, 
        index=STATUS_OPTIONS.index(default_status) if default_status in STATUS_OPTIONS else None,
        placeholder="Выберите статус...", key=f"{key_prefix}status")
    loan_type = c3.selectbox("Тип заявки", LOAN_TYPE_OPTIONS,
        index=LOAN_TYPE_OPTIONS.index(default_loan_type) if default_loan_type in LOAN_TYPE_OPTIONS else None,
        placeholder="Выберите тип...", key=f"{key_prefix}loan_type")
    with c4:
        credit_sum = formatted_number_input("Требуемая сумма кредита", f"{key_prefix}credit_sum_input", value=default_credit_sum)

    # =========================================
    # ROW 2: Object Price, LTV, CIAN, First Pay
    # =========================================
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns([1.2, 1, 1, 1])
    
    with r2_c1:
        op_cols = st.columns([0.85, 0.15])
        with op_cols[0]:
            obj_price = formatted_number_input("Стоимость объекта", f"{key_prefix}obj_price_input", value=default_obj_price)
        op_cols[1].markdown("<div style='padding-top: 28px;'><a href='https://www.cian.ru/kalkulator-nedvizhimosti/' target='_blank' style='text-decoration: none; font-size: 20px;'>🧮</a></div>", unsafe_allow_html=True)

    ltv_val = (credit_sum / obj_price * 100) if obj_price > 0 else 0.0
    r2_c2.text_input("КЗ (Коэффициент Залога)", value=f"{ltv_val:.1f}%", disabled=True)
    cian_report_link = r2_c3.text_input("Отчет об оценке ЦИАН", value=default_cian_report_link, key=f"{key_prefix}cian_report_link")
    
    first_pay = 0
    if loan_type == "Ипотека":
        with r2_c4:
            first_pay = formatted_number_input("Первоначальный взнос", f"{key_prefix}first_pay_input", value=default_first_pay)

    # =========================================
    # PLEDGE ROW: Is Pledged, Bank, Amount
    # =========================================
    p_c1, p_c2, p_c3 = st.columns([1, 1, 1])
    with p_c1:
        is_pledged_val = st.radio("Объект сейчас в залоге?", YES_NO_OPTIONS, horizontal=True,
            index=YES_NO_OPTIONS.index(default_is_pledged), key=f"{key_prefix}is_pledged_val")
    is_pledged = is_pledged_val == "Да"
    
    pledge_bank = ""
    pledge_amount = 0
    if is_pledged:
        with p_c2:
            pledge_bank = st.text_input("Где заложен (Банк)", value=default_pledge_bank, key=f"{key_prefix}pledge_bank")
        with p_c3:
            pledge_amount = formatted_number_input("Сумма текущего долга", f"{key_prefix}pledge_amount_input", value=default_pledge_amount)

    # =========================================
    # TABS
    # =========================================
    tab1, tab2, tab3 = st.tabs(["Личные данные", "Финансы", "Залог"])
    
    # =========================================
    # TAB 1: ЛИЧНЫЕ ДАННЫЕ
    # =========================================
    with tab1:
        # Gender, DOB, Age, Birth Place
        pd_r1_1, pd_r1_2, pd_r1_3, pd_r1_4 = st.columns([1, 1.2, 0.4, 2])
        gender = pd_r1_1.radio("Пол", GENDER_OPTIONS, horizontal=True,
            index=GENDER_OPTIONS.index(default_gender) if default_gender in GENDER_OPTIONS else None,
            key=f"{key_prefix}gender")
        dob = pd_r1_2.date_input("Дата рождения", min_value=min_date, max_value=max_date,
            value=default_dob, key=f"{key_prefix}dob", format="DD.MM.YYYY")
        
        age_val = relativedelta(datetime.now().date(), dob).years if dob else ""
        pd_r1_3.text_input("Возраст", value=str(age_val), disabled=True)
        birth_place = pd_r1_4.text_input("Место рождения", value=default_birth_place, key=f"{key_prefix}birth_place")
        
        # Phone, Email, SNILS, INN
        pd_r2_1, pd_r2_2, pd_r2_3, pd_r2_4, pd_r2_5 = st.columns([1, 2, 0.7, 0.7, 0.2])
        with pd_r2_1:
            phone = formatted_phone_input("Телефон", f"{key_prefix}phone_input", value=default_phone)
        with pd_r2_2:
            em_c1, em_c2 = st.columns([1.5, 1])
            email_user_part = default_email.split("@")[0] if "@" in default_email else default_email
            email_domain_part = "@" + default_email.split("@")[1] if "@" in default_email else None
            
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
        
        # --- Robust nalog JSON: берём актуальные значения из session_state ---
        def ss(key, fallback=""):
            return st.session_state.get(f"{key_prefix}{key}", fallback)
            
        # Helper to get current names (user might have edited them)
        _surname, _name, _patronymic = parse_fio(ss("fio", default_fio))
        
        nalog_data = {
            "source": "sokol",
            "surname": clean_value(_surname),
            "name": clean_value(_name),
            "patronymic": clean_value(_patronymic),
            "dob": str(ss("dob", default_dob)) if ss("dob", default_dob) else None,
            "passport_ser": clean_int_str(ss("pass_ser", default_pass_ser)),
            "passport_num": clean_int_str(ss("pass_num", default_pass_num)),
            "passport_date": str(ss("pass_date", default_pass_date)) if ss("pass_date", default_pass_date) else None,
        }
        nalog_json = json.dumps(nalog_data, ensure_ascii=False)
        
        # Prepare for JS: unique ID and safe string encoding
        btn_id = f"copyOpenBtn_{key_prefix}".replace("-", "_").replace(".", "_")
        txt_js = json.dumps(nalog_json, ensure_ascii=False)
        
        with pd_r2_5:
            # Custom JS Button via components.html
            btn_html = f"""
            <div style="padding-top: 28px;">
              <button id="{btn_id}"
                style="border:none;background:transparent;font-size:20px;cursor:pointer;padding:0;"
                title="Скопировать данные и открыть ФНС">🔍</button>
            </div>

            <script>
              (function() {{
                const txt = {txt_js};
                const btn = document.getElementById("{btn_id}");
                btn.addEventListener("click", async () => {{
                  try {{
                    await navigator.clipboard.writeText(txt);
                    btn.textContent = "✅";
                    setTimeout(() => btn.textContent = "🔍", 1200);
                  }} catch (e) {{
                    // если clipboard заблокирован — просто оставляем fallback ниже
                  }}
                  window.open("https://service.nalog.ru/inn.do", "_blank", "noopener,noreferrer");
                }});
              }})();
            </script>
            """
            components.html(btn_html, height=55, scrolling=False)

        # Fallback: Streamlit Copy работает всегда (вынесли из узкой колонки для удобства)
        with st.expander("JSON для nalog", expanded=False):
            st.code(nalog_json, language="json")
        
        # Marital Status, Children, Marriage Contract
        pd_r3_1, pd_r3_2, pd_r3_3 = st.columns([0.9, 1.1, 2.2])
        family = pd_r3_1.selectbox("Семейное положение", FAMILY_STATUS_OPTIONS,
            index=FAMILY_STATUS_OPTIONS.index(default_family) if default_family in FAMILY_STATUS_OPTIONS else None,
            placeholder="Выберите...", key=f"{key_prefix}family")
        children_count = pd_r3_2.number_input("Кол-во несовершеннолетних детей", 0, 10,
            value=int(default_children_count), key=f"{key_prefix}children_count")
        marriage_contract = pd_r3_3.radio("Наличие брачного договора / нотариального согласия", MARRIAGE_CONTRACT_OPTIONS, horizontal=True,
            index=MARRIAGE_CONTRACT_OPTIONS.index(default_marriage_contract) if default_marriage_contract in MARRIAGE_CONTRACT_OPTIONS else None,
            key=f"{key_prefix}marriage_contract")
        
        # Children dates (dynamic)
        children_dates = []
        if children_count > 0:
            st.caption("Даты рождения детей:")
            cols = st.columns(5)
            for i in range(children_count):
                if i > 0 and i % 5 == 0:
                    cols = st.columns(5)
                with cols[i % 5]:
                    default_child_date = pd.to_datetime(default_children_dates[i]).date() if i < len(default_children_dates) and default_children_dates[i] else None
                    d = st.date_input(f"Ребенок {i+1}", min_value=datetime(2000,1,1).date(), max_value=max_date,
                        key=f"{key_prefix}child_{i}", value=default_child_date, format="DD.MM.YYYY")
                    children_dates.append(str(d) if d else "")
        
        # Passport
        st.subheader("Паспорт")
        p1, p2, p3, p4, p5 = st.columns([1, 1, 1, 3, 1])
        pass_ser = p1.text_input("Серия", value=default_pass_ser, key=f"{key_prefix}pass_ser")
        pass_num = p2.text_input("Номер", value=default_pass_num, key=f"{key_prefix}pass_num")
        pass_code = p3.text_input("Код подразделения", value=default_pass_code, key=f"{key_prefix}pass_code")
        pass_issued = p4.text_input("Кем выдан", value=default_pass_issued, key=f"{key_prefix}pass_issued")
        pass_date = p5.date_input("Дата выдачи", min_value=datetime(1990, 1, 1).date(), max_value=max_date,
            value=default_pass_date, key=f"{key_prefix}pass_date", format="DD.MM.YYYY")
        
        # Registration Address
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

    # =========================================
    # TAB 2: ФИНАНСЫ
    # =========================================
    with tab2:
        st.subheader("Работа")
        
        jr1_1, jr1_2 = st.columns(2)
        job_type = jr1_1.selectbox("Тип занятости", JOB_TYPE_OPTIONS,
            index=JOB_TYPE_OPTIONS.index(default_job_type) if default_job_type in JOB_TYPE_OPTIONS else None,
            placeholder="Выберите...", key=f"{key_prefix}job_type")
        job_official_val = jr1_2.radio("Официально трудоустроен", JOB_OFFICIAL_OPTIONS, horizontal=True,
            index=JOB_OFFICIAL_OPTIONS.index(default_job_official), key=f"{key_prefix}job_official_val")
        job_official = job_official_val == "Да"
        
        # Job fields (shown if employed)
        job_company = ""
        job_industry = ""
        job_inn = ""
        job_date = None
        job_position = ""
        job_income = 0
        job_start_date = None
        exp_str = ""
        total_exp_val = max(0, age_val - 18) if isinstance(age_val, int) else 0
        job_ceo = ""
        job_phone_val = ""
        job_address = ""
        
        if job_type and job_type != "Не работаю":
            jr1_1, jr1_2, jr1_3, jr1_4 = st.columns(4)
            job_company = jr1_1.text_input("Название компании", value=default_job_company, key=f"{key_prefix}job_company")
            job_industry = jr1_2.text_input("Сфера деятельности", value=default_job_sphere, key=f"{key_prefix}job_industry")
            
            with jr1_3:
                inn_c1, inn_c2 = st.columns([4, 1])
                job_inn = inn_c1.text_input("ИНН Компании", value=default_job_inn, key=f"{key_prefix}job_inn")
                inn_c2.markdown("<div style='padding-top: 28px;'><a href='https://www.rusprofile.ru/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
            job_date = jr1_4.date_input("Дата основания компании", min_value=min_date, max_value=max_date, value=default_job_found_date, format="DD.MM.YYYY", key=f"{key_prefix}job_found_date")
            
            jr2_1, jr2_2, jr2_3, jr2_4, jr2_5 = st.columns([1.2, 1.2, 1, 0.8, 0.8])
            job_position = jr2_1.text_input("Должность", value=default_job_pos, key=f"{key_prefix}job_pos")
            with jr2_2:
                inc_c1, inc_c2 = st.columns([0.85, 0.15])
                with inc_c1:
                    job_income = formatted_number_input("Доход", f"{key_prefix}job_income_input", value=default_job_income)
                calc_amount = int(credit_sum) if credit_sum else 10000000
                banki_url = f"https://www.banki.ru/services/calculators/credits/?amount={calc_amount}&periodNotation=20y&rate=28"
                inc_c2.markdown(f"<div style='padding-top: 28px;'><a href='{banki_url}' target='_blank' style='text-decoration: none; font-size: 20px;'>🧮</a></div>", unsafe_allow_html=True)
            job_start_date = jr2_3.date_input("Начало работы", min_value=min_date, max_value=max_date, value=default_job_start_date, format="DD.MM.YYYY", key=f"{key_prefix}job_start_date")
            
            # Calculate experience
            if job_start_date:
                today = datetime.now().date()
                delta = relativedelta(today, job_start_date)
                exp_str = f"{delta.years} г. {delta.months} м."
            
            # Total Experience
            if isinstance(age_val, int):
                total_exp_val = max(0, age_val - 18)
            
            jr2_4.text_input("Тек. стаж", value=exp_str, disabled=True)
            jr2_5.text_input("Общ. стаж", value=str(total_exp_val), disabled=True)
            
            # CEO, Address, Work Phone
            jr3_1, jr3_2, jr3_3 = st.columns(3)
            job_ceo = jr3_1.text_input("ФИО Гендиректора", value=default_job_ceo, key=f"{key_prefix}job_ceo")
            job_address = jr3_2.text_input("Адрес работы", value=default_job_address, key=f"{key_prefix}job_address")
            with jr3_3:
                job_phone_val = formatted_phone_input("Рабочий телефон", f"{key_prefix}job_phone_input", value=default_job_phone)
        
        st.subheader("Финансы")
        
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            loan_term = formatted_number_input("Срок кредита (лет)", f"{key_prefix}loan_term_input", value=default_loan_term)
        loan_term_months = loan_term * 12
        f2.text_input("Срок в месяцах", value=str(loan_term_months), disabled=True)
        has_coborrower = f3.radio("Будет ли созаемщик?", YES_NO_OPTIONS, horizontal=True,
            index=YES_NO_OPTIONS.index(default_has_coborrower), key=f"{key_prefix}has_coborrower_val")
        
        # Debts, MosGorSud, FSSP, Block
        f3_cols = st.columns([3, 2, 1.2, 2, 1.2, 2, 1.2])
        with f3_cols[0]:
            current_debts = formatted_number_input("Текущие платежи по кредитам", f"{key_prefix}current_debts_input", value=default_current_debts)
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
        
        # Assets
        assets_default_selected = [a for a in default_assets if a in ASSET_OPTIONS]
        assets_list = st.multiselect("Доп. активы", ASSET_OPTIONS, default=assets_default_selected, key=f"{key_prefix}assets")
        assets_str = ", ".join(assets_list)
        
        if "Другое" in assets_list:
            other_asset = st.text_input("Укажите другое имущество", value=default_other_asset, key=f"{key_prefix}other_asset")
            if other_asset:
                assets_str += f" ({other_asset})"

    # =========================================
    # TAB 3: ЗАЛОГ
    # =========================================
    with tab3:
        st.subheader("Объект")
        
        o_row1_1, o_row1_2, o_row1_3 = st.columns(3)
        obj_type = o_row1_1.selectbox("Тип объекта", OBJ_TYPE_OPTIONS,
            index=OBJ_TYPE_OPTIONS.index(default_obj_type) if default_obj_type in OBJ_TYPE_OPTIONS else None,
            placeholder="Выберите...", key=f"{key_prefix}obj_type")
        
        own_doc_type = o_row1_2.selectbox("Правоустановка", OBJ_DOC_TYPE_OPTIONS,
            index=OBJ_DOC_TYPE_OPTIONS.index(default_obj_doc_type) if default_obj_doc_type in OBJ_DOC_TYPE_OPTIONS else None,
            placeholder="Выберите...", key=f"{key_prefix}obj_doc_type")
        
        # Gift donor fields (for "Договор дарения")
        gift_donor_consent = "Нет"
        gift_donor_registered = "Нет"
        gift_donor_deregister = "Нет"
        
        if own_doc_type == "Другое":
            custom_doc_val = default_obj_doc_type if default_obj_doc_type not in OBJ_DOC_TYPE_OPTIONS else ""
            own_doc_type = st.text_input("Впишите документ", value=custom_doc_val, key=f"{key_prefix}obj_doc_type_custom")
        elif own_doc_type == "Договор дарения":
            g1, g2, g3 = st.columns(3)
            gift_donor_consent = g1.radio("Есть ли согласие дарителя?", YES_NO_OPTIONS, horizontal=True,
                index=YES_NO_OPTIONS.index(default_gift_donor_consent) if default_gift_donor_consent in YES_NO_OPTIONS else None,
                key=f"{key_prefix}gift_donor_consent")
            gift_donor_registered = g2.radio("Прописан ли даритель?", YES_NO_OPTIONS, horizontal=True,
                index=YES_NO_OPTIONS.index(default_gift_donor_registered) if default_gift_donor_registered in YES_NO_OPTIONS else None,
                key=f"{key_prefix}gift_donor_registered")
            if gift_donor_registered == "Да":
                gift_donor_deregister = g3.radio("Готов ли он выписаться?", YES_NO_OPTIONS, horizontal=True,
                    index=YES_NO_OPTIONS.index(default_gift_donor_deregister) if default_gift_donor_deregister in YES_NO_OPTIONS else None,
                    key=f"{key_prefix}gift_donor_deregister")
        
        obj_date = o_row1_3.date_input("Дата правоустановки", min_value=min_date, max_value=max_date, value=default_obj_date, key=f"{key_prefix}obj_date", format="DD.MM.YYYY")
        
        o1, o2, o3, o4, o5 = st.columns(5)
        with o1:
            obj_area = formatted_number_input("Площадь (м²)", f"{key_prefix}obj_area_input", allow_float=True, value=default_obj_area)
        with o2:
            obj_floor = formatted_number_input("Этаж", f"{key_prefix}obj_floor_input", value=default_obj_floor)
        with o3:
            obj_total_floors = formatted_number_input("Этажность", f"{key_prefix}obj_total_floors_input", value=default_obj_total_floors)
        with o4:
            obj_walls = st.selectbox("Материал стен", OBJ_WALLS_OPTIONS,
                index=OBJ_WALLS_OPTIONS.index(default_obj_walls) if default_obj_walls in OBJ_WALLS_OPTIONS else None,
                placeholder="Выберите...", key=f"{key_prefix}obj_walls")
        with o5:
            obj_renovation_val = st.radio("Реновация", YES_NO_OPTIONS, horizontal=True,
                index=YES_NO_OPTIONS.index(default_obj_renovation), key=f"{key_prefix}obj_renovation_val")
        obj_renovation = "Да" if obj_renovation_val == "Да" else "Нет"
        
        st.subheader("Адрес объекта")
        copy_addr_val = st.radio("Совпадает с адресом регистрации", YES_NO_OPTIONS, horizontal=True,
            index=YES_NO_OPTIONS.index(copy_addr_val), key=f"{key_prefix}copy_addr_val")
        copy_addr = copy_addr_val == "Да"
        
        if copy_addr:
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
            obj_index = oa1.text_input("Индекс", value=default_obj_index, key=f"{key_prefix}obj_index")
            oa2.markdown("<div style='padding-top: 28px;'><a href='https://xn--80a1acny.ru.com/' target='_blank' style='text-decoration: none; font-size: 20px;'>🔍</a></div>", unsafe_allow_html=True)
            obj_region = oa3.text_input("Регион", value=default_obj_region, key=f"{key_prefix}obj_region")
            obj_city = oa4.text_input("Город", value=default_obj_city, key=f"{key_prefix}obj_city")
            
            oa5, oa6, oa7, oa8, oa9 = st.columns(5)
            obj_street = oa5.text_input("Улица", value=default_obj_street, key=f"{key_prefix}obj_street")
            obj_house = oa6.text_input("Дом", value=default_obj_house, key=f"{key_prefix}obj_house")
            obj_korpus = oa7.text_input("Корпус", value=default_obj_korpus, key=f"{key_prefix}obj_korpus")
            obj_structure = oa8.text_input("Строение", value=default_obj_structure, key=f"{key_prefix}obj_structure")
            obj_flat = oa9.text_input("Квартира", value=default_obj_flat, key=f"{key_prefix}obj_flat")

    # =========================================
    # Build Return Data
    # =========================================
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

    # Helper to uppercase text fields
    def up(val):
        return val.upper() if isinstance(val, str) else val
    
    data = {
        "status": status,
        "loan_type": loan_type,
        "fio": up(fio),
        "surname": up(surname),
        "name": up(name),
        "patronymic": up(patronymic),
        "gender": gender,
        "dob": str(dob) if dob else None,
        "birth_place": up(birth_place),
        "phone": phone,
        "email": email.lower() if email else email,  # email stays lowercase
        "passport_ser": pass_ser,
        "passport_num": pass_num,
        "passport_issued": up(pass_issued),
        "passport_date": str(pass_date) if pass_date else None,
        "kpp": pass_code,
        "inn": inn,
        "snils": snils,
        "addr_index": addr_index,
        "addr_region": up(addr_region),
        "addr_city": up(addr_city),
        "addr_street": up(addr_street),
        "addr_house": addr_house,
        "addr_korpus": addr_korpus,
        "addr_structure": addr_structure,
        "addr_flat": addr_flat,
        "obj_type": obj_type,
        "obj_index": obj_index,
        "obj_region": up(obj_region),
        "obj_city": up(obj_city),
        "obj_street": up(obj_street),
        "obj_house": obj_house,
        "obj_korpus": obj_korpus,
        "obj_structure": obj_structure,
        "obj_flat": obj_flat,
        "obj_area": obj_area,
        "obj_price": obj_price,
        "obj_doc_type": own_doc_type,
        "obj_date": str(obj_date) if obj_date else None,
        "obj_renovation": obj_renovation,
        "obj_floor": obj_floor,
        "obj_total_floors": obj_total_floors,
        "obj_walls": obj_walls,
        "gift_donor_consent": gift_donor_consent,
        "gift_donor_registered": gift_donor_registered,
        "gift_donor_deregister": gift_donor_deregister,
        "cian_report_link": cian_report_link,
        "age": age_val if isinstance(age_val, int) else None,
        "family_status": family,
        "marriage_contract": marriage_contract,
        "children_count": children_count,
        "children_dates": "; ".join(children_dates),
        "job_type": job_type,
        "job_official": "Да" if job_official else "Нет",
        "job_company": up(job_company),
        "job_sphere": up(job_industry),
        "job_found_date": str(job_date) if job_date else None,
        "job_ceo": up(job_ceo),
        "job_address": up(job_address),
        "job_phone": job_phone_val,
        "job_inn": job_inn,
        "job_pos": up(job_position),
        "job_income": job_income,
        "job_start_date": str(job_start_date) if job_start_date else None,
        "job_exp": exp_str,
        "total_exp": total_exp_val,
        "credit_sum": credit_sum,
        "loan_term": loan_term,
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
        "bank_interactions": client_data.get("bank_interactions") if client_data else None,
        "yandex_link": client_data.get("yandex_link") if client_data else None,
    }
    
    return data
