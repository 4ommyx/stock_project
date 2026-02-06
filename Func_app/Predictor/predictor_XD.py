import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta # [เพิ่ม] timedelta
from Func_app.config import SET50_TICKERS

# --- Helper Functions ---

def dayofyear_to_str(doy, year=2000):
    if pd.isna(doy): return None
    base = pd.Timestamp(f'{year}-01-01')
    return (base + pd.to_timedelta(int(round(doy))-1, unit='D')).strftime('%d/%m')

def tag_dividends_per_year(df_div):
    df = df_div.copy()
    df = df[df['Dividends'] != 0].copy()
    if df.empty: return df
    
    idx = pd.to_datetime(df.index)
    if idx.tz is not None: idx = idx.tz_convert(None)
    df.index = idx
    
    df['year'] = df.index.year
    df['month'] = df.index.month
    df = df.sort_index()
    
    df['tag'] = np.where(df['month'] <= 6, 1, 2)
    
    return df

def calculate_days_to_dividend(avg_month_day_str):
    """
    คำนวณวันนับถอยหลัง และ วันที่ที่จะถึง (ISO Format)
    """
    if not avg_month_day_str: return None, None
    
    current_date = datetime.now()
    current_year = current_date.year
    
    try:
        # Input format: DD/MM (e.g., 15/04)
        target_date = datetime.strptime(f"{current_year}/{avg_month_day_str}", "%Y/%d/%m")
        
        # ถ้าวันที่ของปีนี้ผ่านไปแล้ว ให้นับเป็นปีหน้า
        if target_date < current_date:
            target_date = datetime.strptime(f"{current_year + 1}/{avg_month_day_str}", "%Y/%d/%m")
            
        diff = (target_date - current_date).days
        
        return diff, target_date.strftime('%Y-%m-%d')
        
    except ValueError:
        return None, None

# --- Core Analysis Functions ---

def analyze_stock_seasonality(symbol: str):
    try:
        clean_symbol = symbol.upper().replace('.BK', '')
        ticker = f"{clean_symbol}.BK"
        
        stock = yf.Ticker(ticker)
        # ดึง 5 ปี เพื่อหาค่าเฉลี่ย
        hist = stock.history(period="5y") 
        
        if hist.empty:
            return None
            
        div_df = hist[['Dividends']]
        tagged_df = tag_dividends_per_year(div_df)
        
        if tagged_df.empty or 'tag' not in tagged_df.columns:
            return None

        result_data = {'Symbol': clean_symbol}
        
        for t in [1, 2]:
            subset = tagged_df[tagged_df['tag'] == t].copy()
            
            if not subset.empty:
                # 1. หาค่าเฉลี่ยวันที่ (XD Date)
                doy_values = subset.index.dayofyear
                doy_series = pd.Series(doy_values) 
                
                avg_str = dayofyear_to_str(doy_series.mean())
                min_str = dayofyear_to_str(doy_series.min())
                max_str = dayofyear_to_str(doy_series.max())
                
                # 2. คำนวณวันที่ XD ถัดไป (Predicted XD)
                days_remaining, next_date_iso = calculate_days_to_dividend(avg_str)
                
                # ======================================================
                # [NEW] คำนวณเงินปันผล + วันจ่ายเงิน (Pay Date)
                # ======================================================
                
                # lass dividend amount
                last_dividend_amt = subset['Dividends'][-1]
                
                
                # B. ประมาณการวันจ่ายเงิน (Estimated Pay Date)
                # ปกติหุ้นไทยจ่ายเงินหลัง XD ประมาณ 15-20 วัน -> ใช้ค่ากลางคือ +18 วัน
                est_pay_date_iso = None
                if next_date_iso:
                    xd_date_obj = datetime.strptime(next_date_iso, "%Y-%m-%d")
                    pay_date_obj = xd_date_obj + timedelta(days=18)
                    est_pay_date_iso = pay_date_obj.strftime("%Y-%m-%d")

                # ======================================================

                result_data[f'Tag{t}'] = {
                    "Stats": {
                        "Min_Date": min_str,
                        "Max_Date": max_str,
                        "Avg_Date": avg_str,
                        "Data_Points": len(subset)
                    },
                    "Countdown": {
                        "Avg_Date": avg_str,          # วัน XD เฉลี่ย (DD/MM)
                        "Next_XD_Date": next_date_iso, # วัน XD ที่คาดการณ์ (YYYY-MM-DD)
                        "Days_Remaining": days_remaining,
                        
                        "Est_Dividend_Baht": round(last_dividend_amt, 4), # เงินปันผล (บาท)
                        "Est_Pay_Date": est_pay_date_iso                 # วันจ่ายเงิน (YYYY-MM-DD)
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