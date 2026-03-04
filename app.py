import gspread
import numpy as np
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# --- 1. ページ基本設定 ---
st.set_page_config(
    page_title="Altemist Dash",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- 2. スタイル調整（見切れ防止・最適化） ---
st.markdown(
    """
    <style>
    /* 上部の見切れを防ぎつつ余白を最小化 */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
    /* タイトルの位置とサイズ調整 */
    h1 {
        font-size: 1.4rem !important;
        margin-top: 0rem !important;
        margin-bottom: -0.5rem !important;
        white-space: nowrap;
    }
    /* ヘッダー：1行に収める */
    h2 {
        font-size: 1.0rem !important;
        margin-top: 1.2rem !important;
        margin-bottom: 0.5rem !important;
        color: #777;
        white-space: nowrap;
    }
    h3 { font-size: 0.9rem !important; margin-top: 0.5rem; }
    /* メトリック（数字）の調整 */
    [data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    /* テーブルフォント */
    .stDataFrame { font-size: 0.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 3. 設定・認証 ---
CREDENTIALS_FILE = "credentials.json"
SHEET_ID = "1wKC4E_r1-1mhGSgIOkz4xRDCba2Ma9bq3phSnBrDXf8"


# --- 4. データ取得関数（60秒キャッシュ） ---
@st.cache_data(ttl=60)
def load_data():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=scopes
        )
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(SHEET_ID)

        ws_trades = spreadsheet.worksheet("altemist_trades")
        df_t = pd.DataFrame(ws_trades.get_all_records())

        ws_daily = spreadsheet.worksheet("altemist_daily")
        df_d = pd.DataFrame(ws_daily.get_all_records())

        return df_t, df_d
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return pd.DataFrame(), pd.DataFrame()


df_trades, df_daily = load_data()

# ==========================================
# 5. 画面描画
# ==========================================

st.markdown("# 📈 Altemist Dashboard")

if df_trades.empty and df_daily.empty:
    st.info("データ待機中... botの初回記録をお待ちください。")
    st.stop()

# --- セクション1：本日の推移 ---
st.markdown("## 📊 本日の推移")

today_profit = df_trades["損益"].sum() if "損益" in df_trades.columns else 0
trade_count = len(df_trades)
current_status = (
    "待機中"
    if df_trades.empty or df_trades.iloc[-1].get("状態") == "確定"
    else "保有中"
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="損益", value=f"¥{today_profit:,}")
with col2:
    st.metric(label="回数", value=f"{trade_count}回")
with col3:
    st.metric(label="状態", value=current_status)

st.markdown("### 📝 今日の履歴")
if not df_trades.empty:
    st.dataframe(df_trades.iloc[::-1], use_container_width=True, hide_index=True)

st.divider()

# --- セクション2：AI分析 (Random Forest) ---
st.markdown("## 🧠 AI分析ステータス")

if not df_trades.empty and "上昇確率" in df_trades.columns:
    last_row = df_trades.iloc[-1]
    try:
        up_val = str(last_row["上昇確率"]).replace("%", "")
        down_val = str(last_row["下落確率"]).replace("%", "")
        up_p = float(up_val) / 100 if float(up_val) > 1 else float(up_val)
        down_p = float(down_val) / 100 if float(down_val) > 1 else float(down_val)
    except:
        up_p, down_p = 0.5, 0.5

    st.markdown("### 🎯 予測スコア")
    c_up, c_down = st.columns(2)
    with c_up:
        st.write(f"📈 上昇: {up_p * 100:.1f}%")
        st.progress(up_p)
    with c_down:
        st.write(f"📉 下落: {down_p * 100:.1f}%")
        st.progress(down_p)

st.divider()

# --- セクション3：累計成績 ---
st.markdown("## 📊 運用レポート")

if not df_daily.empty:
    total_profit = df_daily["確定損益"].sum()
    total_t = df_daily["トレード回数"].sum()
    total_wins = df_daily["勝数"].sum()
    win_rate = round((total_wins / total_t * 100), 1) if total_t > 0 else 0

    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric(label="累計損益", value=f"¥{total_profit:,}")
    with col5:
        st.metric(label="累計勝率", value=f"{win_rate}%")
    with col6:
        st.metric(label="総回数", value=f"{total_t}回")

    st.markdown("### 📈 資産推移")
    df_daily["累計"] = df_daily["確定損益"].cumsum()
    st.line_chart(df_daily.set_index("日付")["累計"])

    st.markdown("### 📊 日別損益")
    st.bar_chart(df_daily.set_index("日付")["確定損益"])
