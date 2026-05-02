import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import plotly.graph_objects as go

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="ETF 投資戰情室", layout="wide")

# 自定義 CSS
st.markdown("""
    <style>
    [data-testid="stMetricDelta"] svg { fill: red; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; }
    
    .news-box { background-color: #f0f7ff; border-left: 6px solid #4a90e2; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 1px 1px 4px rgba(0,0,0,0.05); }
    .news-title { font-size: 20px; font-weight: bold; color: #1e3c72; margin-bottom: 15px; display: flex; align-items: center; }
    .news-item { font-size: 16px; color: #333; margin-bottom: 12px; line-height: 1.5; font-weight: 500;}
    .news-item a { text-decoration: none; color: #1e3c72; transition: color 0.2s;}
    .news-item a:hover { text-decoration: underline; color: #d32f2f; }

    .ex-div-box { background-color: #ffeaea; border: 2px solid #e06666; border-radius: 10px; padding: 25px 15px; text-align: center; margin-bottom: 15px; height: 100%; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}
    .ex-div-title { color: #cc0000; font-weight: bold; font-size: 16px; margin-bottom: 10px; }
    .ex-div-text { color: #783f04; font-size: 14px; font-weight: bold; }
    
    .pay-div-box { background-color: #fff2cc; border: 2px solid #f6b26b; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);}
    .pay-div-title { color: #b45f06; font-weight: bold; font-size: 16px; margin-bottom: 8px; }
    .pay-div-text { color: #783f04; font-size: 14px; font-weight: bold; }

    /* 💰 損益與配息大看板樣式 */
    .pnl-container { display: flex; gap: 15px; margin-bottom: 20px; align-items: stretch; }
    .pnl-card { flex: 1; background-color: #f8f9fa; border-radius: 8px; padding: 25px; text-align: center; border: 1px solid #e9ecef; box-shadow: 1px 1px 5px rgba(0,0,0,0.02); display: flex; flex-direction: column; justify-content: center;}
    .pnl-title { font-size: 16px; color: #2c3e50; margin-bottom: 10px; font-weight: bold; }
    .pnl-amount-red { font-size: 42px; font-weight: bold; color: #e74c3c; }
    .pnl-amount-green { font-size: 42px; font-weight: bold; color: #2ecc71; }
    .pnl-subtitle { font-size: 14px; color: #7f8c8d; margin-top: 5px; font-weight: 500;}

    .month-card { background-color: #e9ecef; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 10px; border: 1px solid #ced4da; }
    .month-title { font-size: 20px; font-weight: bold; color: #495057; }
    .month-amount { font-size: 28px; font-weight: bold; color: #d9534f; margin: 10px 0; }
    .month-sources { font-size: 14px; color: #6c757d; }
    
    div.stButton > button { font-weight: bold; border-radius: 8px; }
    .secret-box { padding: 25px; border: 2px dashed #dc3545; border-radius: 12px; background-color: #fffafb; }
    .net-worth-box { background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 系統設定與資料庫 ---
SETTINGS_FILE = 'settings.json'

ETF_NAME_DB = {
    "0050": "0050 元大台灣50", "006208": "006208 富邦台50", "00692": "00692 富邦公司治理", 
    "0056": "0056 元大高股息", "00878": "00878 國泰永續高股息", "00713": "00713 元大台灣高息低波",
    "00919": "00919 群益台灣精選高息", "00929": "00929 復華台灣科技優息", "00940": "00940 元大台灣價值高息",
    "00891": "00891 中信關鍵半導體", "00927": "00927 群益半導體收益", "00981A": "00981A 主動統一台股增長 ETF"
}

DIVIDEND_SCHEDULE = {
    "0050.TW": [1, 7], "0056.TW": [1, 4, 7, 10], "00878.TW": [2, 5, 8, 11],
    "00891.TW": [2, 5, 8, 11], "00919.TW": [3, 6, 9, 12], "00927.TW": [1, 4, 7, 10],
    "00929.TW": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "00940.TW": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
}

DIVIDEND_DB = {
    "0056.TW": {"v": 1.07, "d": "2026-04-16", "p": "2026-05-15"}, 
    "00927.TW": {"v": 0.94, "d": "2026-04-18", "p": "2026-05-15"}  
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {
        "etfs": [
            {"symbol": "0056.TW", "name": "0056 元大高股息", "holdings": 4.1, "cost": 41.11, "alert_high": 0.0, "alert_low": 0.0},
            {"symbol": "00891.TW", "name": "00891 中信關鍵半導體", "holdings": 5.0, "cost": 31.30, "alert_high": 0.0, "alert_low": 0.0},
            {"symbol": "00919.TW", "name": "00919 群益台灣精選高息", "holdings": 10.0, "cost": 23.04, "alert_high": 0.0, "alert_low": 0.0},
            {"symbol": "00927.TW", "name": "00927 群益半導體收益", "holdings": 6.0, "cost": 27.63, "alert_high": 0.0, "alert_low": 0.0}
        ],
        "loan": {"months_paid": 1, "first_amount": 6000, "regular_amount": 15000, "total_months": 84}
    }

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if 'my_data' not in st.session_state: st.session_state.my_data = load_settings()

# 按鈕開關
for key in ['show_us', 'show_tw', 'show_calendar', 'show_div_db', 'show_tech', 'show_holdings', 'show_secret']:
    if key not in st.session_state: st.session_state[key] = False

def toggle_us(): st.session_state.show_us = not st.session_state.show_us
def toggle_tw(): st.session_state.show_tw = not st.session_state.show_tw
def toggle_calendar(): st.session_state.show_calendar = not st.session_state.show_calendar
def toggle_div_db(): st.session_state.show_div_db = not st.session_state.show_div_db
def toggle_tech(): st.session_state.show_tech = not st.session_state.show_tech
def toggle_holdings(): st.session_state.show_holdings = not st.session_state.show_holdings
def toggle_secret(): st.session_state.show_secret = not st.session_state.show_secret

# --- 📡 抓取焦點新聞與數據 ---
@st.cache_data(ttl=3600)
def fetch_etf_news():
    news_list = []
    today_str = datetime.now().strftime("%m/%d")
    try:
        url = "https://news.google.com/rss/search?q=%E5%8F%B0%E7%81%A3+ETF+%E9%85%8D%E6%81%AF&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            root = ET.fromstring(response.read()); items = root.findall('.//item')[:4]
            for item in items:
                title = item.find('title').text.rsplit(" - ", 1)[0]
                news_list.append({"title": f"{today_str} {title}", "link": item.find('link').text})
    except: news_list = [{"title": f"{today_str} 暫無最新 ETF 配息新聞", "link": "#"}]
    return news_list

@st.cache_data(ttl=60)
def fetch_macro_data():
    tickers = {"us": {"那斯達克": "^IXIC", "輝達": "NVDA"}, "tw": {"台股大盤": "^TWII", "台積電": "2330.TW"}}
    res = {"us": {}, "tw": {}}
    for region, t_dict in tickers.items():
        for name, symbol in t_dict.items():
            try:
                hist = yf.Ticker(symbol).history(period="2d")
                curr, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                res[region][name] = {"price": curr, "diff": curr-prev, "pct": (curr-prev)/prev*100, "date": hist.index[-1].strftime("%m/%d")}
            except: pass
    return res

def render_macro_cards(data_dict, region_prefix):
    cols = st.columns(len(data_dict))
    for idx, (name, data) in enumerate(data_dict.items()):
        color = "#e74c3c" if data['diff'] >= 0 else "#2ecc71"
        with cols[idx]:
            st.markdown(f"""<div style="border-left:5px solid {color}; padding:10px; background:#fff; border-radius:5px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                <small>{region_prefix} {name} ({data['date']})</small><br>
                <b style="font-size:20px;">{data['price']:,.2f}</b><br>
                <span style="color:{color}; font-weight:bold;">{data['diff']:+,.2f} ({data['pct']:+.2f}%)</span>
            </div>""", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def fetch_data(etf_list):
    results, tech_results = [], []
    total_mkt, total_cost, total_today_pnl = 0, 0, 0
    radar_ex, radar_pay, price_alerts = [], [], []
    monthly_calendar = {i: {"amount": 0, "sources": []} for i in range(1, 13)}
    today = datetime.today()

    for item in etf_list:
        try:
            tk = yf.Ticker(item['symbol']); hist = tk.history(period='5d')
            if hist.empty: continue
            curr_p, prev_close = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
            shares = item['holdings'] * 1000
            mkt_val, cost_val = shares * curr_p, shares * item['cost']
            total_mkt += mkt_val; total_cost += cost_val; total_today_pnl += shares * (curr_p - prev_close)
            
            # 配息處理
            div_amount, is_announced = 0, False
            cfg = DIVIDEND_DB.get(item['symbol'])
            if cfg: div_amount, is_announced = cfg['v'], True
            else:
                actions = tk.actions
                if not actions.empty:
                    latest = actions.sort_index(ascending=False).head(1)
                    div_amount = float(latest['Dividends'].values[0]); is_announced = True
            
            months = DIVIDEND_SCHEDULE.get(item['symbol'], [])
            for m in months:
                monthly_calendar[m]["amount"] += (shares * div_amount)
                monthly_calendar[m]["sources"].append(item['name'])

            results.append({"代號": item['symbol'], "名稱": item['name'], "現價": curr_p, "均價": item['cost'], "張數": item['holdings'], "市值": mkt_val, "損益": mkt_val-cost_val, "報酬率": (mkt_val-cost_val)/cost_val*100 if cost_val else 0, "已公告": is_announced, "每股配息": div_amount})
        except: continue
    return pd.DataFrame(results), total_mkt, total_cost, total_today_pnl, monthly_calendar

df, g_mkt, g_cost, g_today_pnl, monthly_calendar = fetch_data(st.session_state.my_data['etfs'])
macro_data = fetch_macro_data()

# --- 5. 介面呈現 ---
st.title("📈 實戰資產戰情室")

# 新聞
news_html = "<div class='news-box'><div class='news-title'>🗞️ 今日財經焦點</div>"
for news in fetch_etf_news(): news_html += f"<div class='news-item'>👉 <a href='{news['link']}' target='_blank'>{news['title']}</a></div>"
st.markdown(news_html + "</div>", unsafe_allow_html=True)

if not df.empty:
    # --- 💰 損益與現金流黃金三角大看板 ---
    p_total = g_mkt - g_cost
    today_color = "pnl-amount-red" if g_today_pnl >= 0 else "pnl-amount-green"
    total_color = "pnl-amount-red" if p_total >= 0 else "pnl-amount-green"
    current_month_num = datetime.today().month
    current_div = monthly_calendar[current_month_num]["amount"]
    
    col_a, col_b, col_c = st.columns([1, 1.2, 1])
    
    with col_a:
        st.markdown(f"""<div class="pnl-card"><div class="pnl-title">今日損益</div><div class="{today_color}">{g_today_pnl:+,.0f}</div><div class="pnl-subtitle">市值即時動態</div></div>""", unsafe_allow_html=True)
    
    with col_b:
        # 📈 瑪表（儀表板）實作
        target_goal = 20000 # 這裡可以設定您的每月領息目標
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = current_div,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"🗓️ {current_month_num}月 預估領息總額", 'font': {'size': 16, 'color': '#2c3e50', 'bold': True}},
            number = {'prefix': "$", 'font': {'color': '#f39c12', 'size': 40}},
            gauge = {
                'axis': {'range': [None, max(target_goal, current_div * 1.2)], 'tickwidth': 1, 'tickcolor': "#7f8c8d"},
                'bar': {'color': "#f1c40f"}, # 亮金色指針
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "#e9ecef",
                'steps': [
                    {'range': [0, target_goal*0.5], 'color': '#fff9e6'},
                    {'range': [target_goal*0.5, target_goal], 'color': '#fff4cc'}],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': target_goal}}))
        fig.update_layout(height=260, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_c:
        st.markdown(f"""<div class="pnl-card"><div class="pnl-title">累積總損益</div><div class="{total_color}">{p_total:+,.0f}</div><div class="pnl-subtitle">含未實現資本利得</div></div>""", unsafe_allow_html=True)

    # 指標
    c1, c2, c3 = st.columns(3)
    c1.metric("股票總市值", f"${g_mkt:,.0f}")
    c2.metric("投資總成本", f"${g_cost:,.0f}", f"總報酬率 {(p_total/g_cost*100):+.2f}%", delta_color="off")
    c3.metric("全年預估總領息", f"${sum([monthly_calendar[m]['amount'] for m in range(1, 13)]):,.0f}")
    
    st.write("---")
    
    # --- 控制台 ---
    cols_btn = st.columns(7)
    with cols_btn[0]: st.button("🌎 美股", on_click=toggle_us, use_container_width=True)
    with cols_btn[1]: st.button("🇹🇼 台股", on_click=toggle_tw, use_container_width=True)
    with cols_btn[2]: st.button("📅 日曆", on_click=toggle_calendar, use_container_width=True)
    with cols_btn[3]: st.button("📂 除息", on_click=toggle_div_db, use_container_width=True)
    with cols_btn[4]: st.button("📡 監控", on_click=toggle_tech, use_container_width=True)
    with cols_btn[5]: st.button("📊 明細", on_click=toggle_holdings, use_container_width=True)
    with cols_btn[6]: st.button("🔒 機密", on_click=toggle_secret, use_container_width=True)

    if st.session_state.show_us: render_macro_cards(macro_data["us"], "🌎")
    if st.session_state.show_tw: render_macro_cards(macro_data["tw"], "🇹🇼")
    
    if st.session_state.show_holdings:
        st.markdown("#### 📊 持股動態明細")
        for _, row in df.iterrows():
            color = "red" if row['損益'] >= 0 else "green"
            with st.expander(f"💎 {row['名稱']} | 報酬: :{color}[{row['報酬率']:+.2f}%]"):
                st.write(f"張數: {row['張數']} | 市值: ${row['市值']:,.0f} | 損益: :{color}[${row['損益']:,.0f}]")

# 尾部
st.write("---")
if st.button("🔄 手動更新"): st.cache_data.clear(); st.rerun()