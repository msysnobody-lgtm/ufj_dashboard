import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# --- 設定部分 ---
CREDENTIALS_FILE = "credentials.json"
SHEET_ID = "1wKC4E_r1-1mhGSgIOkz4xRDCba2Ma9bq3phSnBrDXf8"

st.set_page_config(page_title="運用ダッシュボード", page_icon="📈", layout="centered")


# --- Google Sheetsからデータを取得する関数（60秒間キャッシュしてAPI制限を防ぐ） ---
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

        # ① 今日のトレード履歴を取得
        worksheet_trades = spreadsheet.worksheet("altemist_trades")
        data_trades = worksheet_trades.get_all_records()
        df_trades = pd.DataFrame(data_trades)

        # ② 日次の確定レポートを取得
        worksheet_daily = spreadsheet.worksheet("altemist_daily")
        data_daily = worksheet_daily.get_all_records()
        df_daily = pd.DataFrame(data_daily)

        return df_trades, df_daily
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return pd.DataFrame(), pd.DataFrame()


# データ読み込み実行
df_trades, df_daily = load_data()

# ==========================================
# 画面描画スタート
# ==========================================
st.title("📈 運用ダッシュボード (Altemist)")

# --- データが空の場合の安全装置 ---
if df_trades.empty and df_daily.empty:
    st.warning(
        "まだスプレッドシートにデータがありません。botが動き出すのをお待ちください！"
    )
    st.stop()

# --- 計算ロジック（最新データから数値を抽出） ---
# 今日の合計損益（見込含む）などを計算
today_profit = (
    df_trades["損益"].sum()
    if not df_trades.empty and "損益" in df_trades.columns
    else 0
)
trade_count = len(df_trades)

# 日次データから累計などを計算
total_profit = (
    df_daily["確定損益"].sum()
    if not df_daily.empty and "確定損益" in df_daily.columns
    else 0
)
total_trades = (
    df_daily["トレード回数"].sum()
    if not df_daily.empty and "トレード回数" in df_daily.columns
    else 0
)
total_wins = (
    df_daily["勝数"].sum() if not df_daily.empty and "勝数" in df_daily.columns else 0
)
win_rate = round((total_wins / total_trades * 100), 1) if total_trades > 0 else 0

# --- セクション1：本日のリアルタイム状況 ---
st.header("🟢 本日のリアルタイム状況")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="📅 今日の損益 (見込含)", value=f"¥{today_profit:,}")
with col2:
    st.metric(label="📊 本日のトレード数", value=f"{trade_count}回")
with col3:
    st.metric(
        label="🚜 現在の状態", value="稼働中"
    )  # ※ここは将来APIで動的に変えられます

st.subheader("📝 今日のトレード履歴")
if not df_trades.empty:
    st.dataframe(df_trades, use_container_width=True, hide_index=True)

st.divider()

# --- セクション2：運用成績レポート ---
st.header("📊 運用成績レポート (日次確定)")
col4, col5, col6 = st.columns(3)
with col4:
    st.metric(label="💰 累計確定損益", value=f"¥{total_profit:,}")
with col5:
    st.metric(label="🎯 累計勝率", value=f"{win_rate}%")
with col6:
    st.metric(label="📊 総トレード数", value=f"{total_trades}回")

if not df_daily.empty:
    st.subheader("📈 資産推移")
    # 累計損益のカラムを作って折れ線グラフに
    df_daily["累計"] = df_daily["確定損益"].cumsum()
    st.line_chart(df_daily.set_index("日付")["累計"])

    st.subheader("📊 日別損益")
    st.bar_chart(df_daily.set_index("日付")["確定損益"])
