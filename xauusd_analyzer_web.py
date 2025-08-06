import streamlit as st
from fredapi import Fred
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from deep_translator import GoogleTranslator
import requests
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as pdf_canvas
import pyperclip

# 🧱 設定中文字型與負號顯示
matplotlib.rcParams['font.family'] = 'Microsoft JhengHei'
matplotlib.rcParams['axes.unicode_minus'] = False

# === API Keys ===
FRED_API_KEY = "913e705eb7b2662d21f98066093a8a43"
GROQ_API_KEY = "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"

# === tvDatafeed 登入 ===
tv = TvDatafeed(username="bill111880", password="Acbel@108261")

indicators = {
    "CPI": "CPIAUCSL",
    "Unemployment Rate": "UNRATE",
    "Federal Funds Rate": "FEDFUNDS",
    "M2 Money Supply": "M2SL",
    "10Y Treasury Yield": "GS10",
    "Nonfarm Payrolls": "PAYEMS"
}

TIMEFRAMES = {
    "5min": Interval.in_5_minute,
    "15min": Interval.in_15_minute,
    "1h": Interval.in_1_hour,
    "4h": Interval.in_4_hour
}

# === 主題選擇 ===
st.set_page_config(page_title="📈 XAUUSD 分析工具", layout="wide")
theme = st.sidebar.selectbox("選擇圖表主題", ["🌞 淺色主題", "🌙 深色主題"])

if theme == "🌙 深色主題":
    matplotlib.style.use("dark_background")
    bg_color = "#0e1117"
    text_color = "white"
else:
    matplotlib.style.use("default")
    bg_color = "white"
    text_color = "black"

# === 資料抓取函式 ===
def fetch_macro_data():
    fred = Fred(api_key=FRED_API_KEY)
    result = {}
    for name, code in indicators.items():
        series = fred.get_series(code)
        result[name] = round(series.iloc[-1], 2)
    return result

def fetch_candles(symbol="XAUUSD", interval="15min", limit=100):
    df = tv.get_hist(symbol=symbol, exchange="OANDA", interval=TIMEFRAMES[interval], n_bars=limit)
    df.reset_index(inplace=True)
    df.rename(columns={"date": "datetime"}, inplace=True)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df

def make_prompt(macro_data, kline_data, user_instruction):
    summary = ""
    for tf, df in kline_data.items():
        close = df.iloc[-1]['close']
        time = df.iloc[-1]['datetime']
        summary += f"[{tf}] 最新收盤價: {close} (時間: {time})\n"

    prompt = f"""
Below are the latest U.S. macroeconomic indicators:
- CPI: {macro_data['CPI']}
- Unemployment rate: {macro_data['Unemployment Rate']}%
- Federal funds rate: {macro_data['Federal Funds Rate']}%
- M2 money supply: {macro_data['M2 Money Supply']}
- 10-year Treasury yield: {macro_data['10Y Treasury Yield']}%
- Nonfarm Payrolls: {macro_data['Nonfarm Payrolls']} thousand jobs

Next is the recent price information of XAU/USD (Gold):
{summary}

{user_instruction}
"""
    return prompt

def analyze_with_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-70b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]

def translate_to_chinese(text):
    return GoogleTranslator(source='en', target='zh-TW').translate(text)

def generate_pdf(content):
    buffer = BytesIO()
    p = pdf_canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    for line in content.splitlines():
        p.drawString(40, y, line[:90])
        y -= 15
        if y < 40:
            p.showPage()
            y = height - 40
    p.save()
    buffer.seek(0)
    return buffer

# === 介面 UI ===
st.title("📈 XAUUSD 分析工具")

col1, col2 = st.columns([1, 2])

with col1:
    user_instruction = st.text_area("請輸入分析指令", height=300, value=(
        "You are a professional forex market analyst specializing in XAUUSD. "
        "Based on the macroeconomic data and multi-timeframe candlestick price action data I provide, "
        "your task is to analyze the current market conditions and provide actionable short-term trading strategies. "
        "Focus your analysis on the 15-minute and 5-minute timeframes. Your output should include: "
        "1. Key support and resistance levels "
        "2. Whether to go long (buy) or go short (sell) "
        "3. Suggested entry price level "
        "4. Suggested take profit (TP) and stop loss (SL) levels "
        "A brief explanation for your trading recommendation, based on the observed price structure and macroeconomic context. "
        "Use clear and concise professional trading language in your response."
    ))

    if st.button("🔍 開始分析"):
        with st.spinner("正在抓取資料與分析..."):
            try:
                macro = fetch_macro_data()
                kline_data = {tf: fetch_candles(interval=tf) for tf in TIMEFRAMES}
                prompt = make_prompt(macro, kline_data, user_instruction)
                result = analyze_with_groq(prompt)

                st.session_state["analysis_result"] = result
                st.session_state["macro_data"] = macro
                st.session_state["kline_data"] = kline_data

            except Exception as e:
                st.error(f"❌ 分析失敗: {e}")

    if "analysis_result" in st.session_state:
        st.text_area("AI 分析結果", value=st.session_state["analysis_result"], height=700)

        if st.button("📘 翻譯分析結果為中文"):
            translated = translate_to_chinese(st.session_state["analysis_result"])
            st.text_area("翻譯結果", value=translated, height=700)

        if st.button("📋 複製分析結果"):
            pyperclip.copy(st.session_state["analysis_result"])
            st.success("分析結果已複製到剪貼簿")

        if st.download_button("📄 下載 PDF 報告", data=generate_pdf(st.session_state["analysis_result"]),
                              file_name="XAUUSD_分析報告.pdf", mime="application/pdf"):
            st.success("PDF 下載成功")

with col2:
    if "macro_data" in st.session_state:
        st.subheader("✅ 總經資料")
        st.json(st.session_state["macro_data"])

    if "kline_data" in st.session_state:
        st.subheader("📊 K 線圖")
        for tf, df in st.session_state["kline_data"].items():
            fig, ax = plt.subplots(figsize=(8, 3))
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color)
            ax.plot(df["datetime"], df["close"], label="Close", color="gold")
            ax.set_title(f"{tf} 收盤價", color=text_color)
            ax.tick_params(axis='x', rotation=45, colors=text_color)
            ax.tick_params(axis='y', colors=text_color)
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            ax.grid(True, color='gray', linestyle='--', linewidth=0.5)
            st.pyplot(fig)
