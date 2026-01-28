"""
Client Manager Application - Main Entry Point
Refactored version using Supabase and modular architecture.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
import json
from streamlit_searchbox import st_searchbox

# Local imports
from config.settings import settings
from config.constants import (
    STATUS_OPTIONS, LOAN_TYPE_OPTIONS, BANK_STAGE_OPTIONS,
    GENDER_OPTIONS, FAMILY_STATUS_OPTIONS, MARRIAGE_CONTRACT_OPTIONS,
    JOB_TYPE_OPTIONS, OBJ_TYPE_OPTIONS, OBJ_DOC_TYPE_OPTIONS,
    OBJ_WALLS_OPTIONS, ASSET_OPTIONS, YES_NO_OPTIONS, ITEMS_PER_PAGE
)
from database.repository import ClientRepository, BankRepository
from services.yandex_disk import YandexDiskService
from services.documents import DocumentService
from utils.formatters import clean_value, clean_int_str, safe_int, format_phone_string
from utils.helpers import parse_fio, calculate_age, transliterate, format_client_info
from ui.components import formatted_number_input, formatted_phone_input, generate_yandex_mail_link
from ui.client_form import render_client_form
from ui.pages.banks import render_banks_page

# --- Initialize Services ---
client_repo = ClientRepository()
bank_repo = BankRepository()
yandex_service = YandexDiskService()
document_service = DocumentService()

# --- Caching ---
@st.cache_data(show_spinner=False, ttl=60)
def get_cached_clients():
    return client_repo.load_all()

@st.cache_data(show_spinner=False, ttl=60)
def get_cached_banks():
    return bank_repo.load_all()

def clear_cache():
    get_cached_clients.clear()
    get_cached_banks.clear()

# --- CSS Styles ---
# --- Load CSS ---
def load_css():
    with open("ui/styles.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- Page Config ---
st.set_page_config(page_title="Mortgage CRM", layout="wide", page_icon="🏦")
load_css()


# --- Navigation Logic ---
pages = ["➕ Новый", "📋 Клиенты", "🏦 Банки", "💻 Рабочий стол", "⚙️ Сервисы"]

# 1. APPLY PENDING NAV BEFORE WIDGETS (Two-step navigation)
# --- Read URL params ---
qp_page = st.query_params.get("page")
qp_edit = st.query_params.get("edit")

# Apply edit only when target page is "➕ Новый" (or not set)
if qp_edit and (qp_page is None or qp_page == "➕ Новый"):
    st.session_state["editing_client_id"] = qp_edit
    st.session_state["nav_to"] = "➕ Новый"

# If user switched away from "➕ Новый" — drop edit mode + URL param
if qp_page and qp_page != "➕ Новый":
    st.session_state.pop("editing_client_id", None)
    st.query_params.pop("edit", None)

# 1. APPLY PENDING NAV BEFORE WIDGETS (Two-step navigation)
if "nav_to" in st.session_state:
    target = st.session_state.pop("nav_to")
    if target in pages:
        st.session_state["main_nav"] = target
        st.query_params["page"] = target

# 2. Initialize main_nav from URL or default if not set
if "main_nav" not in st.session_state:
    qp = st.query_params.get("page")
    st.session_state["main_nav"] = qp if qp in pages else "💻 Рабочий стол"

# 2. Render Radio (Single Source of Truth)
selected_page = st.radio(
    "Меню",
    pages,
    horizontal=True,
    label_visibility="collapsed",
    key="main_nav"
)

# 3. Sync page state and URL with radio selection
st.session_state["page"] = selected_page
if st.query_params.get("page") != selected_page:
    st.query_params["page"] = selected_page


# ===================================================
# PAGE: НОВЫЙ КЛИЕНТ (New/Edit Client)
# ===================================================
if selected_page == "➕ Новый":
    edit_client_id = st.session_state.get("editing_client_id")
    edit_client_data = None
    
    if edit_client_id:
        st.header("✏️ Редактирование клиента")
        all_clients = get_cached_clients()
        if not all_clients.empty and edit_client_id in all_clients["id"].values:
            edit_client_data = all_clients[all_clients["id"] == edit_client_id].iloc[0].to_dict()
        else:
            st.error("Клиент не найден!")
            st.session_state.pop("editing_client_id", None)
            st.query_params.pop("edit", None)
            st.rerun()
        
        btn_col1, btn_col2, _ = st.columns([1, 1, 3])
        with btn_col1:
            cancel_clicked = st.button("❌ Отмена")
        with btn_col2:
            save_clicked = st.button("💾 Сохранить изменения")
        
        if cancel_clicked:
            st.session_state.editing_client_id = None
            st.query_params.pop("edit", None)
            st.rerun()
        
        form_data = render_client_form(client_data=edit_client_data, key_prefix="edit_")
        
        if save_clicked:
            with st.spinner("Сохранение..."):
                data = form_data.copy()
                data["id"] = edit_client_data["id"]
                data["created_at"] = edit_client_data.get("created_at")
                # yandex_link is created automatically on client creation - not editable in form
                data["yandex_link"] = edit_client_data.get("yandex_link", "")
                
                if client_repo.save(data):
                    clear_cache()
                    st.success(f"Клиент {data['fio']} обновлен!")
                    st.session_state.editing_client_id = None
                    st.query_params.pop("edit", None)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Ошибка сохранения")
    else:
        st.header("🆕 Новый клиент")
        form_data = render_client_form(key_prefix="new_")
        
        if st.button("✨ Создать клиента"):
            if not form_data["fio"]:
                st.error("ФИО обязательно!")
            else:
                with st.spinner("Создание..."):
                    import uuid
                    data = form_data.copy()
                    data["id"] = str(uuid.uuid4())
                    data["created_at"] = datetime.now().isoformat()
                    
                    # Create Yandex folder (with error handling)
                    # Sanitize folder name from special characters
                    folder_fio = clean_value(form_data["fio"]).strip()
                    folder_fio = folder_fio.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "")
                    folder_name = f"{folder_fio}_{datetime.now().strftime('%Y-%m-%d')}"
                    try:
                        data["yandex_link"] = yandex_service.create_folder(folder_name)
                    except Exception as e:
                        data["yandex_link"] = ""
                        st.warning(f"Папка на Яндекс.Диске не создана: {e}")
                    
                    if client_repo.save(data):
                        clear_cache()
                        st.success(f"Клиент {data['fio']} создан!")
                    else:
                        st.error("Ошибка создания")


# ===================================================
# PAGE: БАЗА КЛИЕНТОВ
# ===================================================
elif selected_page == "📋 Клиенты":
    st.title("📂 База Клиентов")
    df = get_cached_clients()
    
    if df.empty:
        st.info("База пуста. Добавьте первого клиента!")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect("Статус", options=df["status"].dropna().unique().tolist(), label_visibility="collapsed")
        with col2:
            type_filter = st.multiselect("Тип", options=LOAN_TYPE_OPTIONS, label_visibility="collapsed")
        with col3:
            search = st.text_input("Поиск ФИО", placeholder="Введите ФИО", label_visibility="collapsed")
        
        filtered_df = df.copy()
        if status_filter:
            filtered_df = filtered_df[filtered_df["status"].isin(status_filter)]
        if type_filter:
            filtered_df = filtered_df[filtered_df["loan_type"].isin(type_filter)]
        if search:
            filtered_df = filtered_df[filtered_df["fio"].str.contains(search, case=False, na=False)]
        
        # Display
        display_cols = ["fio", "status", "loan_type", "credit_sum", "phone", "obj_city"]
        st.dataframe(
            filtered_df.reindex(columns=display_cols),
            use_container_width=True,
            column_config={
                "fio": "ФИО",
                "status": "Статус",
                "loan_type": "Тип",
                "credit_sum": st.column_config.NumberColumn("Сумма", format="%d"),
                "phone": "Телефон",
                "obj_city": "Город"
            }
        )

# ===================================================
# PAGE: БАЗА БАНКОВ
# ===================================================
elif selected_page == "🏦 Банки":
    render_banks_page(bank_repo, get_cached_banks, clear_cache)


# ===================================================
# PAGE: РАБОЧИЙ СТОЛ
# ===================================================
elif selected_page == "💻 Рабочий стол":
    all_clients = get_cached_clients()
    
    if all_clients.empty:
        st.info("База клиентов пуста")
    else:
        # Load banks for features
        banks_db_df = get_cached_banks()
        banks_list = banks_db_df.to_dict('records') if not banks_db_df.empty else []
        
        # Filters with defaults (all except "Отказ" and "Архив")
        excluded_statuses = ["Отказ", "Архив"]
        available_statuses = all_clients["status"].dropna().unique().tolist()
        # Default: all available except excluded
        valid_defaults = [s for s in available_statuses if s not in excluded_statuses]
        
        with st.expander("🔍 Фильтры", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                selected_statuses = st.multiselect("Статус", options=available_statuses, default=valid_defaults, label_visibility="collapsed")
            with c2:
                selected_types = st.multiselect("Тип", options=LOAN_TYPE_OPTIONS, label_visibility="collapsed", placeholder="Тип сделки")
        
        filtered_df = all_clients.copy()
        if selected_statuses:
            filtered_df = filtered_df[filtered_df["status"].isin(selected_statuses)]
        if selected_types:
            filtered_df = filtered_df[filtered_df["loan_type"].isin(selected_types)]
        
        if filtered_df.empty:
            st.warning("Нет клиентов по фильтрам")
        else:
            # Pagination
            if "desktop_page" not in st.session_state:
                st.session_state.desktop_page = 1
            
            total_items = len(filtered_df)
            total_pages = max(1, (total_items - 1) // ITEMS_PER_PAGE + 1)
            current_page = min(st.session_state.desktop_page, total_pages)
            
            start_idx = (current_page - 1) * ITEMS_PER_PAGE
            end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
            paginated_df = filtered_df.iloc[start_idx:end_idx]
            
            st.caption(f"Показаны {start_idx + 1}-{end_idx} из {total_items}")
            
            for _, client in paginated_df.iterrows():
                client_id = str(client.get("id", ""))
                
                with st.container():
                    fio = client.get("fio", "Без имени")
                    status = client.get("status", "Новый")
                    credit_sum = safe_int(client.get("credit_sum", 0))
                    obj_type = str(client.get("obj_type", "") or "")
                    obj_city = str(client.get("obj_city", "") or "")
                    addr_info = f"{obj_type} | {obj_city}" if obj_type and obj_city else obj_type or obj_city
                    
                    # Expander with all info in label (status as plain text - Streamlit limitation)
                    expander_label = f"👤 {fio}  ·  {credit_sum:,} руб.  ·  {addr_info}  ·  {status}"
                    with st.expander(expander_label, expanded=False):
                        # Bank Interactions Display
                        interactions = []
                        interactions_json = client.get("bank_interactions")
                        if interactions_json:
                            try:
                                if isinstance(interactions_json, str):
                                    interactions = json.loads(interactions_json)
                                elif isinstance(interactions_json, list):
                                    interactions = interactions_json
                            except Exception as e:
                                interactions = []
                                print(f"Warning: bank_interactions parse error: {e}")
                        
                        # Yandex Disk Link only
                        yandex_link = client.get("yandex_link", "")
                        if yandex_link and yandex_link != "Ссылка не создана":
                            st.markdown(f"📂 [Яндекс.Диск]({yandex_link})")
                        
                        # Collapsible client info for easy copying
                        with st.expander("📋 Инфо (для копирования)", expanded=False):
                            client_info = format_client_info(client.to_dict())
                            st.code(client_info, language=None)
                        
                        if interactions:
                            banks_text = ""
                            for inter in interactions[-5:]:  # Show last 5 (newest)
                                bank = inter.get("bank_name", "?")
                                stage = inter.get("stage", "-")
                                comment = str(inter.get("comment", ""))
                                banks_text += f"🔹 {bank} | {stage} : {comment}\n"
                            st.code(banks_text.strip(), language=None)
                        
                        # Action Buttons - all in one row
                        edit_key = f"edit_banks_{client_id}"
                        write_key = f"write_bank_{client_id}"
                        docs_key = f"docs_desk_{client_id}"
                        
                        if edit_key not in st.session_state: st.session_state[edit_key] = False
                        if write_key not in st.session_state: st.session_state[write_key] = False
                        if docs_key not in st.session_state: st.session_state[docs_key] = False
                        
                        c_btn1, c_btn2, c_btn3, c_btn4, c_btn5 = st.columns([1, 1, 1, 1.2, 2])
                        
                        with c_btn1:
                            if st.button("✏️ Клиент", key=f"btn_edit_{client_id}"):
                                st.query_params["page"] = "➕ Новый"
                                st.query_params["edit"] = client_id
                                st.session_state["nav_to"] = "➕ Новый"
                                st.rerun()
                        
                        with c_btn2:
                            toggle_label = "❌ Закрыть" if st.session_state[edit_key] else "✏️ Банки"
                            if st.button(toggle_label, key=f"btn_banks_{client_id}"):
                                st.session_state[edit_key] = not st.session_state[edit_key]
                                if st.session_state[edit_key]:
                                    st.session_state[write_key] = False
                                    st.session_state[docs_key] = False
                                st.rerun()
                        
                        with c_btn3:
                            w_label = "❌ Закрыть" if st.session_state[write_key] else "📧 Письмо"
                            if st.button(w_label, key=f"btn_write_{client_id}"):
                                st.session_state[write_key] = not st.session_state[write_key]
                                if st.session_state[write_key]:
                                    st.session_state[edit_key] = False
                                    st.session_state[docs_key] = False
                                st.rerun()
                        
                        with c_btn4:
                            d_label = "❌ Закрыть" if st.session_state[docs_key] else "📄 Документы"
                            if st.button(d_label, key=f"btn_docs_{client_id}"):
                                st.session_state[docs_key] = not st.session_state[docs_key]
                                if st.session_state[docs_key]:
                                    st.session_state[edit_key] = False
                                    st.session_state[write_key] = False
                                st.rerun()
                        
                        with c_btn5:
                            desk_up = st.file_uploader("Загрузка файлов", accept_multiple_files=True, label_visibility="collapsed", key=f"desk_up_{client_id}")
                            if desk_up:
                                folder_name = yandex_service.get_client_folder_name(client.to_dict())
                                success = 0
                                with st.spinner("Загрузка..."):
                                    for f in desk_up:
                                        f.seek(0)
                                        try:
                                            yandex_service.upload_file(f, folder_name, f.name)
                                            success += 1
                                        except Exception as e:
                                            print(f"Upload error: {e}")
                                if success:
                                    st.toast(f"✅ Загружено {success} файлов")
                        
                        # --- Bank Interactions Editor ---
                        if st.session_state[edit_key]:
                            st.markdown("---")
                            st.markdown("**Редактирование взаимодействий:**")
                            
                            df_inter = pd.DataFrame(interactions) if interactions else pd.DataFrame(columns=["bank_name", "stage", "comment", "date"])
                            
                            for col in ["bank_name", "stage", "comment"]:
                                if col not in df_inter.columns:
                                    df_inter[col] = ""
                            
                            combined_stages = BANK_STAGE_OPTIONS.copy()
                            bank_names_list = [b["name"] for b in banks_list] if banks_list else []
                            
                            edited_interactions = st.data_editor(
                                df_inter[["bank_name", "stage", "comment"]],
                                num_rows="dynamic",
                                column_config={
                                    "bank_name": st.column_config.SelectboxColumn("Банк", options=bank_names_list),
                                    "stage": st.column_config.SelectboxColumn("Этап", options=combined_stages),
                                    "comment": st.column_config.TextColumn("Комментарий"),
                                },
                                key=f"editor_{client_id}",
                                use_container_width=True
                            )
                            
                            if st.button("💾 Сохранить", key=f"save_banks_{client_id}"):
                                new_interactions = edited_interactions.to_dict(orient="records")
                                client_data = client.to_dict()
                                client_data["bank_interactions"] = new_interactions
                                if client_repo.save(client_data):
                                    clear_cache()
                                    st.toast("✅ Сохранено!")
                                    st.session_state[edit_key] = False
                                    st.rerun()
                        
                        # --- Email Generation ---
                        if st.session_state[write_key]:
                            st.markdown("---")
                            wb_c1, wb_c2 = st.columns([1, 2])
                            bank_names = [b["name"] for b in banks_list]
                            
                            sel_bank_name = wb_c1.selectbox("Выберите банк", bank_names, key=f"desk_sel_bank_{client_id}", index=None, placeholder="Выберите...", label_visibility="collapsed")
                            
                            if sel_bank_name:
                                sel_bank = next((b for b in banks_list if b["name"] == sel_bank_name), None)
                                if sel_bank:
                                    link = generate_yandex_mail_link(client.to_dict(), sel_bank)
                                    with wb_c2:
                                        if link:
                                            st.markdown(f'<a href="{link}" target="_blank" style="display:inline-block;padding:0.5em 1em;color:white;background-color:#ffcc00;border-radius:5px;text-decoration:none;">📧 Написать</a>', unsafe_allow_html=True)
                                        else:
                                            st.warning("Нет email у банка")
                        
                        # --- Document Generation ---
                        if st.session_state[docs_key]:
                            st.markdown("---")
                            st.markdown("**📄 Генерация документов**")
                            bank_names = [b["name"] for b in banks_list]
                            
                            d_sel_bank_name = st.selectbox("Банк для шаблонов", bank_names, key=f"docs_sel_bank_{client_id}", index=None, placeholder="Выберите...", label_visibility="collapsed")
                            
                            if d_sel_bank_name:
                                d_sel_bank = next((b for b in banks_list if b["name"] == d_sel_bank_name), None)
                                if d_sel_bank:
                                    import os
                                    bank_folder = transliterate(d_sel_bank_name)
                                    tpl_dir = f"templates/{bank_folder}"
                                    common_dir = "templates/common"
                                    
                                    templates = []
                                    if os.path.exists(tpl_dir):
                                        templates.extend([(f, os.path.join(tpl_dir, f)) for f in os.listdir(tpl_dir) if f.endswith(('.docx', '.xlsx', '.pdf')) and not f.startswith('~$')])
                                    if os.path.exists(common_dir):
                                        templates.extend([(f, os.path.join(common_dir, f)) for f in os.listdir(common_dir) if f.endswith(('.docx', '.xlsx', '.pdf')) and not f.startswith('~$')])
                                    
                                    if templates:
                                        cols = st.columns(3)
                                        for i, (tpl_name, tpl_path) in enumerate(templates):
                                            if cols[i % 3].button(f"📄 {tpl_name}", key=f"gen_{client_id}_{tpl_name}"):
                                                with st.spinner(f"Генерация {tpl_name}..."):
                                                    # Build context for document
                                                    doc_context = document_service.build_document_context(client.to_dict(), d_sel_bank_name)
                                                    
                                                    # Generate based on file type
                                                    if tpl_name.endswith('.docx'):
                                                        result = document_service.fill_docx_template(tpl_path, doc_context)
                                                        if result:
                                                            st.download_button(
                                                                label=f"⬇️ Скачать {tpl_name}",
                                                                data=result,
                                                                file_name=f"{client.get('fio', 'client')}_{tpl_name}",
                                                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                                                key=f"dl_{client_id}_{tpl_name}"
                                                            )
                                                        else:
                                                            st.error("Ошибка генерации DOCX")
                                                    
                                                    elif tpl_name.endswith('.xlsx'):
                                                        result = document_service.fill_excel_template(tpl_path, doc_context)
                                                        if result:
                                                            st.download_button(
                                                                label=f"⬇️ Скачать {tpl_name}",
                                                                data=result,
                                                                file_name=f"{client.get('fio', 'client')}_{tpl_name}",
                                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                                key=f"dl_{client_id}_{tpl_name}"
                                                            )
                                                        else:
                                                            st.error("Ошибка генерации Excel")
                                                    
                                                    elif tpl_name.endswith('.pdf'):
                                                        result, error = document_service.fill_pdf_form(tpl_path, doc_context)
                                                        if result:
                                                            st.download_button(
                                                                label=f"⬇️ Скачать {tpl_name}",
                                                                data=result,
                                                                file_name=f"{client.get('fio', 'client')}_{tpl_name}",
                                                                mime="application/pdf",
                                                                key=f"dl_{client_id}_{tpl_name}"
                                                            )
                                                        else:
                                                            st.error(f"Ошибка PDF: {error}")
                                    else:
                                        st.caption(f"Шаблоны не найдены (templates/{bank_folder})")
            
            # Pagination controls
            st.markdown("---")
            p_c1, p_c2, p_c3 = st.columns([1, 2, 1])
            with p_c1:
                if current_page > 1:
                    if st.button("⬅️ Назад"):
                        st.session_state.desktop_page -= 1
                        st.rerun()
            with p_c2:
                st.markdown(f"<div style='text-align:center'>Стр. {current_page} из {total_pages}</div>", unsafe_allow_html=True)
            with p_c3:
                if current_page < total_pages:
                    if st.button("Вперед ➡️"):
                        st.session_state.desktop_page += 1
                        st.rerun()

# ============ СЕРВИСЫ ============
elif selected_page == "⚙️ Сервисы":
    
    # CSS for service buttons
    st.markdown("""
    <style>
    .service-link {
        display: inline-block;
        padding: 6px 12px;
        margin: 3px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        text-decoration: none;
        border-radius: 6px;
        font-size: 0.85em;
        font-weight: 500;
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.25);
    }
    .service-link:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.35);
    }
    .service-category {
        margin-top: 12px;
        margin-bottom: 6px;
        font-size: 0.95em;
        font-weight: 600;
        color: #667eea;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Define services by category
    services = {
        "💼 Главное": [
            ("АВИТО", "https://www.avito.ru/profile/pro/items"),
            ("ЦИАН", "https://my.cian.ru/my-offers/"),
            ("Яндекс Диск", "https://disk.yandex.ru/client/disk"),
            ("Почта", "https://mail.yandex.ru/"),
            ("Оценка ЦИАН", "https://www.cian.ru/kalkulator-nedvizhimosti/"),
            ("Оценка ДомКлик", "https://price.domclick.ru/"),

        ],
        "📄 Рабочие инструменты": [
            ("Сжать PDF", "https://bigpdf.11zon.com/ru/compress-pdf/compress-pdf-to-1mb.php"),
            ("Удалить фон", "https://app.photoroom.com/create"),
            ("Калькулятор НДФЛ", "https://secrets.tbank.ru/calculators/ndfl/"),
            ("CRM YouGile", "https://ru.yougile.com/team/projects"),
        ],
        "🏛️ Государственные сервисы": [
            ("Приостановка счета", "https://service.nalog.ru/bi.html"),
            ("ИНН", "https://service.nalog.ru/inn.do"),
            ("Росреестр онлайн", "https://lk.rosreestr.ru/eservices/real-estate-objects-online"),
            ("ФССП", "https://r74.govfssp.ru/"),
        ],
        "📊 Кредитная история": [
            ("НБКИ", "https://person.nbki.ru/login"),
            ("ОКБ", "https://credistory.ru/credithistory"),
            ("Как посмотреть КИ", "https://www.gosuslugi.ru/help/faq/credit_bureau/100748"),
            ("Центральный каталог КИ", "https://www.gosuslugi.ru/600311/1/form"),
        ],
        "📋 Справки": [
            ("ЭТК", "https://www.gosuslugi.ru/600302/1/form"),
            ("Выписка СФР", "https://www.gosuslugi.ru/600303/1/form"),
            ("Справка о пенсии", "https://www.gosuslugi.ru/600113/1/form"),
            ("Соц. выплаты и льготы", "https://www.gosuslugi.ru/600321/1/form"),
            ("ЕГРН", "https://www.gosuslugi.ru/600359/1/form"),
            ("ВДК Москва", "https://www.mos.ru/pgu2/landing/target/7700000000160962562/"),
            ("ВДК МО", "https://uslugi.mosreg.ru/services/21787"),

        ],
    }
    
    # Render services
    for category, links in services.items():
        st.markdown(f"<div class='service-category'>{category}</div>", unsafe_allow_html=True)
        links_html = ""
        for name, url in links:
            links_html += f'<a href="{url}" target="_blank" class="service-link">{name}</a>'
        st.markdown(links_html, unsafe_allow_html=True)
