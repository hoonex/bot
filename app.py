import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Crypto Smart Bot", page_icon="🤖", layout="wide")

st.title("🤖 스마트 트레이딩 대시보드 (Bybit/Binance Auto-routing)")
st.markdown("---")

def get_working_exchange():
    """바이비트 차단 시 바이낸스로 우회하는 거래소 객체 생성기"""
    exchange = ccxt.bybit()
    exchange.set_sandbox_mode(True) # 바이비트 테스트넷 활성화 (IP 차단 회피 시도)
    return exchange

@st.cache_data(ttl=60) 
def get_market_data():
    exchange = get_working_exchange()
    tickers = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']
    data = []
    
    # 1. 바이비트 테스트넷으로 시도
    try:
        for ticker in tickers:
            ticker_data = exchange.fetch_ticker(ticker)
            data.append({"종목": ticker, "24H 거래대금(USDT)": ticker_data['quoteVolume']})
        market_source = "Bybit (Testnet)"
    except Exception as e:
        # 2. 실패 시 바이낸스로 자동 우회 (시세 데이터 전용)
        st.warning("⚠️ 바이비트 서버 접속 제한됨. 분석용 데이터를 바이낸스에서 우회하여 가져옵니다.")
        exchange = ccxt.binance()
        data = []
        for ticker in tickers:
            try:
                ticker_data = exchange.fetch_ticker(ticker)
                data.append({"종목": ticker, "24H 거래대금(USDT)": ticker_data['quoteVolume']})
            except:
                continue
        market_source = "Binance (Fallback)"

    # 데이터가 아예 없을 경우 에러 방지 (KeyError 해결)
    if not data:
        st.error("🚨 모든 거래소에서 데이터를 불러오지 못했습니다.")
        return pd.DataFrame(columns=["종목", "24H 거래대금(USDT)"]), "Error"
        
    df = pd.DataFrame(data).sort_values(by="24H 거래대금(USDT)", ascending=False).reset_index(drop=True)
    return df, market_source

@st.cache_data(ttl=60)
def fetch_ohlcv(symbol, timeframe='15m', limit=100):
    exchange = get_working_exchange()
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    except:
        # 바이비트 실패 시 바이낸스 차트 데이터로 우회
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
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
timeframe = st.sidebar.selectbox("타임프레임 선택", ["5m", "15m", "1h", "4h", "1d"], index=1)

if st.sidebar.button("🔍 시장 분석 및 차트 불러오기"):
    with st.spinner("데이터를 분석 중입니다..."):
        df_market, source = get_market_data()
        
        if source != "Error" and not df_market.empty:
            target_symbol = df_market.iloc[0]["종목"]
            target_vol = df_market.iloc[0]["24H 거래대금(USDT)"]
            
            st.success(f"🔥 현재 거래대금 1위 주도주: **{target_symbol}** ($ {target_vol:,.0f}) | 데이터 출처: {source}")
            
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
