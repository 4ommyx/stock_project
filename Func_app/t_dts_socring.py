# ไฟล์: Func_app/tdts_logic.py
import yfinance as yf
import pandas as pd
from datetime import datetime

def analyze_stock_tdts(symbol: str, start_year: int = 2022, end_year: int = 2024, threshold: float = 10.0):
    """
    ฟังก์ชันหลัก: ดึงข้อมูล, คำนวณ T-DTS, และแยก Outlier
    """
    all_data = []
    
    try:
        # 1. ดึงข้อมูลจาก Yahoo Finance
        stock = yf.Ticker(symbol)
        history = stock.history(start=f"{start_year}-01-01", end=f"{end_year+1}-12-31")
        dividends = stock.dividends

        # จัดการ Timezone และ Index
        if not history.empty: history.index = history.index.normalize()
        if not dividends.empty: dividends.index = dividends.index.normalize()

        # กรองเฉพาะช่วงปีที่กำหนด
        mask = (dividends.index.year >= start_year) & (dividends.index.year <= end_year)
        target_dividends = dividends.loc[mask]

        if target_dividends.empty:
            return {"status": "error", "message": "No dividend data found"}

        # 2. Loop คำนวณ T-DTS
        for date, amount in target_dividends.items():
            ex_date = date
            if ex_date not in history.index: continue

            loc_ex = history.index.get_loc(ex_date)
            if loc_ex == 0: continue

            loc_cum = loc_ex - 1
            p_ex = history.iloc[loc_ex]['Close']
            p_cum = history.iloc[loc_cum]['Close']
            
            # สูตรคำนวณ
            dy = (amount / p_cum) * 100
            pd_pct = ((p_cum - p_ex) / p_cum) * 100
            t_dts = (pd_pct / dy) if dy != 0 else 0

            all_data.append({
                'Stock': symbol,
                'Year': ex_date.year,
                'Ex_Date': ex_date.strftime('%Y-%m-%d'),
                'DPS': amount,
                'P_cum': p_cum,
                'P_ex': p_ex,
                'DY_percent': round(dy, 2),
                'PD_percent': round(pd_pct, 2),
                'T_DTS': round(t_dts, 4)
            })
            
        if not all_data:
            return {"status": "error", "message": "Insufficient price data for calculation"}

        # 3. แปลงเป็น DataFrame เพื่อแยก Outlier
        df = pd.DataFrame(all_data)
        
        # Logic การแยก (Before Drop / After Drop)
        is_outlier = (df['T_DTS'] < -threshold) | (df['T_DTS'] > threshold)
        
        df_clean = df[~is_outlier]       # ข้อมูลปกติ (After Drop)
        df_outliers = df[is_outlier]     # ข้อมูลผิดปกติ (Outliers)

        # 4. ส่งค่ากลับ (Return Dictionary)
        return {
            "status": "success",
            "symbol": symbol,
            "summary": {
                "total_count": len(df),
                "clean_count": len(df_clean),
                "outlier_count": len(df_outliers)
            },
            "data": {
                "raw_data": df.to_dict(orient='records'),      # ก่อนตัด
                "clean_data": df_clean.to_dict(orient='records'),  # หลังตัด
                "outliers": df_outliers.to_dict(orient='records')  # ตัวที่ถูกตัด
            }
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}