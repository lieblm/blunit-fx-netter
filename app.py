#!/usr/bin/env python3
"""
Blunit FX Netter - Interactive Web Dashboard & Simulator.

Built with Streamlit and Plotly for real-time visualization of
internal FX netting, risk limits, auto-hedging, and profitability.
Features institutional risk management (VaR, three-zone limits, inventory skewing).
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
    help="Prahová hodnota otevřené pozice pro spuštění auto-hedgingu (doporučeno 25 000 EUR dle citlivostní analýzy)",
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

st.sidebar.subheader("Simulační tok")
orders_per_candle_input = st.sidebar.slider(
    "Počet pokynů na svíčku (H4)",
    min_value=1,
    max_value=5,
    value=1,
    help="Frekvence klientských objednávek v rámci každého 4hodinového intervalu",
)

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
    "Interní netting engine s dynamickým řízením tržního rizika a škálováním pro měnový pár EUR/CZK."
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
)
runner = SimulationRunner(engine=engine)

summary = runner.run_historical(
    candles=candles,
    orders_per_candle=orders_per_candle_input,
    seed=seed_input,
    verbose=False,
)

records = engine.trade_log
df_records = pd.DataFrame([
    {
        "trade_id": r.trade_id,
        "timestamp": r.timestamp,
        "event_type": r.event_type,
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
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">Externí zajištění (Hedge)</div>
            <div class="metric-value">{summary['hedge_count']} operací</div>
            <div class="metric-subtitle">Hedgováno {summary['total_hedged_eur']:,.0f} EUR ({summary['hedge_count']/summary['total_orders']*100:.1f} % pokynů)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")


# --- Institutional Risk Cockpit: Value at Risk & Three-Zone Traffic Light ---
st.subheader("Řízení rizik a kapitálová přiměřenost (Risk Cockpit)")

# Calculate real quantitative risk metrics (historical daily std = 0.2165% for EUR/CZK)
daily_sigma = 0.002165
ref_rate = summary.get("mid_rate", 25.0)

var95_czk = max_abs_nop * ref_rate * 1.645 * daily_sigma
var99_czk = max_abs_nop * ref_rate * 2.326 * daily_sigma
max_historical_shock_czk = max_abs_nop * ref_rate * 0.01823  # 10Y max drop: 1.823%

# Determine Traffic Light Zone
# Green: <= 60% of limit
# Yellow: 60% - 100% of limit
# Red: >= 100% (triggers hedge)
zone_threshold_green = hedge_limit_input * 0.60
zone_threshold_yellow = hedge_limit_input * 1.00

if max_abs_nop <= zone_threshold_green:
    current_zone = "ZELENÁ ZÓNA (0 – 60 % limitu)"
    zone_class = "zone-green"
    zone_desc = "Běžný provozní netting. Minimální tržní riziko, nulový zásah externího trhu."
elif max_abs_nop <= zone_threshold_yellow:
    current_zone = "ŽLUTÁ ZÓNA (60 – 100 % limitu)"
    zone_class = "zone-yellow"
    zone_desc = "Zvýšená otevřená pozice. Aktivní cenové vychylování (skewing) k přirozenému rebalancingu."
else:
    current_zone = "ČERVENÁ ZÓNA (>= 100 % limitu)"
    zone_class = "zone-red"
    zone_desc = "Dosažen limit rizika. Automatický auto-hedge přebytku na externím trhu."

col_r1, col_r2, col_r3 = st.columns([1.2, 1.4, 1.4])

with col_r1:
    st.markdown(
        f"""
        <div class="risk-card {zone_class}">
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">Semafor rizika</div>
            <div style="font-size: 1.3rem; font-weight: 800; margin-top: 4px;">{current_zone.split(' ')[0]} {current_zone.split(' ')[1]}</div>
            <div style="font-size: 0.85rem; margin-top: 6px;">{zone_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_r2:
    st.markdown(
        f"""
        <div class="risk-card" style="background-color: #f8fafc;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #475569; text-transform: uppercase;">Denní tržní riziko (Value at Risk)</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-top: 4px;">VaR 99 %: {var99_czk:,.0f} CZK</div>
            <div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">
                VaR 95 %: <b>{var95_czk:,.0f} CZK</b> &bull; Riziko tvoří <b>{var99_czk / summary['total_pnl_czk'] * 100:.2f} %</b> ročního zisku
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_r3:
    st.markdown(
        f"""
        <div class="risk-card" style="background-color: #f8fafc;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #475569; text-transform: uppercase;">Stresový test (10letý šok 1,82 %)</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #b91c1c; margin-top: 4px;">-{max_historical_shock_czk:,.0f} CZK</div>
            <div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">
                Maximální jednorázová ztráta při nejhorším 4H pohybu EUR/CZK od roku 2017
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Visual progress bar with zones
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
        annotation_text="Žlutá zóna (Rebalancing & Skewing)",
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

    # Hedge events
    hedge_rows = df_records[df_records["event_type"] == "HEDGE"]
    if not hedge_rows.empty:
        fig_nop.add_trace(
            go.Scatter(
                x=hedge_rows["timestamp"],
                y=hedge_rows["nop_eur"],
                mode="markers",
                name="Auto-Hedge v bance",
                marker=dict(color="#dc2626", size=9, symbol="diamond"),
                hovertemplate="%{x}<br>Auto-Hedge na cílovou pozici: %{y:,.2f} EUR<extra></extra>",
            )
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
        title="Vývoj otevřené pozice (NOP) vůči třízónovému rámci řízení rizik",
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

col_f1, col_f2 = st.columns([2, 1])
with col_f1:
    filter_type = st.radio(
        "Filtrovat transakce:",
        options=["Všechny", "Pouze klientské obchody", "Pouze externí hedge"],
        horizontal=True,
    )

if filter_type == "Pouze klientské obchody":
    display_df = df_records[df_records["event_type"] == "CLIENT"]
elif filter_type == "Pouze externí hedge":
    display_df = df_records[df_records["event_type"] == "HEDGE"]
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
