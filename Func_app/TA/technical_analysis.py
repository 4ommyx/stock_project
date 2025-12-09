import yfinance as yf
import pandas as pd
import numpy as np
from Func_app.config import SET50_TICKERS

# ==========================================
# 1. Core Calculation Logic (สูตรคำนวณ)
# ==========================================

def calculate_rsi(series, period=14):
    """
    คำนวณ RSI (Relative Strength Index)
    สูตร: Wilder's Smoothing (Exponential)
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
    คำนวณ MACD (Moving Average Convergence Divergence)
    Return: MACD Line, Signal Line, Histogram
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

# ==========================================
# 2. Function: Get History (สำหรับกราฟรายตัว)
# ==========================================

def get_technical_history(symbol: str, period: str = "1y"):
    """
    ดึงข้อมูลราคา + MACD + RSI แบบรายวัน (Time Series)
    เหมาะสำหรับนำไปพลอตกราฟย้อนหลัง
    """
    try:
        # จัดการชื่อหุ้น
        clean_symbol = symbol.upper().replace('.BK', '')
        ticker = f"{clean_symbol}.BK"
        
        # ดึงข้อมูลย้อนหลัง
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        
        if df.empty:
            return {"status": "error", "message": f"No data found for {symbol}"}
            
        # คำนวณ Indicators (ใส่ลงไปใน DataFrame เลย)
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'], df['Signal'], df['Hist'] = calculate_macd(df['Close'])
        
        # ลบค่า NaN ช่วงต้น (ที่คำนวณ Indicator ไม่ได้)
        df = df.dropna()
        
        # แปลงข้อมูลเป็น List of Dicts
        history_data = []
        for date, row in df.iterrows():
            # แปลงสัญญาณ MACD รายวัน (Optional)
            signal_status = "Neutral"
            if row['Hist'] > 0: signal_status = "Bullish"
            elif row['Hist'] < 0: signal_status = "Bearish"

            history_data.append({
                "Date": date.strftime('%Y-%m-%d'),
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
            "period": period,
            "count": len(history_data),
            "data": history_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 3. Function: Snapshot (สำหรับตารางสรุป SET50)
# ==========================================

def get_technical_snapshot(tickers: list = None):
    """
    ดึงค่า RSI/MACD ล่าสุด ของหุ้นหลายตัว (Batch)
    เหมาะสำหรับทำตาราง Screener หรือ Dashboard หน้าแรก
    """
    target_tickers = tickers if tickers else SET50_TICKERS
    results = []
    
    for symbol in target_tickers:
        try:
            clean_symbol = symbol.replace('.BK', '')
            ticker = f"{clean_symbol}.BK"
            
            stock = yf.Ticker(ticker)
            # ดึงแค่ 6 เดือนก็พอสำหรับการคำนวณค่าปัจจุบัน
            df = stock.history(period="6mo")
            
            if df.empty: continue
            
            # คำนวณ
            df['RSI'] = calculate_rsi(df['Close'])
            df['MACD'], df['Signal'], df['Hist'] = calculate_macd(df['Close'])
            
            # เอาค่าล่าสุด
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # วิเคราะห์สัญญาณ Cross
            macd_signal = "Neutral"
            if last['MACD'] > last['Signal'] and prev['MACD'] <= prev['Signal']:
                macd_signal = "Golden Cross (Buy)"
            elif last['MACD'] < last['Signal'] and prev['MACD'] >= prev['Signal']:
                macd_signal = "Dead Cross (Sell)"
            
            rsi_status = "Neutral"
            if last['RSI'] >= 70: rsi_status = "Overbought"
            elif last['RSI'] <= 30: rsi_status = "Oversold"
            
            results.append({
                "Stock": clean_symbol,
                "Date": last.name.strftime('%Y-%m-%d'),
                "Close": round(last['Close'], 2),
                "RSI": round(last['RSI'], 2),
                "RSI_Status": rsi_status,
                "MACD_Signal": macd_signal,
                "MACD_Hist": round(last['Hist'], 4)
            })
            
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            continue
            
    return {
        "status": "success",
        "count": len(results),
        "data": results
    }