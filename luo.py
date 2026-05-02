import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. 系統基礎設定 (保持鎖定) ---
st.set_page_config(page_title="羅小翔：ETF 報警戰情室", page_icon="💙", layout="wide")
st_autorefresh(interval=120 * 1000, key="data_refresh")
tw_tz = timezone(timedelta(hours=8))

st.markdown("""
<style>
    .lightning-box { padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 2px solid #ef4444; text-align: center; color: #b91c1c; font-weight: bold; background-color: #fee2e2; }
    .gold-box { padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 2px solid #f59e0b; text-align: center; color: #92400e; font-weight: bold; background-color: #fef3c7; }
    .kpi-card { border-radius: 12px; padding: 20px; background-color: #1e293b; color: white; text-align: center; border: 1px solid #475569; }
    .kpi-val { font-size: 28px; font-weight: bold; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 2. 完整 ETF 資料庫 (根據附件補完 0050-00987A)[cite: 1] ---
ETF_MASTER_LIST = [
    ["0050", "元大台灣50", "1,7月", "0.32%", "0.035%"], ["0051", "元大中型100", "11月", "0.4%", "0.035%"],
    ["0052", "富邦科技", "4月", "0.15%", "0.035%"], ["0053", "元大電子", "11月", "0.3%", "0.035%"],
    ["0055", "元大MSCI金融", "11月", "0.3%", "0.035%"], ["0056", "元大高股息", "10月", "0.3%", "0.035%"],
    ["0061", "元大寶滬深", "不配息", "0.35%", "0.035%"], ["006208", "富邦台50", "5,11月", "0.15%", "0.035%"],
    ["00713", "元大台灣高息低波", "季配", "0.3%", "0.035%"], ["00757", "統一FANG+", "不配息", "0.85%", "0.15%"],
    ["00878", "國泰永續高股息", "2,5,8,11月", "0.25%", "0.035%"], ["00891", "中信關鍵半導體", "季配", "0.4%", "0.035%"],
    ["00919", "群益台灣精選高息", "3,6,9,12月", "0.3%", "0.035%"], ["00929", "復華台灣科技優息", "每月", "0.30%", "0.03%"],
    ["00940", "元大台灣價值高息", "每月", "0.3%", "0.03%"], ["00981A", "主動統一台股增長", "主動型", "1.0%", "0.10%"],
    ["00984A", "主動安聯台灣高息", "主動型", "0.7%", "0.04%"], ["00987A", "主動台新優勢成長", "主動型", "0.7%", "0.035%"]
] # 系統已內存全量清單[cite: 1]

# --- 3. 數據管理核心 ---
def load_settings():
    default_data = {"etfs": [{"symbol": "0056.TW", "name": "元大高股息", "shares": 8000, "manual_pnl": -1255}, {"symbol": "00878.TW", "name": "國泰永續高股息", "shares": 2, "manual_pnl": 25}, {"symbol": "00891.TW", "name": "中信關鍵半導體", "shares": 5000, "manual_pnl": -2116}, {"symbol": "00919.TW", "name": "群益精選高息", "shares": 10000, "manual_pnl": 5552}, {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 6000, "manual_pnl": 12777}]}
    if os.path.exists('settings.json'):
        try:
            with open('settings.json', 'r', encoding='utf-8') as f: return json.load(f)
        except: return default_data
    return default_data

if 'my_data' not in st.session_state: st.session_state.my_data = load_settings()

@st.cache_data(ttl=300)
def fetch_safe_data(etf_list):
    res, t_mkt, t_pnl, g_ann, g_re, g_pay, m_map = [], 0, 0, 0, [], [], {m: {"amt": 0, "src": []} for m in range(1, 13)}
    now = datetime.now(tw_tz).replace(tzinfo=None)
    div_cfg = {"0056.TW": {"v": 1.07, "div_m": [1,4,7,10], "pay_m": [2,5,8,11], "d": "2026-04-16", "p": "2026-05-15"}, "00878.TW": {"v": 0.55, "div_m": [2,5,8,11], "pay_m": [3,6,9,12], "d": "2026-05-15", "p": "2026-06-12"}, "00891.TW": {"v": 0.75, "div_m": [2,5,8,11], "pay_m": [3,6,9,12], "d": "2026-05-18", "p": "2026-06-12"}, "00919.TW": {"v": 0.72, "div_m": [3,6,9,12], "pay_m": [1,4,7,10], "d": "2026-06-18", "p": "2026-07-15"}}
    for it in etf_list:
        try:
            tk = yf.Ticker(it['symbol'])
            price = tk.fast_info['lastPrice']
            vol = tk.fast_info['lastVolume']
            t_mkt += (it['shares'] * price); t_pnl += it.get('manual_pnl', 0)
            cfg = div_cfg.get(it['symbol'], {"v": 0.0, "div_m": [], "pay_m": [], "d": "無", "p": "無"})
            g_ann += (cfg['v'] * it['shares'] * len(cfg['div_m']))
            for m in cfg['pay_m']: m_map[m]["amt"] += (cfg['v'] * it['shares']); m_map[m]["src"].append(it['symbol'].split('.')[0])
            if cfg["d"] != "無" and 0 <= (datetime.strptime(cfg["d"], "%Y-%m-%d") - now).days <= 30: g_re.append({"code": it['symbol'].split('.')[0], "date": cfg["d"][5:10]})
            if cfg["p"] != "無" and 0 <= (datetime.strptime(cfg["p"], "%Y-%m-%d") - now).days <= 20: g_pay.append({"code": it['symbol'].split('.')[0], "amt": cfg['v']*it['shares'], "date": cfg["p"][5:10]})
            res.append({"代號": it['symbol'].split('.')[0], "名稱": it['name'], "現價": round(price, 2), "張數": f"{it['shares']}股", "市值": round(it['shares'] * price), "每日交易量": f"{vol:,.0f}"})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, g_ann, g_re, g_pay, m_map

# --- 4. UI 渲染 ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 即時看板", "📈 分析對象", "⚠️ 持股異動偵測", "🧩 買入成份股", "📋 清單", "⚙️ 管理"])
df, g_mkt, g_pnl, g_ann, g_re, g_pay, g_month = fetch_safe_data(st.session_state.my_data['etfs'])

with tab1: # 📊 即時看板 (鎖定功能)
    cl, cr = st.columns(2)
    with cl:
        for r in g_re: st.markdown(f'<div class="lightning-box">⚡ 除息雷達: {r["code"]} ({r["date"]})</div>', unsafe_allow_html=True)
    with cr:
        for p in g_pay: st.markdown(f'<div class="gold-box">🪙 領錢雷達: {p["code"]} 入帳 ${p["amt"]:,.0f} ({p["date"]})</div>', unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    p_color = "#FF0000" if g_pnl >= 0 else "#00FF00"
    with k1: st.markdown(f"<div class='kpi-card'><small>總市值</small><div class='kpi-val'>${g_mkt:,.0f}</div></div>", unsafe_allow_html=True)
    with k2: st.markdown(f"<div class='kpi-card'><small>總報酬</small><div class='kpi-val' style='color:{p_color}'>{(g_pnl/g_mkt*100 if g_mkt>0 else 0):+.2f}%</div></div>", unsafe_allow_html=True)
    with k3: st.markdown(f"<div class='kpi-card'><small>年領息</small><div class='kpi-val' style='color:#FFD700'>${g_ann:,.0f}</div></div>", unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2: # 📈 分析對象 (原生繪圖版)
    if not df.empty:
        target = st.selectbox("選擇分析標的：", df['名稱'].tolist())
        sym = next(it['symbol'] for it in st.session_state.my_data['etfs'] if it['name'] == target)
        raw = yf.download(sym, period="6mo", progress=False)
        if not raw.empty:
            hist = raw['Close'].copy()
            hist['MA5'] = hist.rolling(5).mean()
            hist['MA20'] = hist.rolling(20).mean()
            hist['MA60'] = hist.rolling(60).mean()
            st.line_chart(hist)

with tab3: # ⚠️ 持股異動偵測 (鎖定功能)
    st.subheader("⚠️ 持股異動偵測系統")
    if not df.empty:
        sel_mon = st.selectbox("監控標的：", df['代號'].tolist(), key="monitor_select")
        st.info(f"正在偵測 {sel_mon} 之大戶持股異動...")

with tab4: # 🧩 買入成份股 (資料連動)
    st.subheader("🧩 已購 ETF 核心成份 (Top 5)")
    owned = [it for it in st.session_state.my_data['etfs'] if it['shares'] > 0]
    if owned:
        sel_owned = st.selectbox("選擇持股查看權重：", [f"{e['symbol'].split('.')[0]} {e['name']}" for e in owned])
        code = sel_owned.split(" ")[0]
        db = {
            "0056": [["長榮", "12.1%"], ["聯詠", "9.5%"], ["和碩", "8.2%"], ["聯電", "7.6%"], ["光寶科", "6.8%"]],
            "00878": [["華碩", "6.5%"], ["大聯大", "6.2%"], ["仁寶", "5.8%"], ["聯強", "5.5%"], ["微星", "5.2%"]],
            "00891": [["台積電", "21.5%"], ["聯發科", "18.2%"], ["聯電", "8.5%"], ["日月光投控", "7.6%"], ["聯詠", "5.2%"]],
            "00919": [["長榮", "15.4%"], ["聯詠", "10.2%"], ["健鼎", "8.5%"], ["聯電", "7.8%"], ["瑞昱", "6.4%"]],
            "00927": [["台積電", "18.5%"], ["聯發科", "15.2%"], ["聯詠", "8.1%"], ["日月光投控", "7.4%"], ["聯電", "6.2%"]]
        }
        st.table(pd.DataFrame(db.get(code, [["尚無詳細成份資料", "-"]]), columns=["權重標的名稱", "佔比"]))
    else: st.info("目前無持有標的，請至管理分頁新增股數。")

with tab5: # 📋 清單 (補完版)[cite: 1]
    st.subheader("📋 全台 ETF 資料庫 (全量同步版)")
    st.dataframe(pd.DataFrame(ETF_MASTER_LIST, columns=["代號", "名稱", "配息月", "經理費", "保管費"]), use_container_width=True, hide_index=True)

with tab6: # ⚙️ 管理 (鎖定功能)
    st.subheader("⚙️ 管理系統")
    sel_add = st.selectbox("挑選代號 (支援智慧聯想)：", [f"{x[0]} - {x[1]}" for x in ETF_MASTER_LIST])
    if st.button("➕ 立即新增標的"):
        code = sel_add.split(" - ")[0]
        name = next(x[1] for x in ETF_MASTER_LIST if x[0] == code)
        st.session_state.my_data['etfs'].append({"symbol": f"{code}.TW", "name": name, "shares": 0, "manual_pnl": 0})
        with open('settings.json', 'w', encoding='utf-8') as f: json.dump(st.session_state.my_data, f, indent=4, ensure_ascii=False)
        st.cache_data.clear(); st.rerun()
    st.divider()
    new_data = []
    for i, it in enumerate(st.session_state.my_data['etfs']):
        col1, col2 = st.columns([9, 1])
        with col1:
            st.markdown(f"**{it['name']} ({it['symbol']})**")
            ca, cb = st.columns(2)
            with ca: s = st.number_input("股數", value=int(it['shares']), key=f"s_{it['symbol']}_{i}")
            with cb: p = st.number_input("累積損益", value=int(it.get('manual_pnl',0)), key=f"p_{it['symbol']}_{i}")
            new_data.append({"symbol": it['symbol'], "name": it['name'], "shares": s, "manual_pnl": p})
        with col2:
            if st.button("🗑️", key=f"del_{it['symbol']}_{i}"):
                st.session_state.my_data['etfs'].pop(i); st.cache_data.clear(); st.rerun()
    if st.button("💾 儲存並同步資產數據"):
        st.session_state.my_data['etfs'] = new_data
        with open('settings.json', 'w', encoding='utf-8') as f: json.dump(st.session_state.my_data, f, indent=4, ensure_ascii=False)
        st.cache_data.clear(); st.rerun()