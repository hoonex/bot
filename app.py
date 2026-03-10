import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

st.set_page_config(page_title="Crypto Smart Bot", page_icon="🤖", layout="wide")

st.title("🤖 스마트 봇 모의투자 (1분봉 실시간 테스트)")
st.markdown("---")

# --- 1. 세션 상태(기억 장치) 초기화 ---
if 'balance' not in st.session_state: st.session_state['balance'] = 10000.0
if 'position' not in st.session_state: st.session_state['position'] = None
if 'history' not in st.session_state: st.session_state['history'] = []
# 화면이 리셋되지 않도록 '분석 모드' 켜짐 상태를 기억하는 변수 추가
if 'dashboard_active' not in st.session_state: st.session_state['dashboard_active'] = False

TICKERS = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'XRP/USDT': 'XRP-USD', 'SOL/USDT': 'SOL-USD'}

# ttl=10으로 줄여서 10초마다 최신 실시간 데이터를 가져오도록 세팅
@st.cache_data(ttl=10) 
def get_market_data():
    data = []
    for bybit_ticker, yf_ticker in TICKERS.items():
        try:
            hist = yf.Ticker(yf_ticker).history(period="1d")
            if not hist.empty:
                quote_vol = hist['Volume'].iloc[-1] * hist['Close'].iloc[-1]
                data.append({"종목": bybit_ticker, "24H 거래대금(USDT)": quote_vol})
        except:
            continue
    if not data: return pd.DataFrame(columns=["종목", "24H 거래대금(USDT)"])
    return pd.DataFrame(data).sort_values(by="24H 거래대금(USDT)", ascending=False).reset_index(drop=True)

@st.cache_data(ttl=10)
def fetch_ohlcv(symbol, timeframe='1m', limit=100):
    yf_ticker = TICKERS[symbol]
    
    # 1분봉은 yfinance에서 최근 7일치까지만 지원함
    if timeframe == '1m': period = "5d"
    elif timeframe in ['5m', '15m']: period = "1mo"
    else: period = "1mo"
        
    df = yf.Ticker(yf_ticker).history(period=period, interval=timeframe).tail(limit).reset_index()
    df = df.rename(columns={'Datetime': 'timestamp', 'Date': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    return df

def analyze_strategy(df, weights):
    score = 0
    reasons = []
    recent_low = df['low'][-20:-5].min() 
    current_price = df['close'].iloc[-1]
    
    if recent_low * 0.995 <= current_price <= recent_low * 1.005:
        score += weights['ob']
        reasons.append(f"✅ 오더블럭 도달 (+{weights['ob']}점)")
        
    vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
    if df['volume'].iloc[-1] > vol_ma20 * 1.5:
        score += weights['vol']
        reasons.append(f"✅ 거래량 급증 (+{weights['vol']}점)")
        
    x = np.arange(len(df))
    fit = np.polyfit(x, df['close'], 1)
    if fit[0] > 0:
        score += weights['trend']
        reasons.append(f"✅ 상승 추세선 (+{weights['trend']}점)")
        
    lows = df['low'].nsmallest(2).values
    if len(lows) == 2 and abs(lows[0] - lows[1]) / lows[0] < 0.01:
        score += weights['pattern']
        reasons.append(f"✅ 바닥 수렴 패턴 (+{weights['pattern']}점)")

    return score, reasons

# --- 사이드바 ---
st.sidebar.header("⚙️ 봇 컨트롤 패널")
# 1분봉(1m) 추가
timeframe = st.sidebar.selectbox("타임프레임 선택", ["1m", "5m", "15m", "1h", "4h", "1d"], index=0)
entry_threshold = st.sidebar.number_input("🚨 매수 진입 기준 점수", min_value=10, max_value=100, value=70)

weights = {
    'ob': st.sidebar.slider("오더블럭 비중", 0, 100, 40, 5),
    'trend': st.sidebar.slider("추세선 비중", 0, 100, 30, 5),
    'vol': st.sidebar.slider("거래량 비중", 0, 100, 20, 5),
    'pattern': st.sidebar.slider("패턴 비중", 0, 100, 10, 5)
}

# 분석 버튼을 누르면 상태를 True로 변경
if st.sidebar.button("🔍 시장 분석 시작 / 새로고침"):
    st.session_state['dashboard_active'] = True

# --- 메인 대시보드 UI ---
col_bal, col_pos = st.columns(2)
col_bal.metric(label="💰 내 가상 지갑 잔고", value=f"$ {st.session_state['balance']:,.2f}")
if st.session_state['position']:
    pos = st.session_state['position']
    col_pos.metric(label="📈 현재 보유 포지션", value=f"{pos['symbol']} (진입가: $ {pos['entry_price']:,.2f})")
else:
    col_pos.metric(label="📈 현재 보유 포지션", value="없음 (관망 중)")

st.markdown("---")

# 대시보드가 켜져 있을 때만 아래 내용을 그림 (매수/매도 버튼을 눌러도 여기가 계속 실행됨)
if st.session_state['dashboard_active']:
    df_market = get_market_data()
    
    if not df_market.empty:
        target_symbol = df_market.iloc[0]["종목"]
        df_ohlcv = fetch_ohlcv(target_symbol, timeframe)
        current_price = df_ohlcv['close'].iloc[-1]
        total_score, matched_reasons = analyze_strategy(df_ohlcv, weights)
        
        st.subheader(f"🔥 타겟 종목: {target_symbol} (현재가: $ {current_price:,.2f})")
        st.write(f"**전략 총점: {total_score}점** / 100점")
        for r in matched_reasons: st.caption(r)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # 매수/매도 버튼 로직
            if total_score >= entry_threshold and st.session_state['position'] is None:
                st.success("🟢 매수 시그널 포착! (모의 진입 가능)")
                if st.button("🛒 테스트 매수 (Buy)", use_container_width=True):
                    st.session_state['position'] = {'symbol': target_symbol, 'entry_price': current_price}
                    st.session_state['history'].append({"시간": datetime.now().strftime("%H:%M:%S"), "종목": target_symbol, "구분": "매수", "가격": current_price, "수익금": 0})
                    st.rerun() # 화면 새로고침해도 dashboard_active가 True라 안 날아감
                    
            elif st.session_state['position'] is not None:
                pos = st.session_state['position']
                profit = current_price - pos['entry_price']
                profit_pct = (profit / pos['entry_price']) * 100
                
                st.warning(f"🟡 현재 {pos['symbol']} 보유 중 (수익률: {profit_pct:.2f}%)")
                if st.button("💸 테스트 매도 (Sell & Take Profit)", use_container_width=True):
                    st.session_state['balance'] += profit 
                    st.session_state['history'].append({"시간": datetime.now().strftime("%H:%M:%S"), "종목": pos['symbol'], "구분": "매도", "가격": current_price, "수익금": round(profit, 2)})
                    st.session_state['position'] = None 
                    st.rerun()
            else:
                st.info("조건 미달로 관망 중입니다.")
                
        with col2:
            fig = go.Figure(data=[go.Candlestick(x=df_ohlcv['timestamp'], open=df_ohlcv['open'], high=df_ohlcv['high'], low=df_ohlcv['low'], close=df_ohlcv['close'])])
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 왼쪽 사이드바에서 '시장 분석 시작' 버튼을 눌러 봇을 가동해주세요.")

st.markdown("---")
st.subheader("📝 모의투자 매매 일지")
if st.session_state['history']:
    st.dataframe(pd.DataFrame(st.session_state['history']).iloc[::-1], use_container_width=True) # 최신 내역이 위로 오게 뒤집기
else:
    st.write("아직 매매 기록이 없습니다.")
