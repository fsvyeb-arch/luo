import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="羅小翔專用：ETF 報警戰情室", page_icon="💙", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=15 * 1000, key="data_refresh")

tw_tz = timezone(timedelta(hours=8))

# 🎯 視覺特效 CSS
st.markdown("""
<style>
    @keyframes lightning { 0%, 100% { background-color: #fee2e2; box-shadow: 0 0 0px #fff; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ffffff, 0 0 60px #ef4444; } }
    @keyframes gold-flash { 0%, 100% { background-color: #fef3c7; box-shadow: 0 0 0px #fff; } 10% { background-color: #ffffff; box-shadow: 0 0 30px #ffffff, 0 0 60px #f59e0b; } }
    @keyframes pulse-alert { 0% { box-shadow: 0 0 0px 0px rgba(139, 92, 246, 0.7); } 70% { box-shadow: 0 0 0px 15px rgba(139, 92, 246, 0); } 100% { box-shadow: 0 0 0px 0px rgba(139, 92, 246, 0); } }
    .lightning-box { animation: lightning 3s infinite; padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 3px solid #ef4444; text-align: center; color: #b91c1c; }
    .gold-box { animation: gold-flash 3s infinite; padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 3px solid #f59e0b; text-align: center; color: #92400e; }
    .price-alert-box { animation: pulse-alert 2s infinite; padding: 20px; border-radius: 15px; margin-bottom: 15px; border: 3px solid #8b5cf6; text-align: center; background-color: #f5f3ff; color: #5b21b6; }
    [data-testid="stDataFrameColHeader"] { background-color: #FFD700 !important; }
    div[data-testid="stDataFrameColHeaderCell"] span { color: #000000 !important; font-size: 20px !important; font-weight: 900 !important; }
    .month-blue-title { color: #0056b3 !important; font-weight: bold; font-size: 18px; }
</style>
""", unsafe_allow_html=True)

# --- 2. 數據管理 (含備忘錄儲存) ---
SETTINGS_FILE = 'settings.json'

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_settings():
    # 預設資料，包含 0056 (8張) 與 00927 (6張)
    default_data = {
        "etfs": [
            {"symbol": "0056.TW", "name": "元大高股息", "shares": 8000, "manual_pnl": 0, "upper": 0.0, "lower": 0.0},
            {"symbol": "00927.TW", "name": "群益半導體收益", "shares": 6000, "manual_pnl": 0, "upper": 0.0, "lower": 0.0}
        ],
        "memo": "在這裡輸入你的操盤心得或重要筆記..."
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    data = json.loads(content)
                    if "memo" not in data: data["memo"] = ""
                    return data
        except: return default_data
    return default_data

if 'my_data' not in st.session_state:
    st.session_state.my_data = load_settings()

# --- 3. 計算核心 ---
@st.cache_data(ttl=10)
def fetch_analysis(etf_list):
    res, reminders, pay_reminders, p_alerts = [], [], [], []
    t_mkt, t_pnl, t_cost, t_day, annual_total = 0, 0, 0, 0, 0
    m_stats = {f"{m}月": {"total": 0, "detail": []} for m in range(1, 13)}
    price_map = {}
    now_tw = datetime.now(tw_tz).replace(tzinfo=None)
    
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
            vol = f_info.get('lastVolume', 0)
            price_map[item['symbol']] = curr_p
            
            if item.get('upper', 0) > 0 and curr_p >= item['upper']:
                p_alerts.append(f"🚀 {item['name']} 達標止盈！現價 {curr_p:.2f}")
            if item.get('lower', 0) > 0 and curr_p <= item['lower']:
                p_alerts.append(f"📉 {item['name']} 跌破低接！現價 {curr_p:.2f}")

            cfg = div_cfg.get(item['symbol'], {"m": [], "d": "無", "p": "無", "v": 0.0})
            dy_yield = (cfg['v'] / curr_p * 100) if curr_p > 0 else 0
            cash = cfg['v'] * item['shares']
            for m in cfg["m"]:
                m_stats[f"{m}月"]["total"] += cash
                m_stats[f"{m}月"]["detail"].append({"code": item['symbol'].split('.')[0], "amount": cash})
                annual_total += cash

            t_mkt += (item['shares'] * curr_p); t_pnl += item['manual_pnl']
            t_cost += (item['shares'] * prev_close); t_day += (curr_p - prev_close) * item['shares']
            
            res.append({
                "代號": item['symbol'].split('.')[0], "名稱": item['name'], "現價": round(curr_p, 2), "殖利率": f"{dy_yield:.2f}%",
                "今日漲跌": (curr_p - prev_close) * item['shares'], "累積損益": item['manual_pnl'],
                "張數": f"{int(item['shares']/1000)}張", "交易量": vol, "市值": item['shares'] * curr_p
            })
            if cfg["d"] != "無":
                d_dt = datetime.strptime(cfg["d"], "%Y-%m-%d")
                if 0 <= (d_dt - now_tw).days <= 30: reminders.append({"code": item['symbol'].split('.')[0], "date": d_dt.strftime("%m/%d")})
            if cfg["p"] != "無":
                p_dt = datetime.strptime(cfg["p"], "%Y-%m-%d")
                if 0 <= (p_dt - now_tw).days <= 14: pay_reminders.append({"code": item['symbol'].split('.')[0], "date": p_dt.strftime("%m/%d"), "amount": cash})
        except: continue
    return pd.DataFrame(res), t_mkt, t_pnl, t_cost, m_stats, annual_total, reminders, t_day, pay_reminders, p_alerts, price_map

# --- 4. 畫面渲染 ---
df, g_mkt, g_pnl, g_cost, g_months, g_annual, g_re, g_day, g_pay, g_price_alerts, g_price_map = fetch_analysis(st.session_state.my_data['etfs'])

st.title("👾 羅小翔：ETF 報警戰情室")

# 警報區
if g_price_alerts:
    for msg in g_price_alerts: st.markdown(f'<div class="price-alert-box"><b style="font-size:24px;">🔔 股價警報：</b><br>{msg}</div>', unsafe_allow_html=True)

col_r1, col_r2 = st.columns(2)
with col_r1:
    if g_re:
        for r in g_re: st.markdown(f'<div class="lightning-box"><b>⚡ 除息提醒：</b>{r["code"]} 於 {r["date"]}</div>', unsafe_allow_html=True)
with col_r2:
    if g_pay:
        for p in g_pay: st.markdown(f'<div class="gold-box"><b>🪙 領息提醒：</b>{p["code"]} ${p["amount"]:,.0f} 於 {p["date"]}</div>', unsafe_allow_html=True)

# 損益面板
d_color = "#FF4B4B" if g_day >= 0 else "#09AB3B"
p_color = "#FF4B4B" if g_pnl >= 0 else "#09AB3B"
g_roi = (g_pnl / g_cost * 100) if g_cost > 0 else 0
roi_color = "#FF4B4B" if g_roi >= 0 else "#09AB3B"

c1, c2 = st.columns(2)
with c1: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>今日即時損益<h2 style='color:{d_color};'>${g_day:+,.0f}</h2></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div style='background-color:#f0f2f6; padding:15px; border-radius:12px; text-align:center;'>累積總損益<h2 style='color:{p_color};'>${g_pnl:,.0f}</h2></div>", unsafe_allow_html=True)

ca, cb, cc = st.columns(3)
with ca: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>股票總市值</small><h3 style='margin:0;'>${g_mkt:,.0f}</h3></div>", unsafe_allow_html=True)
with cb: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>總成本</small><h3 style='margin:0;'>${g_cost:,.0f}</h3></div>", unsafe_allow_html=True)
with cc: st.markdown(f"<div style='border:1px solid #ddd; padding:10px; border-radius:10px; text-align:center;'><small>總報酬率</small><h3 style='color:{roi_color}; margin:0;'>{g_roi:+.2f}%</h3></div>", unsafe_allow_html=True)

st.divider()
if not df.empty:
    st.dataframe(df.style.format({"現價":"{:.2f}","今日漲跌":"{:+,.0f}","累積損益":"{:,.0f}","市值":"{:,.0f}","交易量":"{:,.0f}"}), use_container_width=True, hide_index=True)

# 📥 匯出 CSV
summary_text = f"總市值,${g_mkt:,.0f}\n總成本,${g_cost:,.0f}\n總損益,${g_pnl:,.0f}\n總報酬,{g_roi:+.2f}%\n\n"
csv_data = summary_text + df.to_csv(index=False)
st.download_button(label="📥 匯出完整報表", data=csv_data.encode('utf-8-sig'), file_name=f"ETF_Report_{datetime.now(tw_tz).strftime('%Y%m%d')}.csv", use_container_width=True)

# --- 🗓️ 全年領息預估 ---
st.divider()
st.subheader("🗓️ 全年領息預估")
for i in range(1, 13, 2):
    m1, m2 = f"{i}月", f"{i+1}月"; cl1, cl2 = st.columns(2)
    with cl1:
        d1 = g_months[m1]; st.markdown(f"<p class='month-blue-title'>{m1}：+${d1['total']:,.0f}</p>", unsafe_allow_html=True)
        for s in d1["detail"]: st.write(f"└ {s['code']}： ${s['amount']:,.0f}")
    with cl2:
        d2 = g_months[m2]; st.markdown(f"<p class='month-blue-title'>{m2}：+${d2['total']:,.0f}</p>", unsafe_allow_html=True)
        for s in d2["detail"]: st.write(f"└ {s['code']}： ${s['amount']:,.0f}")

st.markdown(f"<div style='background-color:#e8f4fd; padding:18px 15px; border-radius:10px; margin-top:20px; border-left: 6px solid #0056b3; display:flex; justify-content:space-between; align-items:center;'><div><span style='font-size:18px; font-weight:900; color:#0056b3;'>🏆 全年領息總結</span></div><div style='text-align:right;'><span style='color:#0056b3; font-weight:900; font-size:26px;'>${g_annual:,.0f}</span></div></div>", unsafe_allow_html=True)

# --- 📝 羅小翔專屬備忘錄 (新增功能) ---
st.divider()
st.subheader("📝 羅小翔專屬備忘錄")
user_memo = st.text_area("在下面記下你的操盤筆記或生活提醒：", value=st.session_state.my_data.get("memo", ""), height=150)
if st.button("💾 儲存筆記"):
    st.session_state.my_data["memo"] = user_memo
    save_to_json(st.session_state.my_data)
    st.success("筆記儲存成功！")

# --- ⚙️ 管理系統 ---
st.divider()
st.subheader("⚙️ 標的管理與警報系統")
with st.expander("⚙️ 修改現有持股與警報 (對照即時股價)"):
    up_list, del_idx = [], -1
    for i, it in enumerate(st.session_state.my_data.get('etfs', [])):
        curr_p = g_price_map.get(it['symbol'], 0.0)
        st.markdown(f"**{it['name']} ({it['symbol']}) —— 即時價：`${curr_p:.2f}`**")
        cA, cB, cC, cD, cE = st.columns([2, 2, 2, 2, 1])
        with cA: s = st.number_input("股數", value=int(it['shares']), key=f"s_{i}")
        with cB: p = st.number_input("累積損益", value=int(it['manual_pnl']), key=f"p_{i}")
        with cC: upper = st.number_input("上限提醒", value=float(it.get('upper',0.0)), key=f"up_{i}")
        with cD: lower = st.number_input("下限提醒", value=float(it.get('lower',0.0)), key=f"low_{i}")
        with cE: 
            if st.button("🗑️", key=f"del_{i}"): del_idx = i
        up_list.append({"symbol": it['symbol'], "name": it['name'], "shares": s, "manual_pnl": p, "upper": upper, "lower": lower})
    if del_idx != -1:
        st.session_state.my_data['etfs'].pop(del_idx); save_to_json(st.session_state.my_data); st.rerun()
    if st.button("💾 儲存標的與警報設定", use_container_width=True):
        st.session_state.my_data['etfs'] = up_list; save_to_json(st.session_state.my_data); st.success("設定儲存成功！"); st.rerun()