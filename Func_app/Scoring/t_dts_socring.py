import yfinance as yf
import pandas as pd
from datetime import datetime

def analyze_stock_tdts(symbol: str, start_year: int = 2022, end_year: int = 2024, threshold: float = 10.0):
    """
    Logic: คำนวณ T-DTS (Technical Dividend Trap Score) รายตัว
    """
    all_data = []
    
    try:
        # ป้องกันกรณีส่ง List เข้ามา
        if isinstance(symbol, list):
            symbol = symbol[0]
            
        # ทำความสะอาดชื่อหุ้น
        clean_symbol = symbol.upper()
        
        # 1. ดึงข้อมูล
        stock = yf.Ticker(clean_symbol)
        
        # ดึงเผื่อปีเริ่มต้นไป 1 ปี เพื่อหา P_cum
        history = stock.history(start=f"{start_year}-01-01", end=f"{end_year+1}-12-31")
        dividends = stock.dividends

        # จัดการ Timezone
        if not history.empty: 
            history.index = history.index.normalize()
        if not dividends.empty: 
            dividends.index = dividends.index.normalize()

        # กรองเฉพาะช่วงปีที่กำหนด
        mask = (dividends.index.year >= start_year) & (dividends.index.year <= end_year)
        target_dividends = dividends.loc[mask]

        if target_dividends.empty:
            return {"status": "error", "message": f"No dividend data found for {clean_symbol} in {start_year}-{end_year}"}

        # 2. Loop คำนวณ T-DTS
        for date, amount in target_dividends.items():
            ex_date = date
            if ex_date not in history.index: 
                continue

            loc_ex = history.index.get_loc(ex_date)
            if loc_ex == 0: 
                continue

            loc_cum = loc_ex - 1
            p_ex = history.iloc[loc_ex]['Close']
            p_cum = history.iloc[loc_cum]['Close']
            
            # สูตรคำนวณ
            dy = (amount / p_cum) * 100
            pd_pct = ((p_cum - p_ex) / p_cum) * 100
            
            # ป้องกันการหารด้วย 0
            t_dts = (pd_pct / dy) if dy != 0 else 0

            all_data.append({
                'Stock': clean_symbol.replace('.BK', ''), 
                'Year': ex_date.year,
                'Ex_Date': ex_date.strftime('%Y-%m-%d'),
                'DPS': amount,
                'P_cum': round(p_cum, 2),
                'P_ex': round(p_ex, 2),
                'DY (%)': round(dy, 2),
                'PD (%)': round(pd_pct, 2),
                'T-DTS': round(t_dts, 4)  # [FIX] ใช้ T_DTS (underscore) เพื่อลดปัญหา KeyError
            })
            
        if not all_data:
            return {"status": "error", "message": "Insufficient price data around XD dates"}

        # 3. จัดการ Data & Outlier
        df = pd.DataFrame(all_data)
        df = df.sort_values(by='Ex_Date', ascending=False)
        
        # Logic ตัด Outlier
        is_outlier = (df['T-DTS'] < -threshold) | (df['T-DTS'] > threshold)
        
        # [FIX] ส่งคืนค่า 3 ส่วน: Raw, Clean, Unclean
        return {
            "status": "success",
            "symbol": clean_symbol,
            "summary": {
                "total_count": len(df),
                "clean_count": len(df[~is_outlier]),
                "unclean_count": len(df[is_outlier])
            },
            "data": {
                "raw_data": df.to_dict(orient='records'),           # ข้อมูลดิบทั้งหมด
                "clean_data": df[~is_outlier].to_dict(orient='records'), # ข้อมูลที่ผ่านเกณฑ์
                "unclean_data": df[is_outlier].to_dict(orient='records') # ข้อมูล Outlier
            }
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}