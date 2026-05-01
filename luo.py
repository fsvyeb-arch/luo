import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="ETF 領息戰情室", layout="wide")

# 手機端建議刷新頻率不要太高，設為 15-30 秒以節省流量
st_autorefresh(interval=15 * 1000, key="data_refresh")

# --- 2. 核心數據規則 ---
SETTINGS_FILE = 'settings.json'

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_settings():
    default_data = {
        "etfs": [
            {"symbol": "0056.TW", "name": "元大高股息", "shares": 4100, "cost": 41.11, "manual_pnl": -1255},
            {"symbol": "00891.TW", "name": "中信關鍵半導體", "shares": 5000, "cost": 31.30, "manual_pnl": -2116},
            {"symbol": "00919.TW", "name": "群益台灣精選高息", "shares": 10000, "cost": 23.04, "manual_pnl": 5552},
            {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 6000, "cost": 27.63, "manual_pnl": 12777}
        ]
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return default_data
    return default_data

if 'my_data' not in st.session_state:
    st.session_state.my_data = load_settings()

# --- 3. 側邊欄：手機修改數據區 ---
st.sidebar.header("⚙️ 資產管理")
updated_list = []
for i, item in enumerate(st.session_state.my_data.get('etfs', [])):
    with st.sidebar.expander(f"📍 {item['name']}"):
        s = st.number_input("股數", value=int(item['shares']), key=f"s_{i}")
        c = st.number_input("成本", value=float(item['cost']), key=f"c_{i}")
        p = st.number_input("損益修正", value=int(item['manual_pnl']), key=f"p_{i}")
        updated_list.append({"symbol": item['symbol'], "name": item['name'], "shares": s, "cost": c, "manual_pnl": p})

if st.sidebar.button("💾 儲存修改"):
    st.session_state.my_data['etfs'] = updated_list
    save_to_json(st.session_state.my_data)
    st.rerun()

# --- 4. 計算核心 ---
@st.cache_data(ttl=15)
def fetch_analysis(etf_list):
    if not etf_list: return pd.DataFrame(), 0, 0, 0, {}
    res = []
    t_mkt, t_pnl, t_cost = 0, 0, 0
    m_stats = {f"{m}月": 0 for m in range(1, 13)}
    
    # 領息月規則
    logic = {"0056.TW": [2,5,8,11], "00891.TW": [3,6,9,12], "00919.TW": [1,4,7,10], "00927.TW": [2,5,8,11]}
    
    for item in etf_list:
        try:
            tk = yf.Ticker(item['symbol'])
            curr_p = tk.fast_info['lastPrice']
            
            # 00891 修正 0.75
            actions = tk.actions.tail(5)
            div = actions['Dividends'].max() if not actions.empty else 0.0
            if item['symbol'] == "00891.TW" and div < 0.75: div = 0.75
            
            cash = div * item['shares']
            for m in logic.get(item['symbol'], []): m_stats[f"{m}月"] += cash
            
            t_mkt += (item['shares'] * curr_p)
            t_pnl += item['manual_pnl']
            t_cost += (item['shares'] * item['cost'])
            
            res.append({"名稱": item['name'], "現價": curr_p, "損益": item['manual_pnl'], "月領月份": logic.get(item['symbol'], [])})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, t_cost, m_stats

df, g_mkt, g_pnl, g_cost, g_months = fetch_analysis(st.session_state.my_data['etfs'])

# --- 5. 手機版視覺優化 ---
st.title("📱 ETF 隨身戰情室")

# 手機端使用 Column 容易擁擠，改用直列式大指標
p_col = "#FF0000" if g_pnl >= 0 else "#008000"
roi = (g_pnl / g_cost * 100) if g_cost != 0 else 0

st.markdown(f"""
    <div style='background-color:#f0f2f6; padding:15px; border-radius:15px; text-align:center;'>
        <p style='margin:0; color:#666;'>未實現總損益</p>
        <h1 style='margin:0; color:{p_col}; font-size:50px;'>${g_pnl:,.0f}</h1>
        <p style='margin:0; font-weight:bold; color:{p_col}; font-size:20px;'>{roi:+.2f}%</p>
    </div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.metric("總投資成本", f"${g_cost:,.0f}")
with col2:
    st.metric("當前總市值", f"${g_mkt:,.0f}")

st.divider()

# 月領金額改用更適合手機閱讀的清單
st.subheader("🗓️ 近期預估領息金額")
# 找出有錢領的月份顯示即可
for m_name, val in g_months.items():
    if val > 0:
        st.write(f"**{m_name}**： :green[+${val:,.0f}]")

st.divider()
st.caption(f"最後更新：{datetime.now().strftime('%H:%M:%S')}")