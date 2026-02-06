# Func_app/GGM/ggm_cal.py
import yfinance as yf
import pandas as pd
import datetime
from typing import List, Dict, Optional
from Func_app.config import SET50_TICKERS 

def calculate_ddm_dynamic(symbol: str, years: int, r_expected: float, growth_rate: float = 0.0) -> Optional[Dict]:
    """
    [UPDATED LOGIC] DDM Valuation using Historical Dividends as Proxy
    
    Logic Changes:
      - Ignores 'growth_rate' input (uses historical data instead).
      - Forces 3-Year Model structure to match Div(Y-2), Div(Y-1), Div(Y-0).
      - Terminal Value = Current Price (Conservative).
      - Diff_Percent = (Target - Current) / Current (Upside %).
      - Threshold: +/- 2.5% considered 'Fairly Valued'.
    """
    try:
        symbol_input = symbol if symbol.endswith(".BK") else f"{symbol}.BK"
        stock = yf.Ticker(symbol_input)
        current_price = stock.fast_info['last_price']
        
        if current_price is None or current_price == 0: return None
        
        # ดึงปันผลทั้งหมด
        dividends = stock.dividends
        if dividends.empty: return None
        
        # เตรียมตัวแปรเวลา
        now = pd.Timestamp.now(tz=datetime.timezone.utc)

        calc_years = years 
        threshold_pct = 2.5
        
        total_pv_dividends = 0
        dividends_flow = {}

        col_names = {1: "Div(Y-2)", 2: "Div(Y-1)", 3: "Div(Y-0)"}

        for i in range(1, calc_years + 1):
            history_year_offset = calc_years - i + 1
            
            start_date = now - pd.DateOffset(years=history_year_offset + 1)
            end_date = now - pd.DateOffset(years=history_year_offset)
            
            d_historic = dividends[(dividends.index >= start_date) & (dividends.index < end_date)].sum()
            
            col_name = col_names.get(i, f"D{i}")
            dividends_flow[col_name] = round(d_historic, 4)
            
            # คิดลด PV
            pv = d_historic / ((1 + r_expected) ** i)
            total_pv_dividends += pv

        pv_terminal_price = current_price / ((1 + r_expected) ** calc_years)
        
        target_price = total_pv_dividends + pv_terminal_price

        if current_price != 0:
            upside_percent = ((target_price - current_price) / current_price) * 100
        else:
            upside_percent = 0
        
        # --- Threshold Logic (+- 2.5%) ---
        if abs(upside_percent) <= threshold_pct:
            meaning = "Fairly Valued"
        elif upside_percent > threshold_pct:
            meaning = "Undervalue"
        else: 
            meaning = "Overvalue"

        return {
            "Symbol": symbol,
            "Current_Price": round(current_price, 2),
            "Target_Price": round(target_price, 2), # เปลี่ยน Key เป็น Target ให้สื่อความหมาย (หรือจะใช้ Pred_Price เหมือนเดิมก็ได้)
            "Diff_Percent": round(upside_percent, 2),
            "Meaning": meaning,
            "Dividends_Flow": dividends_flow
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