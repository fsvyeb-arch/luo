import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. 基礎設定 ---
st.set_page_config(page_title="羅小翔：ETF 報警戰情室", page_icon="💙", layout="wide")
st_autorefresh(interval=60 * 1000, key="data_refresh")
tw_tz = timezone(timedelta(hours=8))

# 🎯 視覺特效 CSS
st.markdown("""
<style>
    @keyframes lightning { 0%, 100% { background-color: #fee2e2; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ef4444; } }
    @keyframes gold-flash { 0%, 100% { background-color: #fef3c7; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #f59e0b; } }
    .lightning-box { animation: lightning 3s infinite; padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 3px solid #ef4444; text-align: center; color: #b91c1c; }
    .gold-box { animation: gold-flash 3s infinite; padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 3px solid #f59e0b; text-align: center; color: #92400e; }
    .kpi-card { border-radius: 10px; padding: 15px; background-color: #1e293b; color: white; text-align: center; margin-bottom: 10px; border: 1px solid #475569; }
</style>
""", unsafe_allow_html=True)

# --- 2. 標的分類資料庫 ---
ETF_DB = {
    "0050": {"name": "元大台灣50", "type": "被動"},
    "0052": {"name": "富邦科技", "type": "被動"},
    "0056": {"name": "元大高股息", "type": "被動"},
    "00878": {"name": "國泰永續高股息", "type": "被動"},
    "00891": {"name": "中信關鍵半導體", "type": "被動"},
    "00919": {"name": "群益台灣精選高息", "type": "被動"},
    "00927": {"name": "群益半導體收益", "type": "被動"},
    "00929": {"name": "復華台灣科技優息", "type": "被動"},
    "00999A": {"name": "元大主動成長", "type": "主動"},
    "00998B": {"name": "群益主動精選", "type": "主動"}
}

# --- 3. 數據持久化 ---
SETTINGS_FILE = 'settings.json'

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_settings():
    default_data = {
        "etfs": [
            {"symbol": "0056.TW", "name": "元大高股息", "shares": 8000, "manual_pnl": -1255, "upper": 0.0, "lower": 0.0},
            {"symbol": "00891.TW", "name": "中信關鍵半導體", "shares": 5000, "manual_pnl": -2116, "upper": 0.0, "lower": 0.0},
            {"symbol": "00919.TW", "name": "群益台灣精選高息", "shares": 10000, "manual_pnl": 5552, "upper": 0.0, "lower": 0.0},
            {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 6000, "manual_pnl": 12777, "upper": 0.0, "lower": 0.0}
        ],
        "memo": "🎯 200 萬投資目標執行中"
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default_data
    return default_data

if 'my_data' not in st.session_state: st.session_state.my_data = load_settings()

# --- 4. 分析核心 ---
@st.cache_data(ttl=60)
def fetch_analysis(etf_list):
    res, reminders, pay_reminders, t_mkt, t_pnl, t_day, g_annual = [], [], [], 0, 0, 0, 0
    monthly_data = {m: {"amount": 0, "sources": []} for m in range(1, 13)}
    now_tw = datetime.now(tw_tz).replace(tzinfo=None)
    div_cfg = {
        "0056.TW": {"m": [1,4,7,10], "d": "2026-07-16", "p": "2026-05-15", "v": 1.07},
        "00891.TW": {"m": [2,5,8,11], "d": "2026-05-18", "p": "2026-06-12", "v": 0.75},
        "00919.TW": {"m": [3,6,9,12], "d": "2026-06-18", "p": "2026-07-15", "v": 0.72},
        "00927.TW": {"m": [1,4,7,10], "d": "2026-07-16", "p": "2026-05-15", "v": 0.94}
    }
    for it in etf_list:
        try:
            tk = yf.Ticker(it['symbol']); info = tk.fast_info
            c_p = info['lastPrice']; prev_c = info.get('regularMarketPreviousClose', c_p)
            t_mkt += (it['shares'] * c_p); t_pnl += it['manual_pnl']; t_day += (c_p - prev_c) * it['shares']
            cfg = div_cfg.get(it['symbol'], {"m": [], "d": "無", "p": "無", "v": 0.0})
            dy_yield = (cfg['v'] * len(cfg['m']) / c_p * 100) if c_p > 0 else 0
            g_annual += (cfg['v'] * it['shares'] * len(cfg['m']))
            for month in cfg['m']:
                monthly_data[month]["amount"] += (cfg['v'] * it['shares'])
                monthly_data[month]["sources"].append(it['symbol'].split('.')[0])
            if cfg["d"] != "無":
                d_dt = datetime.strptime(cfg["d"], "%Y-%m-%d")
                if 0 <= (d_dt - now_tw).days <= 30: reminders.append({"code": it['symbol'].split('.')[0], "date": d_dt.strftime("%m/%d")})
            if cfg["p"] != "無":
                p_dt = datetime.strptime(cfg["p"], "%Y-%m-%d")
                if 0 <= (p_dt - now_tw).days <= 14: pay_reminders.append({"code": it['symbol'].split('.')[0], "date": p_dt.strftime("%m/%d"), "amount": cfg['v']*it['shares']})
            res.append({"代號": it['symbol'].split('.')[0], "名稱": it['name'], "現價": round(c_p, 2), "今日漲跌": (c_p - prev_c) * it['shares'], "累積損益": it['manual_pnl'], "張數": f"{int(it['shares']/1000)}張", "市值": it['shares'] * c_p})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, t_day, g_annual, reminders, pay_reminders, monthly_data

# --- 5. UI 渲染 ---
st.title("👾 羅小翔：ETF 報警戰情室")
tab1, tab2, tab3 = st.tabs(["📊 即時看板", "📈 技術分析", "⚙️ 系統管理"])

df_sum, g_mkt, g_pnl, g_day, g_annual, g_re, g_pay, g_month_data = fetch_analysis(st.session_state.my_data['etfs'])

with tab1:
    cr1, cr2 = st.columns(2)
    with cr1:
        if g_re:
            for r in g_re: st.markdown(f'<div class="lightning-box"><b style="font-size:20px;">⚡ 除息雷達</b><br>{r["code"]} 於 {r["date"]} 除息</div>', unsafe_allow_html=True)
    with cr2:
        if g_pay:
            for p in g_pay: st.markdown(f'<div class="gold-box"><b style="font-size:20px;">🪙 領息雷達</b><br>{p["code"]} ${p["amount"]:,.0f} 於 {p["date"]} 入帳</div>', unsafe_allow_html=True)
    dc, pc = ("#FF0000" if g_day >= 0 else "#00FF00"), ("#FF0000" if g_pnl >= 0 else "#00FF00")
    k1, k2 = st.columns(2)
    with k1: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>今日損益<h2 style='color:{dc};'>${g_day:+,.0f}</h2></div>", unsafe_allow_html=True)
    with k2: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>總報酬額<h2 style='color:{pc};'>${g_pnl:,.0f}</h2></div>", unsafe_allow_html=True)
    st.divider()
    st.subheader("📅 每月預估領息來源明細")
    m_cols = st.columns(6)
    for m in range(1, 13):
        with m_cols[(m-1)%6]:
            st.metric(f"{m}月", f"${g_month_data[m]['amount']:,.0f}")
            st.caption(f"來源: {', '.join(g_month_data[m]['sources']) if g_month_data[m]['sources'] else '無'}")
    st.divider()
    st.dataframe(df_sum.style.format({"現價":"{:.2f}","今日漲跌":"{:+,.0f}","累積損益":"{:,.0f}","市值":"{:,.0f}"}).map(lambda x: f'color:{"#FF0000" if (isinstance(x, (int,float)) and x>=0) or str(x).startswith("+") else "#00FF00" if (isinstance(x, (int,float)) and x<0) or str(x).startswith("-") else "black"};font-weight:bold;', subset=['今日漲跌', '累積損益']), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📈 K線技術分析展示 (均價線 MA)")
    if not df_sum.empty:
        target = st.selectbox("請選擇分析標的：", df_sum['名稱'].tolist())
        sym = next(it['symbol'] for it in st.session_state.my_data['etfs'] if it['name'] == target)
        raw = yf.download(sym, period="1y", interval="1d", progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            close_d, open_d, high_d, low_d = raw['Close'][sym], raw['Open'][sym], raw['High'][sym], raw['Low'][sym]
        else:
            close_d, open_d, high_d, low_d = raw['Close'], raw['Open'], raw['High'], raw['Low']
        
        # 追加均價線數據
        ma5 = close_d.rolling(window=5).mean()
        ma20 = close_d.rolling(window=20).mean()
        ma60 = close_d.rolling(window=60).mean()
        
        fig = go.Figure(data=[go.Candlestick(x=raw.index, open=open_d, high=high_d, low=low_d, close=close_d, name="K線")])
        fig.add_trace(go.Scatter(x=raw.index, y=ma5, line=dict(color='yellow', width=1), name='MA5'))
        fig.add_trace(go.Scatter(x=raw.index, y=ma20, line=dict(color='orange', width=1), name='MA20'))
        fig.add_trace(go.Scatter(x=raw.index, y=ma60, line=dict(color='cyan', width=1), name='MA60'))
        
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("⚙️ 標的管理系統 (含上下限監控)")
    option_labels = [f"[{v['type']}] {k} - {v['name']}" for k, v in ETF_DB.items()]
    selected_label = st.selectbox("挑選新標的：", option_labels)
    s_code = selected_label.split("] ")[1].split(" -")[0]
    if st.button("➕ 新增至持股清單"):
        if not any(it['symbol'] == f"{s_code}.TW" for it in st.session_state.my_data['etfs']):
            st.session_state.my_data['etfs'].append({"symbol": f"{s_code}.TW", "name": ETF_DB[s_code]['name'], "shares": 0, "manual_pnl": 0, "upper": 0.0, "lower": 0.0})
            save_to_json(st.session_state.my_data); st.rerun()
    st.divider(); up_list, del_idx = [], -1
    for i, it in enumerate(st.session_state.my_data['etfs']):
        st.markdown(f"**{it['name']} ({it['symbol']})**")
        cA, cB, cC, cD, cE = st.columns([2, 2, 2, 2, 1])
        with cA: s = st.number_input("股數", value=int(it['shares']), key=f"s_{i}")
        with cB: p = st.number_input("累積損益", value=int(it['manual_pnl']), key=f"p_{i}")
        with cC: upper = st.number_input("上限提醒", value=float(it.get('upper', 0.0)), key=f"up_{i}")
        with cD: lower = st.number_input("下限提醒", value=float(it.get('lower', 0.0)), key=f"low_{i}")
        with cE: 
            if st.button("🗑️", key=f"del_{i}"): del_idx = i
        up_list.append({"symbol": it['symbol'], "name": it['name'], "shares": s, "manual_pnl": p, "upper": upper, "lower": lower})
    if del_idx != -1:
        st.session_state.my_data['etfs'].pop(del_idx); save_to_json(st.session_state.my_data); st.rerun()
    if st.button("💾 儲存並同步數據", use_container_width=True):
        st.session_state.my_data['etfs'] = up_list; save_to_json(st.session_state.my_data); st.success("設定同步成功！"); st.rerun()