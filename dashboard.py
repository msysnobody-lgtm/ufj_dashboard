import datetime
import os

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# =========================================================
# ⚙️ ページ設定
# =========================================================
st.set_page_config(page_title="UFJ-Bot ダッシュボード", layout="wide")

# =========================================================
# 📝 設定：パスとシートID
# =========================================================
load_dotenv()

# ID取得
ENV_SHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_KEY = (
    ENV_SHEET_ID if ENV_SHEET_ID else "1wKC4E_r1-1mhGSgIOkz4xRDCba2Ma9bq3phSnBrDXf8"
)

# パス解決
CREDENTIALS_FILE = "credentials.json"
LOCAL_ADJACENT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ufj_bot",
    "credentials.json",
)

if os.path.exists(CREDENTIALS_FILE):
    JSON_PATH = CREDENTIALS_FILE
elif os.path.exists(LOCAL_ADJACENT_PATH):
    JSON_PATH = LOCAL_ADJACENT_PATH
else:
    JSON_PATH = None


# =========================================================
# 📥 データ読み込み関数
# =========================================================
@st.cache_data(ttl=30)
def load_data():
    if not JSON_PATH:
        return None, None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        credentials = Credentials.from_service_account_file(JSON_PATH, scopes=scopes)
        client = gspread.authorize(credentials)
        workbook = client.open_by_key(SHEET_KEY)

        # --- A. 過去の履歴 (summaryシート) ---
        try:
            sheet_his = workbook.worksheet("summary")
            data_his = sheet_his.get_all_records()
            df_his = pd.DataFrame(data_his)
            if not df_his.empty:
                df_his["損益(円)"] = pd.to_numeric(
                    df_his["損益(円)"], errors="coerce"
                ).fillna(0)
                df_his["トレード回数"] = pd.to_numeric(
                    df_his["トレード回数"], errors="coerce"
                ).fillna(0)
        except Exception:
            df_his = pd.DataFrame()

        # --- B. 今日のリアルタイム (realtime_logs) ---
        try:
            sheet_rt = workbook.worksheet("realtime_logs")
            data_rt = sheet_rt.get_all_records()
            df_rt = pd.DataFrame(data_rt)
            if not df_rt.empty:
                # カラム名がずれている場合の保険（CSVアップロード時などの対策）
                # 1列目をTimeとして扱う
                if "Time" not in df_rt.columns and len(df_rt.columns) >= 1:
                    df_rt.rename(columns={df_rt.columns[0]: "Time"}, inplace=True)

                df_rt["Datetime"] = pd.to_datetime(df_rt["Time"])
        except Exception:
            df_rt = pd.DataFrame()

        return df_his, df_rt

    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return None, None


# =========================================================
# 🖥️ メイン画面描画
# =========================================================
st.title("📈 システムトレード 運用ダッシュボード")

if st.button("🔄 最新データに更新"):
    st.cache_data.clear()
    st.rerun()

if not JSON_PATH:
    st.error("⚠️ credentials.json が見つかりません。")
    st.stop()

df_history, df_realtime = load_data()

if df_history is None:
    st.stop()

# ---------------------------------------------------------
# 🟢 セクション1：本日のリアルタイム状況
# ---------------------------------------------------------
st.header("🟢 本日のリアルタイム状況")

today_profit = 0
today_trades = 0
today_str = datetime.datetime.now().strftime("%Y-%m-%d")
df_today_log = pd.DataFrame()

if not df_realtime.empty and "Datetime" in df_realtime.columns:
    df_today_log = df_realtime[
        df_realtime["Datetime"].dt.strftime("%Y-%m-%d") == today_str
    ].copy()

    if not df_today_log.empty:
        # ★修正: "BUY/SELL" だけでなく "買い/売り" も検知するように変更
        # 2列目(Type)を文字列にして判定
        # カラム名が Type でない場合も考慮して、2番目のカラムを使うとより安全だが、
        # ここでは "Type" カラムがあると仮定（gspreadのget_all_recordsは1行目をヘッダーにするため）

        # 買いの合計
        mask_buy = (
            df_today_log["Type"]
            .astype(str)
            .str.contains("BUY|買い", case=False, na=False)
        )
        buys = df_today_log.loc[mask_buy, "Price"].sum()

        # 売りの合計
        mask_sell = (
            df_today_log["Type"]
            .astype(str)
            .str.contains("SELL|売り", case=False, na=False)
        )
        sells = df_today_log.loc[mask_sell, "Price"].sum()

        today_profit = sells - buys
        today_trades = len(df_today_log) // 2

col_t1, col_t2 = st.columns(2)
col_t1.metric(
    "📅 今日の推定損益", f"¥{int(today_profit):,}", delta=f"{int(today_profit)}円"
)
col_t2.metric("📊 今日のログ数", f"{len(df_today_log)}行")

if not df_today_log.empty:
    with st.expander("📝 今日のトレード履歴を見る", expanded=True):
        st.dataframe(
            df_today_log[["Time", "Type", "Price", "Note"]].sort_values(
                "Time", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("今日のトレードはまだありません。")

st.divider()

# ---------------------------------------------------------
# 📊 セクション2：過去の運用成績
# ---------------------------------------------------------
st.header("📊 運用成績レポート (日次集計)")

if df_history.empty:
    st.warning("日次レポート(summary)のデータがまだありません。")
else:
    # 指標
    total_profit = df_history["損益(円)"].sum()
    total_trades = df_history["トレード回数"].sum()
    win_count = len(df_history[df_history["損益(円)"] > 0])
    win_rate = (win_count / len(df_history)) * 100 if len(df_history) > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 累計損益", f"¥{int(total_profit):,}")
    col2.metric("🎯 勝率 (日単位)", f"{win_rate:.1f}%")
    col3.metric("📊 総トレード数", f"{int(total_trades)}回")

    # グラフ
    df_history["累積損益"] = df_history["損益(円)"].cumsum()

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("📈 資産推移")
        fig1 = px.line(
            df_history, x="日付", y="累積損益", markers=True, template="plotly_dark"
        )
        fig1.update_traces(line_color="#00ff00")
        st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
        st.subheader("📊 日別損益")
        fig2 = px.bar(
            df_history,
            x="日付",
            y="損益(円)",
            color="損益(円)",
            color_continuous_scale="RdYlGn",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # 履歴一覧
    st.subheader("📋 履歴一覧 (最新10件)")
    df_display = df_history.sort_values("日付", ascending=False).head(10)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
