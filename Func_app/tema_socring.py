import yfinance as yf
import pandas as pd
from Func_app.config import SET50_TICKERS # Import จากไฟล์กลาง

def calculate_tema(series, span):
    """ฟังก์ชันช่วยคำนวณ TEMA"""
    ema1 = series.ewm(span=span, adjust=False).mean()
    ema2 = ema1.ewm(span=span, adjust=False).mean()
    ema3 = ema2.ewm(span=span, adjust=False).mean()
    return (3 * ema1) - (3 * ema2) + ema3

def analyze_stock_tema(tickers: list = None, start_year: int = 2022, end_year: int = 2024, threshold: float = 0.0, window: int = 15):
    """
    Main Logic: คำนวณ TEMA สำหรับรายชื่อหุ้นที่ระบุ
    """
    target_tickers = tickers if tickers else SET50_TICKERS
    all_data = []

    for symbol in target_tickers:
        try:
            # ป้องกันกรณีส่ง List ซ้อน List
            if isinstance(symbol, list): symbol = symbol[0]
            
            # ลบ .BK ออกชั่วคราวเพื่อความสะอาดของข้อมูล
            clean_symbol = symbol.upper()

            stock = yf.Ticker(clean_symbol)
            
            # 1. ดึงข้อมูล
            fetch_start = f"{start_year - 1}-01-01" 
            history = stock.history(start=fetch_start, end=f"{end_year+1}-12-31")
            dividends = stock.dividends

            if history.empty: continue

            # 2. คำนวณ TEMA
            history['TEMA'] = calculate_tema(history['Close'], span=window)
            history.index = history.index.normalize()
            
            if not dividends.empty:
                dividends.index = dividends.index.normalize()

            # กรองปันผลตามปีที่ระบุ
            mask = (dividends.index.year >= start_year) & (dividends.index.year <= end_year)
            target_dividends = dividends.loc[mask]

            if target_dividends.empty: continue

            # 3. วนลูปวิเคราะห์ XD
            for date, amount in target_dividends.items():
                ex_date = date
                if ex_date not in history.index: continue

                loc_xd = history.index.get_loc(ex_date)

                # Boundary Check (ต้องมีข้อมูลหน้า-หลัง ครบตาม Window)
                if (loc_xd - window < 0) or (loc_xd + window >= len(history)):
                    continue

                tema_prev_win = history.iloc[loc_xd - window]['TEMA']
                tema_pre_xd   = history.iloc[loc_xd - 1]['TEMA']
                tema_xd       = history.iloc[loc_xd]['TEMA']
                tema_post_win = history.iloc[loc_xd + window]['TEMA']
                
                actual_price_xd = history.iloc[loc_xd]['Close']

                # คำนวณ Return (%)
                ret_bf = ((tema_pre_xd - tema_prev_win) / tema_prev_win) * 100
                ret_af = ((tema_post_win - tema_xd) / tema_xd) * 100

                all_data.append({
                    'Stock': clean_symbol.replace('.BK', ''),
                    'Year': ex_date.year,
                    'Ex_Date': ex_date.strftime('%Y-%m-%d'),
                    'DPS': amount,
                    'Price_Close': round(actual_price_xd, 2),
                    'Price_TEMA': round(tema_xd, 2),
                    'Ret_Bf_TEMA (%)': round(ret_bf, 2), 
                    'Ret_Af_TEMA (%)': round(ret_af, 2)
                })

        except Exception as e:
            print(f"Error checking {symbol}: {e}")
            continue

    if not all_data:
        return {"status": "error", "message": "No data found or insufficient history"}

    # จัดการ Outlier
    df = pd.DataFrame(all_data)
    df = df.sort_values(by=['Stock', 'Ex_Date'], ascending=[True, False])

    is_outlier = (df['Ret_Bf_TEMA (%)'].abs() > threshold) | (df['Ret_Af_TEMA (%)'].abs() > threshold)
    
    # [UPDATED] Return 3 ส่วน: Raw, Clean, Unclean (เปลี่ยนชื่อจาก outliers เป็น unclean_data)
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