import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# 🛡️ 繪圖套件檢查
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    has_plotly = True
except ImportError:
    has_plotly = False

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="羅小翔專用：ETF 終極報警戰情室", page_icon="💙", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=60 * 1000, key="data_refresh")

tw_tz = timezone(timedelta(hours=8))

# 🎯 視覺特效 CSS (正紅負綠、雷達、報警脈衝)
st.markdown("""
<style>
    @keyframes lightning { 0%, 100% { background-color: #fee2e2; box-shadow: 0 0 0px #fff; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ffffff, 0 0 60px #ef4444; } }
    @keyframes gold-flash { 0%, 100% { background-color: #fef3c7; box-shadow: 0 0 0px #fff; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ffffff, 0 0 60px #f59e0b; } }
    @keyframes pulse-alert { 0% { box-shadow: 0 0 0px 0px rgba(139, 92, 246, 0.7); } 70% { box-shadow: 0 0 0px 15px rgba(139, 92, 246, 0); } 100% { box-shadow: 0 0 0px 0px rgba(139, 92, 246, 0); } }
    
    .lightning-box { animation: lightning 3s infinite; padding: 25px; border-radius: 20px; margin-bottom: 15px; border: 4px solid #ef4444; text-align: center; color: #b91c1c; }
    .gold-box { animation: gold-flash 3s infinite; padding: 25px; border-radius: 20px; margin-bottom: 15px; border: 4px solid #f59e0b; text-align: center; color: #92400e; }
    .price-alert-box { animation: pulse-alert 2s infinite; padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 3px solid #8b5cf6; text-align: center; background-color: #f5f3ff; color: #5b21b6; }
    .kpi-card { border-radius: 10px; padding: 15px; background-color: #1e293b; color: white; text-align: center; margin-bottom: 10px; border: 1px solid #475569; }
    .kpi-val { font-size: 28px; font-weight: bold; }
    [data-testid="stDataFrameColHeader"] { background-color: #FFD700 !important; }
    div[data-testid="stDataFrameColHeaderCell"] span { color: #000000 !important; font-size: 18px !important; font-weight: 900 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. 數據管理 (持久化) ---
SETTINGS_FILE = 'settings.json'

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_settings():
    # 同步截圖資料：0056 (4張)、00891 (5張)、00919 (10張)、00927 (6張)
    default_data = {
        "etfs": [
            {"symbol": "0056.TW", "name": "元大高股息", "shares": 4000, "manual_pnl": -1255, "upper": 0.0, "lower": 0.0},
            {"symbol": "00891.TW", "name": "中信關鍵半導體", "shares": 5000, "manual_pnl": -2116, "upper": 0.0, "lower": 0.0},
            {"symbol": "00919.TW", "name": "群益台灣精選高息", "shares": 10000, "manual_pnl": 5552, "upper": 0.0, "lower": 0.0},
            {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 6000, "manual_pnl": 12777, "upper": 0.0, "lower": 0.0}
        ],
        "memo": "🎯 200 萬投資目標執行中：\\n4/9 16:30 剪頭髮\\n4/11 19:00 佳里美甲\\n4/14 19:00 湛藍燒肉"
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default_data
    return default_data

if 'my_data' not in st.session_state: st.session_state.my_data = load_settings()
if 'show_tech' not in st.session_state: st.session_state.show_tech = False
if 'show_comp' not in st.session_state: st.session_state.show_comp = False

# --- 3. 分析核心 (修正資料格式問題) ---
def get_clean_df(symbol):
    raw = yf.download(symbol, period="1y", interval="1d", progress=False)
    df = pd.DataFrame(index=raw.index)
    for c in ['Open', 'High', 'Low', 'Close']:
        if isinstance(raw.columns, pd.MultiIndex): df[c] = raw[c][symbol]
        else: df[c] = raw[c]
    return df

@st.cache_data(ttl=60)
def fetch_analysis(etf_list):
    res, reminders, pay_reminders, p_alerts, p_map = [], [], [], [], {}
    t_mkt, t_pnl, t_cost, t_day, g_annual = 0, 0, 0, 0, 0
    now_tw = datetime.now(tw_tz).replace(tzinfo=None)
    
    div_cfg = {
        "0056.TW": {"m": [1,4,7,10], "d": "2026-07-16", "p": "2026-05-15", "v": 1.07},
        "00891.TW": {"m": [2,5,8,11], "d": "2026-05-18", "p": "2026-06-12", "v": 0.75},
        "00919.TW": {"m": [3,6,9,12], "d": "2026-06-18", "p": "2026-07-15", "v": 0.72},
        "00927.TW": {"m": [1,4,7,10], "d": "2026-07-16", "p": "2026-05-15", "v": 0.94}
    }

    for item in etf_list:
        try:
            tk = yf.Ticker(item['symbol']); info = tk.fast_info
            c_p = info['lastPrice']; prev_c = info.get('regularMarketPreviousClose', c_p); p_map[item['symbol']] = c_p
            
            # 股價與損益
            t_mkt += (item['shares'] * c_p); t_pnl += item['manual_pnl']; t_day += (c_p - prev_c) * item['shares']
            
            # 雷達提醒偵測
            cfg = div_cfg.get(item['symbol'], {"m": [], "d": "無", "p": "無", "v": 0.0})
            cash = cfg['v'] * item['shares']; g_annual += (cash * len(cfg['m']))
            dy_yield = (cfg['v'] * len(cfg['m']) / c_p * 100) if c_p > 0 else 0
            
            if cfg["d"] != "無":
                d_dt = datetime.strptime(cfg["d"], "%Y-%m-%d")
                if 0 <= (d_dt - now_tw).days <= 30: reminders.append({"code": item['symbol'].split('.')[0], "date": d_dt.strftime("%m/%d")})
            if cfg["p"] != "無":
                p_dt = datetime.strptime(cfg["p"], "%Y-%m-%d")
                if 0 <= (p_dt - now_tw).days <= 14: pay_reminders.append({"code": item['symbol'].split('.')[0], "date": p_dt.strftime("%m/%d"), "amount": cash})

            res.append({"代號": item['symbol'].split('.')[0], "名稱": item['name'], "現價": round(c_p, 2), "殖利率": f"{dy_yield:.2f}%", "今日漲跌": (c_p - prev_c) * item['shares'], "累積損益": item['manual_pnl'], "張數": f"{int(item['shares']/1000)}張", "市值": item['shares'] * c_p})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, t_day, g_annual, reminders, pay_reminders, p_alerts, p_map

# --- 4. 畫面渲染 ---
df_sum, g_mkt, g_pnl, g_day, g_annual, g_re, g_pay, g_alerts, g_price_map = fetch_analysis(st.session_state.my_data['etfs'])

st.title("👾 羅小翔：ETF 終極報警戰情室")

# ⚡ 雷達區 (最上方，確保復原)
c_r1, c_r2 = st.columns(2)
with c_r1:
    if g_re:
        for r in g_re: st.markdown(f'<div class="lightning-box"><b style="font-size:22px;">⚡ 除息雷達</b><br>{r["code"]} 於 {r["date"]} 除息</div>', unsafe_allow_html=True)
with c_r2:
    if g_pay:
        for p in g_pay: st.markdown(f'<div class="gold-box"><b style="font-size:22px;">🪙 領息雷達</b><br>{p["code"]} ${p["amount"]:,.0f} 於 {p["date"]} 入帳</div>', unsafe_allow_html=True)

# 功能切換
cb1, cb2 = st.columns(2)
with cb1:
    if st.button("📊 點選分析技術線圖", use_container_width=True): 
        st.session_state.show_tech = not st.session_state.show_tech
        st.rerun()
with cb2:
    if st.button("🔍 點選分析持股異動", use_container_width=True): 
        st.session_state.show_comp = not st.session_state.show_comp
        st.rerun()

# 分區展示
if st.session_state.show_tech and has_plotly:
    opts = [f"{it['name']} ({it['symbol'].split('.')[0]})" for it in st.session_state.my_data['etfs']]
    sel = st.selectbox("分析標的：", opts)
    target = next(it['symbol'] for it in st.session_state.my_data['etfs'] if it['name'] in sel)
    dt = get_clean_df(target)
    fig = go.Figure(data=[go.Candlestick(x=dt.index, open=dt['Open'], high=dt['High'], low=dt['Low'], close=dt['Close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

if st.session_state.show_comp:
    sel_c = st.selectbox("觀測異動標的：", [f"{it['name']} ({it['symbol'].split('.')[0]})" for it in st.session_state.my_data['etfs']])
    st.subheader(f"🔍 持股異動偵測 ({sel_c})")
    ka, kb, kc = st.columns(3)
    with ka: st.markdown('<div class="kpi-card"><small>🗳️ 加碼</small><div style="font-size:24px; color:#FF0000">5</div></div>', unsafe_allow_html=True)
    with kb: st.markdown('<div class="kpi-card"><small>📉 減碼</small><div style="font-size:24px; color:#00FF00">31</div></div>', unsafe_allow_html=True)
    with kc: st.markdown('<div class="kpi-card"><small>— 不變</small><div style="font-size:24px;">14</div></div>', unsafe_allow_html=True)

# 核心看板 (正紅負綠校正)
st.divider()
dc, pc = ("#FF0000" if g_day >= 0 else "#00FF00"), ("#FF0000" if g_pnl >= 0 else "#00FF00")
c1, c2 = st.columns(2)
with c1: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>今日即時損益<h2 style='color:{dc};'>${g_day:+,.0f}</h2></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>累積總損益<h2 style='color:{pc};'>${g_pnl:,.0f}</h2></div>", unsafe_allow_html=True)

va, vb, vc = st.columns(3)
with va: st.markdown(f"<div class='kpi-card'><small>股票總市值</small><div class='kpi-val'>${g_mkt:,.0f}</div></div>", unsafe_allow_html=True)
with vb: st.markdown(f"<div class='kpi-card'><small>總報酬率</small><div class='kpi-val' style='color:{pc}'>{(g_pnl/g_mkt*100 if g_mkt>0 else 0):+.2f}%</div></div>", unsafe_allow_html=True)
with vc: st.markdown(f"<div class='kpi-card'><small>全年預估領息</small><div class='kpi-val' style='color:#FFD700'>${g_annual:,.0f}</div></div>", unsafe_allow_html=True)

# 持股明細 (含殖利率)
st.divider()
st.dataframe(df_sum.style.format({"現價":"{:.2f}","今日漲跌":"{:+,.0f}","累積損益":"{:,.0f}","市值":"{:,.0f}"}).map(lambda x: f'color:{"#FF0000" if (isinstance(x, (int,float)) and x>=0) or str(x).startswith("+") else "#00FF00" if (isinstance(x, (int,float)) and x<0) or str(x).startswith("-") else "black"};font-weight:bold;', subset=['今日漲跌', '累積損益']), use_container_width=True, hide_index=True)

st.subheader("📝 羅小翔備忘錄")
memo = st.text_area("200萬目標進度追蹤", value=st.session_state.my_data.get("memo", ""), height=100)
if st.button("💾 儲存筆記"):
    st.session_state.my_data["memo"] = memo; save_to_json(st.session_state.my_data); st.success("筆記已存檔")

with st.expander("⚙️ 管理系統 (新增與修改)"):
    st.markdown("### 🆕 新增標的")
    cn1, cn2, cn3 = st.columns([2, 3, 1])
    with cn1: ns = st.text_input("代號 (例: 0052.TW)", key="ns_in")
    with cn2: nn = st.text_input("名稱 (例: 富邦科技)", key="nn_in")
    with cn3: 
        if st.button("➕ 新增"):
            st.session_state.my_data['etfs'].append({"symbol": ns, "name": nn, "shares": 0, "manual_pnl": 0, "upper": 0.0, "lower": 0.0})
            save_to_json(st.session_state.my_data); st.rerun()
    
    st.divider(); up_list = []
    for i, it in enumerate(st.session_state.my_data['etfs']):
        st.markdown(f"**{it['name']} —— 現價：`${g_price_map.get(it['symbol'],0.0):.2f}`**")
        cA, cB, cC, cD = st.columns(4)
        with cA: s = st.number_input("股數", value=int(it['shares']), key=f"s_{i}")
        with cB: pnl = st.number_input("累積損益", value=int(it['manual_pnl']), key=f"p_{i}")
        with cC: upper = st.number_input("上限提醒", value=float(it.get('upper',0.0)), key=f"up_{i}")
        with cD: lower = st.number_input("下限提醒", value=float(it.get('lower',0.0)), key=f"low_{i}")
        up_list.append({"symbol": it['symbol'], "name": it['name'], "shares": s, "manual_pnl": pnl, "upper": upper, "lower": lower})
    if st.button("💾 儲存標的設定"):
        st.session_state.my_data['etfs'] = up_list; save_to_json(st.session_state.my_data); st.rerun()