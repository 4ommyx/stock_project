import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from Func_app.config import SET50_TICKERS

# ==========================================
# 1. Core Calculation Logic (RSI & MACD)
# ==========================================

def calculate_rsi(series, period=14):
    """
    คำนวณ RSI (Relative Strength Index) โดยใช้ Wilder's Smoothing
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    """
    คำนวณ MACD Line, Signal Line, Histogram
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

# ==========================================
# 2. Function: Get History (Single Stock Time Series)
# ==========================================

def get_technical_history(symbol: str, start_date: str, end_date: str):
    """
    ดึงข้อมูลราคา + MACD + RSI แบบรายวัน (Time Series)
    ใช้สำหรับคำนวณ Batch และเป็น Fallback สำหรับ GET รายตัว
    """
    try:
        clean_symbol = symbol.upper().replace('.BK', '')
        ticker = f"{clean_symbol}.BK"
        
        # [CRITICAL STEP] เผื่อช่วงเวลา 6 เดือนก่อน start_date เพื่อให้คำนวณ MACD/RSI ได้
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        fetch_start = (start_dt - relativedelta(months=6)).strftime('%Y-%m-%d')
        
        stock = yf.Ticker(ticker)
        df = stock.history(start=fetch_start, end=end_date)
        
        if df.empty:
            return {"status": "error", "message": f"No data found for {symbol}"}
            
        # คำนวณ Indicators
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'], df['Signal'], df['Hist'] = calculate_macd(df['Close'])
        
        # ลบค่า NaN ช่วงแรก และ กรองวันที่ตามที่ User Request (start_date ถึง end_date)
        df = df.dropna()
        df = df[df.index >= start_date]

        history_data = []
        for date_index, row in df.iterrows():
            signal_status = "Neutral"
            if row['Hist'] > 0: signal_status = "Bullish"
            elif row['Hist'] < 0: signal_status = "Bearish"

            history_data.append({
                "Date": date_index.strftime('%Y-%m-%d'),
                "Close": round(row['Close'], 2),
                "RSI": round(row['RSI'], 2),
                "MACD": round(row['MACD'], 4),
                "Signal": round(row['Signal'], 4),
                "Hist": round(row['Hist'], 4),
                "Momentum": signal_status
            })
            
        return {
            "status": "success",
            "symbol": clean_symbol,
            "count": len(history_data),
            "data": history_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 3. Function: Batch Analysis (สำหรับ Cache)
# ==========================================

def analyze_technical_batch(start_year: int):
    """
    คำนวณ MACD/RSI ของหุ้น SET50 ทั้งหมดตั้งแต่ปีเริ่มต้นจนถึงปัจจุบัน
    ใช้สำหรับ Endpoint POST /update_indicator_cache
    """
    target_tickers = SET50_TICKERS
    
    # กำหนดช่วงเวลา: 2022-01-01 จนถึงวันปัจจุบัน
    start_date = f"{start_year}-01-01"
    end_date = date.today().strftime('%Y-%m-%d')
    
    full_cache_data = {}
    
    print(f"Starting technical batch analysis from {start_date} to {end_date}...")
    
    for symbol in target_tickers:
        # เรียกใช้ get_technical_history เพื่อคำนวณประวัติของแต่ละตัว
        res = get_technical_history(symbol, start_date=start_date, end_date=end_date)
        if res['status'] == 'success':
            # เก็บผลลัพธ์ทั้งหมด (ประวัติรายวันตั้งแต่ 2022) ลงใน Dictionary Keyed by Symbol
            full_cache_data[res['symbol']] = res['data']
            
    return {
        "status": "success",
        "start_date": start_date,
        "end_date": end_date,
        "data": full_cache_data
    }