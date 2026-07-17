import streamlit as st
import pandas as pd
import numpy as np
import os
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
import datetime
warnings.filterwarnings('ignore')

# TomTom integration
try:
    from tomtom_traffic import TomTomTraffic
    TOMTOM_KEY = st.secrets.get("tomtom", {}).get("api_key", "") or os.getenv("TOMTOM_API_KEY", "")
    tt_client  = TomTomTraffic(TOMTOM_KEY) if TOMTOM_KEY else None
except Exception:
    tt_client  = None
    TOMTOM_KEY = ""

# Social Sentiment integration
try:
    from social_sentiment import SocialSentimentAnalyzer
    social_analyzer = SocialSentimentAnalyzer()
except Exception:
    social_analyzer = None

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DMRC CrowdSense — Metro Intelligence Dashboard",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark gradient background */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1526 40%, #0a1628 100%);
    color: #e2e8f0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid rgba(99,179,237,0.15);
}

/* Metric cards */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(30,58,138,0.4), rgba(29,78,216,0.2));
    border: 1px solid rgba(99,179,237,0.25);
    border-radius: 16px;
    padding: 16px;
    backdrop-filter: blur(10px);
}

/* Hero header */
.hero-header {
    background: linear-gradient(135deg, #1e3a8a, #1d4ed8, #2563eb);
    border-radius: 20px;
    padding: 36px 40px;
    margin-bottom: 28px;
    box-shadow: 0 20px 60px rgba(37,99,235,0.3);
    border: 1px solid rgba(147,197,253,0.2);
}
.hero-header h1 {
    font-size: 2.4rem;
    font-weight: 800;
    color: white;
    margin: 0 0 8px 0;
    letter-spacing: -0.5px;
}
.hero-header p {
    color: rgba(255,255,255,0.75);
    font-size: 1.05rem;
    margin: 0;
}

/* Section headers */
.section-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #93c5fd;
    border-left: 4px solid #3b82f6;
    padding-left: 12px;
    margin: 24px 0 16px 0;
}

/* Crowd badge */
.badge-green  { background:#064e3b; color:#6ee7b7; border:1px solid #6ee7b7; padding:4px 14px; border-radius:999px; font-weight:600; font-size:.85rem; }
.badge-yellow { background:#451a03; color:#fcd34d; border:1px solid #fcd34d; padding:4px 14px; border-radius:999px; font-weight:600; font-size:.85rem; }
.badge-orange { background:#431407; color:#fb923c; border:1px solid #fb923c; padding:4px 14px; border-radius:999px; font-weight:600; font-size:.85rem; }
.badge-red    { background:#450a0a; color:#f87171; border:1px solid #f87171; padding:4px 14px; border-radius:999px; font-weight:600; font-size:.85rem; }

/* Alert box */
.alert-box {
    padding: 16px 20px;
    border-radius: 12px;
    margin: 8px 0;
    font-weight: 500;
}
.alert-green  { background:rgba(6,78,59,0.4);  border:1px solid #059669; color:#6ee7b7; }
.alert-yellow { background:rgba(69,26,3,0.5);  border:1px solid #d97706; color:#fcd34d; }
.alert-red    { background:rgba(69,10,10,0.5); border:1px solid #dc2626; color:#f87171; }

/* Card */
.info-card {
    background: rgba(30,58,138,0.25);
    border: 1px solid rgba(99,179,237,0.2);
    border-radius: 14px;
    padding: 20px;
    margin: 8px 0;
}

/* Journey result */
.journey-card {
    background: linear-gradient(135deg, rgba(5,150,105,0.2), rgba(6,78,59,0.15));
    border: 1px solid rgba(52,211,153,0.3);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    margin-top: 16px;
}
</style>
""", unsafe_allow_html=True)


# ── Data Loading ─────────────────────────────────────────────────────────────
HOURS = [f'HR{h}' for h in [4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,0]]
BASE_DIR = Path(__file__).resolve().parent

def resolve_data_file(env_var, default_name):
    env_path = os.getenv(env_var, "").strip()
    if env_path:
        return Path(env_path)
    return BASE_DIR / default_name

DATA_FILE = resolve_data_file('DMRC_DATA_FILE', 'stationwise_hourly_entry_exit_february_2024.xlsx')
LOC_FILE  = resolve_data_file('DMRC_LOC_FILE', 'dmrc_station_and_gate_locations.xlsx')
LOAD_FILE = resolve_data_file('DMRC_LOAD_FILE', 'delhimetropassengersloadperkm.xlsx')

SHEET_PAIRS = [
    ('september_2024_entry',  'september_2024_exit',  'Sep 2024'),
    ('october_2024_entry',    'october_2024_exit',    'Oct 2024'),
    ('november_2024_entry',   'november_2024_exit',   'Nov 2024'),
    ('december_2024_entry',   'december_2024_exit',   'Dec 2024'),
    ('january_2025_entry',    'january_2025_exit',    'Jan 2025'),
    ('february_2025_entry',   'february_2025_exit',   'Feb 2025'),
]

LINE_COLORS = {
    'LINE01': '#FF0000',  # Red
    'LINE02': '#FFFF00',  # Yellow
    'LINE03': '#0000FF',  # Blue
    'LINE04': '#00AA00',  # Green
    'LINE05': '#FF69B4',  # Pink
    'LINE06': '#9B59B6',  # Violet
    'LINE07': '#FFA500',  # Orange
    'LINE08': '#00BFFF',  # Aqua
    'RMGL':   '#808080',  # Rapid Metro Gurugram
}

@st.cache_data(show_spinner=True)
def load_all_data():
    missing = [str(p) for p in [DATA_FILE, LOC_FILE, LOAD_FILE] if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required data file(s): " + ", ".join(missing)
        )

    xl   = pd.ExcelFile(DATA_FILE)
    locs = pd.read_excel(LOC_FILE, sheet_name='stations')
    load = pd.read_excel(LOAD_FILE)

    # Fix coordinates — handles 3 formats in the data:
    #   1. Decimal degrees: "28.716892N"
    #   2. DMS:            "28.39.59N"  → 28 + 39/60 + 59/3600
    #   3. Degree symbol:  "28.45°N"
    def parse_coord(val):
        import re
        s = str(val).strip().upper().replace('°','')
        s = re.sub(r'[NSEW]', '', s).strip()
        parts = s.split('.')
        try:
            if len(parts) == 3:          # DMS: DD.MM.SS
                return float(parts[0]) + float(parts[1])/60 + float(parts[2])/3600
            else:                        # Decimal degrees
                return float(s)
        except Exception:
            return float('nan')

    for c in ['Latitude','Longitude']:
        locs[c] = locs[c].apply(parse_coord)

    all_dfs = []
    for e_sheet, x_sheet, label in SHEET_PAIRS:
        try:
            df_e = pd.read_excel(xl, e_sheet)
            df_x = pd.read_excel(xl, x_sheet)
        except Exception:
            continue

        df_e['month'] = label
        df_x['month'] = label

        # Melt to long format
        def melt_df(df, kind):
            id_cols = ['businessday','linename','sitename','station name','station code','month']
            hr_cols = [h for h in HOURS if h in df.columns]
            m = df[id_cols + hr_cols].melt(id_vars=id_cols, var_name='hour_col', value_name=kind)
            m['hour'] = m['hour_col'].str.replace('HR','').astype(int)
            return m.drop(columns='hour_col')

        merged = melt_df(df_e, 'entry').merge(
            melt_df(df_x, 'exit'),
            on=['businessday','linename','sitename','station name','station code','month','hour'],
            how='outer'
        )
        all_dfs.append(merged)

    if not all_dfs:
        raise ValueError(
            "No valid entry/exit sheet pairs found in the main workbook. "
            "Please verify expected sheet names are present."
        )

    full = pd.concat(all_dfs, ignore_index=True)
    full['businessday'] = pd.to_datetime(full['businessday'], errors='coerce')
    full['entry'] = pd.to_numeric(full['entry'], errors='coerce').fillna(0)
    full['exit']  = pd.to_numeric(full['exit'],  errors='coerce').fillna(0)
    full['total'] = full['entry'] + full['exit']
    full['day_of_week'] = full['businessday'].dt.day_name()
    full['is_weekend']  = full['businessday'].dt.dayofweek >= 5

    return full, locs, load

def crowd_level(val, q25, q50, q75):
    if val <= q25:   return ('LOW',       '🟢', 'badge-green')
    elif val <= q50: return ('MODERATE',  '🟡', 'badge-yellow')
    elif val <= q75: return ('HIGH',      '🟠', 'badge-orange')
    else:            return ('VERY HIGH', '🔴', 'badge-red')

def train_model(data):
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.preprocessing import LabelEncoder

    df = data.dropna(subset=['entry','hour','linename','station code']).copy()
    df = df[df['entry'] > 0]

    le_line    = LabelEncoder()
    le_station = LabelEncoder()
    df['line_enc']    = le_line.fit_transform(df['linename'].astype(str))
    df['station_enc'] = le_station.fit_transform(df['station code'].astype(str))
    df['dow']         = df['businessday'].dt.dayofweek
    df['month_num']   = df['businessday'].dt.month

    feats = ['hour','line_enc','station_enc','dow','month_num']
    X = df[feats]
    y = df['entry']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    rf = RandomForestRegressor(n_estimators=120, max_depth=12, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    y_pred = rf.predict(X_test)
    mae  = mean_absolute_error(y_test, y_pred)
    r2   = r2_score(y_test, y_pred)

    return rf, le_line, le_station, feats, mae, r2


# ── Load Data ────────────────────────────────────────────────────────────────
with st.spinner("⚡ Loading DMRC data..."):
    try:
        data, locs, load_data = load_all_data()
    except (FileNotFoundError, ValueError) as err:
        st.error("Unable to load DMRC datasets.")
        st.info(str(err))
        st.stop()

all_stations = sorted(data['station name'].dropna().unique())
all_lines    = sorted(data['linename'].dropna().unique())
all_months   = [l for _, _, l in SHEET_PAIRS]


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚇 DMRC CrowdSense")
    st.markdown("*Metro Intelligence Dashboard*")
    st.divider()

    page = st.radio(
        "Navigation",
        ["🏠 Overview", "🔥 Crowd Heatmap", "📈 Station Analytics",
         "🔮 Predict Crowd", "🚦 Live Traffic", "🗺️ Metro Map",
         "🚆 Train Scheduler", "📰 Social & Sentiment", "📊 Research Metrics"],
        label_visibility="collapsed"
    )

    st.divider()
    if TOMTOM_KEY:
        st.success("🟢 TomTom API connected")
    else:
        st.warning("⚠️ TomTom key missing")
    st.divider()

    st.markdown("**Quick Filters**")
    sel_line = st.selectbox("Metro Line", ["All Lines"] + all_lines)
    sel_month = st.selectbox("Month", ["All Months"] + all_months)
    st.divider()
    st.caption("Data: DMRC Official | Sep 2024 – Feb 2025")
    st.caption("Built for Research @ College 🎓")


# ── Filter helper ────────────────────────────────────────────────────────────
def apply_filters(df):
    out = df.copy()
    if sel_line != "All Lines":
        out = out[out['linename'] == sel_line]
    if sel_month != "All Months":
        out = out[out['month'] == sel_month]
    return out

fdata = apply_filters(data)

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 1 — OVERVIEW                                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝
if page == "🏠 Overview":
    st.markdown("""
    <div class="hero-header">
        <h1>🚇 DMRC CrowdSense</h1>
        <p>AI-powered metro crowd prediction & intelligence platform | Sep 2024 – Feb 2025</p>
    </div>
    """, unsafe_allow_html=True)

    # KPI Row
    total_trips   = int(fdata['entry'].sum())
    total_exits   = int(fdata['exit'].sum())
    unique_sta    = fdata['station name'].nunique()
    peak_station  = fdata.groupby('station name')['entry'].sum().idxmax()
    peak_val      = int(fdata.groupby('station name')['entry'].sum().max())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚶 Total Entries",    f"{total_trips:,.0f}",  delta="Official DMRC Data")
    c2.metric("🚪 Total Exits",      f"{total_exits:,.0f}",  delta="6 months")
    c3.metric("🏢 Stations Tracked", f"{unique_sta}",        delta="Active Stations")
    c4.metric("🔥 Busiest Station",  peak_station,           delta=f"{peak_val:,.0f} entries")

    st.markdown('<div class="section-title">📅 Monthly Ridership Trend</div>', unsafe_allow_html=True)
    monthly = data.groupby('month')[['entry','exit']].sum().reset_index()
    month_order = [l for _,_,l in SHEET_PAIRS]
    monthly['month'] = pd.Categorical(monthly['month'], categories=month_order, ordered=True)
    monthly = monthly.sort_values('month')

    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Bar(
        x=monthly['month'], y=monthly['entry'],
        name='Entries', marker_color='#3b82f6',
        marker_line_color='rgba(147,197,253,0.5)', marker_line_width=1.5
    ))
    fig_monthly.add_trace(go.Bar(
        x=monthly['month'], y=monthly['exit'],
        name='Exits', marker_color='#8b5cf6',
        marker_line_color='rgba(196,181,253,0.5)', marker_line_width=1.5
    ))
    fig_monthly.update_layout(
        barmode='group', paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,14,26,0.6)',
        font=dict(color='#e2e8f0', family='Inter'),
        legend=dict(bgcolor='rgba(0,0,0,0)', bordercolor='rgba(99,179,237,0.2)'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='Passengers'),
        height=380
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-title">🏆 Top 10 Busiest Stations</div>', unsafe_allow_html=True)
        top10 = data.groupby('station name')['entry'].sum().nlargest(10).reset_index()
        fig_top = px.bar(top10, x='entry', y='station name', orientation='h',
                         color='entry', color_continuous_scale='Blues',
                         labels={'entry':'Total Entries','station name':''})
        fig_top.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
            font=dict(color='#e2e8f0', family='Inter'),
            coloraxis_showscale=False, height=380,
            yaxis=dict(autorange='reversed'),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)')
        )
        st.plotly_chart(fig_top, use_container_width=True)

    with col2:
        st.markdown('<div class="section-title">📊 Line-wise Share</div>', unsafe_allow_html=True)
        line_share = data.groupby('linename')['entry'].sum().reset_index()
        fig_pie = px.pie(line_share, values='entry', names='linename',
                         hole=0.55, color_discrete_sequence=px.colors.sequential.Blues_r)
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e2e8f0', family='Inter'),
            legend=dict(bgcolor='rgba(0,0,0,0)'),
            height=380
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown('<div class="section-title">📆 Weekday vs Weekend Patterns</div>', unsafe_allow_html=True)
    dow_data = data.groupby('day_of_week')[['entry','exit']].mean().reset_index()
    day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    dow_data['day_of_week'] = pd.Categorical(dow_data['day_of_week'], categories=day_order, ordered=True)
    dow_data = dow_data.sort_values('day_of_week')
    colors_bar = ['#3b82f6']*5 + ['#f59e0b','#ef4444']

    fig_dow = go.Figure()
    fig_dow.add_trace(go.Bar(
        x=dow_data['day_of_week'], y=dow_data['entry'],
        name='Avg Entry', marker_color=colors_bar
    ))
    fig_dow.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
        font=dict(color='#e2e8f0', family='Inter'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='Avg Passengers/Hour'),
        height=340
    )
    st.plotly_chart(fig_dow, use_container_width=True)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 2 — CROWD HEATMAP                                             ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "🔥 Crowd Heatmap":
    st.markdown('<div class="section-title">🔥 Station × Hour Crowd Heatmap</div>', unsafe_allow_html=True)
    st.caption("Deeper blue = more crowded. Instantly spot rush hours per station.")

    n_stations = st.slider("Number of stations to show", 10, 50, 25)
    metric = st.radio("Metric", ["Entry", "Exit", "Total"], horizontal=True)
    metric_col = metric.lower()

    top_n = fdata.groupby('station name')[metric_col].sum().nlargest(n_stations).index
    heat_df = fdata[fdata['station name'].isin(top_n)]
    pivot = heat_df.groupby(['station name','hour'])[metric_col].mean().reset_index()
    pivot_wide = pivot.pivot(index='station name', columns='hour', values=metric_col).fillna(0)
    hour_labels = [f"{int(h):02d}:00" for h in pivot_wide.columns]

    fig_heat = go.Figure(go.Heatmap(
        z=pivot_wide.values,
        x=hour_labels,
        y=pivot_wide.index.tolist(),
        colorscale='Blues',
        colorbar=dict(title='Avg Passengers', tickfont=dict(color='#e2e8f0')),
        hoverongaps=False,
        hovertemplate='<b>%{y}</b><br>Hour: %{x}<br>Passengers: %{z:.0f}<extra></extra>'
    ))
    fig_heat.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,14,26,0.8)',
        font=dict(color='#e2e8f0', family='Inter'),
        xaxis=dict(title='Hour of Day', tickfont=dict(size=10)),
        yaxis=dict(title='', tickfont=dict(size=9)),
        height=max(500, n_stations * 18),
        margin=dict(l=160, r=20, t=20, b=60)
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # Peak hour summary
    st.markdown('<div class="section-title">⏰ Peak Hours by Station</div>', unsafe_allow_html=True)
    peak_hours = heat_df.groupby(['station name','hour'])[metric_col].mean().reset_index()
    peak_hours = peak_hours.loc[peak_hours.groupby('station name')[metric_col].idxmax()]
    peak_hours['peak_time'] = peak_hours['hour'].apply(lambda h: f"{int(h):02d}:00 – {int(h)+1:02d}:00")
    peak_hours = peak_hours[['station name','peak_time',metric_col]].sort_values(metric_col, ascending=False)
    peak_hours.columns = ['Station', 'Peak Hour', f'Avg {metric} at Peak']
    peak_hours[f'Avg {metric} at Peak'] = peak_hours[f'Avg {metric} at Peak'].round(0).astype(int)
    st.dataframe(peak_hours.reset_index(drop=True), use_container_width=True, height=300)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 3 — STATION ANALYTICS                                         ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "📈 Station Analytics":
    st.markdown('<div class="section-title">📈 Deep-Dive Station Analytics</div>', unsafe_allow_html=True)

    sel_station = st.selectbox("Select Station", all_stations, index=all_stations.index("Kashmere Gate") if "Kashmere Gate" in all_stations else 0)
    sta_data = fdata[fdata['station name'] == sel_station]

    if sta_data.empty:
        st.warning("No data for this station with current filters.")
    else:
        # KPIs
        total_e = int(sta_data['entry'].sum())
        total_x = int(sta_data['exit'].sum())
        avg_e   = round(sta_data['entry'].mean(), 1)
        peak_hr = sta_data.groupby('hour')['entry'].mean().idxmax()
        peak_val = int(sta_data.groupby('hour')['entry'].mean().max())

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Entries",   f"{total_e:,}")
        k2.metric("Total Exits",     f"{total_x:,}")
        k3.metric("Avg Entry/Hr",    f"{avg_e:,}")
        k4.metric("Peak Hour",       f"{int(peak_hr):02d}:00", delta=f"{peak_val} avg pax")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📊 Hourly Entry vs Exit Pattern**")
            hourly = sta_data.groupby('hour')[['entry','exit']].mean().reset_index()
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=hourly['hour'], y=hourly['entry'],
                mode='lines+markers', name='Entry', line=dict(color='#3b82f6', width=2.5),
                fill='tozeroy', fillcolor='rgba(59,130,246,0.15)'))
            fig_line.add_trace(go.Scatter(x=hourly['hour'], y=hourly['exit'],
                mode='lines+markers', name='Exit', line=dict(color='#8b5cf6', width=2.5),
                fill='tozeroy', fillcolor='rgba(139,92,246,0.1)'))
            fig_line.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
                font=dict(color='#e2e8f0', family='Inter'),
                xaxis=dict(title='Hour', gridcolor='rgba(255,255,255,0.05)',
                           tickvals=list(range(4,24))+[0], ticktext=[f"{h:02d}" for h in list(range(4,24))+[0]]),
                yaxis=dict(title='Avg Passengers', gridcolor='rgba(255,255,255,0.05)'),
                height=320, legend=dict(bgcolor='rgba(0,0,0,0)')
            )
            st.plotly_chart(fig_line, use_container_width=True)

        with col2:
            st.markdown("**📅 Weekday vs Weekend**")
            dow = sta_data.groupby('day_of_week')['entry'].mean().reset_index()
            day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            dow['day_of_week'] = pd.Categorical(dow['day_of_week'], categories=day_order, ordered=True)
            dow = dow.sort_values('day_of_week')
            colors_bar = ['#3b82f6']*5 + ['#f59e0b','#ef4444']
            fig_dow = go.Figure(go.Bar(x=dow['day_of_week'], y=dow['entry'], marker_color=colors_bar))
            fig_dow.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
                font=dict(color='#e2e8f0', family='Inter'),
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='Avg Entry'),
                height=320
            )
            st.plotly_chart(fig_dow, use_container_width=True)

        st.markdown("**📆 Monthly Trend**")
        monthly_sta = sta_data.groupby('month')[['entry','exit']].sum().reset_index()
        month_order = [l for _,_,l in SHEET_PAIRS]
        monthly_sta['month'] = pd.Categorical(monthly_sta['month'], categories=month_order, ordered=True)
        monthly_sta = monthly_sta.sort_values('month')
        fig_mtrend = go.Figure()
        fig_mtrend.add_trace(go.Scatter(x=monthly_sta['month'], y=monthly_sta['entry'],
            mode='lines+markers+text', name='Entry',
            line=dict(color='#3b82f6', width=3),
            marker=dict(size=9), text=monthly_sta['entry'].apply(lambda v: f"{v:,.0f}"),
            textposition='top center', textfont=dict(size=10, color='#93c5fd')))
        fig_mtrend.add_trace(go.Scatter(x=monthly_sta['month'], y=monthly_sta['exit'],
            mode='lines+markers', name='Exit', line=dict(color='#8b5cf6', width=2, dash='dot'),
            marker=dict(size=7)))
        fig_mtrend.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
            font=dict(color='#e2e8f0', family='Inter'),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='Passengers'),
            height=300, legend=dict(bgcolor='rgba(0,0,0,0)')
        )
        st.plotly_chart(fig_mtrend, use_container_width=True)

        # Overcrowding alerts
        st.markdown('<div class="section-title">⚠️ Hour-by-Hour Crowd Level</div>', unsafe_allow_html=True)
        hourly2 = sta_data.groupby('hour')[['entry','exit']].mean().reset_index()
        q = hourly2['entry'].quantile([0.25,0.5,0.75])
        q25, q50, q75 = q[0.25], q[0.5], q[0.75]

        alert_cols = st.columns(4)
        for i, (_, row) in enumerate(hourly2.iterrows()):
            level, icon, cls = crowd_level(row['entry'], q25, q50, q75)
            with alert_cols[i % 4]:
                st.markdown(f"""
                <div class="info-card" style="text-align:center; padding:12px;">
                    <div style="font-size:1.5rem;">{icon}</div>
                    <div style="font-weight:700; color:#93c5fd;">{int(row['hour']):02d}:00</div>
                    <div style="font-size:.8rem; color:#94a3b8;">{level}</div>
                    <div style="font-size:.9rem; color:#e2e8f0;">{int(row['entry'])} pax</div>
                </div>
                """, unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 4 — PREDICT CROWD                                             ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "🔮 Predict Crowd":
    st.markdown('<div class="section-title">🔮 AI Crowd Prediction Engine</div>', unsafe_allow_html=True)
    st.caption("Random Forest model trained on 6 months of official DMRC data.")

    col1, col2 = st.columns([1,1])
    with col1:
        pred_station = st.selectbox("Station", all_stations,
                                    index=all_stations.index("Kashmere Gate") if "Kashmere Gate" in all_stations else 0)
        pred_hour    = st.slider("Hour of Day", 4, 23, 9)
        pred_date    = st.date_input("Prediction Date", datetime.date(2026, 7, 17))
        
        # Derived features
        pred_day_name = pred_date.strftime("%A")
        pred_month_num = pred_date.month
        pred_year = pred_date.year

    with col2:
        st.markdown("**How the model works:**")
        st.markdown("""
        <div class="info-card">
            <p>🧠 <b>Algorithm:</b> Random Forest Regressor</p>
            <p>📊 <b>Features:</b> Hour, Station, Line, Day of Week, Month</p>
            <p>🎯 <b>Target:</b> Entry passenger count</p>
            <p>📈 <b>Future Projections:</b> Includes ~6% YoY growth compound for dates beyond 2024.</p>
        </div>
        """, unsafe_allow_html=True)

    if st.button("⚡ Predict Now", type="primary", use_container_width=True):
        with st.spinner("Running prediction model..."):
            try:
                model, le_line, le_station, feats, mae, r2 = train_model(data)

                # Get station line
                sta_row = data[data['station name'] == pred_station].iloc[0]
                line_name = sta_row['linename']
                sta_code  = sta_row['station code']

                day_map = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
                
                try:
                    line_enc = le_line.transform([line_name])[0]
                except:
                    line_enc = 0
                try:
                    sta_enc  = le_station.transform([sta_code])[0]
                except:
                    sta_enc = 0

                X_pred = pd.DataFrame([[pred_hour, line_enc, sta_enc,
                                        day_map[pred_day_name], pred_month_num]],
                                      columns=feats)
                base_pred = max(0, int(model.predict(X_pred)[0]))
                
                # Apply YoY growth for future dates (assuming base data is mostly 2024)
                growth_rate = 0.06 # 6% annual growth
                years_ahead = max(0, pred_year - 2024)
                growth_multiplier = (1 + growth_rate) ** years_ahead
                pred_entry = int(base_pred * growth_multiplier)

                # Estimate exit (usually peak exit is opposite of peak entry)
                pred_exit = int(pred_entry * 0.85)

                # Historical average for comparison
                hist_avg = int(data[(data['station name']==pred_station) &
                                    (data['hour']==pred_hour)]['entry'].mean())

                q = data[(data['station name']==pred_station)]['entry'].quantile([0.25,0.5,0.75])
                level, icon, _ = crowd_level(pred_entry, q[0.25], q[0.5], q[0.75])
                alert_cls = {'LOW':'alert-green','MODERATE':'alert-yellow',
                             'HIGH':'alert-orange','VERY HIGH':'alert-red'}.get(level,'alert-yellow')

                st.markdown(f"""
                <div class="journey-card">
                    <div style="font-size:3rem;">{icon}</div>
                    <div style="font-size:1.8rem; font-weight:800; color:white; margin:8px 0;">{pred_entry:,} passengers</div>
                    <div style="color:#6ee7b7; font-size:1.1rem; margin-bottom:16px;">predicted entry at {pred_hour:02d}:00</div>
                    <div style="display:flex; gap:16px; justify-content:center; flex-wrap:wrap;">
                        <span style="background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:8px;">
                            🚪 Exit: ~{pred_exit:,}
                        </span>
                        <span style="background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:8px;">
                            📊 Hist Avg: {hist_avg:,}
                        </span>
                        <span style="background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:8px;">
                            🎯 Crowd: {level}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Alert
                msg_map = {
                    'LOW':       ("✅ Great time to travel! Station will be comfortable.", 'alert-green'),
                    'MODERATE':  ("⚡ Moderate crowd expected. Plan accordingly.", 'alert-yellow'),
                    'HIGH':      ("⚠️ High crowd expected. Consider travelling ±1 hour.", 'alert-orange'),
                    'VERY HIGH': ("🚨 Very high crowd! Avoid if possible or leave much earlier.", 'alert-red'),
                }
                msg, cls = msg_map[level]
                st.markdown(f'<div class="alert-box {cls}">{msg}</div>', unsafe_allow_html=True)

                # 24-hour forecast
                st.markdown("**📈 Full Day Forecast for this Station**")
                hours_all = list(range(4,24)) + [0]
                preds_all = []
                for h in hours_all:
                    Xi = pd.DataFrame([[h, line_enc, sta_enc, day_map[pred_day_name], pred_month_num]], columns=feats)
                    b_pred = max(0, int(model.predict(Xi)[0]))
                    preds_all.append(int(b_pred * growth_multiplier))

                hist_all = []
                for h in hours_all:
                    val = data[(data['station name']==pred_station) & (data['hour']==h)]['entry'].mean()
                    hist_all.append(int(val) if pd.notna(val) else 0)

                hour_labels = [f"{h:02d}:00" for h in hours_all]

                fig_pred = go.Figure()
                fig_pred.add_trace(go.Scatter(x=hour_labels, y=preds_all,
                    mode='lines+markers', name='🔮 Predicted',
                    line=dict(color='#3b82f6', width=3),
                    marker=dict(size=8)))
                fig_pred.add_trace(go.Scatter(x=hour_labels, y=hist_all,
                    mode='lines', name='📊 Historical Avg',
                    line=dict(color='#6b7280', width=2, dash='dot')))
                
                # Highlight selected hour safely (without add_vline which can crash on string axes in older plotly)
                max_y = max((preds_all + hist_all) or [100])
                fig_pred.add_trace(go.Scatter(
                    x=[f"{pred_hour:02d}:00", f"{pred_hour:02d}:00"],
                    y=[0, max_y * 1.05],
                    mode='lines', name='Selected Hour',
                    line=dict(color="#f59e0b", width=2, dash="dash"),
                    showlegend=False
                ))
                fig_pred.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
                    font=dict(color='#e2e8f0', family='Inter'),
                    xaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='Hour'),
                    yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title='Passengers'),
                    height=340, legend=dict(bgcolor='rgba(0,0,0,0)')
                )
                st.plotly_chart(fig_pred, use_container_width=True)

                st.markdown(f"""
                <div class="info-card">
                    <b>Model Performance:</b> &nbsp;
                    MAE = {mae:.1f} passengers &nbsp;|&nbsp; R² Score = {r2:.3f}
                </div>
                """, unsafe_allow_html=True)

            except Exception as e:
                import traceback
                traceback.print_exc()
                st.error(f"Prediction error: {e}")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 5 — METRO MAP                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "🗺️ Metro Map":
    st.markdown('<div class="section-title">🗺️ Live Crowd Map — Delhi Metro Network</div>', unsafe_allow_html=True)

    try:
        import folium
        from streamlit_folium import st_folium

        sel_hour_map = st.slider("Select Hour", 4, 23, 9)
        map_metric   = st.radio("Show", ["Entry", "Exit", "Total"], horizontal=True)
        map_metric_col = map_metric.lower()

        # Aggregate by station for selected hour
        hour_agg = data[data['hour'] == sel_hour_map].groupby('station code')[map_metric_col].mean().reset_index()
        locs_clean = locs.dropna(subset=['Latitude','Longitude'])
        merged_map = locs_clean.merge(hour_agg, left_on='Station Code', right_on='station code', how='left')
        merged_map[map_metric_col] = merged_map[map_metric_col].fillna(0)

        max_val = merged_map[map_metric_col].max() or 1
        q75_map = merged_map[map_metric_col].quantile(0.75)

        m = folium.Map(location=[28.65, 77.22], zoom_start=11,
                       tiles='CartoDB dark_matter')

        for _, row in merged_map.iterrows():
            if pd.isna(row['Latitude']) or row['Latitude'] == 0:
                continue
            val = row[map_metric_col]
            ratio = val / max_val
            radius = max(5, ratio * 22)
            color  = '#ef4444' if val > q75_map else ('#f59e0b' if val > q75_map*0.5 else '#22c55e')

            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=radius, color=color, fill=True, fill_color=color,
                fill_opacity=0.75, weight=1.5,
                tooltip=f"<b>{row['Name']}</b><br>{map_metric}: {int(val):,}"
            ).add_to(m)

        st_folium(m, width=None, height=550, returned_objects=[])

        st.markdown("""
        <div class="info-card">
        🔴 Very High &nbsp; 🟡 Moderate &nbsp; 🟢 Low crowd stations
        </div>
        """, unsafe_allow_html=True)

    except ImportError:
        st.info("Map requires streamlit-folium. Run: `pip install streamlit-folium folium`")
        # Fallback scatter map
        hour_agg = data[data['hour'] == 9].groupby('station code')['entry'].mean().reset_index()
        locs_clean = locs.dropna(subset=['Latitude','Longitude'])
        merged_map = locs_clean.merge(hour_agg, left_on='Station Code', right_on='station code', how='left')
        merged_map['entry'] = merged_map['entry'].fillna(0)
        fig_map = px.scatter_mapbox(merged_map, lat='Latitude', lon='Longitude',
            size='entry', color='entry', hover_name='Name',
            color_continuous_scale='Reds', zoom=10, height=500,
            mapbox_style='carto-darkmatter')
        fig_map.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                              font=dict(color='#e2e8f0'))
        st.plotly_chart(fig_map, use_container_width=True)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 6 — TRAIN SCHEDULER                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "🚆 Train Scheduler":
    st.markdown('<div class="section-title">🚆 AI Train Scheduling Optimizer</div>', unsafe_allow_html=True)
    st.caption("Dynamic headway recommendations based on predicted crowd at each hour.")

    sel_line_sched = st.selectbox("Select Metro Line", all_lines)
    sel_month_sched = st.selectbox("Month for Schedule", all_months)

    line_data = data[(data['linename'] == sel_line_sched) & (data['month'] == sel_month_sched)]
    hourly_line = line_data.groupby('hour')[['entry','exit']].mean().reset_index()

    max_pax = hourly_line['entry'].max() or 1

    def recommend_headway(entry, max_e):
        ratio = entry / max_e
        if ratio >= 0.80:   return 2,  '🚨 Very High',  '#ef4444', 'Every 2 min'
        elif ratio >= 0.60: return 3,  '🟠 High',       '#f97316', 'Every 3 min'
        elif ratio >= 0.40: return 5,  '🟡 Moderate',   '#eab308', 'Every 5 min'
        elif ratio >= 0.20: return 8,  '🟢 Low',        '#22c55e', 'Every 8 min'
        else:               return 12, '⚪ Very Low',   '#94a3b8', 'Every 12 min'

    rows = []
    for _, row in hourly_line.iterrows():
        hw, level, color, freq = recommend_headway(row['entry'], max_pax)
        rows.append({'Hour': f"{int(row['hour']):02d}:00",
                     'Avg Entry': int(row['entry']),
                     'Crowd Level': level,
                     'Recommended Headway (min)': hw,
                     'Frequency': freq})
    sched_df = pd.DataFrame(rows)

    # Chart
    fig_sched = make_subplots(rows=1, cols=1)
    fig_sched.add_trace(go.Bar(
        x=sched_df['Hour'], y=sched_df['Avg Entry'],
        marker_color=[{'🚨 Very High':'#ef4444','🟠 High':'#f97316','🟡 Moderate':'#eab308',
                       '🟢 Low':'#22c55e','⚪ Very Low':'#94a3b8'}[l] for l in sched_df['Crowd Level']],
        name='Avg Entry', text=sched_df['Frequency'],
        textposition='outside', textfont=dict(size=9, color='#e2e8f0')
    ))
    fig_sched.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
        font=dict(color='#e2e8f0', family='Inter'),
        xaxis=dict(title='Hour', gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(title='Avg Passengers', gridcolor='rgba(255,255,255,0.05)'),
        height=380, showlegend=False
    )
    st.plotly_chart(fig_sched, use_container_width=True)

    st.markdown("**📋 Full Schedule Recommendation Table**")
    st.dataframe(sched_df, use_container_width=True, hide_index=True)

    total_trains_optimal  = int((sched_df['Recommended Headway (min)']).apply(lambda x: 60//x).sum())
    total_trains_fixed    = int(21 * (60 // 5))  # fixed 5-min headway all day
    savings = round((1 - total_trains_optimal / total_trains_fixed) * 100, 1)

    st.markdown(f"""
    <div class="journey-card">
        <div style="font-size:2rem;">🚆</div>
        <div style="font-size:1.4rem; font-weight:700; color:white;">Dynamic scheduling saves ~{savings}% train runs</div>
        <div style="color:#6ee7b7;">vs fixed 5-minute headway all day</div>
    </div>
    """, unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 7 — RESEARCH METRICS                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "📊 Research Metrics":
    st.markdown('<div class="section-title">📊 Research Metrics & Model Evaluation</div>', unsafe_allow_html=True)
    st.caption("Model comparison and statistical analysis for research paper / presentation.")

    if st.button("🔬 Run Full Model Evaluation", type="primary"):
        with st.spinner("Training models... (~30 seconds)"):
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
            from sklearn.linear_model import LinearRegression
            from sklearn.tree import DecisionTreeRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            from sklearn.preprocessing import LabelEncoder

            df = data.dropna(subset=['entry','hour','linename','station code']).copy()
            df = df[df['entry'] > 0]
            le_l = LabelEncoder(); le_s = LabelEncoder()
            df['line_enc']    = le_l.fit_transform(df['linename'].astype(str))
            df['station_enc'] = le_s.fit_transform(df['station code'].astype(str))
            df['dow']       = df['businessday'].dt.dayofweek
            df['month_num'] = df['businessday'].dt.month

            feats = ['hour','line_enc','station_enc','dow','month_num']
            X = df[feats]; y = df['entry']
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            models = {
                'Linear Regression':       LinearRegression(),
                'Decision Tree':           DecisionTreeRegressor(max_depth=10, random_state=42),
                'Random Forest':           RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1),
                'Gradient Boosting (XGB)': GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42),
            }

            results = []
            for name, mdl in models.items():
                mdl.fit(X_train, y_train)
                yp = mdl.predict(X_test)
                results.append({
                    'Model': name,
                    'MAE':  round(mean_absolute_error(y_test, yp), 2),
                    'RMSE': round(np.sqrt(mean_squared_error(y_test, yp)), 2),
                    'R²':   round(r2_score(y_test, yp), 4),
                })

            res_df = pd.DataFrame(results).sort_values('R²', ascending=False)
            best = res_df.iloc[0]['Model']

            st.markdown(f"### 🏆 Best Model: **{best}**")

            fig_res = go.Figure()
            fig_res.add_trace(go.Bar(name='MAE', x=res_df['Model'], y=res_df['MAE'],
                                     marker_color='#3b82f6'))
            fig_res.add_trace(go.Bar(name='RMSE', x=res_df['Model'], y=res_df['RMSE'],
                                     marker_color='#8b5cf6'))
            fig_res.update_layout(
                barmode='group', paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(10,14,26,0.6)',
                font=dict(color='#e2e8f0', family='Inter'),
                yaxis=dict(title='Error (passengers)', gridcolor='rgba(255,255,255,0.05)'),
                height=340, legend=dict(bgcolor='rgba(0,0,0,0)')
            )
            st.plotly_chart(fig_res, use_container_width=True)

            st.markdown("**📋 Full Comparison Table**")
            st.dataframe(res_df.reset_index(drop=True), use_container_width=True, hide_index=True)

            # Feature importance (RF)
            rf_model = models['Random Forest']
            fi = pd.DataFrame({'Feature': feats, 'Importance': rf_model.feature_importances_})
            fi = fi.sort_values('Importance', ascending=True)
            fig_fi = go.Figure(go.Bar(x=fi['Importance'], y=fi['Feature'],
                orientation='h', marker_color='#3b82f6'))
            fig_fi.update_layout(
                title='🔍 Feature Importance (Random Forest)',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,14,26,0.6)',
                font=dict(color='#e2e8f0', family='Inter'),
                height=280
            )
            st.plotly_chart(fig_fi, use_container_width=True)

            # Dataset stats
            st.markdown('<div class="section-title">📐 Dataset Statistics</div>', unsafe_allow_html=True)
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Total Records",   f"{len(data):,}")
            s2.metric("Unique Stations", f"{data['station name'].nunique()}")
            s3.metric("Months Covered",  "6")
            s4.metric("Metro Lines",     f"{data['linename'].nunique()}")

            st.markdown("**Descriptive Statistics — Entry Count**")
            st.dataframe(data['entry'].describe().round(2).to_frame().T, use_container_width=True)
    else:
        st.info("Click the button above to train and evaluate all models. This takes ~30 seconds.")
        st.markdown("""
        <div class="info-card">
            <b>Models that will be evaluated:</b><br><br>
            📉 Linear Regression — baseline<br>
            🌳 Decision Tree — interpretable<br>
            🌲 Random Forest — best overall (expected)<br>
            ⚡ Gradient Boosting (XGBoost-style) — most accurate<br><br>
            <b>Metrics:</b> MAE, RMSE, R² Score
        </div>
        """, unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 5 — LIVE TRAFFIC (TomTom)                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "🚦 Live Traffic":
    st.markdown('<div class="section-title">🚦 Live Road Traffic Near Metro Stations</div>',
                unsafe_allow_html=True)
    st.caption("Real-time congestion from TomTom Traffic API · Correlated with metro crowd prediction.")

    if not tt_client:
        st.error("TomTom API key not found. Set tomtom.api_key in Streamlit secrets or TOMTOM_API_KEY as an environment variable.")
        st.stop()

    # Station selector
    locs_clean = locs.dropna(subset=['Latitude', 'Longitude'])
    locs_clean = locs_clean[locs_clean['Latitude'] != 0]
    station_names_map = dict(zip(locs_clean['Name'], zip(locs_clean['Latitude'], locs_clean['Longitude'])))
    available = sorted(station_names_map.keys())

    col_a, col_b = st.columns([2, 1])
    with col_a:
        sel_traffic_stations = st.multiselect(
            "Select stations to query (max 15 to stay within API rate limit)",
            available,
            default=[s for s in ["Kashmere Gate", "Rajiv Chowk", "Central Secretariat",
                                  "Connaught Place", "New Delhi", "Hauz Khas",
                                  "Inderlok", "Chandni Chowk"] if s in available][:8]
        )
    with col_b:
        radius_km = st.slider("Incident search radius (km)", 0.5, 3.0, 1.0, 0.5)
        show_incidents = st.toggle("Show nearby incidents", value=True)

    if st.button("⚡ Fetch Live Traffic Data", type="primary", use_container_width=True):
        if not sel_traffic_stations:
            st.warning("Please select at least one station.")
            st.stop()

        stations_to_query = [
            {"name": n, "lat": station_names_map[n][0], "lon": station_names_map[n][1]}
            for n in sel_traffic_stations[:15]
        ]

        progress = st.progress(0, text="Fetching traffic data...")
        results = []
        for i, sta in enumerate(stations_to_query):
            flow = tt_client.flow_at_station(sta["lat"], sta["lon"])
            sta["traffic"] = flow
            results.append(sta)
            progress.progress((i + 1) / len(stations_to_query),
                              text=f"Querying {sta['name']}...")
        progress.empty()

        # ── Summary KPIs ───────────────────────────────────────────────
        valid = [r for r in results if not r["traffic"].get("error")]
        if not valid:
            st.error("All API calls failed. Check your TomTom key.")
            st.stop()

        avg_cong  = np.mean([r["traffic"]["congestion_pct"] for r in valid])
        jammed    = sum(1 for r in valid if r["traffic"]["level"] == "STANDSTILL")
        congested = sum(1 for r in valid if r["traffic"]["level"] == "CONGESTED")
        free_flow = sum(1 for r in valid if r["traffic"]["level"] == "FREE")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avg Congestion",  f"{avg_cong:.1f}%",  delta="across selected stations")
        k2.metric("🔴 Standstill",   f"{jammed} stations")
        k3.metric("🟠 Congested",    f"{congested} stations")
        k4.metric("🟢 Free Flow",    f"{free_flow} stations")

        # ── Station Traffic Table ──────────────────────────────────────
        st.markdown('<div class="section-title">📋 Station-by-Station Traffic Status</div>',
                    unsafe_allow_html=True)

        rows = []
        for r in valid:
            t = r["traffic"]
            boost = TomTomTraffic.congestion_to_crowd_boost(t["congestion_ratio"])
            # Get historical avg crowd for this station
            hist = data[data["station name"].str.contains(
                r["name"].split()[0], case=False, na=False)]["entry"].mean()
            hist = int(hist) if not np.isnan(hist) else 0
            boosted_crowd = int(hist * boost)
            rows.append({
                "Station":           r["name"],
                "Status":            f"{t['level_icon']} {t['level']}",
                "Current Speed":     f"{t['currentSpeed']} km/h",
                "Free Flow Speed":   f"{t['freeFlowSpeed']} km/h",
                "Congestion":        f"{t['congestion_pct']}%",
                "Road Closed":       "🚧 YES" if t.get("roadClosure") else "No",
                "Metro Crowd Boost": f"+{(boost-1)*100:.0f}%",
                "Est. Metro Pax":    f"{boosted_crowd:,}",
                "API Confidence":    f"{t['confidence']*100:.0f}%",
            })

        traffic_df = pd.DataFrame(rows)
        st.dataframe(traffic_df, use_container_width=True, hide_index=True)

        # ── Congestion vs Metro Crowd Chart ────────────────────────────
        st.markdown('<div class="section-title">📊 Road Congestion vs Predicted Metro Crowd</div>',
                    unsafe_allow_html=True)

        chart_data = []
        for r in valid:
            t = r["traffic"]
            boost = TomTomTraffic.congestion_to_crowd_boost(t["congestion_ratio"])
            hist = data[data["station name"].str.contains(
                r["name"].split()[0], case=False, na=False)]["entry"].mean()
            hist = int(hist) if not np.isnan(hist) else 0
            chart_data.append({
                "Station":       r["name"],
                "Congestion %":  t["congestion_pct"],
                "Metro Pax":     int(hist * boost),
                "Crowd Boost":   f"+{(boost-1)*100:.0f}%",
                "Status":        t["level"],
            })
        cdf = pd.DataFrame(chart_data)

        color_map = {"FREE": "#22c55e", "SLOW": "#eab308",
                     "CONGESTED": "#f97316", "STANDSTILL": "#ef4444", "UNKNOWN": "#94a3b8"}

        fig_corr = go.Figure()
        for status, grp in cdf.groupby("Status"):
            fig_corr.add_trace(go.Bar(
                x=grp["Station"], y=grp["Congestion %"],
                name=f"Road: {status}",
                marker_color=color_map.get(status, "#94a3b8"),
                yaxis="y",
                text=grp["Congestion %"].apply(lambda v: f"{v:.0f}%"),
                textposition="outside"
            ))
        fig_corr.add_trace(go.Scatter(
            x=cdf["Station"], y=cdf["Metro Pax"],
            name="Est. Metro Pax (boosted)",
            mode="lines+markers",
            line=dict(color="#60a5fa", width=3),
            marker=dict(size=10),
            yaxis="y2"
        ))
        fig_corr.update_layout(
            yaxis=dict(title="Road Congestion %", gridcolor="rgba(255,255,255,0.05)",
                       range=[0, 110]),
            yaxis2=dict(title="Est. Metro Pax", overlaying="y", side="right",
                        gridcolor="rgba(255,255,255,0)"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(10,14,26,0.6)",
            font=dict(color="#e2e8f0", family="Inter"),
            legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.1),
            height=420, barmode="group"
        )
        st.plotly_chart(fig_corr, use_container_width=True)

        st.markdown("""
        <div class="info-card">
            <b>💡 How Traffic Boosts Metro Crowd:</b><br>
            When roads are congested, commuters switch to metro.
            Our model applies a <b>congestion multiplier</b> (up to +35%) to the
            baseline ML-predicted crowd — giving a more accurate real-world estimate.
        </div>
        """, unsafe_allow_html=True)

        # ── Incidents ─────────────────────────────────────────────────
        if show_incidents:
            st.markdown('<div class="section-title">🚨 Nearby Road Incidents</div>',
                        unsafe_allow_html=True)
            all_incidents = []
            with st.spinner("Fetching incidents..."):
                for sta in stations_to_query[:8]:   # limit to 8 for rate limit
                    incs = tt_client.incidents_near_station(
                        sta["lat"], sta["lon"], radius_km=radius_km)
                    for inc in incs:
                        if "error" not in inc:
                            all_incidents.append({"Near Station": sta["name"], **inc})

            if all_incidents:
                inc_df = pd.DataFrame(all_incidents)[
                    ["Near Station", "severity", "description", "from", "to", "delay_sec"]
                ].copy()
                inc_df.columns = ["Near Station", "Severity", "Description", "From", "To", "Delay (sec)"]
                inc_df["Delay (sec)"] = inc_df["Delay (sec)"].apply(
                    lambda x: f"{int(x)//60} min" if x else "—")
                sev_colors = {"Major": "🔴", "Moderate": "🟠", "Minor": "🟡", "Unknown": "⚪"}
                inc_df["Severity"] = inc_df["Severity"].apply(
                    lambda s: f"{sev_colors.get(s,'⚪')} {s}")
                st.dataframe(inc_df, use_container_width=True, hide_index=True)
            else:
                st.markdown("""
                <div class="alert-box alert-green">✅ No major incidents detected near selected stations.</div>
                """, unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PAGE 8 — SOCIAL & SENTIMENT (News + Twitter)                       ║
# ╚══════════════════════════════════════════════════════════════════════╝
elif page == "📰 Social & Sentiment":
    st.markdown('<div class="section-title">📰 Live Social & News Sentiment</div>', unsafe_allow_html=True)
    st.caption("Real-time sentiment analysis from Twitter/X and News sources to detect potential crowds and delays.")

    if not social_analyzer:
        st.error("Social sentiment module not loaded.")
        st.stop()

    social_station = st.selectbox("Filter Tweets by Station (Optional)", ["All Stations"] + all_stations)
    st_query = None if social_station == "All Stations" else social_station
    
    if st.button("🔄 Fetch Latest Updates", type="primary"):
        with st.spinner("Scanning Twitter and News..."):
            col_news, col_tweets = st.columns(2)
            
            with col_tweets:
                st.markdown("### 🐦 Live Twitter Sentiment")
                tweets = social_analyzer.fetch_live_tweets(st_query)
                
                # Sentiment breakdown
                neg_count = sum(1 for t in tweets if t['sentiment'] == 'Negative')
                pos_count = sum(1 for t in tweets if t['sentiment'] == 'Positive')
                
                if neg_count > pos_count * 2:
                    st.error("🚨 Warning: High negative sentiment detected (Potential overcrowding/delays).")
                elif pos_count > neg_count:
                    st.success("✅ Positive sentiment: Metro is running smoothly.")
                else:
                    st.info("ℹ️ Mixed/Neutral sentiment.")
                
                for t in tweets:
                    border_color = "rgba(248,113,113,0.3)" if t['sentiment']=="Negative" else "rgba(110,231,183,0.3)" if t['sentiment']=="Positive" else "rgba(255,255,255,0.1)"
                    st.markdown(f"""
                    <div style="border:1px solid {border_color}; padding: 12px; border-radius: 8px; margin-bottom: 12px; background: rgba(0,0,0,0.2);">
                        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                            <span style="font-weight:bold; color:#93c5fd;">{t['user']}</span>
                            <span style="font-size:0.85em; color:#94a3b8;">{t['time']}</span>
                        </div>
                        <div style="margin-bottom:8px;">{t['text']}</div>
                        <div><span style="font-size:0.85em; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.1);">{t['icon']} {t['sentiment']}</span></div>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col_news:
                st.markdown("### 📰 Recent DMRC News")
                articles = social_analyzer.fetch_google_news()
                
                for a in articles:
                    border_color = "rgba(248,113,113,0.3)" if a['sentiment']=="Negative" else "rgba(110,231,183,0.3)" if a['sentiment']=="Positive" else "rgba(255,255,255,0.1)"
                    st.markdown(f"""
                    <div style="border:1px solid {border_color}; padding: 12px; border-radius: 8px; margin-bottom: 12px; background: rgba(0,0,0,0.2);">
                        <div style="font-weight:bold; margin-bottom:6px;"><a href="{a['link']}" target="_blank" style="color:#e2e8f0; text-decoration:none;">{a['title']}</a></div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:0.8em; color:#94a3b8;">{a['source']} · {a['date'][:16]}</span>
                            <span style="font-size:0.85em; padding:2px 8px; border-radius:4px; background:rgba(255,255,255,0.1);">{a['icon']} {a['sentiment']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
