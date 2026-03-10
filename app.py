import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Crypto Smart Bot", page_icon="🤖", layout="wide")

st.title("🤖 스마트 트레이딩 대시보드 (TradingView 데이터 연동)")
st.markdown("---")

# 종목 심볼 매핑 (바이비트 이름 -> 글로벌 데이터 이름)
TICKERS = {
    'BTC/USDT': 'BTC-USD', 
    'ETH/USDT': 'ETH-USD', 
    'XRP/USDT': 'XRP-USD', 
    'SOL/USDT': 'SOL-USD'
}

@st.cache_data(ttl=60) 
def get_market_data():
    data = []
    for bybit_ticker, yf_ticker in TICKERS.items():
        try:
            ticker = yf.Ticker(yf_ticker)
            # 오늘 하루치 데이터만 가져오기
            hist = ticker.history(period="1d")
            if not hist.empty:
                # 글로벌 데이터는 코인 갯수 기준이므로 가격을 곱해 거래대금(USDT)으로 변환
                quote_vol = hist['Volume'].iloc[-1] * hist['Close'].iloc[-1]
                data.append({"종목": bybit_ticker, "24H 거래대금(USDT)": quote_vol})
        except Exception as e:
            st.error(f"🚨 {bybit_ticker} 데이터 오류: {e}")
            continue
            
    if not data:
        return pd.DataFrame(columns=["종목", "24H 거래대금(USDT)"])
        
    df = pd.DataFrame(data).sort_values(by="24H 거래대금(USDT)", ascending=False).reset_index(drop=True)
    return df

@st.cache_data(ttl=60)
def fetch_ohlcv(symbol, timeframe='15m', limit=100):
    yf_ticker = TICKERS[symbol]
    ticker = yf.Ticker(yf_ticker)
    
    # yfinance는 기간(period)을 설정해야 분봉을 가져올 수 있음
    period = "5d" if timeframe in ["5m", "15m"] else "1mo"
    df = ticker.history(period=period, interval=timeframe)
    
    df = df.tail(limit).reset_index()
    # 열 이름을 이전 코드와 똑같이 맞춤
    df = df.rename(columns={'Datetime': 'timestamp', 'Date': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    return df

def draw_chart(df, symbol):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, subplot_titles=(f'{symbol} 차트', 'Volume'), 
                        row_width=[0.2, 0.7])

    fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Candle'), row=1, col=1)

    colors = ['green' if row['close'] >= row['open'] else 'red' for index, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df['timestamp'], y=df['volume'], marker_color=colors, name='Volume'), row=2, col=1)

    x = np.arange(len(df))
    fit = np.polyfit(x, df['close'], 1)
    trendline = np.poly1d(fit)(x)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=trendline, mode='lines', name='Trendline', line=dict(color='orange', width=2, dash='dot')), row=1, col=1)

    recent_low = df['low'][-20:].min()
    fig.add_hrect(y0=recent_low * 0.998, y1=recent_low * 1.002, line_width=0, fillcolor="blue", opacity=0.2, annotation_text="Support OB", row=1, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, showlegend=False)
    return fig

# --- 사이드바 & 메인 UI ---
st.sidebar.header("⚙️ 봇 컨트롤 패널")
timeframe = st.sidebar.selectbox("타임프레임 선택", ["5m", "15m", "1h", "1d"], index=1)

if st.sidebar.button("🔍 시장 분석 및 차트 불러오기"):
    with st.spinner("트레이딩뷰 데이터를 분석 중입니다..."):
        df_market = get_market_data()
        
        if not df_market.empty:
            target_symbol = df_market.iloc[0]["종목"]
            target_vol = df_market.iloc[0]["24H 거래대금(USDT)"]
            
            st.success(f"🔥 현재 거래대금 1위 주도주: **{target_symbol}** ($ {target_vol:,.0f})")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                st.subheader("📊 랭킹")
                st.dataframe(df_market.style.format({"24H 거래대금(USDT)": "$ {:,.0f}"}), use_container_width=True)
                
            with col2:
                st.subheader(f"📈 {target_symbol} 기술적 분석 ({timeframe})")
                df_ohlcv = fetch_ohlcv(target_symbol, timeframe)
                fig = draw_chart(df_ohlcv, target_symbol)
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("👈 왼쪽 사이드바에서 '시장 분석 및 차트 불러오기' 버튼을 눌러주세요.")
