import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

st.set_page_config(page_title="Crypto Smart Bot", page_icon="🤖", layout="wide")

st.title("🤖 스마트 트레이딩 봇 (실시간 알고리즘 버전)")
st.markdown("---")

# --- 세션 상태 초기화 ---
if 'balance' not in st.session_state: st.session_state['balance'] = 10000.0
if 'position' not in st.session_state: st.session_state['position'] = None
if 'history' not in st.session_state: st.session_state['history'] = []

TICKERS = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'XRP/USDT': 'XRP-USD', 'SOL/USDT': 'SOL-USD'}

@st.cache_data(ttl=5) # 5초마다 최신 데이터 캐싱
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

@st.cache_data(ttl=5)
def fetch_ohlcv(symbol, timeframe='1m', limit=100):
    yf_ticker = TICKERS[symbol]
    period = "5d" if timeframe == '1m' else "1mo"
    df = yf.Ticker(yf_ticker).history(period=period, interval=timeframe).tail(limit).reset_index()
    df = df.rename(columns={'Datetime': 'timestamp', 'Date': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    return df

def smart_bot_logic(df, position):
    """봇이 스스로 생각해서 매매 방향을 결정하는 핵심 알고리즘"""
    current_price = df['close'].iloc[-1]
    
    # 1. 오더블럭 (지지/저항선 탐색)
    support_ob = df['low'][-20:-5].min()
    resistance_ob = df['high'][-20:-5].max()
    
    # 2. 추세 판단 (지수이동평균선 EMA 9 vs 21)
    df['EMA9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
    uptrend = df['EMA9'].iloc[-1] > df['EMA21'].iloc[-1]
    downtrend = df['EMA9'].iloc[-1] < df['EMA21'].iloc[-1]
    
    # 3. 거래량 스파이크 확인
    vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
    vol_spike = df['volume'].iloc[-1] > vol_ma20 * 1.5
    
    signal = "HOLD"
    reasons = []

    # --- 포지션이 없을 때 (진입 고민) ---
    if position is None:
        if current_price <= support_ob * 1.002: # 지지선 근접
            reasons.append("✅ 지지 오더블럭 도달")
            if uptrend or vol_spike:
                reasons.append("✅ 상승 추세 및 스마트머니 유입 확인")
                signal = "LONG"
                
        elif current_price >= resistance_ob * 0.998: # 저항선 근접
            reasons.append("✅ 저항 오더블럭 도달")
            if downtrend or vol_spike:
                reasons.append("✅ 하락 추세 및 매도 압력 확인")
                signal = "SHORT"
        
        if signal == "HOLD":
            reasons.append("확실한 추세나 오더블럭 도달이 없어 관망합니다.")

    # --- 포지션이 있을 때 (청산 고민) ---
    else:
        entry_price = position['entry_price']
        profit_pct = (current_price - entry_price) / entry_price if position['type'] == 'Long' else (entry_price - current_price) / entry_price
        profit_pct *= 100
        
        reasons.append(f"현재 수익률: {profit_pct:.2f}%")
        
        if profit_pct >= 0.5: # 0.5% 이상 수익 시
            signal = "CLOSE"
            reasons.append("🎯 목표 수익권 도달 (익절 추천)")
        elif profit_pct <= -0.3: # -0.3% 이하 손실 시
            signal = "CLOSE"
            reasons.append("🛑 손절 라인 이탈 (리스크 관리 필요)")
        else:
            reasons.append("현재 포지션을 유지하며 추세를 지켜봅니다.")
            
    return signal, reasons, support_ob, resistance_ob

# --- 사이드바 ---
st.sidebar.header("⚙️ 봇 컨트롤 패널")
timeframe = st.sidebar.selectbox("타임프레임 선택", ["1m", "5m", "15m", "1h"], index=0)

# 실시간 갱신 스위치 (이게 켜져 있으면 5초마다 자동 새로고침)
auto_refresh = st.sidebar.toggle("🔄 실시간 갱신 모드 (5초 단위)", value=True)

st.sidebar.markdown("---")
st.sidebar.info("💡 **알고리즘 작동 방식:**\n\n봇이 오더블럭, EMA 추세, 거래량 폭발 여부를 실시간으로 계산하여 최적의 진입/청산 타이밍을 브리핑합니다.")

# --- 메인 대시보드 ---
col_bal, col_pos = st.columns(2)
col_bal.metric(label="💰 내 가상 지갑 잔고", value=f"$ {st.session_state['balance']:,.2f}")

if st.session_state['position']:
    pos = st.session_state['position']
    col_pos.metric(label=f"📈 현재 보유 포지션 ({pos['type']})", value=f"{pos['symbol']} (진입가: $ {pos['entry_price']:,.2f})")
else:
    col_pos.metric(label="📈 현재 보유 포지션", value="없음 (관망 중)")

st.markdown("---")

df_market = get_market_data()

if not df_market.empty:
    target_symbol = df_market.iloc[0]["종목"]
    df_ohlcv = fetch_ohlcv(target_symbol, timeframe)
    current_price = df_ohlcv['close'].iloc[-1]
    
    # 봇 알고리즘 호출
    signal, reasons, sup_ob, res_ob = smart_bot_logic(df_ohlcv, st.session_state['position'])
    
    st.subheader(f"🔥 타겟 종목: {target_symbol} (현재가: $ {current_price:,.2f})")
    
    col_ai, col_action, col_chart = st.columns([1.2, 1, 2.5])
    
    with col_ai:
        st.write("🧠 **봇의 실시간 분석 브리핑**")
        for r in reasons: 
            st.caption(f"- {r}")
            
        st.markdown("<br>", unsafe_allow_html=True)
        if signal == "LONG": st.success("🚀 **봇 추천: 롱(매수) 진입**")
        elif signal == "SHORT": st.error("☄️ **봇 추천: 숏(매도) 진입**")
        elif signal == "CLOSE": st.warning("⚠️ **봇 추천: 포지션 즉시 청산**")
        else: st.info("💤 **봇 추천: 관망 (Hold)**")
            
    with col_action:
        st.write("**🕹️ 수동 매매 조종석**")
        
        if st.session_state['position'] is None:
            if st.button("📈 롱(Buy) 진입", use_container_width=True):
                st.session_state['position'] = {'symbol': target_symbol, 'entry_price': current_price, 'type': 'Long'}
                st.session_state['history'].append({"시간": datetime.now().strftime("%H:%M:%S"), "종목": target_symbol, "구분": "롱 진입", "가격": current_price, "수익금": 0})
                st.rerun()
            
            if st.button("📉 숏(Sell) 진입", use_container_width=True):
                st.session_state['position'] = {'symbol': target_symbol, 'entry_price': current_price, 'type': 'Short'}
                st.session_state['history'].append({"시간": datetime.now().strftime("%H:%M:%S"), "종목": target_symbol, "구분": "숏 진입", "가격": current_price, "수익금": 0})
                st.rerun()
        else:
            pos = st.session_state['position']
            profit = (current_price - pos['entry_price']) if pos['type'] == 'Long' else (pos['entry_price'] - current_price)
            profit_pct = (profit / pos['entry_price']) * 100
            
            if profit >= 0: st.success(f"실시간 수익: +{profit_pct:.2f}% ($ {profit:.2f})")
            else: st.error(f"실시간 손실: {profit_pct:.2f}% ($ {profit:.2f})")
            
            if st.button("❌ 포지션 청산 (Close)", use_container_width=True, type="primary"):
                st.session_state['balance'] += profit 
                st.session_state['history'].append({"시간": datetime.now().strftime("%H:%M:%S"), "종목": pos['symbol'], "구분": f"{pos['type']} 청산", "가격": current_price, "수익금": round(profit, 2)})
                st.session_state['position'] = None 
                st.rerun()
            
    with col_chart:
        fig = go.Figure(data=[go.Candlestick(x=df_ohlcv['timestamp'], open=df_ohlcv['open'], high=df_ohlcv['high'], low=df_ohlcv['low'], close=df_ohlcv['close'])])
        # 차트 위에 봇이 찾은 지지/저항선 그려주기
        fig.add_hline(y=sup_ob, line_dash="dot", line_color="blue", annotation_text="Support OB")
        fig.add_hline(y=res_ob, line_dash="dot", line_color="red", annotation_text="Resistance OB")
        
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

# 실시간 갱신 로직 (사이드바의 토글이 켜져있으면 작동)
if auto_refresh:
    time.sleep(5) # 5초 대기 후
    st.rerun()    # 화면 전체 자동 새로고침 (수익률 실시간 반영)

st.markdown("---")
st.subheader("📝 모의투자 매매 일지")
if st.session_state['history']:
    st.dataframe(pd.DataFrame(st.session_state['history']).iloc[::-1], use_container_width=True)
