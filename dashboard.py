import os

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials

# ページ設定（一番上に書く必要があります）
st.set_page_config(page_title="UFJ-Bot ダッシュボード", layout="wide")

# =========================================================
# 📝 設定：スプレッドシートのキー
# =========================================================
SHEET_KEY = "1wKC4E_r1-1mhGSgIOkz4xRDCba2Ma9bq3phSnBrDXf8"
# =========================================================


# データの読み込み関数（Streamlitのキャッシュ機能を使って高速化）
@st.cache_data(ttl=60)  # 60秒ごとに最新データを読み込む
def load_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "credentials.json")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_file(json_path, scopes=scopes)
    client = gspread.authorize(credentials)

    sheet = client.open_by_key(SHEET_KEY).sheet1
    data = sheet.get_all_records()  # 1行目をヘッダーとして全取得

    df = pd.DataFrame(data)
    # 文字列になっている数値を変換
    df["損益(円)"] = pd.to_numeric(df["損益(円)"], errors="coerce").fillna(0)
    df["トレード回数"] = pd.to_numeric(df["トレード回数"], errors="coerce").fillna(0)
    return df


# ---------------------------------------------------------
# 📊 画面の描画スタート
# ---------------------------------------------------------
st.title("📈 システムトレード 運用ダッシュボード")

try:
    df = load_data()

    if df.empty:
        st.warning("データがまだありません。明日のトレードをお待ちください！")
    else:
        # === 1. サマリー指標（メトリクス） ===
        total_profit = df["損益(円)"].sum()
        total_trades = df["トレード回数"].sum()
        win_count = len(df[df["損益(円)"] > 0])
        win_rate = (
            (win_count / len(df[df["トレード回数"] > 0])) * 100
            if total_trades > 0
            else 0
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 累計損益", f"¥{int(total_profit):,}")
        col2.metric("🎯 勝率", f"{win_rate:.1f}%")
        col3.metric("📊 総トレード数", f"{int(total_trades)}回")
        # 今日の損益
        today_profit = df.iloc[-1]["損益(円)"]
        col4.metric("📅 本日の損益", f"¥{int(today_profit):,}")

        st.divider()

        # === 2. グラフ表示（累積損益の推移） ===
        # 累積損益の列を作る
        df["累積損益"] = df["損益(円)"].cumsum()

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("📈 資産推移（累積損益）")
            fig1 = px.line(
                df, x="日付", y="累積損益", markers=True, template="plotly_dark"
            )
            fig1.update_traces(line_color="#00ff00")
            st.plotly_chart(fig1, use_container_width=True)

        with col_chart2:
            st.subheader("📊 日別損益バーチャート")
            fig2 = px.bar(
                df,
                x="日付",
                y="損益(円)",
                color="損益(円)",
                color_continuous_scale="RdYlGn",
            )
            st.plotly_chart(fig2, use_container_width=True)

        # === 3. 詳細データテーブル ===
        st.subheader("📋 最新のトレード履歴")
        # 新しい日付を一番上にして表示
        st.dataframe(df.sort_values("日付", ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")

# 右下に更新ボタン
if st.button("🔄 データを最新に更新"):
    st.cache_data.clear()
