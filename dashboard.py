import datetime
import os

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials

# =========================================================
# ⚙️ ページ設定
# =========================================================
st.set_page_config(page_title="UFJ-Bot ダッシュボード", layout="wide")

# =========================================================
# 📝 設定：Renderとローカルのパス自動判別
# =========================================================
SHEET_KEY = "1wKC4E_r1-1mhGSgIOkz4xRDCba2Ma9bq3phSnBrDXf8"

# 1. Renderのシークレットファイルの標準パス
RENDER_SECRET_PATH = "/etc/secrets/credentials.json"

# 2. ローカル環境でのパス (../ufj_bot/credentials.json)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
LOCAL_PATH = os.path.join(ROOT_DIR, "ufj_bot", "credentials.json")

# 存在する方を使う
if os.path.exists(RENDER_SECRET_PATH):
    JSON_PATH = RENDER_SECRET_PATH
elif os.path.exists(LOCAL_PATH):
    JSON_PATH = LOCAL_PATH
else:
    JSON_PATH = "credentials.json"  # 同階層にある場合の保険


# =========================================================
# 📥 データ読み込み関数 (履歴 と リアルタイム 両方取得)
# =========================================================
@st.cache_data(ttl=30)  # 30秒ごとに更新
def load_data():
    if not os.path.exists(JSON_PATH):
        return None, None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        credentials = Credentials.from_service_account_file(JSON_PATH, scopes=scopes)
        client = gspread.authorize(credentials)
        workbook = client.open_by_key(SHEET_KEY)

        # --- A. 過去の履歴 (Sheet1) ---
        try:
            sheet_his = workbook.sheet1
            data_his = sheet_his.get_all_records()
            df_his = pd.DataFrame(data_his)
            if not df_his.empty:
                df_his["損益(円)"] = pd.to_numeric(
                    df_his["損益(円)"], errors="coerce"
                ).fillna(0)
                df_his["トレード回数"] = pd.to_numeric(
                    df_his["トレード回数"], errors="coerce"
                ).fillna(0)
        except:
            df_his = pd.DataFrame()

        # --- B. 今日のリアルタイム (realtime_logs) ---
        try:
            sheet_rt = workbook.worksheet("realtime_logs")
            data_rt = sheet_rt.get_all_records()
            df_rt = pd.DataFrame(data_rt)
            if not df_rt.empty:
                df_rt["Datetime"] = pd.to_datetime(df_rt["Time"])
        except:
            df_rt = pd.DataFrame()

        return df_his, df_rt

    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return None, None


# =========================================================
# 🖥️ メイン画面描画
# =========================================================
st.title("📈 システムトレード 運用ダッシュボード")

# 右上に更新ボタン配置
if st.button("🔄 最新データに更新"):
    st.cache_data.clear()
    st.rerun()

df_history, df_realtime = load_data()

if df_history is None:
    st.error("⚠️ 認証ファイルが見つからないか、データ取得に失敗しました。")
    st.stop()

# ---------------------------------------------------------
# 🟢 セクション1：本日のリアルタイム状況 (Render対応)
# ---------------------------------------------------------
st.header("🟢 本日のリアルタイム状況")

today_profit = 0
today_trades = 0
today_str = datetime.datetime.now().strftime("%Y-%m-%d")
df_today_log = pd.DataFrame()

if not df_realtime.empty:
    # 今日だけのデータにフィルタリング
    df_today_log = df_realtime[
        df_realtime["Datetime"].dt.strftime("%Y-%m-%d") == today_str
    ].copy()

    if not df_today_log.empty:
        # 簡易損益計算 (売り総額 - 買い総額)
        buys = df_today_log[df_today_log["Type"].str.contains("買", na=False)][
            "Price"
        ].sum()
        sells = df_today_log[df_today_log["Type"].str.contains("売", na=False)][
            "Price"
        ].sum()
        today_profit = sells - buys
        today_trades = len(df_today_log) // 2  # おおよその往復回数

# 今日のメトリクス表示
col_t1, col_t2, col_t3 = st.columns(3)
col_t1.metric(
    "📅 今日の推定損益", f"¥{int(today_profit):,}", delta=f"{int(today_profit)}円"
)
col_t2.metric("📊 今日の注文数", f"{len(df_today_log)}回")

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
# 📊 セクション2：過去の運用成績 (グラフあり)
# ---------------------------------------------------------
st.header("📊 運用成績レポート (過去ログ)")

if df_history.empty:
    st.warning("過去のデータがまだありません。")
else:
    # === サマリー指標 ===
    total_profit = df_history["損益(円)"].sum()
    total_trades = df_history["トレード回数"].sum()
    win_count = len(df_history[df_history["損益(円)"] > 0])
    win_rate = (win_count / len(df_history)) * 100 if len(df_history) > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 累計損益", f"¥{int(total_profit):,}")
    col2.metric("🎯 勝率 (日単位)", f"{win_rate:.1f}%")
    col3.metric("📊 総トレード数", f"{int(total_trades)}回")

    # === グラフ表示 ===
    # 累積損益の列を作る
    df_history["累積損益"] = df_history["損益(円)"].cumsum()

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("📈 資産推移（累積損益）")
        fig1 = px.line(
            df_history, x="日付", y="累積損益", markers=True, template="plotly_dark"
        )
        fig1.update_traces(line_color="#00ff00")
        st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
        st.subheader("📊 日別損益バーチャート")
        fig2 = px.bar(
            df_history,
            x="日付",
            y="損益(円)",
            color="損益(円)",
            color_continuous_scale="RdYlGn",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # === 詳細データテーブル ===
    st.subheader("📋 履歴一覧")
    st.dataframe(
        df_history.sort_values("日付", ascending=False), use_container_width=True
    )
