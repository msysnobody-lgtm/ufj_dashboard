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
# 親ディレクトリ等を探索するパス（環境に合わせて調整）
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
                # 数値変換（エラー回避のため coerce を使用）
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
            sheet_rt = workbook.worksheet("realtime_logs_micro")
            data_rt = sheet_rt.get_all_records()
            df_rt = pd.DataFrame(data_rt)

            if not df_rt.empty:
                # 1列目をTimeとして扱う（カラム名揺れ対策）
                if "Time" not in df_rt.columns and len(df_rt.columns) >= 1:
                    df_rt.rename(columns={df_rt.columns[0]: "Time"}, inplace=True)

                # Datetime変換（エラー発生時はNaTにする）
                df_rt["Datetime"] = pd.to_datetime(df_rt["Time"], errors="coerce")

                # ★修正: 必須カラムが存在しない場合の欠損埋め
                required_cols = ["Type", "Price", "Note"]
                for col in required_cols:
                    if col not in df_rt.columns:
                        df_rt[col] = ""  # 空文字で埋める

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

#

df_history, df_realtime = load_data()

if df_history is None:
    st.stop()

# =========================================================
# 🟢 セクション1：本日のリアルタイム状況
# =========================================================
st.header("🟢 本日のリアルタイム状況")

today_profit = 0
today_trades = 0
current_position = None  # 現在保有中の価格
today_str = datetime.datetime.now().strftime("%Y-%m-%d")
df_today_log = pd.DataFrame()

# データが存在し、かつDatetime変換に成功している行があるか確認
if not df_realtime.empty and "Datetime" in df_realtime.columns:
    # NaT（変換失敗）を除外して、今日の日付でフィルタ
    df_realtime_valid = df_realtime.dropna(subset=["Datetime"])
    df_today_log = df_realtime_valid[
        df_realtime_valid["Datetime"].dt.strftime("%Y-%m-%d") == today_str
    ].copy()

    if not df_today_log.empty:
        # 時系列順に並べ替え（古い順）
        df_today_log = df_today_log.sort_values("Datetime", ascending=True)

        # 損益積み上げ計算ロジック
        temp_buy_price = None  # 一時的に買い価格を保持

        for index, row in df_today_log.iterrows():
            action_type = str(row.get("Type", ""))
            try:
                price = float(row.get("Price", 0))
            except:
                price = 0

            # "買い" または "BUY" を検知
            if "買い" in action_type or "BUY" in action_type:
                temp_buy_price = price  # ポジションを持った

            # "売り" または "SELL" を検知
            elif "売り" in action_type or "SELL" in action_type:
                if temp_buy_price is not None:
                    # ペア成立！利益計算
                    diff = price - temp_buy_price
                    today_profit += diff
                    today_trades += 1
                    temp_buy_price = None  # ポジション解消

        # ループ終了後にまだ temp_buy_price が残っていれば、それは「保有中」
        current_position = temp_buy_price

# --- 表示エリア ---
col_t1, col_t2, col_t3 = st.columns(3)

# 損益表示
delta_color = "normal"
if today_profit > 0:
    delta_color = "inverse"  # プラスなら緑になる

col_t1.metric(
    "📅 今日の確定損益",
    f"¥{int(today_profit):,}",
    delta=f"{int(today_profit)}円",
    delta_color=delta_color,
)
col_t2.metric("📊 完了トレード数", f"{today_trades}回")

# 保有状況の表示
if current_position is not None:
    col_t3.metric("🚜 現在の状態", "保有中", f"取得単価: {int(current_position)}円")
else:
    col_t3.metric("🚜 現在の状態", "ノーポジ", "待機中")

# 履歴テーブル (新しい順に戻して表示)
if not df_today_log.empty:
    with st.expander("📝 今日のトレード履歴を見る", expanded=True):
        # カラムが存在するか最終確認してから表示
        display_cols = ["Time", "Type", "Price", "Note"]
        existing_cols = [c for c in display_cols if c in df_today_log.columns]

        st.dataframe(
            df_today_log.sort_values("Datetime", ascending=False)[existing_cols],
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
    # 日付型に変換してソート（グラフの時系列ズレ防止）
    if "日付" in df_history.columns:
        df_history["日付"] = pd.to_datetime(df_history["日付"], errors="coerce")
        df_history = df_history.sort_values("日付")

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

    # 履歴一覧 (文字列に戻して表示)
    st.subheader("📋 履歴一覧 (最新10件)")
    # 日付を再度文字列にして見やすくする
    df_display = df_history.copy()
    df_display["日付"] = df_display["日付"].dt.strftime("%Y-%m-%d")
    df_display = df_display.sort_values("日付", ascending=False).head(10)

    st.dataframe(df_display, use_container_width=True, hide_index=True)
