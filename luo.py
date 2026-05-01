import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="羅小翔專用ETF", page_icon="💙", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=15 * 1000, key="data_refresh")

tw_tz = timezone(timedelta(hours=8))

# 🎯 終極 CSS 注入：強制標頭黃底黑字大字體，月份藍色
st.markdown("""
<style>
    /* 強力標頭修正：黃金背景、黑色字、字體加大 */
    [data-testid="stDataFrameColHeader"] {
        background-color: #FFD700 !important;
    }
    div[data-testid="stDataFrameColHeaderCell"] span {
        font-size: 22px !important; 
        color: #000000 !important;
        font-weight: 900 !important;
    }

    /* 月份標題維持深藍色 */
    .month-blue-title {
        color: #0056b3 !important;
        font-weight: bold;
        font-size: 20px;
        margin-bottom: 5px;
    }

    /* 除息雷達閃爍效果 */
    @keyframes blink { 0% { background-color: #fee2e2; } 50% { background-color: #fca5a5; } 100% { background-color: #fee2e2; } }
    .blink-box { 
        animation: blink 1.5s infinite; 
        padding: 20px; border-radius: 15px; 
        margin-bottom: 20px; border: 3px solid #ef4444; 
        text-align: center; 
    }
</style>
""", unsafe_allow_html=True)

# --- 2. 數據管理邏輯 ---
SETTINGS_FILE = 'settings.json'

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_settings():
    default_data = {
        "etfs": [
            {"symbol": "0056.TW", "name": "元大高股息", "shares": 25000, "cost": 38.77, "manual_pnl": 50680},
            {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 20000, "cost": 28.65, "manual_pnl": 22096},
            {"symbol": "00878.TW", "name": "國泰永續高股息", "shares": 13000, "cost": 23.07, "manual_pnl": 29345},
            {"symbol": "00919.TW", "name": "群益台灣精選高息", "shares": 12000, "cost": 22.73, "manual_pnl": 10392},
            {"symbol": "00891.TW", "name": "中信臺灣智慧50", "shares": 10000, "cost": 15.50, "manual_pnl": 0},
            {"symbol": "00981A.TW", "name": "主動統一台股增長", "shares": 12000, "cost": 27.77, "manual_pnl": 5246},
            {"symbol": "00631L.TW", "name": "元大台灣50正2", "shares": 13000, "cost": 27.25, "manual_pnl": 16758}
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

# --- 3. 計算核心 ---
@st.cache_data(ttl=10)
def fetch_analysis(etf_list):
    res, reminders = [], []
    t_mkt, t_pnl, t_cost, t_day_change, annual_total = 0, 0, 0, 0, 0
    m_stats = {f"{m}月": {"total": 0, "detail": []} for m in range(1, 13)}
    now_tw = datetime.now(tw_tz).replace(tzinfo=None)
    
    div_cfg = {
        "0056.TW": {"m": [1, 4, 7, 10], "d": "2026-07-16", "v": 1.07},
        "00927.TW": {"m": [1, 4, 7, 10], "d": "2026-07-16", "v": 0.94},
        "00878.TW": {"m": [2, 5, 8, 11], "d": "2026-05-19", "v": 0.51},
        "00891.TW": {"m": [2, 5, 8, 11], "d": "2026-05-18", "v": 0.75},
        "00919.TW": {"m": [3, 6, 9, 12], "d": "2026-06-18", "v": 0.72},
        "00981A.TW": {"m": [3, 6, 9, 12], "d": "2026-06-17", "v": 0.41}
    }

    for item in etf_list:
        try:
            # 🎯 符號修正：自動補齊 .TW 以確保數據帶入
            sym = item['symbol']
            if "." not in sym: sym += ".TW"
            
            tk = yf.Ticker(sym)
            f_info = tk.fast_info
            curr_p = f_info['lastPrice']
            high_p = f_info.get('dayHigh', curr_p)
            low_p = f_info.get('dayLow', curr_p)
            
            cfg = div_cfg.get(sym, {"m": [], "d": "無", "v": 0.0})
            
            cash = cfg['v'] * item['shares']
            for m in cfg["m"]:
                m_stats[f"{m}月"]["total"] += cash
                m_stats[f"{m}月"]["detail"].append({"code": sym.split('.')[0], "amount": cash})
                annual_total += cash

            prev_p = f_info.get('regularMarketPreviousClose', curr_p)
            day_chg = (curr_p - prev_p) * item['shares']
            t_mkt += (item['shares'] * curr_p)
            t_pnl += item['manual_pnl']
            t_cost += (item['shares'] * item['cost'])
            t_day_change += day_chg
            
            res.append({
                "代號": sym.split('.')[0], "現價": round(curr_p, 2), 
                "最高": round(high_p, 2), "最低": round(low_p, 2), "今日漲跌": day_chg,
                "累積損益": item['manual_pnl'], "張數": f"{int(item['shares']/1000)}張",
                "股息": cfg['v'], "市值": item['shares'] * curr_p
            })
            
            if cfg["d"] != "無":
                div_date = datetime.strptime(cfg["d"], "%Y-%m-%d")
                if 0 <= (div_date - now_tw).days <= 30: 
                    reminders.append({"code": sym.split('.')[0], "date": div_date.strftime("%m/%d")})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, t_cost, m_stats, annual_total, reminders, t_day_change

# --- 4. 數據渲染 ---
df, g_mkt, g_pnl, g_cost, g_months, g_annual, g_reminders, g_day_change = fetch_analysis(st.session_state.my_data['etfs'])

st.title("👾 羅小翔專用ETF")

# 🚨 除息雷達 (補回回歸)
if g_reminders:
    for r in g_reminders:
        st.markdown(f'<div class="blink-box"><b style="color: #b91c1c; font-size: 22px;">💰 🚨 除息雷達提醒</b><br><span style="color: #b91c1c; font-size: 18px;">標的 <b>{r["code"]}</b> 將於 <b>{r["date"]}</b> 除息！</span></div>', unsafe_allow_html=True)

# 💰 頂部損益
d_col, p_col = ("#FF4B4B" if g_day_change >= 0 else "#09AB3B"), ("#FF4B4B" if g_pnl >= 0 else "#09AB3B")
c1, c2 = st.columns(2)
with c1: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>今日損益<h2 style='color:{d_col}; margin:0;'>${g_day_change:+,.0f}</h2></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>累積總損益<h2 style='color:{p_col}; margin:0;'>${g_pnl:,.0f}</h2></div>", unsafe_allow_html=True)

# 🎯 核心資產卡片 (修復括號當機問題)
st.write("")
g_roi = (g_pnl / g_cost * 100) if g_cost > 0 else 0
roi_color = "#FF4B4B" if g_roi >= 0 else "#09AB3B"

col_a, col_b, col_c = st.columns(3)
with col_a: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>股票總市值</small><h3 style='margin:0;'>${g_mkt:,.0f}</h3></div>", unsafe_allow_html=True)
with col_b: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>總成本</small><h3 style='margin:0;'>${g_cost:,.0f}</h3></div>", unsafe_allow_html=True)
with col_c: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>總報酬率</small><h3 style='color:{roi_color}; margin:0;'>{g_roi:+.2f}%</h3></div>", unsafe_allow_html=True)

# 📊 持股清單
st.divider()
if not df.empty:
    st.dataframe(
        df.style.format({"現價": "{:.2f}", "最高": "{:.2f}", "最低": "{:.2f}", "市值": "{:,.0f}", "累積損益": "{:,.0f}", "今日漲跌": "{:+,.0f}"})
        .map(lambda x: f'color:{"red" if (isinstance(x, (int,float)) and x>0) or str(x).startswith("+") else "green" if (isinstance(x, (int,float)) and x<0) or str(x).startswith("-") else "black"};font-weight:bold;', subset=['累積損益', '今日漲跌']),
        use_container_width=True, hide_index=True
    )

# --- 🗓️ 月領息預估 ---
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

# 🏆 全年合計
st.markdown(f"<div style='background-color:#e8f4fd; padding:18px 15px; border-radius:10px; margin-top:20px; border-left: 6px solid #0056b3; display:flex; justify-content:space-between; align-items:center;'><div><span style='font-size:18px; font-weight:900; color:#0056b3;'>🏆 全年預估領息總計</span></div><div style='text-align:right;'><span style='color:#0056b3; font-weight:900; font-size:26px;'>${g_annual:,.0f}</span></div></div>", unsafe_allow_html=True)

# --- ⚙️ 標的管理 ---
st.divider()
st.subheader("⚙️ 標的資產管理")
with st.expander("➕ 新增 ETF 標的"):
    c_n1, c_n2 = st.columns(2)
    with c_n1: new_sym = st.text_input("代碼 (系統會自動補齊 .TW)").upper()
    with c_n2: new_name = st.text_input("名稱")
    if st.button("確認新增"):
        if new_sym and new_name:
            final_sym = new_sym if "." in new_sym else f"{new_sym}.TW"
            st.session_state.my_data['etfs'].append({"symbol": final_sym, "name": new_name, "shares": 0, "cost": 0.0, "manual_pnl": 0})
            save_to_json(st.session_state.my_data)
            st.rerun()

with st.expander("⚙️ 修改與刪除現有持股"):
    updated_list, to_delete_idx = [], -1
    for i, item in enumerate(st.session_state.my_data.get('etfs', [])):
        st.markdown(f"**{item['name']} ({item['symbol']})**")
        cA, cB, cC, cD = st.columns([2, 2, 2, 1])
        with cA: s = st.number_input("股數", value=int(item['shares']), key=f"s_{i}")
        with cB: c = st.number_input("成本", value=float(item['cost']), key=f"c_{i}")
        with cC: p = st.number_input("損益", value=int(item['manual_pnl']), key=f"p_{i}")
        with cD: 
            if st.button("🗑️", key=f"del_{i}"): to_delete_idx = i
        updated_list.append({"symbol": item['symbol'], "name": item['name'], "shares": s, "cost": c, "manual_pnl": p})
    if to_delete_idx != -1:
        st.session_state.my_data['etfs'].pop(to_delete_idx)
        save_to_json(st.session_state.my_data)
        st.rerun()
    if st.button("💾 儲存並更新數據", use_container_width=True):
        st.session_state.my_data['etfs'] = updated_list
        save_to_json(st.session_state.my_data)
        st.success("數據已成功儲存！")
        st.rerun()