import re
import pandas as pd
import streamlit as st
from streamlit_searchbox import st_searchbox


# =========================================================
# PARSERS / FORMATTERS
# =========================================================
def _parse_money(text: str) -> float:
    """
    Accepts: '8 000 000', '8000000', '8.5', '8,5', '80 000 ₽' -> float
    """
    if text is None:
        return 0.0
    s = str(text).strip()
    if not s:
        return 0.0
    s = s.replace("₽", "").replace("руб", "").replace("р.", "").replace("р", "")
    s = s.replace("\u00a0", " ").replace(" ", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _parse_int(text: str) -> int:
    if text is None:
        return 0
    s = str(text).strip()
    if not s:
        return 0
    s = s.replace("\u00a0", " ").replace(" ", "")
    s = s.replace(",", ".")
    try:
        return int(float(s))
    except Exception:
        return 0


def _parse_pct(text: str) -> float:
    """
    Accepts: '30', '30.5', '30,5', '30%' -> float
    """
    if text is None:
        return 0.0
    s = str(text).strip().replace("%", "").replace(",", ".")
    try:
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def _fmt_money(x: float) -> str:
    try:
        return f"{float(x):,.0f}".replace(",", " ") + " ₽"
    except Exception:
        return "0 ₽"


def _fmt_pct(x: float) -> str:
    try:
        # для UI оставим с точкой; если хочешь запятую — скажи, сделаю
        return f"{float(x):.2f}%"
    except Exception:
        return "0.00%"


def _fmt_int_spaces(x: float) -> str:
    """1000000 -> '1 000 000'"""
    try:
        return f"{int(round(float(x))):,}".replace(",", " ")
    except Exception:
        return ""


def on_money_format(key: str):
    """Форматирует поле st.session_state[key] в '1 000 000' (если там число)."""
    v = _parse_money(st.session_state.get(key, ""))
    st.session_state[key] = _fmt_int_spaces(v) if v else ""


def _parse_months_list(text: str) -> list[int]:
    """
    '1,2' -> [1,2]
    '1 2 3' -> [1,2,3]
    '1-3' -> [1,2,3]
    '1,2,3-5' -> [1,2,3,4,5]
    """
    if not text:
        return []
    s = str(text).strip()
    if not s:
        return []

    s = s.replace(";", ",").replace(" ", ",")
    parts = [p for p in s.split(",") if p.strip()]
    out: list[int] = []
    for p in parts:
        p = p.strip()
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", p)
        if m:
            a = int(m.group(1))
            b = int(m.group(2))
            if a > b:
                a, b = b, a
            out.extend(range(a, b + 1))
        else:
            try:
                out.append(int(p))
            except Exception:
                pass
    return sorted({m for m in out if m > 0})


# =========================================================
# FINANCE MATH
# =========================================================
def annuity_payment(S: float, n: int, annual_rate_pct: float) -> float:
    if S <= 0 or n <= 0:
        return 0.0
    r = annual_rate_pct / 12.0 / 100.0
    if r == 0:
        return S / n
    try:
        p = S * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        return float(p)
    except Exception:
        return 0.0


def annuity_rate_from_payment(S: float, n: int, payment: float) -> float:
    """
    Годовая ставка (%) по заданному платежу (аннуитет) — бинарный поиск.
    """
    if S <= 0 or n <= 0 or payment <= 0:
        return 0.0

    # если платеж меньше, чем S/n, то ставка ~ 0
    if payment <= S / n:
        return 0.0

    lo = 0.0
    hi = 300.0  # 300% годовых достаточно для "любой жести"

    for _ in range(60):
        mid = (lo + hi) / 2.0
        pmid = annuity_payment(S, n, mid)
        if pmid < payment:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2.0)


def pct_to_sum(base: float, pct: float) -> float:
    if base <= 0:
        return 0.0
    return base * (pct / 100.0)


def sum_to_pct(base: float, amount: float) -> float:
    if base <= 0:
        return 0.0
    return (amount / base) * 100.0


# =========================================================
# MAIN UI
# =========================================================
def render_expense_calculator(
    clients_df: pd.DataFrame | None = None,
    banks: list[str] | None = None,
):
    """
    ВАЖНО:
    - banks НЕ имеет дефолта. Должен прийти из БД (как ты просишь).
    - clients_df желательно с колонкой 'fio' (для поиска).
    """

    if not banks or not isinstance(banks, list) or len(banks) == 0:
        st.error("Банки не переданы (banks пустой). Подтяни из БД и передай в render_expense_calculator(...).")
        return

    # --- CSS: выравнивание searchbox/inputs, чтобы было "как по линейке" ---
    st.markdown(
        """
        <style>
          /* делаем одинаковую высоту для инпутов/селектов */
          div[data-testid="stTextInput"] input,
          div[data-testid="stSearchBox"] input{
            min-height: 40px !important;
            height: 40px !important;
            padding-top: 8px !important;
            padding-bottom: 8px !important;
          }

          /* Для селекта (банка) не задаем жесткий padding/height, чтобы не резало текст выборки */
          div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            min-height: 40px !important;
            display: flex !important;
            align-items: center !important;
          }

          /* caption чуть светлее, чтобы было видно на темной теме */
          .calc-cap { color: rgba(255,255,255,0.78); font-size: 0.86rem; margin-bottom: 4px; }

          /* подписи "платёж базовый" делаем видимыми */
          .calc-muted { color: rgba(255,255,255,0.72); font-size: 0.88rem; }
          .calc-val { color: rgba(255,255,255,0.95); font-weight: 700; font-size: 1.05rem; }

          /* карточка итогов */
          .calc-card{
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 14px;
            padding: 14px 16px;
            background: rgba(255,255,255,0.03);
          }
          .calc-big{
            font-size: 1.35rem;
            font-weight: 850;
            line-height: 1.05;
            color: rgba(255,255,255,0.96);
          }
          .calc-sub{
            color: rgba(255,255,255,0.70);
            font-size: 0.86rem;
          }

          /* убираем лишние отступы у searchbox */
          div[data-testid="stSearchBox"]{ margin-top: 0px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    def _spacer():
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------
    # CLIENT SEARCH
    # -----------------------------------------------------
    selected_client = None

    def _search_client(query: str):
        if clients_df is None or clients_df.empty or "fio" not in clients_df.columns:
            return []
        q = (query or "").strip().lower()

        f = clients_df.dropna(subset=["fio"]).copy()
        f["fio"] = f["fio"].astype(str)

        if len(q) < 2:
            return f.head(25)["fio"].tolist()

        m = f["fio"].str.lower().str.contains(q, na=False)
        return f[m].head(25)["fio"].tolist()

    # -----------------------------------------------------
    # STATE INIT (pairs)
    # -----------------------------------------------------
    def _init(key: str, default: str = ""):
        if key not in st.session_state:
            st.session_state[key] = default

    # Row1
    _init("calc_bank", banks[0])
    _init("calc_credit_sum", "")
    _init("calc_term", "")

    # Rates / hump
    _init("base_rate", "30")
    _init("hump_rate", "")
    _init("hump_pay", "")
    _init("hump_months", "")

    # First on account
    _init("keep_first", False)

    # Insurance pair
    _init("ins_pct", "")
    _init("ins_sum", "")

    # RKO pair
    _init("rko_pct", "")
    _init("rko_sum", "")

    # Other numeric fields
    _init("reg_add", "")
    _init("reg_remove", "")
    _init("notary", "5000")
    _init("pnd_nd", "")
    _init("buyout", "")
    _init("fast", "")
    _init("accr", "")

    # Short money
    _init("overlap", "")
    _init("inv_pct", "")
    _init("inv_comm", "") # New key for bidirectional commission logic

    # -----------------------------------------------------
    # COMPUTED BASE INPUTS (must exist before callbacks)
    # -----------------------------------------------------
    def _get_credit_sum() -> float:
        return _parse_money(st.session_state.get("calc_credit_sum", ""))

    def _get_term() -> int:
        return _parse_int(st.session_state.get("calc_term", ""))

    def _get_base_rate() -> float:
        return _parse_pct(st.session_state.get("base_rate", ""))

    # -----------------------------------------------------
    # CALLBACKS: HUMP (rate <-> pay)
    # -----------------------------------------------------
    def on_hump_rate_change():
        S = _get_credit_sum()
        n = _get_term()
        rate = _parse_pct(st.session_state.get("hump_rate", ""))
        months = _parse_months_list(st.session_state.get("hump_months", ""))
        if S > 0 and n > 0 and rate > 0 and len(months) > 0:
            pay = annuity_payment(S, n, rate)
            st.session_state["hump_pay"] = f"{pay:,.0f}".replace(",", " ")
        # если месяцев нет — платеж не считаем (оставим как есть)

    def on_hump_pay_change():
        S = _get_credit_sum()
        n = _get_term()
        pay = _parse_money(st.session_state.get("hump_pay", ""))
        months = _parse_months_list(st.session_state.get("hump_months", ""))
        if S > 0 and n > 0 and pay > 0 and len(months) > 0:
            rate = annuity_rate_from_payment(S, n, pay)
            st.session_state["hump_rate"] = f"{rate:.2f}"

    # -----------------------------------------------------
    # CALLBACKS: INSURANCE (pct <-> sum)
    # -----------------------------------------------------
    def on_ins_pct_change():
        S = _get_credit_sum()
        pct = _parse_pct(st.session_state.get("ins_pct", ""))
        if S > 0:
            s = pct_to_sum(S, pct)
            st.session_state["ins_sum"] = f"{s:,.0f}".replace(",", " ")

    def on_ins_sum_change():
        S = _get_credit_sum()
        s = _parse_money(st.session_state.get("ins_sum", ""))
        if S > 0:
            pct = sum_to_pct(S, s)
            st.session_state["ins_pct"] = f"{pct:.2f}"

    # -----------------------------------------------------
    # CALLBACKS: RKO (pct <-> sum)
    # -----------------------------------------------------
    def on_rko_pct_change():
        S = _get_credit_sum()
        pct = _parse_pct(st.session_state.get("rko_pct", ""))
        if S > 0:
            s = pct_to_sum(S, pct)
            st.session_state["rko_sum"] = f"{s:,.0f}".replace(",", " ")

    def on_rko_sum_change():
        S = _get_credit_sum()
        s = _parse_money(st.session_state.get("rko_sum", ""))
        if S > 0:
            pct = sum_to_pct(S, s)
            st.session_state["rko_pct"] = f"{pct:.2f}"

    # -----------------------------------------------------
    # CALLBACKS: Short Money Commission (pct <-> comm) (NEW)
    # -----------------------------------------------------
    def on_inv_pct_change():
        # inv_pct changed -> calc inv_comm
        overlap = _parse_money(st.session_state.get("overlap", ""))
        raw_pct = str(st.session_state.get("inv_pct", "")).strip()
        if overlap > 0 and raw_pct:
            pct = _parse_pct(raw_pct)
            comm = overlap * (pct / 100.0)
            st.session_state["inv_comm"] = f"{comm:,.0f}".replace(",", " ")
        else:
            st.session_state["inv_comm"] = ""
            
    def on_inv_comm_change():
        # inv_comm changed -> calc inv_pct
        overlap = _parse_money(st.session_state.get("overlap", ""))
        raw_comm = str(st.session_state.get("inv_comm", "")).strip()
        if overlap > 0 and raw_comm:
            comm = _parse_money(raw_comm)
            pct = (comm / overlap) * 100.0
            st.session_state["inv_pct"] = f"{pct:.2f}"
        else:
            st.session_state["inv_pct"] = ""

    # -----------------------------------------------------
    # CALLBACK: Global recalculation (Credit Sum / Term)
    # -----------------------------------------------------
    def on_credit_or_term_change():
        # пересчитать страх/комиссию из того, что заполнено
        if str(st.session_state.get("ins_pct", "")).strip():
            on_ins_pct_change()
        elif str(st.session_state.get("ins_sum", "")).strip():
            on_ins_sum_change()

        if str(st.session_state.get("rko_pct", "")).strip():
            on_rko_pct_change()
        elif str(st.session_state.get("rko_sum", "")).strip():
            on_rko_sum_change()

        # пересчитать горб (если заданы месяцы)
        months = _parse_months_list(st.session_state.get("hump_months", ""))
        if len(months) > 0:
            if str(st.session_state.get("hump_rate", "")).strip():
                on_hump_rate_change()
            elif str(st.session_state.get("hump_pay", "")).strip():
                on_hump_pay_change()

    # =========================================================
    # 1) ROW 1: client | bank | sum | term  (ONE LINE ровно)
    # =========================================================
    c1, c2, c3, c4 = st.columns([2.4, 1.2, 1.3, 0.9], gap="small")

    with c1:
        st.markdown("<div class='calc-cap'>Клиент</div>", unsafe_allow_html=True)
        fio_pick = st_searchbox(
            _search_client,
            placeholder="Начни ввод",
            key="calc_client_search",
        )
        client_fio = fio_pick or ""

    with c2:
        st.markdown("<div class='calc-cap'>Банк</div>", unsafe_allow_html=True)
        st.selectbox("", banks, key="calc_bank", label_visibility="collapsed")

    # find client
    if clients_df is not None and not clients_df.empty and fio_pick and "fio" in clients_df.columns:
        hit = clients_df[clients_df["fio"].astype(str) == fio_pick]
        if not hit.empty:
            selected_client = hit.iloc[0].to_dict()

    # autofill credit_sum if empty - ОТКЛЮЧЕНО ПО ПРОСЬБЕ ЮЗЕРА
    # if selected_client and selected_client.get("credit_sum") and not str(st.session_state["calc_credit_sum"]).strip():
    #     st.session_state["calc_credit_sum"] = str(selected_client.get("credit_sum"))

    with c3:
        st.markdown("<div class='calc-cap'>Сумма кредита</div>", unsafe_allow_html=True)
        st.text_input(
            "",
            key="calc_credit_sum",
            label_visibility="collapsed",
            on_change=lambda: (on_money_format("calc_credit_sum"), on_credit_or_term_change()),
        )

    with c4:
        st.markdown("<div class='calc-cap'>Срок (мес)</div>", unsafe_allow_html=True)
        st.text_input("", key="calc_term", placeholder="240", label_visibility="collapsed", on_change=on_credit_or_term_change)

    # computed
    credit_sum = _get_credit_sum()
    credit_term = _get_term()
    bank_name = st.session_state.get("calc_bank", "")
    _spacer()

    # =========================================================
    # 2) ROW 2: base% | hump% | hump pay | hump months | keep first
    #    (ты просила checkbox тут)
    # =========================================================
    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns([0.9, 0.9, 1.1, 1.2, 0.9], gap="small")

    with r2c1:
        st.markdown("<div class='calc-cap'>База %</div>", unsafe_allow_html=True)
        st.text_input("", key="base_rate", placeholder="30", label_visibility="collapsed")

    with r2c2:
        st.markdown("<div class='calc-cap'>Горб %</div>", unsafe_allow_html=True)
        st.text_input("", key="hump_rate", placeholder="48", label_visibility="collapsed", on_change=on_hump_rate_change)

    with r2c3:
        st.markdown("<div class='calc-cap'>Платёж горба ₽</div>", unsafe_allow_html=True)
        st.text_input(
            "",
            key="hump_pay",
            placeholder="80 000",
            label_visibility="collapsed",
            on_change=lambda: (on_money_format("hump_pay"), on_hump_pay_change()),
        )

    with r2c4:
        st.markdown("<div class='calc-cap'>Месяцы горба</div>", unsafe_allow_html=True)
        st.text_input("", key="hump_months", placeholder="1,2 или 1-3", label_visibility="collapsed", on_change=on_hump_rate_change)

    with r2c5:
        st.markdown("<div class='calc-cap'>1-й на счёте</div>", unsafe_allow_html=True)
        st.checkbox("", key="keep_first", label_visibility="collapsed")

    base_rate = _get_base_rate()
    hump_rate = _parse_pct(st.session_state.get("hump_rate", ""))
    hump_months = _parse_months_list(st.session_state.get("hump_months", ""))
    hump_count = len(hump_months)

    base_payment = annuity_payment(credit_sum, credit_term, base_rate)

    # hump payment:
    # - если user ввёл % -> он сам пересчитался в поле hump_pay (через callback)
    # - если user ввёл платёж -> % мог пересчитаться
    hump_payment = _parse_money(st.session_state.get("hump_pay", ""))

    # если нет месяцев — считаем горб "неактивным"
    if hump_count == 0:
        hump_payment = 0.0
        # Очищаем визуально поле платежа, чтобы не путать юзера
        # НЕ трогаем st.session_state["hump_pay"] во избежание ошибки StreamlitAPIException


    hump_sum_payments = hump_payment * hump_count

    # =========================================================
    # 2.1) Under row: payments blocks (видимые подписи)
    # =========================================================
    p1, p2 = st.columns([1, 1], gap="small")
    with p1:
        st.markdown(f"<div class='calc-muted'>Платёж базовый</div><div class='calc-val'>{_fmt_money(base_payment)}</div>", unsafe_allow_html=True)
    with p2:
        if hump_sum_payments > 0:
            st.markdown(f"<div class='calc-muted'>Сумма платежей горба</div><div class='calc-val'>{_fmt_money(hump_sum_payments)}</div>", unsafe_allow_html=True)

    # divider removed
    _spacer()

    # =========================================================
    # 4) Insurance + Commission (4 cols in one row)
    # =========================================================
    # Ins% | InsSum | Com% | ComSum
    c_ins1, c_ins2, c_com1, c_com2 = st.columns([0.8, 1.2, 0.8, 1.2], gap="small")

    # --- INSURANCE ---
    with c_ins1:
        st.markdown("<div class='calc-cap'>Страховка %</div>", unsafe_allow_html=True)
        st.text_input("", key="ins_pct", placeholder="3", label_visibility="collapsed", on_change=on_ins_pct_change)
    with c_ins2:
        st.markdown("<div class='calc-cap'>Страховка ₽</div>", unsafe_allow_html=True)
        st.text_input(
            "",
            key="ins_sum",
            placeholder="120 000",
            label_visibility="collapsed",
            on_change=lambda: (on_money_format("ins_sum"), on_ins_sum_change()),
        )

    insurance_percent = _parse_pct(st.session_state.get("ins_pct", ""))
    insurance_sum = _parse_money(st.session_state.get("ins_sum", ""))

    # --- COMMISSION ---
    with c_com1:
        st.markdown("<div class='calc-cap'>Комиссия %</div>", unsafe_allow_html=True)
        st.text_input("", key="rko_pct", placeholder="1,5", label_visibility="collapsed", on_change=on_rko_pct_change)
    with c_com2:
        st.markdown("<div class='calc-cap'>Комиссия ₽</div>", unsafe_allow_html=True)
        st.text_input(
            "",
            key="rko_sum",
            placeholder="150 000",
            label_visibility="collapsed",
            on_change=lambda: (on_money_format("rko_sum"), on_rko_sum_change()),
        )

    rko_percent = _parse_pct(st.session_state.get("rko_pct", ""))
    rko_sum = _parse_money(st.session_state.get("rko_sum", ""))

    # divider removed
    _spacer()

    # =========================================================
    # 5) Reg + Notary + PND + Accr (5 columns in one row)
    # =========================================================
    # reg_add | reg_remove | notary | pnd_nd | accr
    r5c1, r5c2, r5c3, r5c4, r5c5 = st.columns([1, 1, 1, 1, 1], gap="small")

    with r5c1:
        st.markdown("<div class='calc-cap'>Рег. (налож.)</div>", unsafe_allow_html=True)
        st.text_input("", key="reg_add", placeholder="0", label_visibility="collapsed", on_change=lambda: on_money_format("reg_add"))
    with r5c2:
        st.markdown("<div class='calc-cap'>Рег. (снятие)</div>", unsafe_allow_html=True)
        st.text_input("", key="reg_remove", placeholder="0", label_visibility="collapsed", on_change=lambda: on_money_format("reg_remove"))
    with r5c3:
        st.markdown("<div class='calc-cap'>Нотариус</div>", unsafe_allow_html=True)
        st.text_input("", key="notary", placeholder="5000", label_visibility="collapsed", on_change=lambda: on_money_format("notary"))
    with r5c4:
        st.markdown("<div class='calc-cap'>ПНД / НД</div>", unsafe_allow_html=True)
        st.text_input("", key="pnd_nd", placeholder="0", label_visibility="collapsed", on_change=lambda: on_money_format("pnd_nd"))
    with r5c5:
        st.markdown("<div class='calc-cap'>Аккредитив</div>", unsafe_allow_html=True)
        st.text_input("", key="accr", placeholder="0", label_visibility="collapsed", on_change=lambda: on_money_format("accr"))

    reg_add = _parse_money(st.session_state.get("reg_add", ""))
    reg_remove = _parse_money(st.session_state.get("reg_remove", ""))
    notary = _parse_money(st.session_state.get("notary", ""))
    pnd_nd = _parse_money(st.session_state.get("pnd_nd", ""))
    accr = _parse_money(st.session_state.get("accr", ""))

    _spacer()

    # =========================================================
    # 7) Buyout / Fast
    # =========================================================
    with st.expander("Закладная"):
        b1, b2 = st.columns(2, gap="small")
        with b1:
            st.markdown("<div class='calc-cap'>Выкуп закладной</div>", unsafe_allow_html=True)
            st.text_input("", key="buyout", placeholder="0", label_visibility="collapsed", on_change=lambda: on_money_format("buyout"))
        with b2:
            st.markdown("<div class='calc-cap'>Ускор. закладной</div>", unsafe_allow_html=True)
            st.text_input("", key="fast", placeholder="0", label_visibility="collapsed", on_change=lambda: on_money_format("fast"))

    buyout = _parse_money(st.session_state.get("buyout", ""))
    fast = _parse_money(st.session_state.get("fast", ""))
    # accr moved to prev block

    # divider removed
    _spacer()

    # =========================================================
    # 8) Short money (simple scheme)
    # =========================================================
    # =========================================================
    # 8) Short money (simple scheme) - Collapsible
    # =========================================================
    with st.expander("Короткие"):
        # Layout: Debt(0.8) | Inv%(0.5) | InvComm(0.8) | Return(1.0)
        s1, s2, s3, s4 = st.columns([0.8, 0.5, 0.8, 1.0], gap="small")
        with s1:
            st.markdown("<div class='calc-cap'>Сумма к перекрытию</div>", unsafe_allow_html=True)
            st.text_input(
                "", 
                key="overlap", 
                placeholder="5 000 000", 
                label_visibility="collapsed", 
                on_change=lambda: (on_money_format("overlap"), on_inv_pct_change()) # also recalc comm if overlap changes
            )
        with s2:
            st.markdown("<div class='calc-cap'>Комса инвестора %</div>", unsafe_allow_html=True)
            st.text_input("", key="inv_pct", placeholder="4", label_visibility="collapsed", on_change=on_inv_pct_change)
        
        with s3:
            st.markdown("<div class='calc-cap'>Комса ₽</div>", unsafe_allow_html=True)
            st.text_input(
                "",
                key="inv_comm",
                placeholder="0",
                label_visibility="collapsed",
                on_change=lambda: (on_money_format("inv_comm"), on_inv_comm_change())
            )

        overlap = _parse_money(st.session_state.get("overlap", ""))
        inv_pct = _parse_pct(st.session_state.get("inv_pct", ""))
        inv_comm = _parse_money(st.session_state.get("inv_comm", ""))

        # Calc total return
        inv_fee = inv_comm # Alias for compatibility
        to_investor = overlap + inv_comm

        with s4:
            st.markdown("<div class='calc-cap'>Вернуть инвестору</div>", unsafe_allow_html=True)
            st.text_input(
                "",
                value=_fmt_money(to_investor),
                disabled=True,
                label_visibility="collapsed"
            )

    _spacer()

    # =========================================================
    # 9) Totals (hold logic)
    # =========================================================
    keep_first = bool(st.session_state.get("keep_first", False))

    hold_payment = 0.0
    if keep_first:
        # User logic: 
        # Если 1-й месяц входит в горб и есть платеж горба -> берем горб.
        # Иначе (нет горба или 1-го месяца нет в списке) -> берем базу.
        if (1 in hump_months) and (hump_payment > 0):
            hold_payment = hump_payment
        else:
            hold_payment = base_payment

    total_expenses_wo_hold = (
        insurance_sum
        + rko_sum
        + reg_add
        + reg_remove
        + notary
        + pnd_nd
        + buyout
        + fast
        + accr
        + inv_fee
    )
    total_expenses_with_hold = total_expenses_wo_hold + hold_payment

    # На руки = сумма кредита − (все расходы) − (перекрытие старого банка)
    on_hand_wo_hold = credit_sum - total_expenses_wo_hold - overlap
    on_hand_with_hold = credit_sum - total_expenses_with_hold - overlap

    if keep_first:
        st.markdown(
            f"""
            <div class="calc-card">
              <div class="calc-sub">ИТОГИ</div>
              <div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:8px;">
                <div style="min-width:240px;">
                  <div class="calc-sub">Итого расходов (без 1-го)</div>
                  <div class="calc-big">{_fmt_money(total_expenses_wo_hold)}</div>
                </div>
                <div style="min-width:240px;">
                  <div class="calc-sub">Итого расходов (с 1-м)</div>
                  <div class="calc-big">{_fmt_money(total_expenses_with_hold)}</div>
                  <div class="calc-sub">удержание: {_fmt_money(hold_payment)}</div>
                </div>
                <div style="min-width:240px;">
                  <div class="calc-sub">На руки (без 1-го)</div>
                  <div class="calc-big">{_fmt_money(on_hand_wo_hold)}</div>
                </div>
                <div style="min-width:240px;">
                  <div class="calc-sub">На руки (с 1-м)</div>
                  <div class="calc-big">{_fmt_money(on_hand_with_hold)}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Simple view (only totals)
        st.markdown(
            f"""
            <div class="calc-card">
              <div class="calc-sub">ИТОГИ</div>
              <div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:8px;">
                <div style="min-width:240px;">
                  <div class="calc-sub">Итого расходов</div>
                  <div class="calc-big">{_fmt_money(total_expenses_wo_hold)}</div>
                </div>
                <div style="min-width:240px;">
                  <div class="calc-sub">На руки</div>
                  <div class="calc-big">{_fmt_money(on_hand_wo_hold)}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # divider removed

    # =========================================================
    # 10) Report for copy (WhatsApp)
    # =========================================================
    months_line = ", ".join(str(m) for m in hump_months) if hump_months else "—"

    lines = []
    lines.append(f"Клиент: {client_fio or '—'}")
    lines.append(f"Банк: {bank_name}")
    lines.append("")
    lines.append(f"Сумма кредита: {_fmt_money(credit_sum)}")
    lines.append(f"Срок: {credit_term} мес")
    lines.append("")
    lines.append("Ставки и платежи:")
    lines.append(f"• База: {base_rate:.2f}% → {_fmt_money(base_payment)}")
    if hump_count > 0 and (hump_rate > 0 or hump_payment > 0):
        # покажем и % и платеж из текущих полей
        lines.append(f"• Горб: {hump_rate:.2f}% → {_fmt_money(hump_payment)} (мес: {months_line})")
        lines.append(f"• Сумма платежей горба ({hump_count} мес): {_fmt_money(hump_sum_payments)}")
    else:
        lines.append("• Горб: —")

    if keep_first:
        lines.append(f"• 1-й платеж оставить на счёте: {_fmt_money(hold_payment)}")

    lines.append("")
    lines.append("Расходы:")
    if insurance_sum > 0:
        lines.append(f"• Страховка: {_fmt_pct(insurance_percent)} = {_fmt_money(insurance_sum)}")
    if rko_sum > 0:
        lines.append(f"• Комиссия банка: {_fmt_pct(rko_percent)} = {_fmt_money(rko_sum)}")
    if reg_add > 0:
        lines.append(f"• Регистрация (наложение): {_fmt_money(reg_add)}")
    if reg_remove > 0:
        lines.append(f"• Регистрация (снятие): {_fmt_money(reg_remove)}")
    if notary > 0:
        lines.append(f"• Нотариус: {_fmt_money(notary)}")
    if pnd_nd > 0:
        lines.append(f"• ПНД/НД: {_fmt_money(pnd_nd)}")
    if buyout > 0:
        lines.append(f"• Выкуп закладной: {_fmt_money(buyout)}")
    if fast > 0:
        lines.append(f"• Ускор. закладной: {_fmt_money(fast)}")
    if accr > 0:
        lines.append(f"• Аккредитив: {_fmt_money(accr)}")

    lines.append("")
    lines.append("Короткие:")
    lines.append(f"• Сумма к перекрытию: {_fmt_money(overlap)}")
    if overlap > 0 and inv_pct > 0:
        lines.append(f"• Комиссия инвестора %: {inv_pct:.2f}%")
        lines.append(f"• Комиссия инвестора ₽: {_fmt_money(inv_fee)}")
        lines.append(f"• Вернуть инвестору: {_fmt_money(to_investor)}")

    lines.append("")
    if keep_first:
        lines.append(f"ИТОГО расходов (без 1-го платежа): {_fmt_money(total_expenses_wo_hold)}")
        lines.append(f"ИТОГО расходов (с 1-м платежом): {_fmt_money(total_expenses_with_hold)}")
        lines.append(f"НА РУКИ (без 1-го платежа): {_fmt_money(on_hand_wo_hold)}")
        lines.append(f"НА РУКИ (с 1-м платежом): {_fmt_money(on_hand_with_hold)}")
    else:
        lines.append(f"ИТОГО расходов: {_fmt_money(total_expenses_wo_hold)}")
        lines.append(f"НА РУКИ: {_fmt_money(on_hand_wo_hold)}")

    wa_text = "\n".join(lines)

    st.markdown("<div class='calc-cap'>&nbsp;</div>", unsafe_allow_html=True)
    st.code(wa_text, language=None)