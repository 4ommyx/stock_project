# Func_app/GGM/ggm_cal.py
import yfinance as yf
import pandas as pd
import datetime
from typing import List, Dict, Optional
from Func_app.config import SET50_TICKERS 

def calculate_ddm_dynamic(symbol: str, years: int, r_expected: float, growth_rate: float) -> Optional[Dict]:
    try:
    
        symbol_input = symbol if symbol.endswith(".BK") else f"{symbol}.BK"
        
        stock = yf.Ticker(symbol_input)
        current_price = stock.fast_info['last_price']
        
        if current_price is None: return None
        
        # หา D0
        dividends = stock.dividends
        one_year_ago = pd.Timestamp.now(tz=datetime.timezone.utc) - pd.DateOffset(years=1)
        d0 = dividends[dividends.index >= one_year_ago].sum()
        if d0 == 0: d0 = 0 

        # Loop คำนวณ D1...Dn และ PV
        total_pv_dividends = 0
        current_d = d0
        dynamic_columns = {} 
        
        for i in range(1, years + 1):
            current_d = current_d * (1 + growth_rate)
            dynamic_columns[f"D{i}"] = round(current_d, 4)
            pv = current_d / ((1 + r_expected) ** i)
            total_pv_dividends += pv
        
        # Terminal Value
        pn_future = current_price * ((1 + growth_rate) ** years)
        pn_discounted = pn_future / ((1 + r_expected) ** years)
        
        # รวมมูลค่า
        pred = total_pv_dividends + pn_discounted
        diff_percent = (pred - current_price) / pred if pred != 0 else 0
        meaning = 'Undervalue' if diff_percent > 0 else 'Overvalue'

        return {
            "Symbol": symbol, # ส่งชื่อเดิมกลับไปแสดงผล
            "Current_Price": round(current_price, 2),
            "Pred_Price": round(pred, 2),
            "Diff_Percent": round(diff_percent * 100, 2),
            "Meaning": meaning,
            "Dividends_Flow": dynamic_columns
        }

    except Exception as e:
        # print(f"Error {symbol}: {e}") 
        return None

def analyze_ggm_batch(tickers: Optional[List[str]], years: int, r_expected: float, growth_rate: float) -> List[Dict]:

    target_tickers = tickers if tickers else SET50_TICKERS
    
    results = []
    for stock in target_tickers:
        res = calculate_ddm_dynamic(stock, years, r_expected, growth_rate)
        if res:
            results.append(res)
    
    results.sort(key=lambda x: x['Diff_Percent'], reverse=True)
    return results