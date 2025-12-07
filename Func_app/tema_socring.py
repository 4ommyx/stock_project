import yfinance as yf
import pandas as pd
from datetime import datetime

# รายชื่อหุ้น SET50 (Default list)
SET50_TICKERS = [
    "ADVANC.BK","AOT.BK","AWC.BK","BANPU.BK","BBL.BK","BDMS.BK","BEM.BK","BGRIM.BK","BH.BK","BJC.BK",
    "BPP.BK","CPALL.BK","CPF.BK","CPN.BK","CRC.BK","DELTA.BK","EGCO.BK","ESSO.BK","GULF.BK","HMPRO.BK",
    "IRPC.BK","KBANK.BK","KTB.BK","KTC.BK","LH.BK","MINT.BK","MTC.BK","OR.BK","OSP.BK",
    "PTT.BK","PTTEP.BK","PTTGC.BK","RATCH.BK","SAWAD.BK","SCB.BK","SCC.BK","SCGP.BK","TISCO.BK","TLI.BK",
    "TOP.BK","TTB.BK","TU.BK","VGI.BK","WHA.BK","GLOBAL.BK","BAM.BK","CPAXT.BK","GPSC.BK","BLA.BK"
]

def calculate_tema(series, span):
    """ฟังก์ชันช่วยคำนวณ TEMA"""
    ema1 = series.ewm(span=span, adjust=False).mean()
    ema2 = ema1.ewm(span=span, adjust=False).mean()
    ema3 = ema2.ewm(span=span, adjust=False).mean()
    return (3 * ema1) - (3 * ema2) + ema3

def analyze_stock_tema(symbol: str, start_year: int = 2022, end_year: int = 2024, threshold: float = 10.0, window: int = 15):
    """
    Main Logic: ดึงข้อมูลและคำนวณ TEMA รอบวัน XD พร้อมแยก Clean/Outlier
    threshold: ใช้ตัด outlier สำหรับค่า % Return (ถ้าเปลี่ยนแปลงเกิน % นี้ถือว่าผิดปกติ)
    """
    tickers = [symbol] if symbol else SET50_TICKERS
    all_data = []

    # วนลูปหุ้นแต่ละตัว
    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            
            # 1. ดึงข้อมูล
            fetch_start = f"{start_year - 1}-01-01" 
            history = stock.history(start=fetch_start, end=f"{end_year+1}-12-31")
            dividends = stock.dividends

            if history.empty: continue

            # 2. คำนวณ TEMA
            history['TEMA'] = calculate_tema(history['Close'], span=window)

            # 3. จัดการ Timezone
            history.index = history.index.normalize()
            if not dividends.empty:
                dividends.index = dividends.index.normalize()

            # กรองปันผล
            mask = (dividends.index.year >= start_year) & (dividends.index.year <= end_year)
            target_dividends = dividends.loc[mask]

            if target_dividends.empty: continue

            # 4. วนลูปวิเคราะห์ XD
            for date, amount in target_dividends.items():
                ex_date = date
                if ex_date not in history.index: continue

                loc_xd = history.index.get_loc(ex_date)

                # Boundary Check
                if (loc_xd - window < 0) or (loc_xd + window >= len(history)):
                    continue

                # ดึงค่า TEMA
                tema_prev_win = history.iloc[loc_xd - window]['TEMA']
                tema_pre_xd   = history.iloc[loc_xd - 1]['TEMA']
                tema_xd       = history.iloc[loc_xd]['TEMA']
                tema_post_win = history.iloc[loc_xd + window]['TEMA']
                
                actual_price_xd = history.iloc[loc_xd]['Close']

                # คำนวณ Return (%)
                ret_bf = ((tema_pre_xd - tema_prev_win) / tema_prev_win) * 100
                ret_af = ((tema_post_win - tema_xd) / tema_xd) * 100

                all_data.append({
                    'Stock': symbol.replace('.BK', ''),
                    'Year': ex_date.year,
                    'Ex_Date': ex_date.strftime('%Y-%m-%d'),
                    'DPS': amount,
                    'Price_Close': round(actual_price_xd, 2),
                    'Price_TEMA': round(tema_xd, 2),
                    'Ret_Bf_TEMA_Percent': round(ret_bf, 2),
                    'Ret_Af_TEMA_Percent': round(ret_af, 2)
                })

        except Exception as e:
            print(f"Error checking {symbol}: {e}")
            continue

    if not all_data:
        return {"status": "error", "message": "No data found or insufficient history"}

    # --- ส่วนการจัด Group Data (Clean vs Outlier) ---
    df = pd.DataFrame(all_data)
    df = df.sort_values(by=['Stock', 'Ex_Date'], ascending=[True, False])

    # Logic ตัด Outlier: ถ้า % การเปลี่ยนแปลง (Before หรือ After) มากกว่า threshold (คิดเป็น absolute)
    # เช่น threshold=20 คือห้ามบวกเกิน 20% หรือลบเกิน -20%
    is_outlier = (df['Ret_Bf_TEMA_Percent'].abs() > threshold) | (df['Ret_Af_TEMA_Percent'].abs() > threshold)

    df_clean = df[~is_outlier]
    df_outliers = df[is_outlier]

    return {
        "status": "success",
        "params": {
            "tickers_count": len(tickers),
            "start_year": start_year,
            "end_year": end_year,
            "window": window,
            "threshold": threshold
        },
        "summary": {
            "total_count": len(df),
            "clean_count": len(df_clean),
            "outlier_count": len(df_outliers)
        },
        "data": {
            "clean_data": df_clean.to_dict(orient='records'),
            "outliers": df_outliers.to_dict(orient='records'),
            "raw_data": df.to_dict(orient='records')
        }
    }