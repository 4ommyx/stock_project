from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pandas as pd

# --- Local Modules (Logic) ---
from Func_app.config import SET50_TICKERS
from Func_app.calculate_text import optimize_dividend_tax 
from Func_app.Scoring.t_dts_socring import analyze_stock_tdts
from Func_app.Scoring.tema_socring import analyze_stock_tema
from Func_app.Scoring.main_scoring import process_cluster_and_score
from Func_app.TA.technical_analysis import analyze_technical_batch
from Func_app.Predictor.predictor_XD import analyze_seasonality_batch

app = FastAPI(
    title="Stock Analysis API",
    description="API for SET50 Stock Analysis: Scoring, Clustering, T-DTS, TEMA, and Technical Indicators",
    version="1.0.0"
)

# ======================================================
# 1. GLOBAL CACHES (In-Memory Database)
# ======================================================
CACHE_SCORING: Dict[str, dict] = {}   # Scoring Results & Cluster Info
CACHE_TDTS: Dict[str, list] = {}      # T-DTS Raw History
CACHE_TEMA: Dict[str, list] = {}      # TEMA Raw History
TECHNICAL_CACHE: Dict[str, list] = {} # MACD/RSI Historical Data
CACHE_SEASONALITY: Dict[str, dict] = {} # Seasonality Analysis

# ======================================================
# 2. PYDANTIC MODELS (Request Schemas)
# ======================================================
class TaxInput(BaseModel):
    base_net_income: float
    dividend_amount: float
    corporate_tax_rate: float

class BatchInput(BaseModel):
    start_year: int = Field(2022, description="Start Year")
    end_year: int = Field(2024, description="End Year")
    window: int = Field(15, description="TEMA Window")
    threshold: float = Field(20.0, description="Outlier Threshold (%)")

class TechnicalBatchInput(BaseModel):
    start_year: int = Field(2022, description="Start Year for Technical Data")

# ======================================================
# 3. GENERAL ENDPOINTS
# ======================================================
@app.get("/", tags=["General"])
def home():
    """Health Check & Cache Status"""
    return {
        "status": "Online",
        "timestamp": datetime.now(),
        "cache_status": {
            "scoring_count": len(CACHE_SCORING),
            "tdts_count": len(CACHE_TDTS),
            "tema_count": len(CACHE_TEMA),
            "technical_count": len(TECHNICAL_CACHE),
            "seasonality_count": len(CACHE_SEASONALITY)
        }
    }

@app.post("/main_app/calculate_tax", tags=["General"])
def api_calculate_tax(payload: TaxInput):
    """Calculate Dividend Tax Optimization"""
    return optimize_dividend_tax(
        payload.base_net_income, 
        payload.dividend_amount, 
        payload.corporate_tax_rate
    )

# ======================================================
# 4. SCORING & CLUSTERING (Batch & Get)
# ======================================================
@app.post("/main_app/update_scoring_cache", tags=["Scoring & Clustering"])
def api_update_scoring_cache(payload: BatchInput, background_tasks: BackgroundTasks):
    """
    [POST] Trigger Background Task to calculate Scores & Clusters for ALL SET50 stocks.
    """
    background_tasks.add_task(_run_scoring_batch_analysis, payload_dict=payload.model_dump())
    return {
        "status": "processing", 
        "message": "Scoring batch analysis started in background."
    }

@app.get("/main_app/stock_recommendation/{symbol}", tags=["Scoring & Clustering"])
def api_get_stock_score(symbol: str):
    """
    [GET] Retrieve Score & Cluster for a stock (or 'SET50' for all).
    """
    if not CACHE_SCORING:
        raise HTTPException(status_code=400, detail="Cache empty. Run POST /update_scoring_cache first.")
        
    symbol_upper = symbol.upper()
    
    # Case A: Get All SET50 Ranked
    if symbol_upper == 'SET50':
        all_stocks = list(CACHE_SCORING.values())
        sorted_stocks = sorted(all_stocks, key=lambda x: x.get('Total_Score (%)', -999), reverse=True)
        return {"status": "success", "source": "cache", "count": len(sorted_stocks), "data": sorted_stocks}
        
    # Case B: Get Single Stock
    stock_key = symbol_upper.replace('.BK', '')
    if stock_key in CACHE_SCORING:
        return {"status": "success", "source": "cache", "data": CACHE_SCORING[stock_key]}
    
    raise HTTPException(status_code=404, detail=f"Stock '{stock_key}' not found.")

# ======================================================
# 5. TECHNICAL ANALYSIS (Batch & Get)
# ======================================================
@app.post("/main_app/update_indicator_cache", tags=["Technical Analysis"])
def api_update_indicator_cache(payload: TechnicalBatchInput, background_tasks: BackgroundTasks):
    """
    [POST] Trigger Background Task to calculate MACD/RSI for ALL SET50 stocks.
    """
    background_tasks.add_task(_run_technical_batch_analysis, start_year=payload.start_year)
    return {
        "status": "processing", 
        "message": f"Technical analysis started from {payload.start_year} in background."
    }

@app.get("/main_app/technical_history/{symbol}", tags=["Technical Analysis"])
def api_get_technical_history(symbol: str):
    """
    [GET] Retrieve 1-Year Historical Technical Data (MACD/RSI) from Cache.
    """
    stock_key = symbol.upper().replace('.BK', '')
    
    if stock_key not in TECHNICAL_CACHE:
        raise HTTPException(status_code=404, detail="Data not in cache. Run POST /update_indicator_cache first.")
        
    full_history = TECHNICAL_CACHE[stock_key]
    one_year_ago = (date.today() - relativedelta(years=1)).strftime('%Y-%m-%d')
    
    filtered_data = [r for r in full_history if r['Date'] >= one_year_ago]
    
    return {
        "status": "success", "symbol": stock_key, "source": "cache",
        "period": "1 year", "data": filtered_data
    }

# ======================================================
# 6. INDIVIDUAL METRICS (T-DTS & TEMA)
# ======================================================
@app.get("/main_app/analyze_tdts/{input_stock}", tags=["Individual Metrics"])
def api_analyze_tdts(input_stock: str, threshold: float = 20.0, start_year: int = 2022, end_year: int = 2024):
    """Get T-DTS Analysis (Cache -> Live Fallback)"""
    stock_key = input_stock.upper().replace('.BK', '')
    
    if stock_key in CACHE_TDTS:
        return _format_cache_response(stock_key, CACHE_TDTS[stock_key], threshold, score_col='T-DTS')
    
    return analyze_stock_tdts(input_stock, start_year, end_year, threshold)

@app.get("/main_app/analyze_tema/{input_stock}", tags=["Individual Metrics"])
def api_analyze_tema(input_stock: str, threshold: float = 20.0, start_year: int = 2022, end_year: int = 2024, window: int = 15):
    """Get TEMA Analysis (Cache -> Live Fallback)"""
    stock_key = input_stock.upper().replace('.BK', '')
    
    if stock_key in CACHE_TEMA:
        # TEMA logic checks both Bf and Af columns
        return _format_cache_response(stock_key, CACHE_TEMA[stock_key], threshold, score_col='TEMA_Multi')
        
    return analyze_stock_tema([input_stock], start_year, end_year, threshold, window)


# ======================================================
# INTERNAL HELPER FUNCTIONS (Background Tasks & Utils)
# ======================================================

def _run_scoring_batch_analysis(payload_dict: Dict):
    """Background Task: Run Clustering & Update Scoring Caches"""
    global CACHE_SCORING, CACHE_TDTS, CACHE_TEMA
    
    payload = BatchInput(**payload_dict)
    result = process_cluster_and_score(
        tickers=None, 
        start_year=payload.start_year, end_year=payload.end_year,
        window=payload.window, threshold=payload.threshold
    )
    
    if result.get('status') == 'success':
        # Update Scoring Cache
        CACHE_SCORING = {item['Stock']: item for item in result['data']}
        
        # Helper to group raw list by stock
        def group_by_stock(raw_list):
            grouped = {}
            for item in raw_list:
                s = item['Stock'].upper().replace('.BK', '')
                if s not in grouped: grouped[s] = []
                grouped[s].append(item)
            return grouped

        CACHE_TDTS = group_by_stock(result.get('raw_tdts', []))
        CACHE_TEMA = group_by_stock(result.get('raw_tema', []))
        
        print(f"✅ CACHE UPDATED: Scoring ({len(CACHE_SCORING)})")
    else:
        print(f"❌ CACHE UPDATE FAILED: {result.get('message')}")

def _run_technical_batch_analysis(start_year: int):
    """Background Task: Run Technical Analysis & Update Cache"""
    global TECHNICAL_CACHE
    result = analyze_technical_batch(start_year=start_year)
    
    if result.get('status') == 'success':
        TECHNICAL_CACHE = result['data']
        print(f"✅ CACHE UPDATED: Technical ({len(TECHNICAL_CACHE)})")
    else:
        print(f"❌ CACHE UPDATE FAILED: {result.get('message')}")

def _format_cache_response(stock_key, raw_data, threshold, score_col):
    """Format raw cache list into Clean/Unclean structure"""
    df = pd.DataFrame(raw_data)
    
    if score_col == 'TEMA_Multi':
        is_outlier = (df['Ret_Bf_TEMA (%)'].abs() > threshold) | (df['Ret_Af_TEMA (%)'].abs() > threshold)
    else:
        is_outlier = (df[score_col] < -threshold) | (df[score_col] > threshold)
        
    return {
        "status": "success", "source": "cache", "symbol": stock_key,
        "data": {
            "raw_data": df.to_dict(orient='records'),
            "clean_data": df[~is_outlier].to_dict(orient='records'),
            "unclean_data": df[is_outlier].to_dict(orient='records')
        }
    }


# ======================================================
# DIVIDEND SEASONALITY ENDPOINTS
# ======================================================

# --- 1. POST: Update Cache (เส้นเดียวจบ) ---
def _run_seasonality_batch():
    """Background Task"""
    global CACHE_SEASONALITY
    result = analyze_seasonality_batch()
    if result.get('status') == 'success':
        CACHE_SEASONALITY = result['data']
        print(f"✅ CACHE UPDATED: Seasonality ({len(CACHE_SEASONALITY)})")
    else:
        print("❌ CACHE UPDATE FAILED: Seasonality")

@app.post("/main_app/update_seasonality_cache", tags=["Dividend Seasonality"])
def api_update_seasonality_cache(background_tasks: BackgroundTasks):
    """
    [POST] คำนวณสถิติปันผล SET50 ทั้งหมดเก็บลง Cache (Min/Max/Avg/Countdown)
    """
    background_tasks.add_task(_run_seasonality_batch)
    return {"status": "processing", "message": "Dividend seasonality analysis started in background."}


# --- Helper เพื่อดึงข้อมูลรายตัว หรือ ทั้งหมด (SET50) ---
def get_seasonality_from_cache(symbol_input: str):
    if not CACHE_SEASONALITY:
        raise HTTPException(status_code=400, detail="Cache empty. Please run POST /update_seasonality_cache first.")
    
    key = symbol_input.upper().replace('.BK', '')
    
    # กรณีดึงทั้งหมด
    if key == 'SET50':
        return list(CACHE_SEASONALITY.values())
    
    # กรณีดึงรายตัว
    if key in CACHE_SEASONALITY:
        return CACHE_SEASONALITY[key]
    
    raise HTTPException(status_code=404, detail=f"Stock '{key}' not found in cache.")


# --- 2. GET: Statistics Line (เส้นสถิติ) ---
@app.get("/main_app/dividend_statistics/{symbol}", tags=["Dividend Seasonality"])
def api_dividend_stats(symbol: str):
    """
    [GET] ดูสถิติย้อนหลัง (Min, Max, Avg Date)
    Input: ชื่อหุ้น (เช่น 'PTT') หรือ 'SET50'
    """
    raw_data = get_seasonality_from_cache(symbol)
    
    # ถ้าเป็น List (SET50) ให้ Loop กรองเอาเฉพาะส่วน Stats
    if isinstance(raw_data, list):
        output = []
        for item in raw_data:
            output.append({
                "Symbol": item['Symbol'],
                "Tag1_Stats": item.get('Tag1', {}).get('Stats') if item.get('Tag1') else None,
                "Tag2_Stats": item.get('Tag2', {}).get('Stats') if item.get('Tag2') else None
            })
        return {"status": "success", "mode": "SET50", "data": output}
    
    # ถ้าเป็นรายตัว
    return {
        "status": "success",
        "symbol": raw_data['Symbol'],
        "Tag1_Stats": raw_data.get('Tag1', {}).get('Stats') if raw_data.get('Tag1') else None,
        "Tag2_Stats": raw_data.get('Tag2', {}).get('Stats') if raw_data.get('Tag2') else None
    }


# --- 3. GET: Countdown Line (เส้นนับถอยหลัง) ---
@app.get("/main_app/dividend_countdown/{symbol}", tags=["Dividend Seasonality"])
def api_dividend_countdown(symbol: str):
    """
    [GET] ดูวันนับถอยหลัง (Countdown Days)
    Input: ชื่อหุ้น (เช่น 'PTT') หรือ 'SET50'
    """
    raw_data = get_seasonality_from_cache(symbol)
    
    # ถ้าเป็น List (SET50) ให้ Loop กรองเอาเฉพาะส่วน Countdown
    if isinstance(raw_data, list):
        output = []
        for item in raw_data:
            output.append({
                "Symbol": item['Symbol'],
                "Tag1_Countdown": item.get('Tag1', {}).get('Countdown') if item.get('Tag1') else None,
                "Tag2_Countdown": item.get('Tag2', {}).get('Countdown') if item.get('Tag2') else None
            })
        # เรียงลำดับตามวันที่เหลือน้อยสุด (ใกล้ปันผลสุด) ของ Tag1
        try:
            output.sort(key=lambda x: x['Tag1_Countdown']['Days_Remaining'] if x['Tag1_Countdown'] else 999)
        except:
            pass
        return {"status": "success", "mode": "SET50", "data": output}
    
    # ถ้าเป็นรายตัว
    return {
        "status": "success",
        "symbol": raw_data['Symbol'],
        "Tag1_Countdown": raw_data.get('Tag1', {}).get('Countdown') if raw_data.get('Tag1') else None,
        "Tag2_Countdown": raw_data.get('Tag2', {}).get('Countdown') if raw_data.get('Tag2') else None
    }