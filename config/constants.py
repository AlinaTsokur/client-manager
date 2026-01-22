"""
Application constants and option lists.
"""

# --- Status Options ---
STATUS_OPTIONS = [
    "Новый", "В работе", "Одобрен", "Сделка", 
    "Подписание", "Выдача", "Отказ", "Архив"
]

LOAN_TYPE_OPTIONS = ["Ипотека", "Залог"]

# --- Bank Stage Options ---
BANK_STAGE_OPTIONS = [
    "Сделать", "Отправлено", "Рассмотрение", "Доп. запрос",
    "Одобрено", "Сделка", "Подписание", "Выдача", "Отказ", "Архив"
]

# --- Personal Data Options ---
GENDER_OPTIONS = ["Мужской", "Женский"]

FAMILY_STATUS_OPTIONS = [
    "Холост/Не замужем", "Женат/Замужем", "Разведен(а)", "Вдовец/Вдова"
]

MARRIAGE_CONTRACT_OPTIONS = ["Брачный контракт", "Нотариальное согласие", "Нет"]

# --- Job Options ---
JOB_TYPE_OPTIONS = [
    "Найм", "ИП", "Собственник бизнеса", "Самозанятый", "Пенсионер", "Не работаю"
]

JOB_OFFICIAL_OPTIONS = ["Да", "Нет"]

# --- Object Options ---
OBJ_TYPE_OPTIONS = [
    "Квартира", "Дом", "Земельный участок", "Коммерция", 
    "Комната", "Апартаменты", "Таунхаус"
]

OBJ_DOC_TYPE_OPTIONS = [
    "Договор купли-продажи", "Договор дарения", "Наследство",
    "Приватизация", "ДДУ", "Договор мены", "Договор ренты",
    "Договор уступки права требования", "Справка ЖСК о полной выплате пая",
    "Решение суда", "Другое"
]

OBJ_WALLS_OPTIONS = ["Кирпич", "Панель", "Монолит", "Блоки", "Дерево", "Смешанные"]

# --- Asset Options ---
ASSET_OPTIONS = ["Машина", "Квартира", "Дом с ЗУ", "Коммерция", "Машиноместо", "Другое"]

# --- Boolean Options ---
YES_NO_OPTIONS = ["Да", "Нет"]

# --- Pagination ---
ITEMS_PER_PAGE = 10

# --- Database Columns (for migration reference) ---
CLIENT_COLS = [
    "id", "created_at", "status", "loan_type", "fio", "surname", "name", "patronymic", 
    "dob", "age", "birth_place", "phone", "email", "passport_ser", "passport_num", 
    "passport_issued", "passport_date", "kpp", "inn", "snils", "addr_index", "addr_region",
    "addr_city", "addr_street", "addr_house", "addr_korpus", "addr_structure", "addr_flat", 
    "obj_type", "obj_index", "obj_region", "obj_city", "obj_street", "obj_house", 
    "obj_korpus", "obj_structure", "obj_flat", "obj_area", "obj_price", "obj_doc_type", 
    "obj_date", "obj_renovation", "obj_floor", "obj_total_floors", "obj_walls",
    "gift_donor_consent", "gift_donor_registered", "gift_donor_deregister",
    "cian_report_link", "family_status", "marriage_contract", "gender",
    "children_count", "children_dates", "job_type", "job_official", "job_company", 
    "job_sphere", "job_found_date", "job_ceo", "job_phone", "job_inn", "job_address", 
    "job_pos", "job_income", "job_start_date", "job_exp", "total_exp", "credit_sum", 
    "loan_term", "has_coborrower", "first_pay", "current_debts", "assets", "is_pledged",
    "pledge_bank", "pledge_amount", "yandex_link", "mosgorsud_comment", "fssp_comment", 
    "block_comment", "bank_interactions"
]

BANK_COLS = [
    "id", "name", "manager_fio", "manager_phone", "manager_email", 
    "email2", "email3", "lk_link", "address"
]

APP_COLS = [
    "id", "client_id", "client_fio", "bank", "date_submitted", 
    "status", "approved_sum", "comment"
]

# --- Russian Months ---
MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]
