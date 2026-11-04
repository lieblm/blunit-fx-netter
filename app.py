#!/usr/bin/env python3
"""
Blunit FX Netter - Interactive Web Dashboard & Simulator.

Built with Streamlit and Plotly for real-time visualization of
internal FX netting, risk limits, auto-hedging, and profitability.
Features institutional risk management (VaR, three-zone limits, inventory skewing,
and opportunistic market-timed hedging).
"""

import sys
from datetime import datetime, timezone, date
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Ensure src package is accessible
sys.path.insert(0, str(Path(__file__).parent / "src"))

from blunit_fx.pricing import PricingModel, InventorySkewPricingModel
from blunit_fx.engine import NetterEngine
from blunit_fx.simulator import SimulationRunner
from blunit_fx.data_loader import load_market_data


# --- Page Configuration ---
st.set_page_config(
    page_title="Blunit FX Netter Dashboard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for executive cards and styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .metric-subtitle {
        font-size: 0.85rem;
        color: #475569;
    }
    .risk-card {
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
        border: 1px solid #e2e8f0;
    }
    .zone-green {
        background-color: #f0fdf4;
        border-color: #bbf7d0;
        color: #166534;
    }
    .zone-yellow {
        background-color: #fefce8;
        border-color: #fef08a;
        color: #854d0e;
    }
    .zone-red {
        background-color: #fef2f2;
        border-color: #fecaca;
        color: #991b1b;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        padding-left: 16px;
        padding-right: 16px;
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def get_historical_candles(filepath: str, start_dt: datetime, end_dt: datetime):
    """Load and cache market candle data for the selected date range."""
    return load_market_data(
        filepath=Path(filepath),
        start_date=start_dt,
        end_date=end_dt,
    )


# --- Sidebar: Configuration & Controls ---
st.sidebar.title("Parametry simulace")

default_data_file = "fxdata/eurczk-h4-bid-2017-01-02-2026-10-15.csv"
data_file_path = st.sidebar.text_input(
    "Soubor s kurzy",
    value=default_data_file,
    help="Cesta k historickým datům EUR/CZK (H4 svíčky)",
)

# Date Presets
st.sidebar.subheader("Časové období")
preset = st.sidebar.selectbox(
    "Přednastavené období",
    options=["Rok 2025 (Výchozí)", "Rok 2023", "Vlastní rozsah"],
    index=0,
)

if preset == "Rok 2025 (Výchozí)":
    init_start = date(2025, 1, 1)
    init_end = date(2025, 12, 31)
elif preset == "Rok 2023":
    init_start = date(2023, 1, 1)
    init_end = date(2023, 12, 31)
else:
    init_start = date(2024, 1, 1)
    init_end = date(2024, 12, 31)

col_d1, col_d2 = st.sidebar.columns(2)
start_date_val = col_d1.date_input("Od", value=init_start)
end_date_val = col_d2.date_input("Do", value=init_end)

st.sidebar.subheader("Řízení rizika & Škálování")
hedge_limit_input = st.sidebar.number_input(
    "Limit rizika NOP (EUR)",
    min_value=1000.0,
    max_value=200000.0,
    value=25000.0,
    step=2500.0,
    help="Prahová hodnota otevřené pozice pro spuštění havarijního auto-hedgingu",
)

hedge_mode_choice = st.sidebar.selectbox(
    "Režim auto-hedgingu",
    options=[
        "Částečné dorovnání na 50 % (Doporučeno)",
        "Kompletní reset na 0 EUR",
    ],
    index=0,
    help="Částečné dorovnání ponechává rezervu pro okamžitý přirozený netting dalších protichůdných pokynů.",
)
hedge_target_ratio_val = 0.5 if "50 %" in hedge_mode_choice else 0.0

st.sidebar.subheader("Oportunistický hedging (Časování)")
enable_opp_hedge = st.sidebar.checkbox(
    "Aktivovat oportunistický hedging",
    value=True,
    help="Vybírá výhodný tržní kurz pro odprodej/dokup přebytku v Zóně 2 dříve, než pozice narazí na havarijní limit.",
)

if enable_opp_hedge:
    opp_threshold_input = st.sidebar.slider(
        "Prahová hodnota pro časování (EUR)",
        min_value=5000.0,
        max_value=hedge_limit_input,
        value=min(17500.0, hedge_limit_input * 0.8),
        step=2500.0,
        help="Minimální otevřená pozice (NOP), při které se začíná vyhodnocovat příznivý kurz pro odbourání inventáře",
    )
    timing_k_input = st.sidebar.slider(
        "Citlivost odchylky kurzu (k * sigma)",
        min_value=0.25,
        max_value=2.0,
        value=0.75,
        step=0.25,
        help="Požadovaná odchylka od klouzavého průměru (0.75 = střední citlivost)",
    )
else:
    opp_threshold_input = 17500.0
    timing_k_input = 0.75

st.sidebar.subheader("Cenotvorba & Vychylování")
spread_pct_input = st.sidebar.slider(
    "Klientský spread (%)",
    min_value=0.10,
    max_value=1.50,
    value=0.40,
    step=0.05,
    help="Celkový spread mezi klientským Bid a Ask kurzem (výchozí 0.40 % = půl-spread 0.20 %)",
)

enable_skew = st.sidebar.checkbox(
    "Aktivovat Inventory Skewing",
    value=True,
    help="Posouvá kótované kurzy podle otevřené pozice: láká protisměrné klienty k přirozenému nettingu a snižuje zásahy banky.",
)

if enable_skew:
    skew_bps_input = st.sidebar.slider(
        "Intenzita vychýlení (bps)",
        min_value=1,
        max_value=15,
        value=5,
        step=1,
        help="Posun středu kurzu při 100% naplnění limitu (5 bps = 0.05 %)",
    )
    skew_factor_val = skew_bps_input / 10000.0
else:
    skew_factor_val = 0.0

st.sidebar.subheader("Simulační tok & Frekvence")
flow_mode_choice = st.sidebar.radio(
    "Režim klientského toku",
    options=["Vysokofrekvenční (Backtest)", "Nízkofrekvenční / Řídký (Praxe firem)"],
    index=0,
    help="Nízkofrekvenční režim simuluje reálný stav, kdy přichází jen několik velkých či nepravidelných pokynů týdně.",
)

if flow_mode_choice == "Nízkofrekvenční / Řídký (Praxe firem)":
    days_between_orders = st.sidebar.slider(
        "Průměrná prodleva mezi obchody (dny)",
        min_value=0.5,
        max_value=14.0,
        value=2.0,
        step=0.5,
        help="2 dny = v průměru 1 klientský pokyn za 2 dny (~150 pokynů ročně)",
    )
    # 6 H4 candles per day
    orders_per_candle_val = 1.0 / (days_between_orders * 6.0)
else:
    orders_per_candle_input = st.sidebar.slider(
        "Počet pokynů na svíčku (H4)",
        min_value=1,
        max_value=5,
        value=1,
        help="Frekvence klientských objednávek v rámci každého 4hodinového intervalu",
    )
    orders_per_candle_val = float(orders_per_candle_input)

st.sidebar.subheader("Časové řízení rizik (Aging & Víkend)")
enable_aging_limit = st.sidebar.checkbox(
    "Časový limit otevřené pozice (Time-Stop)",
    value=True,
    help="Vynutí vyrovnání pozice (Hedge), pokud zůstane otevřená déle než stanovený počet hodin bez protipokynu.",
)
if enable_aging_limit:
    max_holding_hours_val = st.sidebar.slider(
        "Maximální doba držení (hodiny)",
        min_value=12,
        max_value=120,
        value=48,
        step=6,
        help="Po uplynutí této doby je NOP automaticky zredukováno.",
    )
    enable_time_decay_val = st.sidebar.checkbox(
        "Aktivovat Time-Decay (útlum prahu a k-parametru v čase)",
        value=True,
        help="Jak pozice stárne, oportunistický práh klesá a systém je ochoten vzít i průměrný kurz pro odbourání rizika.",
    )
else:
    max_holding_hours_val = None
    enable_time_decay_val = False

enable_weekend_flatten_val = st.sidebar.checkbox(
    "Páteční víkendové zploštění (Weekend Flattening)",
    value=True,
    help="V pátek v 16:00 UTC zredukuje NOP pod bezpečnostní limit před zavřením trhů, čímž eliminuje víkendový gap risk.",
)
if enable_weekend_flatten_val:
    weekend_threshold_val = st.sidebar.number_input(
        "Páteční bezpečný limit NOP (EUR)",
        min_value=0.0,
        max_value=float(hedge_limit_input),
        value=min(5000.0, float(hedge_limit_input)),
        step=1000.0,
        help="Pokud je v pátek v 16:00 UTC pozice vyšší než tato hodnota, přebytek se odprodá/dokoupí.",
    )
else:
    weekend_threshold_val = 5000.0

enable_block_split = st.sidebar.checkbox(
    "Dělení velkých objednávek (Block Order Split)",
    value=False,
    help="Při příchodu velkého klientského tiketu pošle část ihned na mezibankovní trh (Back-to-Back) a zbytek internalizuje.",
)
if enable_block_split:
    block_threshold_val = st.sidebar.number_input(
        "Práh velkého pokynu (EUR)",
        min_value=5000.0,
        max_value=100000.0,
        value=15000.0,
        step=2500.0,
    )
    block_split_ratio_val = st.sidebar.slider(
        "Podíl okamžitého zajištění na trhu (%)",
        min_value=10,
        max_value=90,
        value=50,
        step=10,
    ) / 100.0
else:
    block_threshold_val = None
    block_split_ratio_val = 0.5

seed_input = st.sidebar.number_input(
    "Náhodný seed (RNG)",
    min_value=1,
    max_value=99999,
    value=42,
    help="Zajišťuje plnou reprodukovatelnost klientských toků",
)

run_button = st.sidebar.button("Spustit simulaci", type="primary", use_container_width=True)


# --- Main Application Header ---
st.title("Blunit FX Netter - Dashboard")
st.caption(
    "Interní netting engine s oportunistickým hedgingem, řízením tržního rizika a škálováním pro pár EUR/CZK."
)

# Convert dates to UTC datetimes
start_dt = datetime.combine(start_date_val, datetime.min.time(), tzinfo=timezone.utc)
end_dt = datetime.combine(end_date_val, datetime.max.time(), tzinfo=timezone.utc)

data_path = Path(data_file_path)
if not data_path.exists():
    st.error(f"Soubor s daty nebyl nalezen: `{data_path}`")
    st.stop()

# Load data and run simulation
with st.spinner("Načítání tržních dat a provádění výpočtů..."):
    candles = get_historical_candles(str(data_path), start_dt, end_dt)

if not candles:
    st.warning("Pro zvolené časové období nebyly v datasetu nalezeny žádné tržní svíčky.")
    st.stop()

initial_mid = candles[0].mid_price
pricing = PricingModel(
    mid_rate=initial_mid,
    spread_pct=spread_pct_input / 100.0,
    skew_factor=skew_factor_val,
    hedge_limit=hedge_limit_input,
)
engine = NetterEngine(
    pricing_model=pricing,
    hedge_limit=hedge_limit_input,
    hedge_target_ratio=hedge_target_ratio_val,
    enable_opportunistic_hedge=enable_opp_hedge,
    opportunistic_threshold=opp_threshold_input,
    timing_window=20,
    timing_k=timing_k_input,
    max_holding_hours=max_holding_hours_val,
    enable_time_decay=enable_time_decay_val,
    enable_weekend_flattening=enable_weekend_flatten_val,
    weekend_flatten_hour=16,
    weekend_flatten_threshold=weekend_threshold_val,
    large_order_threshold=block_threshold_val,
    large_order_split_ratio=block_split_ratio_val,
)
runner = SimulationRunner(engine=engine)

summary = runner.run_historical(
    candles=candles,
    orders_per_candle=orders_per_candle_val,
    seed=seed_input,
    verbose=False,
)

records = engine.trade_log
df_records = pd.DataFrame([
    {
        "trade_id": r.trade_id,
        "timestamp": r.timestamp,
        "event_type": r.event_type,
        "event_subtype": getattr(r, "event_subtype", ""),
        "side": r.side.value,
        "volume_eur": r.volume_eur,
        "execution_rate": r.execution_rate,
        "volume_czk": r.volume_czk,
        "spread_profit_czk": r.spread_profit_czk,
        "balance_eur": r.balance_eur,
        "balance_czk": r.balance_czk,
        "nop_eur": r.nop_eur,
        "market_rate": r.market_rate,
        "running_pnl_czk": r.running_pnl_czk,
        "running_pnl_eur": r.running_pnl_eur,
    }
    for r in records
])


# --- Top KPI Summary Section ---
col1, col2, col3, col4 = st.columns(4)

netted_vol = summary.get("netted_volume_eur", summary.get("internalized_volume_eur", 0.0))
netting_rate = summary.get("netting_rate_pct", summary.get("internalization_rate_pct", 0.0))
opp_hedges_cnt = summary.get("opportunistic_hedge_count", 0)
time_stop_cnt = summary.get("time_stop_hedge_count", 0)
weekend_cnt = summary.get("weekend_flatten_hedge_count", 0)
block_split_cnt = summary.get("block_split_hedge_count", 0)
hard_hedges_cnt = summary.get("hard_hedge_count", summary.get("hedge_count", 0))

# Calculate holding durations
holding_durations = []
current_start = None
for r in records:
    if abs(r.nop_eur) > 1e-4:
        if current_start is None:
            current_start = r.timestamp
    else:
        if current_start is not None:
            holding_durations.append((r.timestamp - current_start).total_seconds() / 3600.0)
            current_start = None
if current_start is not None and records:
    holding_durations.append((records[-1].timestamp - current_start).total_seconds() / 3600.0)
max_holding_hrs = max(holding_durations) if holding_durations else 0.0

with col1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Klientský obrat</div>
            <div class="metric-value">{summary['total_volume_eur']:,.0f} EUR</div>
            <div class="metric-subtitle">{summary['total_volume_czk']:,.0f} CZK &bull; {summary['total_orders']:,} pokynů</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Míra internalizace</div>
            <div class="metric-value">{netting_rate:.1f} %</div>
            <div class="metric-subtitle">{netted_vol:,.0f} EUR vyrovnáno uvnitř firmy</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Čistý výsledek (MtM)</div>
            <div class="metric-value" style="color: #16a34a;">+{summary['total_pnl_czk']:,.0f} CZK</div>
            <div class="metric-subtitle">Spread: +{summary['accumulated_spread_czk']:,.0f} CZK (~{summary['total_pnl_eur']:,.0f} EUR)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

max_abs_nop = df_records["nop_eur"].abs().max() if not df_records.empty else 0.0
limit_utilization = (max_abs_nop / hedge_limit_input) * 100 if hedge_limit_input > 0 else 0

with col4:
    hedge_sub_parts = []
    if opp_hedges_cnt > 0:
        hedge_sub_parts.append(f"Oportun.: {opp_hedges_cnt}")
    if time_stop_cnt > 0:
        hedge_sub_parts.append(f"Časové: {time_stop_cnt}")
    if weekend_cnt > 0:
        hedge_sub_parts.append(f"Víkend: {weekend_cnt}")
    if hard_hedges_cnt > 0:
        hedge_sub_parts.append(f"Hard stop: {hard_hedges_cnt}")
    if not hedge_sub_parts:
        hedge_sub_parts.append(f"Hedgováno {summary['total_hedged_eur']:,.0f} EUR")
    hedge_subtext = " &bull; ".join(hedge_sub_parts)

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Externí zajištění (Hedge)</div>
            <div class="metric-value">{summary['hedge_count']} operací</div>
            <div class="metric-subtitle" style="font-size: 0.78rem;">{hedge_subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")


# --- Institutional Risk Cockpit: Value at Risk & Three-Zone Traffic Light ---
st.subheader("Řízení rizik a kapitálová přiměřenost (Risk Cockpit)")

daily_sigma = 0.002165
ref_rate = summary.get("mid_rate", 25.0)

var95_czk = max_abs_nop * ref_rate * 1.645 * daily_sigma
var99_czk = max_abs_nop * ref_rate * 2.326 * daily_sigma
max_historical_shock_czk = max_abs_nop * ref_rate * 0.01823  # 10Y max drop: 1.823%

zone_threshold_green = hedge_limit_input * 0.60
zone_threshold_yellow = hedge_limit_input * 1.00

# Two-dimensional traffic light (Volume x Duration)
if max_abs_nop <= zone_threshold_green:
    if max_holding_hours_val and max_holding_hrs >= max_holding_hours_val * 0.8:
        current_zone = "ŽLUTÁ ZÓNA (Časové varování)"
        zone_class = "zone-yellow"
        zone_desc = f"Objem NOP v normě, ale pozice byla držena až {max_holding_hrs:.1f} h (blízko limitu {max_holding_hours_val:.0f} h)."
    else:
        current_zone = "ZELENÁ ZÓNA (0 – 60 % limitu)"
        zone_class = "zone-green"
        zone_desc = "Běžný provozní netting. Minimální tržní i časové riziko."
elif max_abs_nop <= zone_threshold_yellow:
    current_zone = "ŽLUTÁ ZÓNA (60 – 100 % limitu)"
    zone_class = "zone-yellow"
    zone_desc = "Zvýšená otevřená pozice. Aktivní cenové vychylování a časové/oportunistické zajištění."
else:
    current_zone = "ČERVENÁ ZÓNA (>= 100 % limitu)"
    zone_class = "zone-red"
    zone_desc = "Dosažen limit rizika. Proveden havarijní auto-hedge na externím trhu."

col_r1, col_r2, col_r3, col_r4 = st.columns([1.1, 1.1, 1.1, 1.1])

with col_r1:
    st.markdown(
        f"""
        <div class="risk-card {zone_class}">
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">Semafor rizika (2D)</div>
            <div style="font-size: 1.25rem; font-weight: 800; margin-top: 4px;">{current_zone.split(' ')[0]} {current_zone.split(' ')[1]}</div>
            <div style="font-size: 0.82rem; margin-top: 6px;">{zone_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_r2:
    st.markdown(
        f"""
        <div class="risk-card" style="background-color: #f8fafc;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #475569; text-transform: uppercase;">Tržní riziko (Value at Risk)</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-top: 4px;">VaR 99 %: {var99_czk:,.0f} CZK</div>
            <div style="font-size: 0.82rem; color: #64748b; margin-top: 4px;">
                VaR 95 %: <b>{var95_czk:,.0f} CZK</b> &bull; Riziko: <b>{var99_czk / (summary['total_pnl_czk'] or 1.0) * 100:.2f} %</b> zisku
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_r3:
    st.markdown(
        f"""
        <div class="risk-card" style="background-color: #f8fafc;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #475569; text-transform: uppercase;">Stresový test (10Y šok 1,82 %)</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #b91c1c; margin-top: 4px;">-{max_historical_shock_czk:,.0f} CZK</div>
            <div style="font-size: 0.82rem; color: #64748b; margin-top: 4px;">
                Nejhorší 4H pohyb EUR/CZK od roku 2017
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_r4:
    aging_status_color = "#16a34a" if (not max_holding_hours_val or max_holding_hrs < max_holding_hours_val * 0.8) else "#b91c1c"
    limit_str = f"{max_holding_hours_val:.0f} h" if max_holding_hours_val else "Bez limitu"
    st.markdown(
        f"""
        <div class="risk-card" style="background-color: #f8fafc;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #475569; text-transform: uppercase;">Stáří pozice (Position Aging)</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: {aging_status_color}; margin-top: 4px;">Max: {max_holding_hrs:.1f} h</div>
            <div style="font-size: 0.82rem; color: #64748b; margin-top: 4px;">
                Limit: <b>{limit_str}</b> &bull; Time-Stop: <b>{time_stop_cnt}</b> &bull; Víkend: <b>{weekend_cnt}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    f"**Vytížení limitu NOP:** Maximální pozice **{max_abs_nop:,.0f} EUR** z limitu **{hedge_limit_input:,.0f} EUR** ({limit_utilization:.1f} %)."
)
st.progress(min(max(max_abs_nop / hedge_limit_input, 0.0), 1.0))

st.write("")


# --- Interactive Charts Section ---
tab_pnl, tab_nop, tab_rates = st.tabs([
    "📈 Kumulativní zisk (PnL)",
    "⚖️ Vývoj otevřené pozice a riziková pásma (NOP)",
    "📊 Tržní kurz EUR/CZK",
])

with tab_pnl:
    fig_pnl = go.Figure()
    fig_pnl.add_trace(
        go.Scatter(
            x=df_records["timestamp"],
            y=df_records["running_pnl_czk"],
            mode="lines",
            name="Čistý zisk (MtM PnL CZK)",
            line=dict(color="#16a34a", width=2.5),
            hovertemplate="%{x}<br>Čistý zisk: %{y:,.2f} CZK<extra></extra>",
        )
    )
    fig_pnl.update_layout(
        title="Vývoj čistého zisku v čase (CZK)",
        xaxis_title="Datum a čas",
        yaxis_title="Zisk v CZK",
        template="plotly_white",
        height=450,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_pnl, use_container_width=True)

with tab_nop:
    fig_nop = go.Figure()

    # Green Zone background shape (-0.6 * limit to +0.6 * limit)
    fig_nop.add_hrect(
        y0=-zone_threshold_green,
        y1=zone_threshold_green,
        fillcolor="rgba(34, 197, 94, 0.08)",
        line_width=0,
        annotation_text="Zelená zóna (Standardní netting)",
        annotation_position="inside top left",
    )

    # Yellow Zone background shapes
    fig_nop.add_hrect(
        y0=zone_threshold_green,
        y1=hedge_limit_input,
        fillcolor="rgba(234, 179, 8, 0.12)",
        line_width=0,
        annotation_text="Žlutá zóna (Rebalancing & Oportunistický hedge)",
        annotation_position="inside top left",
    )
    fig_nop.add_hrect(
        y0=-hedge_limit_input,
        y1=-zone_threshold_green,
        fillcolor="rgba(234, 179, 8, 0.12)",
        line_width=0,
    )

    # NOP curve
    fig_nop.add_trace(
        go.Scatter(
            x=df_records["timestamp"],
            y=df_records["nop_eur"],
            mode="lines",
            name="Otevřená pozice (NOP EUR)",
            line=dict(color="#2563eb", width=2),
            hovertemplate="%{x}<br>NOP: %{y:,.2f} EUR<extra></extra>",
        )
    )

    # Opportunistic Hedge events
    opp_hedge_rows = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "OPPORTUNISTIC")]
    if not opp_hedge_rows.empty:
        fig_nop.add_trace(
            go.Scatter(
                x=opp_hedge_rows["timestamp"],
                y=opp_hedge_rows["nop_eur"],
                mode="markers",
                name="Oportunistický hedge (Časování trhem)",
                marker=dict(color="#f59e0b", size=9, symbol="star"),
                hovertemplate="%{x}<br>Oportunistický hedge: %{y:,.2f} EUR<extra></extra>",
            )
        )

    # Time Stop Hedge events
    time_stop_rows = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "TIME_STOP")]
    if not time_stop_rows.empty:
        fig_nop.add_trace(
            go.Scatter(
                x=time_stop_rows["timestamp"],
                y=time_stop_rows["nop_eur"],
                mode="markers",
                name="Časový hedge (Time-Stop / Aging)",
                marker=dict(color="#0284c7", size=9, symbol="square"),
                hovertemplate="%{x}<br>Časový hedge (Time-Stop): %{y:,.2f} EUR<extra></extra>",
            )
        )

    # Weekend Flattening events
    weekend_rows = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "WEEKEND_FLATTEN")]
    if not weekend_rows.empty:
        fig_nop.add_trace(
            go.Scatter(
                x=weekend_rows["timestamp"],
                y=weekend_rows["nop_eur"],
                mode="markers",
                name="Páteční zploštění (Weekend Flattening)",
                marker=dict(color="#9333ea", size=10, symbol="triangle-up"),
                hovertemplate="%{x}<br>Páteční zploštění: %{y:,.2f} EUR<extra></extra>",
            )
        )

    # Block Split events
    block_rows = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "BLOCK_SPLIT")]
    if not block_rows.empty:
        fig_nop.add_trace(
            go.Scatter(
                x=block_rows["timestamp"],
                y=block_rows["nop_eur"],
                mode="markers",
                name="Dělení velkého pokynu (Block Split)",
                marker=dict(color="#0d9488", size=8, symbol="x"),
                hovertemplate="%{x}<br>Block Split hedge: %{y:,.2f} EUR<extra></extra>",
            )
        )

    # Hard Stop Hedge events
    hard_hedge_rows = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "HARD_STOP")]
    if not hard_hedge_rows.empty:
        fig_nop.add_trace(
            go.Scatter(
                x=hard_hedge_rows["timestamp"],
                y=hard_hedge_rows["nop_eur"],
                mode="markers",
                name="Havarijní hedge (Hard Stop)",
                marker=dict(color="#dc2626", size=9, symbol="diamond"),
                hovertemplate="%{x}<br>Havarijní hedge: %{y:,.2f} EUR<extra></extra>",
            )
        )

    # Opportunistic threshold guidelines if active
    if enable_opp_hedge and opp_threshold_input < hedge_limit_input:
        fig_nop.add_hline(
            y=opp_threshold_input,
            line_dash="dot",
            line_color="#d97706",
            annotation_text=f"Prah časování (+{opp_threshold_input:,.0f} EUR)",
            annotation_position="top left",
        )
        fig_nop.add_hline(
            y=-opp_threshold_input,
            line_dash="dot",
            line_color="#d97706",
            annotation_text=f"Prah časování (-{opp_threshold_input:,.0f} EUR)",
            annotation_position="bottom left",
        )

    # Upper and lower hedge boundaries (Red Zone trigger)
    fig_nop.add_hline(
        y=hedge_limit_input,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text=f"+Červený limit ({hedge_limit_input:,.0f} EUR)",
        annotation_position="top right",
    )
    fig_nop.add_hline(
        y=-hedge_limit_input,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text=f"-Červený limit (-{hedge_limit_input:,.0f} EUR)",
        annotation_position="bottom right",
    )

    # Target buffer lines after hedge if partial hedge
    if hedge_target_ratio_val > 0.0:
        target_val = hedge_limit_input * hedge_target_ratio_val
        fig_nop.add_hline(
            y=target_val,
            line_dash="dot",
            line_color="#0284c7",
            annotation_text=f"Cílový buffer (+{target_val:,.0f} EUR)",
            annotation_position="top left",
        )
        fig_nop.add_hline(
            y=-target_val,
            line_dash="dot",
            line_color="#0284c7",
            annotation_text=f"Cílový buffer (-{target_val:,.0f} EUR)",
            annotation_position="bottom left",
        )

    fig_nop.add_hline(y=0, line_color="#94a3b8", line_width=1)

    fig_nop.update_layout(
        title="Vývoj otevřené pozice (NOP) vůči třízónovému rámci a oportunistickým prahům",
        xaxis_title="Datum a čas",
        yaxis_title="Pozice v EUR",
        template="plotly_white",
        height=470,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_nop, use_container_width=True)

with tab_rates:
    df_candles = pd.DataFrame([
        {"timestamp": c.timestamp, "rate": c.mid_price}
        for c in candles
    ])
    fig_rates = go.Figure()
    fig_rates.add_trace(
        go.Scatter(
            x=df_candles["timestamp"],
            y=df_candles["rate"],
            mode="lines",
            name="Referenční kurz (Mid)",
            line=dict(color="#475569", width=2),
            hovertemplate="%{x}<br>Kurz: %{y:.4f} CZK/EUR<extra></extra>",
        )
    )
    fig_rates.update_layout(
        title="Tržní kurz EUR/CZK (H4 svíčky)",
        xaxis_title="Datum a čas",
        yaxis_title="Kurz CZK za EUR",
        template="plotly_white",
        height=450,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_rates, use_container_width=True)


# --- Ledger & Transactions Section ---
st.subheader("Deník transakcí a klientských operací")

col_f1, col_f2 = st.columns([2.5, 1])
with col_f1:
    filter_type = st.radio(
        "Filtrovat transakce:",
        options=[
            "Všechny",
            "Pouze klientské obchody",
            "Všechny externí hedgy",
            "Pouze oportunistické hedgy",
            "Pouze časové hedgy (Time Stop)",
            "Pouze víkendové hedgy (Weekend Flatten)",
            "Pouze havarijní hedgy (Hard Stop)",
        ],
        horizontal=True,
    )

if filter_type == "Pouze klientské obchody":
    display_df = df_records[df_records["event_type"] == "CLIENT"]
elif filter_type == "Všechny externí hedgy":
    display_df = df_records[df_records["event_type"] == "HEDGE"]
elif filter_type == "Pouze oportunistické hedgy":
    display_df = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "OPPORTUNISTIC")]
elif filter_type == "Pouze časové hedgy (Time Stop)":
    display_df = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "TIME_STOP")]
elif filter_type == "Pouze víkendové hedgy (Weekend Flatten)":
    display_df = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "WEEKEND_FLATTEN")]
elif filter_type == "Pouze havarijní hedgy (Hard Stop)":
    display_df = df_records[(df_records["event_type"] == "HEDGE") & (df_records["event_subtype"] == "HARD_STOP")]
else:
    display_df = df_records

with col_f2:
    csv_bytes = df_records.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Stáhnout kompletní CSV deník",
        data=csv_bytes,
        file_name=f"blunit_fx_results_{start_date_val}_{end_date_val}.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.dataframe(
    display_df[[
        "trade_id",
        "timestamp",
        "event_type",
        "event_subtype",
        "side",
        "volume_eur",
        "execution_rate",
        "volume_czk",
        "spread_profit_czk",
        "nop_eur",
        "running_pnl_czk",
    ]].style.format({
        "volume_eur": "{:,.2f} €",
        "execution_rate": "{:.4f}",
        "volume_czk": "{:,.2f} Kč",
        "spread_profit_czk": "{:,.2f} Kč",
        "nop_eur": "{:,.2f} €",
        "running_pnl_czk": "{:,.2f} Kč",
    }),
    use_container_width=True,
    height=350,
)
