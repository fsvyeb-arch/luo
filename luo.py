import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="羅小翔專用：ETF 終極戰情室", page_icon="💙", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=15 * 1000, key="data_refresh")

tw_tz = timezone(timedelta(hours=8))

# 🎯 視覺特效 CSS 注入
st.markdown("""
<style>
    /* ⚡ 除息提醒：紅色閃電 */
    @keyframes lightning { 0%, 100% { background-color: #fee2e2; box-shadow: 0 0 0px #fff; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ffffff, 0 0 60px #ef4444; } 15% { background-color: #ffffff; box-shadow: 0 0 40px #ffffff, 0 0 80px #ef4444; } }
    /* 🪙 領息提醒：金光閃爍 */
    @keyframes gold-flash { 0%, 100% { background-color: #fef3c7; box-shadow: 0 0 0px #fff; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ffffff, 0 0 60px #f59e0b; } 15% { background-color: #ffffff; box-shadow: 0 0 40px #ffffff, 0 0 80px #f59e0b; } }
    
    .lightning-box { animation: lightning 3s infinite; padding: 25px; border-radius: 20px; margin-bottom: 15px; border: 4px solid #ef4444; text-align: center; color: #b91c1c; }
    .gold-box { animation: gold-flash 3s infinite; padding: 25px; border-radius: 20px; margin-bottom: 15px; border: 4px solid #f59e0b; text-align: center; color: #92400e; }
    
    /* 🟡 表格標頭：黃金背景、黑色加大字體 */
    [data-testid="stDataFrameColHeader"] { background-color: #FFD700 !important; }
    div[data-testid="stDataFrameColHeaderCell"] span { color: #000000 !important; font-size: 22px !important; font-weight: 900 !important; }
    
    /* 🔵 月份標題：深藍色字體 */
    .month-blue-title { color: #0056b3 !important; font-weight: bold; font-size: 20px; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 2. 數據管理 (含中文名稱映射) ---
SETTINGS_FILE = 'settings.json'
NAME_MAP = {
    "0056.TW": "元大高股息", "00878.TW": "國泰永續高股息", 
    "00919.TW": "群益台灣精選高息", "00927.TW": "群益半導體收益",
    "00891.TW": "中信臺灣智慧50", "00981A.TW": "統一台灣高息優選"
}

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_settings():
    # 預設持股：0056 (8張), 00927 (6張)
    default_data = {"etfs": [
        {"symbol": "0056.TW", "name": "元大高股息", "shares": 8000, "manual_pnl": 0},
        {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 6000, "manual_pnl": 0},
        {"symbol": "00878.TW", "name": "國泰永續高股息", "shares": 10000, "manual_pnl": 0},
        {"symbol": "00919.TW", "name": "群益台灣精選高息", "shares": 10000, "manual_pnl": 0},
        {"symbol": "00891.TW", "name": "中信臺灣智慧50", "shares": 10000, "manual_pnl": 0}
    ]}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return default_data
    return default_data

if 'my_data' not in st.session_state:
    st.session_state.my_data = load_settings()

# --- 3. 計算核心 ---
@st.cache_data(ttl=10)
def fetch_analysis(etf_list):
    res, reminders, pay_reminders = [], [], []
    t_mkt, t_pnl, t_cost, t_day_chg, annual_total = 0, 0, 0, 0, 0
    m_stats = {f"{m}月": {"total": 0, "detail": []} for m in range(1, 13)}
    now_tw = datetime.now(tw_tz).replace(tzinfo=None)
    
    # 🎯 股息數據預設 (2026 預估)
    div_cfg = {
        "0056.TW": {"m": [1, 4, 7, 10], "d": "2026-07-16", "p": "2026-05-15", "v": 1.07},
        "00927.TW": {"m": [1, 4, 7, 10], "d": "2026-07-16", "p": "2026-05-15", "v": 0.94},
        "00878.TW": {"m": [2, 5, 8, 11], "d": "2026-05-19", "p": "2026-06-12", "v": 0.51},
        "00891.TW": {"m": [2, 5, 8, 11], "d": "2026-05-18", "p": "2026-06-12", "v": 0.75},
        "00919.TW": {"m": [3, 6, 9, 12], "d": "2026-06-18", "p": "2026-07-15", "v": 0.72}
    }

    for item in etf_list:
        try:
            tk = yf.Ticker(item['symbol'])
            f_info = tk.fast_info
            curr_p = f_info['lastPrice']
            prev_close = f_info.get('regularMarketPreviousClose', curr_p)
            cfg = div_cfg.get(item['symbol'], {"m": [], "d": "無", "p": "無", "v": 0.0})
            
            # 殖利率與配息
            dy_yield = (cfg['v'] / curr_p * 100) if curr_p > 0 else 0
            cash = cfg['v'] * item['shares']
            for m in cfg["m"]:
                m_stats[f"{m}月"]["total"] += cash
                m_stats[f"{m}月"]["detail"].append({"code": item['symbol'].split('.')[0], "amount": cash})
                annual_total += cash

            t_mkt += (item['shares'] * curr_p)
            t_pnl += item['manual_pnl']
            t_cost += (item['shares'] * prev_close) # 成本隨股市收盤自動更新
            t_day_chg += (curr_p - prev_close) * item['shares']
            
            res.append({
                "代號": item['symbol'].split('.')[0], "現價": round(curr_p, 2), "殖利率": dy_yield,
                "今日漲跌": (curr_p - prev_close) * item['shares'], "累積損益": item['manual_pnl'],
                "張數": f"{int(item['shares']/1000)}張", "股息": cfg['v'], "市值": item['shares'] * curr_p
            })
            
            if cfg["d"] != "無":
                d_dt = datetime.strptime(cfg["d"], "%Y-%m-%d")
                if 0 <= (d_dt - now_tw).days <= 30: reminders.append({"code": item['symbol'].split('.')[0], "date": d_dt.strftime("%m/%d")})
            if cfg["p"] != "無":
                p_dt = datetime.strptime(cfg["p"], "%Y-%m-%d")
                if 0 <= (p_dt - now_tw).days <= 14: pay_reminders.append({"code": item['symbol'].split('.')[0], "date": p_dt.strftime("%m/%d"), "amount": cash})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, t_cost, m_stats, annual_total, reminders, t_day_chg, pay_reminders

# --- 4. 畫面渲染 ---
df, g_mkt, g_pnl, g_cost, g_months, g_annual, g_re, g_day, g_pay = fetch_analysis(st.session_state.my_data['etfs'])

st.title("👾 羅小翔專用：終極戰情室")

# 雙重雷達
col_re1, col_re2 = st.columns(2)
with col_re1:
    if g_re:
        for r in g_re: st.markdown(f'<div class="lightning-box"><b style="font-size: 22px;">⚡ 除息提醒 ⚡</b><br>標的 <b>{r["code"]}</b> 將於 <b>{r["date"]}</b> 除息</div>', unsafe_allow_html=True)
with col_re2:
    if g_pay:
        for p in g_pay: st.markdown(f'<div class="gold-box"><b style="font-size: 22px;">🪙 領息提醒 🪙</b><br>標的 <b>{p["code"]}</b> 股息約 <b>${p["amount"]:,.0f}</b> 將於 <b>{p["date"]}</b> 入帳！</div>', unsafe_allow_html=True)

# 損益面板
d_color = "#FF4B4B" if g_day >= 0 else "#09AB3B"
p_color = "#FF4B4B" if g_pnl >= 0 else "#09AB3B"
c1, c2 = st.columns(2)
with c1: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>今日即時損益<h2 style='color:{d_color}; margin:0;'>${g_day:+,.0f}</h2></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>累積總損益<h2 style='color:{p_color}; margin:0;'>${g_pnl:,.0f}</h2></div>", unsafe_allow_html=True)

# 資產概況 (解決語法錯誤的邏輯)
st.write("")
g_roi = (g_pnl / g_cost * 100) if g_cost > 0 else 0
roi_color = "#FF4B4B" if g_roi >= 0 else "#09AB3B"

col_a, col_b, col_c = st.columns(3)
with col_a: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>股票總市值</small><h3 style='margin:0;'>${g_mkt:,.0f}</h3></div>", unsafe_allow_html=True)
with col_b: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>總成本 (每日更新)</small><h3 style='margin:0;'>${g_cost:,.0f}</h3></div>", unsafe_allow_html=True)
with col_c: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>總報酬率</small><h3 style='color:{roi_color}; margin:0;'>{g_roi:+.2f}%</h3></div>", unsafe_allow_html=True)

# 持股清單
st.divider()
if not df.empty:
    st.dataframe(
        df.style.format({"現價": "{:.2f}", "殖利率": "{:.2f}%", "市值": "{:,.0f}", "累積損益": "{:,.0f}", "今日漲跌": "{:+,.0f}", "股息": "{:.2f}"})
        .map(lambda x: f'color:{"red" if (isinstance(x, (int,float)) and x>0) or str(x).startswith("+") else "green" if (isinstance(x, (int,float)) and x<0) or str(x).startswith("-") else "black"};font-weight:bold;', subset=['累積損益', '今日漲跌']),
        use_container_width=True, hide_index=True
    )

# 月領息預估
st.divider()
st.subheader("🗓️ 全年領息預估 (按月)")
for i in range(1, 13, 2):
    m1, m2 = f"{i}月", f"{i+1}月"
    cl1, cl2 = st.columns(2)
    with cl1:
        d1 = g_months[m1]
        with st.container(border=True):
            st.markdown(f"<p class='month-blue-title'>{m1}：+${d1['total']:,.0f}</p>", unsafe_allow_html=True)
            for s in d1["detail"]: st.write(f"└ {s['code']}： ${s['amount']:,.0f}")
    with cl2:
        d2 = g_months[m2]
        with st.container(border=True):
            st.markdown(f"<p class='month-blue-title'>{m2}：+${d2['total']:,.0f}</p>", unsafe_allow_html=True)
            for s in d2["detail"]: st.write(f"└ {s['code']}： ${s['amount']:,.0f}")

st.markdown(f"<div style='background-color:#e8f4fd; padding:18px 15px; border-radius:10px; margin-top:20px; border-left: 6px solid #0056b3; display:flex; justify-content:space-between; align-items:center;'><div><span style='font-size:18px; font-weight:900; color:#0056b3;'>🏆 全年預估領息總計</span></div><div style='text-align:right;'><span style='color:#0056b3; font-weight:900; font-size:26px;'>${g_annual:,.0f}</span></div></div>", unsafe_allow_html=True)

# 標的管理
st.divider()
st.subheader("⚙️ 標的管理系統")
with st.expander("➕ 新增 ETF 標的"):
    new_s = st.text_input("輸入代碼 (例: 00878)").upper()
    det_n = ""
    if new_s:
        fin_s = new_s if "." in new_s else f"{new_s}.TW"
        det_n = NAME_MAP.get(fin_s, "")
        if not det_n:
            try:
                info = yf.Ticker(fin_s).info
                det_n = info.get('longName') or info.get('shortName') or "新標的"
            except: det_n = "查詢中..."
        st.info(f"🔎 偵測名稱：**{det_n}**")
    if st.button("確認新增"):
        if new_s and det_n:
            fin_s = new_s if "." in new_s else f"{new_s}.TW"
            st.session_state.my_data['etfs'].append({"symbol": fin_s, "name": det_n, "shares": 0, "manual_pnl": 0})
            save_to_json(st.session_state.my_data)
            st.rerun()

with st.expander("⚙️ 修改與刪除持股"):
    up_list, del_idx = [], -1
    for i, item in enumerate(st.session_state.my_data.get('etfs', [])):
        st.markdown(f"**{item['name']} ({item['symbol']})**")
        cA, cB, cC = st.columns([2, 2, 1])
        with cA: s = st.number_input("股數", value=int(item['shares']), key=f"s_{i}")
        with cB: p = st.number_input("累積總損益", value=int(item['manual_pnl']), key=f"p_{i}")
        with cC: 
            if st.button("🗑️", key=f"del_{i}"): del_idx = i
        up_list.append({"symbol": item['symbol'], "name": item['name'], "shares": s, "manual_pnl": p})
    if del_idx != -1:
        st.session_state.my_data['etfs'].pop(del_idx)
        save_to_json(st.session_state.my_data)
        st.rerun()
    if st.button("💾 儲存並更新數據"):
        st.session_state.my_data['etfs'] = up_list
        save_to_json(st.session_state.my_data)
        st.success("數據儲存成功！")
        st.rerun()