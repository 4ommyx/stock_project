import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from Func_app.config import SET50_TICKERS

# --- Helper Functions ---

def dayofyear_to_str(doy, year=2000):
    if pd.isna(doy): return None
    base = pd.Timestamp(f'{year}-01-01')
    return (base + pd.to_timedelta(int(round(doy))-1, unit='D')).strftime('%b-%d')

def tag_dividends_per_year(df_div):
    """
    ติด Tag โดยแบ่งตามช่วงเดือน (Seasonality) เพื่อแก้ปัญหาปีที่จ่ายไม่ครบ
    Tag 1: ช่วงครึ่งปีแรก (Jan - Jun)
    Tag 2: ช่วงครึ่งปีหลัง (Jul - Dec)
    """
    df = df_div.copy()
    df = df[df['Dividends'] != 0].copy()
    if df.empty: return df
    
    idx = pd.to_datetime(df.index)
    if idx.tz is not None: idx = idx.tz_convert(None)
    df.index = idx
    
    df['year'] = df.index.year
    df['month'] = df.index.month
    df = df.sort_index()
    
    # [NEW LOGIC] แบ่งตามเดือนแทนลำดับ
    # เดือน 1-6 ให้เป็น Tag 1, เดือน 7-12 ให้เป็น Tag 2
    # ใช้ np.where เพื่อความเร็ว (ต้อง import numpy as np ด้านบน)
    df['tag'] = np.where(df['month'] <= 6, 1, 2)
    
    return df

def calculate_days_to_dividend(avg_month_day_str):
    """คำนวณวันนับถอยหลัง (Countdown)"""
    if not avg_month_day_str: return None
    
    current_date = datetime.now()
    current_year = current_date.year
    
    try:
        # ลองเทียบกับปีนี้
        target_date = datetime.strptime(f"{current_year}-{avg_month_day_str}", "%Y-%b-%d")
        diff = (target_date - current_date).days
        
        # ถ้าเลยวันไปแล้ว (+1 ปี)
        if diff < 0:
            target_next = datetime.strptime(f"{current_year + 1}-{avg_month_day_str}", "%Y-%b-%d")
            diff = (target_next - current_date).days
            
        return diff
    except ValueError:
        return None

# --- Core Analysis Functions ---

def analyze_stock_seasonality(symbol: str):
    """
    วิเคราะห์หุ้นรายตัว: หา Min, Max, Avg Date และ Countdown
    """
    try:
        clean_symbol = symbol.upper().replace('.BK', '')
        ticker = f"{clean_symbol}.BK"
        
        stock = yf.Ticker(ticker)
        # ดึง 10 ปีเพื่อให้เห็น Min/Max ที่มีความหมาย
        hist = stock.history(period="10y") 
        
        if hist.empty:
            return None
            
        div_df = hist[['Dividends']]
        tagged_df = tag_dividends_per_year(div_df)
        
        if tagged_df.empty or 'tag' not in tagged_df.columns:
            return None

        result_data = {'Symbol': clean_symbol}
        
        # วนลูปหา Tag 1 (ต้นปี) และ Tag 2 (กลางปี/ท้ายปี)
        for t in [1, 2]:
            subset = tagged_df[tagged_df['tag'] == t].copy()
            
            if not subset.empty:
                # [FIXED] แปลง Index เป็น Series ก่อนคำนวณ .mean()
                doy_values = subset.index.dayofyear
                doy_series = pd.Series(doy_values)
                
                # ตอนนี้คำนวณได้แล้ว
                avg_str = dayofyear_to_str(doy_series.mean())
                min_str = dayofyear_to_str(doy_series.min())
                max_str = dayofyear_to_str(doy_series.max())
                
                # คำนวณ Countdown
                countdown = calculate_days_to_dividend(avg_str)
                
                result_data[f'Tag{t}'] = {
                    "Stats": {
                        "Min_Date": min_str,
                        "Max_Date": max_str,
                        "Avg_Date": avg_str,
                        "Data_Points": len(subset)
                    },
                    "Countdown": {
                        "Avg_Date": avg_str,
                        "Days_Remaining": countdown
                    }
                }
            else:
                result_data[f'Tag{t}'] = None
                
        return result_data

    except Exception as e:
        print(f"Error seasonality {symbol}: {e}")
        return None

def analyze_seasonality_batch():
    """
    รัน Batch สำหรับ SET50 ทั้งหมด
    """
    results = {}
    print(f"Analyzing Seasonality for {len(SET50_TICKERS)} stocks...")
    
    for symbol in SET50_TICKERS:
        data = analyze_stock_seasonality(symbol)
        if data:
            clean_sym = data['Symbol']
            results[clean_sym] = data
            
    return {
        "status": "success",
        "count": len(results),
        "data": results
    }