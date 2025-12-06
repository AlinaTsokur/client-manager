import pandas as pd
import os
from datetime import datetime

DB_FILE = 'database.xlsx'

# --- 1. СПИСКИ КОЛОНОК (ЭТАЛОН) ---
# Мы вынесли их сюда, чтобы скрипт знал, как ДОЛЖНА выглядеть таблица
CLIENT_COLS = [
    "id", "created_at", "status", "loan_type", "fio", "surname", "name", "patronymic", "dob", "age", "birth_place",
    "phone", "email", "passport_ser", "passport_num", "passport_issued",
    "passport_date", "kpp", "inn", "snils", "addr_index", "addr_region",
    "addr_city", "addr_street", "addr_house", "addr_korpus", "addr_structure", "addr_flat", "obj_type",
    "obj_index", "obj_region", "obj_city", "obj_street", "obj_house", "obj_korpus", "obj_structure", "obj_flat",
    "obj_area", "obj_price", "obj_doc_type", "obj_date", "obj_renovation",
    "obj_floor", "obj_total_floors", "obj_walls",
    "gift_donor_consent", "gift_donor_registered", "gift_donor_deregister",
    "cian_report_link", "family_status", "marriage_contract", "gender",
    "children_count", "children_dates",
    "job_type", "job_official", "job_company", "job_sphere", "job_found_date",
    "job_ceo", "job_phone", "job_inn", "job_pos", "job_income", "job_start_date",
    "job_exp", "total_exp", "credit_sum", "loan_term", "has_coborrower", "first_pay", "current_debts", "assets", "is_pledged",
    "pledge_bank", "pledge_amount", "yandex_link", "mosgorsud_comment", "fssp_comment", "block_comment"
]

BANK_COLS = ["name", "manager_fio", "manager_phone", "manager_email", "email2", "email3", "address", "id"]
APP_COLS = ["id", "client_id", "client_fio", "bank", "date_submitted", "status", "approved_sum", "comment"]

def check_and_heal_sheet(file_path, sheet_name, required_cols):
    """Читает лист, добавляет недостающие колонки и сохраняет обратно."""
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except ValueError:
        # Если листа нет, создаем пустой DataFrame
        df = pd.DataFrame(columns=required_cols)

    # Ищем, каких колонок не хватает в файле
    missing = [c for c in required_cols if c not in df.columns]
    
    # Ищем лишние колонки (которых нет в required_cols)
    extra = [c for c in df.columns if c not in required_cols]
    
    changed = False
    
    if extra:
        print(f"🧹 Чистим таблицу {sheet_name}. Удаляем колонки: {extra}")
        df = df.drop(columns=extra)
        changed = True
    
    if missing:
        print(f"🔧 Лечим таблицу {sheet_name}. Добавляем колонки: {missing}")
        for c in missing:
            df[c] = None # Добавляем пустую колонку
        changed = True
            
    if changed:
        # Сохраняем обновленный файл (перезаписываем)
        # ВАЖНО: Мы сохраняем ВСЕ листы, чтобы не потерять данные
        # Поэтому этот метод вызывается внутри init_db более хитро
        return df, True 
    
    return df, False

def init_db():
    if not os.path.exists(DB_FILE):
        # Если файла нет вообще - создаем новый
        with pd.ExcelWriter(DB_FILE, engine='openpyxl') as writer:
            pd.DataFrame(columns=CLIENT_COLS).to_excel(writer, sheet_name='Clients', index=False)
            pd.DataFrame(columns=BANK_COLS).to_excel(writer, sheet_name='Banks', index=False)
            pd.DataFrame(columns=APP_COLS).to_excel(writer, sheet_name='Applications', index=False)
    else:
        # Если файл есть - проверяем структуру и лечим
        # Читаем все три листа
        clients_df, c_changed = check_and_heal_sheet(DB_FILE, 'Clients', CLIENT_COLS)
        banks_df, b_changed = check_and_heal_sheet(DB_FILE, 'Banks', BANK_COLS)
        apps_df, a_changed = check_and_heal_sheet(DB_FILE, 'Applications', APP_COLS)
        
        # Если хоть где-то были изменения - перезаписываем файл целиком
        if c_changed or b_changed or a_changed:
            with pd.ExcelWriter(DB_FILE, engine='openpyxl') as writer:
                clients_df.to_excel(writer, sheet_name='Clients', index=False)
                banks_df.to_excel(writer, sheet_name='Banks', index=False)
                apps_df.to_excel(writer, sheet_name='Applications', index=False)

def load_sheet(sheet_name):
    init_db() # Проверяем структуру
    try:
        df = pd.read_excel(DB_FILE, sheet_name=sheet_name)
        # ГЛАВНОЕ ИСПРАВЛЕНИЕ:
        # Заменяем "NaN" (пустоту-число) на None (пустоту-объект).
        # Это лечит ошибку с красным экраном в Streamlit.
        return df.where(pd.notnull(df), None)
    except Exception:
        return pd.DataFrame()

def load_clients():
    return load_sheet('Clients')

def load_banks():
    return load_sheet('Banks')

def load_applications():
    return load_sheet('Applications')

def save_entry(sheet_name, data_dict):
    init_db()
    # Сначала читаем актуальный файл (он уже "вылечен" init_db)
    df = pd.read_excel(DB_FILE, sheet_name=sheet_name)
    
    # Логика обновления/добавления
    if 'id' in data_dict and not df.empty and 'id' in df.columns:
        df = df[df['id'] != data_dict['id']]
    
    new_row = pd.DataFrame([data_dict])
    # Выравниваем колонки новой строки под существующий DF (чтобы избежать warning)
    new_row = new_row.reindex(columns=df.columns)
    
    df = pd.concat([df, new_row], ignore_index=True)
    
    with pd.ExcelWriter(DB_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

def save_client(data):
    save_entry('Clients', data)

def save_bank(data):
    save_entry('Banks', data)

def save_application(data):
    save_entry('Applications', data)

def save_all_clients(df):
    """Перезаписывает таблицу клиентов целиком."""
    init_db()
    # Убеждаемся, что колонки соответствуют схеме
    # Если в df есть лишние колонки (например Select), убираем их
    valid_cols = [c for c in df.columns if c in CLIENT_COLS]
    df = df[valid_cols]
    
    with pd.ExcelWriter(DB_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name='Clients', index=False)

def save_all_banks(df):
    """Перезаписывает таблицу банков целиком."""
    init_db()
    # Valid cols check
    valid_cols = [c for c in df.columns if c in BANK_COLS]
    # Ensure ID column exists
    if 'id' not in df.columns:
        df['id'] = [str(abs(hash(str(row)))) for row in df.itertuples()]
    
    # Fill missing IDs if any (for existing rows that had None)
    # We can use a simple counter or hash
    if not df.empty:
        df['id'] = df.apply(lambda row: row['id'] if (pd.notnull(row.get('id')) and str(row.get('id')) != '' and str(row.get('id')) != 'None') else str(abs(hash(str(row.name) + str(datetime.now())))), axis=1)
    
    df = df[valid_cols]
    
    with pd.ExcelWriter(DB_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name='Banks', index=False)

def delete_client(client_id):
    init_db()
    df = pd.read_excel(DB_FILE, sheet_name='Clients')
    if not df.empty and 'id' in df.columns:
        df = df[df['id'] != client_id]
        with pd.ExcelWriter(DB_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name='Clients', index=False)




