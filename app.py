import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Crypto Smart Bot", page_icon="🤖", layout="wide")

st.title("🤖 스마트 트레이딩 대시보드 (조건 결합 알고리즘)")
st.markdown("---")

TICKERS = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'XRP/USDT': 'XRP-USD', 'SOL/USDT': 'SOL-USD'}

@st.cache_data(ttl=60) 
def get_market_data():
    data = []
    for bybit_ticker, yf_ticker in TICKERS.items():
        try:
            ticker = yf.Ticker(yf_ticker)
            hist = ticker.history(period="1d")
            if not hist.empty:
                quote_vol = hist['Volume'].iloc[-1] * hist['Close'].iloc[-1]
                data.append({"종목": bybit_ticker, "24H 거래대금(USDT)": quote_vol})
        except:
            continue
    if not data: return pd.DataFrame(columns=["종목", "24H 거래대금(USDT)"])
    return pd.DataFrame(data).sort_values(by="24H 거래대금(USDT)", ascending=False).reset_index(drop=True)

@st.cache_data(ttl=60)
def fetch_ohlcv(symbol, timeframe='15m', limit=100):
    yf_ticker = TICKERS[symbol]
    ticker = yf.Ticker(yf_ticker)
    period = "5d" if timeframe in ["5m", "15m"] else "1mo"
    df = ticker.history(period=period, interval=timeframe).tail(limit).reset_index()
    df = df.rename(columns={'Datetime': 'timestamp', 'Date': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    return df

def analyze_strategy(df, weights):
    """4가지 조건을 분석하여 점수를 매기는 핵심 알고리즘 (초안)"""
    score = 0
    reasons = []
    
    # 1. 오더블럭 (Support OB 도달 여부)
    recent_low = df['low'][-20:-5].min() # 최근 20봉~5봉 전 최저점
    current_price = df['close'].iloc[-1]
    # 현재 가격이 오더블럭(최저점 근처 0.5% 이내)에 도달했는지
    if recent_low * 0.995 <= current_price <= recent_low * 1.005:
        score += weights['ob']
        reasons.append(f"✅ 오더블럭 도달 (+{weights['ob']}점)")
        
    # 2. 거래량 (Volume Surge)
    vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
    current_vol = df['volume'].iloc[-1]
    if current_vol > vol_ma20 * 1.5: # 20일 평균 대비 1.5배 터졌는지
        score += weights['vol']
        reasons.append(f"✅ 거래량 급증 (+{weights['vol']}점)")
        
    # 3. 추세선 (Trendline)
    x = np.arange(len(df))
    fit = np.polyfit(x, df['close'], 1)
    if fit[0] > 0: # 기울기가 양수(상승 추세)인지
        score += weights['trend']
        reasons.append(f"✅ 상승 추세선 유지 (+{weights['trend']}점)")
        
    # 4. 차트 패턴 (쌍바닥 예시 - 보조 지표)
    # 가장 낮은 두 개의 저점 가격 차이가 1% 이내일 때 쌍바닥으로 간주 (단순화 로직)
    lows = df['low'].nsmallest(2).values
    if len(lows) == 2 and abs(lows[0] - lows[1]) / lows[0] < 0.01:
        score += weights['pattern']
        reasons.append(f"✅ 쌍바닥/수렴 패턴 포착 (+{weights['pattern']}점)")

    return score, reasons

# --- 사이드바 설정 (가중치 조절) ---
st.sidebar.header("⚙️ 봇 컨트롤 패널")
timeframe = st.sidebar.selectbox("타임프레임 선택", ["5m", "15m", "1h", "1d"], index=1)

st.sidebar.subheader("⚖️ 전략 가중치 설정 (총점 100점)")
weight_ob = st.sidebar.slider("오더블럭 (Order Block)", 0, 100, 40, 5)
weight_trend = st.sidebar.slider("추세선 (Trendline)", 0, 100, 30, 5)
weight_vol = st.sidebar.slider("거래량 (Volume)", 0, 100, 20, 5)
weight_pattern = st.sidebar.slider("차트 패턴 (보조)", 0, 100, 10, 5)

entry_threshold = st.sidebar.number_input("🚨 매매 진입 기준 점수", min_value=10, max_value=100, value=70)

weights = {'ob': weight_ob, 'trend': weight_trend, 'vol': weight_vol, 'pattern': weight_pattern}

# --- 메인 UI ---
if st.sidebar.button("🔍 시장 분석 및 차트 불러오기"):
    with st.spinner("데이터 분석 및 매매 시그널 계산 중..."):
        df_market = get_market_data()
        
        if not df_market.empty:
            target_symbol = df_market.iloc[0]["종목"]
            df_ohlcv = fetch_ohlcv(target_symbol, timeframe)
            
            # 전략 점수 계산
            total_score, matched_reasons = analyze_strategy(df_ohlcv, weights)
            
            # --- 결과 출력 ---
            st.subheader(f"🔥 타겟 종목: {target_symbol}")
            
            # 점수에 따른 상태 메시지 (70점 이상이면 매수 신호)
            if total_score >= entry_threshold:
                st.success(f"🟢 **매수 시그널 발생!** (총점: {total_score} / 100)")
            else:
                st.warning(f"🟡 **관망 상태** (총점: {total_score} / 100) - 기준 점수({entry_threshold}) 미달")
                
            # 합격한 조건들 나열
            if matched_reasons:
                for reason in matched_reasons:
                    st.write(reason)
            else:
                st.write("❌ 현재 일치하는 매매 조건이 없습니다.")
                
            st.markdown("---")
            
            # 차트 그리기 (기존과 동일하게 유지하되 단순화하여 호출만 작성)
            # 여기서는 편의상 시각화 코드는 생략하지 않고 기본 캔들만 빠르게 띄웁니다.
            fig = go.Figure(data=[go.Candlestick(x=df_ohlcv['timestamp'], open=df_ohlcv['open'], high=df_ohlcv['high'], low=df_ohlcv['low'], close=df_ohlcv['close'])])
            fig.update_layout(height=500, xaxis_rangeslider_visible=False, title=f"{target_symbol} {timeframe} 차트")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 왼쪽 사이드바에서 전략 가중치를 조절한 뒤 '시장 분석' 버튼을 눌러주세요.")
