import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. 系統基礎與數據持久化 ---
st.set_page_config(page_title="羅小翔：ETF 報警戰情室", page_icon="💙", layout="wide")
st_autorefresh(interval=60 * 1000, key="data_refresh")
tw_tz = timezone(timedelta(hours=8))

def save_to_json(data):
    with open('settings.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_settings():
    # 嚴謹初始化資產狀態
    default_data = {
        "etfs": [
            {"symbol": "0056.TW", "name": "元大高股息", "shares": 8000, "manual_pnl": -1255, "upper": 0.0, "lower": 0.0},
            {"symbol": "00878.TW", "name": "國泰永續高股息", "shares": 2, "manual_pnl": 25, "upper": 0.0, "lower": 0.0},
            {"symbol": "00891.TW", "name": "中信關鍵半導體", "shares": 5000, "manual_pnl": -2116, "upper": 0.0, "lower": 0.0},
            {"symbol": "00919.TW", "name": "群益台灣精選高息", "shares": 10000, "manual_pnl": 5552, "upper": 0.0, "lower": 0.0},
            {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 6000, "manual_pnl": 12777, "upper": 0.0, "lower": 0.0}
        ]
    }
    if os.path.exists('settings.json'):
        try:
            with open('settings.json', 'r', encoding='utf-8') as f: return json.load(f)
        except: return default_data
    return default_data

if 'my_data' not in st.session_state: st.session_state.my_data = load_settings()

# --- 2. 標的資料庫 ---
ETF_DB = {
    "0050": {"name": "元大台灣50", "type": "被動"}, "0056": {"name": "元大高股息", "type": "被動"},
    "00878": {"name": "國泰永續高股息", "type": "被動"}, "00891": {"name": "中信關鍵半導體", "type": "被動"},
    "00919": {"name": "群益台灣精選高息", "type": "被動"}, "00927": {"name": "群益半導體收益", "type": "被動"},
    "00981A": {"name": "復華台灣成長高股息", "type": "被動"}, "00992A": {"name": "中信優息投資級債", "type": "被動"},
    "00999A": {"name": "元大主動成長", "type": "主動"}, "00998B": {"name": "群益主動精選", "type": "主動"}
}

# --- 3. 視覺樣式 ---
st.markdown("""
<style>
    @keyframes lightning { 0%, 100% { background-color: #fee2e2; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ef4444; } }
    @keyframes gold-flash { 0%, 100% { background-color: #fef3c7; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #f59e0b; } }
    .lightning-box { animation: lightning 3s infinite; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 2px solid #ef4444; text-align: center; color: #b91c1c; }
    .gold-box { animation: gold-flash 3s infinite; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 2px solid #f59e0b; text-align: center; color: #92400e; }
    .kpi-card { border-radius: 12px; padding: 20px; background-color: #1e293b; color: white; text-align: center; border: 1px solid #475569; }
    .kpi-val { font-size: 28px; font-weight: bold; margin-top: 5px; }
    .anomaly-box { border-radius: 10px; padding: 15px; background-color: #0f172a; border: 1px solid #334155; text-align: center; color: white; }
    .anomaly-num { font-size: 32px; font-weight: 900; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 4. 數據分析核心 ---
@st.cache_data(ttl=60)
def fetch_complete_integrated_data(etf_list):
    res, t_mkt, t_pnl, g_ann, g_re, g_pay = [], 0, 0, 0, [], []
    m_map = {m: {"amt": 0, "src": []} for m in range(1, 13)}
    now = datetime.now(tw_tz).replace(tzinfo=None)
    div_cfg = {
        "0056.TW": {"m": [1,4,7,10], "v": 1.07, "d": "2026-07-16", "p": "2026-05-15"},
        "00878.TW": {"m": [2,5,8,11], "v": 0.55, "d": "2026-05-15", "p": "2026-06-12"},
        "00891.TW": {"m": [2,5,8,11], "v": 0.75, "d": "2026-05-18", "p": "2026-06-12"},
        "00919.TW": {"m": [3,6,9,12], "v": 0.72, "d": "2026-06-18", "p": "2026-07-15"},
        "00927.TW": {"m": [1,4,7,10], "v": 0.94, "d": "2026-07-16", "p": "2026-05-15"}
    }
    for it in etf_list:
        try:
            tk = yf.Ticker(it['symbol']); price = tk.fast_info['lastPrice']
            t_mkt += (it['shares'] * price); t_pnl += it['manual_pnl']
            cfg = div_cfg.get(it['symbol'], {"m": [], "v": 0.0, "d": "無", "p": "無"})
            g_ann += (cfg['v'] * it['shares'] * len(cfg['m']))
            for m in cfg['m']:
                m_map[m]["amt"] += (cfg['v'] * it['shares']); m_map[m]["src"].append(it['symbol'].split('.')[0])
            if cfg["d"] != "無":
                d_dt = datetime.strptime(cfg["d"], "%Y-%m-%d")
                if 0 <= (d_dt - now).days <= 30: g_re.append({"code": it['symbol'].split('.')[0], "date": d_dt.strftime("%m/%d")})
            if cfg["p"] != "無":
                p_dt = datetime.strptime(cfg["p"], "%Y-%m-%d")
                if 0 <= (p_dt - now).days <= 14: g_pay.append({"code": it['symbol'].split('.')[0], "date": p_dt.strftime("%m/%d"), "amount": cfg['v']*it['shares']})
            res.append({"代號": it['symbol'].split('.')[0], "名稱": it['name'], "現價": round(price, 2), "殖利率": f"{(cfg['v']*len(cfg['m'])/price*100):.2f}%", "張數": f"{it['shares']}股" if it['shares']<1000 else f"{int(it['shares']/1000)}張", "累積損益": it['manual_pnl'], "市值": round(it['shares'] * price)})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, g_ann, g_re, g_pay, m_map

# --- 5. UI 渲染 ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 即時看板", "📈 技術分析", "⚠️ 持股異動", "⚙️ 系統管理"])
df, g_mkt, g_pnl, g_ann, g_re, g_pay, g_month = fetch_complete_integrated_data(st.session_state.my_data['etfs'])

with tab1:
    c_re, c_pay = st.columns(2)
    with c_re:
        for r in g_re: st.markdown(f'<div class="lightning-box"><b>⚡ 除息雷達</b><br>{r["code"]} 於 {r["date"]} 除息</div>', unsafe_allow_html=True)
    with c_pay:
        for p in g_pay: st.markdown(f'<div class="gold-box"><b>🪙 領息雷達</b><br>{p["code"]} ${p["amount"]:,.0f} 於 {p["date"]} 入帳</div>', unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    p_color = "#FF0000" if g_pnl >= 0 else "#00FF00"
    with k1: st.markdown(f"<div class='kpi-card'><small>股票總市值</small><div class='kpi-val'>${g_mkt:,.0f}</div></div>", unsafe_allow_html=True)
    with k2: st.markdown(f"<div class='kpi-card'><small>總報酬率</small><div class='kpi-val' style='color:{p_color}'>{(g_pnl/g_mkt*100 if g_mkt>0 else 0):+.2f}%</div></div>", unsafe_allow_html=True)
    with k3: st.markdown(f"<div class='kpi-card'><small>預估年領息</small><div class='kpi-val' style='color:#FFD700'>${g_ann:,.0f}</div></div>", unsafe_allow_html=True)
    st.divider()
    st.subheader("📅 每月預估領息明細")
    m_cols = st.columns(6)
    for m in range(1, 13):
        with m_cols[(m-1)%6]:
            st.metric(f"{m}月", f"${g_month[m]['amt']:,.0f}")
            st.caption(f"來源: {', '.join(g_month[m]['src']) if g_month[m]['src'] else '無'}")
    st.divider()
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    if not df.empty:
        target = st.selectbox("分析標的：", df['名稱'].tolist())
        sym = next(it['symbol'] for it in st.session_state.my_data['etfs'] if it['name'] == target)
        raw = yf.download(sym, period="1y", interval="1d", progress=False)
        if not raw.empty:
            c = raw['Close'].squeeze()
            ma5, ma20, ma60 = c.rolling(5).mean(), c.rolling(20).mean(), c.rolling(60).mean()
            fig = go.Figure(data=[go.Candlestick(x=raw.index, open=raw['Open'].squeeze(), high=raw['High'].squeeze(), low=raw['Low'].squeeze(), close=c, name="K線")])
            fig.add_trace(go.Scatter(x=raw.index, y=ma5, line=dict(color='yellow', width=1), name='MA5'))
            fig.add_trace(go.Scatter(x=raw.index, y=ma20, line=dict(color='orange', width=1), name='MA20'))
            fig.add_trace(go.Scatter(x=raw.index, y=ma60, line=dict(color='cyan', width=1), name='MA60'))
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("⚠️ 持股異動偵測")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.markdown('<div class="anomaly-box" style="color:#4ade80;">新增<div class="anomaly-num">0</div></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="anomaly-box" style="color:#f87171;">出清<div class="anomaly-num">0</div></div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="anomaly-box" style="color:#60a5fa;">加碼<div class="anomaly-num">5</div></div>', unsafe_allow_html=True)
    with c4: st.markdown('<div class="anomaly-box" style="color:#fbbf24;">減碼<div class="anomaly-num">31</div></div>', unsafe_allow_html=True)
    with c5: st.markdown('<div class="anomaly-box" style="color:#94a3b8;">不變<div class="anomaly-num">14</div></div>', unsafe_allow_html=True)

with tab4:
    st.subheader("⚙️ 標的管理系統")
    st.markdown("### ➕ 新增投資標的")
    labels = [f"[{v['type']}] {k} - {v['name']}" for k, v in ETF_DB.items()]
    selected = st.selectbox("挑選代號：", labels)
    s_code = selected.split("] ")[1].split(" -")[0]
    if st.button("➕ 立即新增標的", use_container_width=True):
        if not any(it['symbol'] == f"{s_code}.TW" for it in st.session_state.my_data['etfs']):
            st.session_state.my_data['etfs'].append({"symbol": f"{s_code}.TW", "name": ETF_DB[s_code]['name'], "shares": 0, "manual_pnl": 0, "upper": 0.0, "lower": 0.0})
            save_to_json(st.session_state.my_data); st.rerun()
    st.divider()
    st.markdown("### 📝 現有持股編輯")
    new_data, del_idx = [], -1
    for i, it in enumerate(st.session_state.my_data['etfs']):
        col_main, col_del = st.columns([9, 1])
        with col_main:
            st.markdown(f"**{it['name']} ({it['symbol']})**")
            ca, cb, cc, cd = st.columns(4)
            with ca: s = st.number_input("股數", value=int(it['shares']), key=f"s_{i}")
            with cb: p = st.number_input("累積損益", value=int(it['manual_pnl']), key=f"p_{i}")
            with cc: up = st.number_input("上限提醒", value=float(it.get('upper',0.0)), key=f"up_{i}")
            with cd: lo = st.number_input("下限提醒", value=float(it.get('lower',0.0)), key=f"lo_{i}")
            new_data.append({"symbol": it['symbol'], "name": it['name'], "shares": s, "manual_pnl": p, "upper": up, "lower": lo})
        with col_del:
            st.write("") # 間隔
            if st.button("🗑️", key=f"del_{i}"): del_idx = i
    
    if del_idx != -1:
        st.session_state.my_data['etfs'].pop(del_idx)
        save_to_json(st.session_state.my_data); st.rerun()
        
    if st.button("💾 儲存並同步數據", use_container_width=True):
        st.session_state.my_data['etfs'] = new_data
        save_to_json(st.session_state.my_data); st.rerun()