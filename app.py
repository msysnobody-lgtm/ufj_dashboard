import numpy as np
import pandas as pd
import streamlit as st

# --- ページ設定 ---
st.set_page_config(page_title="運用ダッシュボード", page_icon="📈", layout="centered")

# --- ダミーデータの作成 ---
# 今日の履歴データ
today_data = pd.DataFrame(
    {
        "時間": ["14:30", "13:15", "10:05", "09:15"],
        "売買": ["買→売", "売→買", "買→売", "売→買"],
        "損益": [1500, -500, 2000, 1400],
    }
)

equity_data = pd.DataFrame({"累計損益": [0, -100, 50, 150, 280]})
daily_profit_data = pd.DataFrame(
    {"損益": [1200, -800, 3000, -500, 4400]},
    index=["2/26", "2/27", "2/28", "3/1", "今日"],
)

# 🌳 ランダムフォレスト特有のデータ（特徴量重要度）
# AIがどのデータを重要視して学習・判断しているか
rf_features = pd.DataFrame(
    {"重要度": [0.35, 0.25, 0.15, 0.10, 0.10, 0.05]},
    index=[
        "直近1分ボラティリティ",
        "買い板の厚み",
        "MACDシグナル",
        "売り板の厚み",
        "RSI",
        "移動平均乖離率",
    ],
)


# ==========================================
# 画面描画スタート
# ==========================================

st.title("📈 システムトレード 運用ダッシュボード")

# --- セクション1：本日のリアルタイム状況 ---
st.header("🟢 本日のリアルタイム状況")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="📅 今日の確定損益", value="¥4,400", delta="+1,400")
with col2:
    st.metric(label="📊 完了トレード数", value="11回")
with col3:
    st.metric(
        label="🚜 現在の状態", value="ノーポジ", delta="待機中", delta_color="off"
    )

# 変更点：履歴を畳まずにそのまま表示
st.subheader("📝 今日のトレード履歴")
st.dataframe(today_data, use_container_width=True, hide_index=True)

st.divider()


# --- 新設セクション：ランダムフォレストの脳内可視化 ---
st.header("🧠 AI (ランダムフォレスト) 分析ステータス")

st.subheader("🎯 現在の方向予測スコア (確信度)")
st.caption("AIが算出している次の一手の確率です")
col_up, col_down = st.columns(2)
with col_up:
    st.metric(label="📈 上昇(Buy) 確率", value="78%")
    st.progress(0.78)  # バー表示
with col_down:
    st.metric(label="📉 下落(Sell) 確率", value="22%")
    st.progress(0.22)  # バー表示

st.subheader("🔍 現在の判断基準 (特徴量重要度)")
st.caption("AIが相場を判定する上で、現在どの指標を強く根拠にしているかのトップ要素です")
st.bar_chart(rf_features)

st.divider()


# --- セクション3：運用成績レポート ---
st.header("📊 運用成績レポート (日次集計)")

col4, col5, col6 = st.columns(3)
with col4:
    st.metric(label="💰 累計損益", value="¥280")
with col5:
    st.metric(label="🎯 勝率 (日単位)", value="34.6%")
with col6:
    st.metric(label="📊 総トレード数", value="80回")

st.subheader("📈 資産推移")
st.line_chart(equity_data["累計損益"])

st.subheader("📊 日別損益")
st.bar_chart(daily_profit_data["損益"])
