#!/usr/bin/env python3
"""
Blunit FX Netter - Interactive Web Dashboard & Simulator.

Built with Streamlit and Plotly for real-time visualization of
internal FX netting, risk limits, auto-hedging, and profitability.
"""

import sys
from datetime import datetime, timezone, date
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Ensure src package is accessible
sys.path.insert(0, str(Path(__file__).parent / "src"))

from blunit_fx.pricing import PricingModel
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
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .metric-subtitle {
        font-size: 0.85rem;
        color: #475569;
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

st.sidebar.subheader("Obchodní podmínky")
spread_pct_input = st.sidebar.slider(
    "Klientský spread (%)",
    min_value=0.10,
    max_value=1.50,
    value=0.40,
    step=0.05,
    help="Celkový spread mezi klientským Bid a Ask kurzem (výchozí 0.40 % = půl-spread 0.20 %)",
)

hedge_limit_input = st.sidebar.number_input(
    "Limit rizika NOP (EUR)",
    min_value=1000.0,
    max_value=100000.0,
    value=10000.0,
    step=1000.0,
    help="Prahová hodnota otevřené pozice sběrného účtu pro automatické dorovnání na externím trhu",
)

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
    "Interní netting engine a řízení tržního rizika pro měnový pár EUR/CZK na skutečných datech."
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
pricing = PricingModel(mid_rate=initial_mid, spread_pct=spread_pct_input / 100.0)
engine = NetterEngine(pricing_model=pricing, hedge_limit=hedge_limit_input)
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

# --- Risk Progress Bar ---
st.markdown(
    f"**Využití limitu otevřené pozice (NOP):** Maximální zaznamenaná pozice byla **{max_abs_nop:,.0f} EUR** z limitu **{hedge_limit_input:,.0f} EUR**."
)
st.progress(min(max(max_abs_nop / hedge_limit_input, 0.0), 1.0))

st.write("")


# --- Interactive Charts Section ---
tab_pnl, tab_nop, tab_rates = st.tabs([
    "📈 Kumulativní zisk (PnL)",
    "⚖️ Vývoj otevřené pozice a hedging (NOP)",
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
                name="Externí hedge v bance",
                marker=dict(color="#dc2626", size=8, symbol="diamond"),
                hovertemplate="%{x}<br>Hedge reset na 0 EUR<extra></extra>",
            )
        )

    # Upper and lower hedge boundaries
    fig_nop.add_hline(
        y=hedge_limit_input,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text=f"+Limit ({hedge_limit_input:,.0f} EUR)",
        annotation_position="top right",
    )
    fig_nop.add_hline(
        y=-hedge_limit_input,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text=f"-Limit (-{hedge_limit_input:,.0f} EUR)",
        annotation_position="bottom right",
    )
    fig_nop.add_hline(y=0, line_color="#94a3b8", line_width=1)

    fig_nop.update_layout(
        title="Vývoj otevřené pozice vůči nastavenému limitu rizika",
        xaxis_title="Datum a čas",
        yaxis_title="Pozice v EUR",
        template="plotly_white",
        height=450,
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

