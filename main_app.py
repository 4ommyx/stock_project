from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from Func_app.config import SET50_TICKERS

# --- Import Logic Modules ---
from Func_app.calculate_text import optimize_dividend_tax 
from Func_app.Scoring.t_dts_socring import analyze_stock_tdts
from Func_app.Scoring.tema_socring import analyze_stock_tema
from Func_app.Scoring.main_scoring import process_cluster_and_score
from Func_app.TA.technical_analysis import analyze_technical_batch, get_technical_history

app = FastAPI()

# ======================================================
# GLOBAL CACHES: ถังเก็บข้อมูลหลัก 3 ใบ
# ======================================================
CACHE_SCORING: Dict[str, dict] = {} # คะแนนรวมและ Clustering
CACHE_TDTS: Dict[str, list] = {}    # ประวัติ T-DTS (Raw Data)
CACHE_TEMA: Dict[str, list] = {}    # ประวัติ TEMA (Raw Data)
TECHNICAL_CACHE: Dict[str, list] = {} # MACD/RSI (Historical Data)

@app.get("/")
def home():
    return {
        "status": "Online",
        "cache_status": {
            "scoring_count": len(CACHE_SCORING),
            "technical_count": len(TECHNICAL_CACHE)
        }
    }

# --- Pydantic Models ---
class TaxInput(BaseModel):
    base_net_income: float
    dividend_amount: float
    corporate_tax_rate: float

class BatchInput(BaseModel):
    start_year: int = Field(2022, description="ปีเริ่มต้นการวิเคราะห์")
    end_year: int = Field(2024, description="ปีสิ้นสุดการวิเคราะห์")
    window: int = Field(15, description="TEMA Window")
    threshold: float = Field(20.0, description="เกณฑ์ตัด Outlier")
    
class TechnicalBatchInput(BaseModel):
    start_year: int = Field(2022, description="ปีเริ่มต้นการดึงข้อมูล")


# ======================================================
# MASTER POST ENDPOINT (Scoring & Clustering)
# ======================================================

# Helper Function สำหรับรัน Batch ใน Background
def run_scoring_batch_analysis(payload_dict: Dict):
    """
    Background Task: รัน Clustering/Scoring และ Update Cache หลัก
    """
    global CACHE_SCORING, CACHE_TDTS, CACHE_TEMA
    
    # แปลง Dict กลับเป็น Input Object
    payload_obj = BatchInput(**payload_dict) 
    
    result = process_cluster_and_score(
        tickers=None, 
        start_year=payload_obj.start_year,
        end_year=payload_obj.end_year,
        window=payload_obj.window,
        threshold=payload_obj.threshold
    )
    
    if result.get('status') == 'success':
        # Update Caches ทั้ง 3 ใบ (Scoring, T-DTS Raw, TEMA Raw)
        CACHE_SCORING = {item['Stock']: item for item in result['data']}

        CACHE_TDTS = {}
        for item in result['raw_tdts']:
            stock = item['Stock'].upper().replace('.BK', '')
            if stock not in CACHE_TDTS: CACHE_TDTS[stock] = []
            CACHE_TDTS[stock].append(item)

        CACHE_TEMA = {}
        for item in result['raw_tema']:
            stock = item['Stock'].upper().replace('.BK', '')
            if stock not in CACHE_TEMA: CACHE_TEMA[stock] = []
            CACHE_TEMA[stock].append(item)
        
        print(f"CACHE: Scoring/T-DTS/TEMA Update SUCCESS - {len(CACHE_SCORING)} stocks.")
    else:
        print(f"CACHE: Scoring Failed - {result.get('message')}")
        

@app.post("/main_app/update_scoring_cache")
def api_update_scoring_cache(payload: BatchInput, background_tasks: BackgroundTasks):
    """
    [POST] สั่งคำนวณ Clustering/Scoring/T-DTS/TEMA ทั้งหมดใน Background (Non-Blocking)
    """
    background_tasks.add_task(run_scoring_batch_analysis, payload_dict=payload.model_dump())
    
    return {
        "status": "processing", 
        "message": "Scoring and T-DTS/TEMA cache update started in background."
    }

# ======================================================
# TECHNICAL INDICATOR ENDPOINTS
# ======================================================

# Helper Function สำหรับรัน Technical Batch ใน Background
def run_technical_batch_analysis(start_year: int):
    """
    Background Task: รัน MACD/RSI Batch Analysis
    """
    global TECHNICAL_CACHE
    result = analyze_technical_batch(start_year=start_year)
    
    if result.get('status') == 'success':
        # เก็บผลลัพธ์ทั้งหมด (ประวัติรายวัน) ลง Cache
        TECHNICAL_CACHE = result['data']
        print(f"TECHNICAL CACHE: MACD/RSI Update SUCCESS - {len(TECHNICAL_CACHE)} stocks.")
    else:
        print(f"TECHNICAL CACHE: MACD/RSI Failed - {result.get('message')}")

@app.post("/main_app/update_indicator_cache")
def api_update_indicator_cache(payload: TechnicalBatchInput, background_tasks: BackgroundTasks):
    """
    [POST] คำนวณ MACD/RSI ของ SET50 ทั้งหมดตั้งแต่ปี 2022 แล้วเก็บลง Cache
    """
    background_tasks.add_task(run_technical_batch_analysis, start_year=payload.start_year)
    
    return {
        "status": "processing", 
        "message": f"Technical indicator analysis started from {payload.start_year} in background."
    }

@app.get("/main_app/technical_history/{symbol}")
def api_get_technical_history(symbol: str):
    """
    [GET] ดึง MACD/RSI รายวันย้อนหลัง 1 ปี จาก Cache (Fast Lookup)
    """
    from dateutil.relativedelta import relativedelta
    from datetime import date

    stock_key = symbol.upper().replace('.BK', '')
    
    if stock_key not in TECHNICAL_CACHE:
        raise HTTPException(status_code=404, detail="Technical history not in cache. Please run POST /update_indicator_cache first.")
        
    # Logic ในการกรองเอาเฉพาะข้อมูลย้อนหลัง 1 ปีจาก Cache
    full_history = TECHNICAL_CACHE[stock_key]
    
    # กำหนดวันที่เริ่มต้นคือ 1 ปีที่แล้ว
    one_year_ago = (date.today() - relativedelta(years=1)).strftime('%Y-%m-%d')
    
    filtered_data = [
        record for record in full_history
        if record['Date'] >= one_year_ago
    ]
    
    return {
        "status": "success",
        "symbol": stock_key,
        "source": "cache",
        "period": "1 year history",
        "data": filtered_data
    }

# ======================================================
# INDIVIDUAL GET ENDPOINTS (Check Cache First)
# ======================================================

@app.post("/main_app/calculate_tax")
def api_calculate_tax(payload: TaxInput):
    """คำนวณภาษีเงินปันผล (ไม่ใช้ Cache)"""
    return optimize_dividend_tax(payload.base_net_income, payload.dividend_amount, payload.corporate_tax_rate)

# [UPDATED] ใช้ Path Parameter {symbol}
@app.get("/main_app/stock_recommendation/{symbol}")
def api_get_stock_score(symbol: str):
    """
    ดึงคะแนน Clustering/Total Score (จาก CACHE_SCORING)
    รองรับการดึงหุ้นรายตัว (เช่น KBANK) หรือพิมพ์ 'ALL' เพื่อดึง SET50 ทั้งหมด
    """
    
    if not CACHE_SCORING:
        raise HTTPException(status_code=400, detail="Scoring cache is empty. Please run POST /update_scoring_cache first.")
        
    symbol_upper = symbol.upper()
    
    # 1. Logic สำหรับดึงหุ้นทั้งหมด (ALL)
    if symbol_upper == 'SET50':
        # แปลง Dict เป็น List แล้วเรียงตาม Total_Score (%) จากมากไปน้อย
        all_stocks = list(CACHE_SCORING.values())
        
        try:
            sorted_stocks = sorted(all_stocks, key=lambda x: x.get('Total_Score (%)', -999), reverse=True)
        except TypeError:
            # กรณีข้อมูลไม่สมบูรณ์
            raise HTTPException(status_code=500, detail="Data integrity error in cache. Total_Score is missing or invalid.")
        
        return {
            "status": "success", 
            "source": "cache", 
            "count": len(sorted_stocks),
            "data": sorted_stocks
        }
        
    # 2. Logic สำหรับดึงหุ้นรายตัว
    else:
        stock_key = symbol_upper.replace('.BK', '')
        
        if stock_key in CACHE_SCORING:
            return {"status": "success", "source": "cache", "data": CACHE_SCORING[stock_key]}
        else:
            raise HTTPException(status_code=404, detail=f"Stock '{stock_key}' not found in SET50 analysis results.")

# --- T-DTS GET (Check Cache, Fallback to Live) ---
def format_tdts_cache_response(stock_key, raw_data, threshold):
    import pandas as pd
    df = pd.DataFrame(raw_data)
    # T_DTS เป็น T-DTS ใน source
    is_outlier = (df['T-DTS'] < -threshold) | (df['T-DTS'] > threshold)
    return {
        "status": "success", "source": "cache", "symbol": stock_key,
        "data": {
            "raw_data": df.to_dict(orient='records'),
            "clean_data": df[~is_outlier].to_dict(orient='records'),
            "unclean_data": df[is_outlier].to_dict(orient='records')
        }
    }

@app.get("/main_app/analyze_tdts/{input_stock}")
def api_analyze_tdts(input_stock: str, threshold: float = 10.0, start_year: int = 2022, end_year: int = 2024):
    stock_key = input_stock.upper().replace('.BK', '')
    
    if stock_key in CACHE_TDTS:
        return format_tdts_cache_response(stock_key, CACHE_TDTS[stock_key], threshold)
    
    # Fallback to Live Calculation
    return analyze_stock_tdts(input_stock, start_year, end_year, threshold)

# --- TEMA GET (Check Cache, Fallback to Live) ---
def format_tema_cache_response(stock_key, raw_data, threshold):
    import pandas as pd
    df = pd.DataFrame(raw_data)
    is_outlier = (df['Ret_Bf_TEMA (%)'].abs() > threshold) | (df['Ret_Af_TEMA (%)'].abs() > threshold)
    return {
        "status": "success", "source": "cache", "symbol": stock_key,
        "data": {
            "raw_data": df.to_dict(orient='records'),
            "clean_data": df[~is_outlier].to_dict(orient='records'),
            "unclean_data": df[is_outlier].to_dict(orient='records')
        }
    }

@app.get("/main_app/analyze_tema/{input_stock}")
def api_analyze_tema(input_stock: str, threshold: float = 20.0, start_year: int = 2022, end_year: int = 2024, window: int = 15):
    stock_key = input_stock.upper().replace('.BK', '')
    
    if stock_key in CACHE_TEMA:
        return format_tema_cache_response(stock_key, CACHE_TEMA[stock_key], threshold)
        
    # Fallback to Live Calculation
    return analyze_stock_tema([input_stock], start_year, end_year, threshold, window)