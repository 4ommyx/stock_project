from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# Import Logic
from Func_app.calculate_text import optimize_dividend_tax 
from Func_app.Scoring.t_dts_socring import analyze_stock_tdts
from Func_app.Scoring.tema_socring import analyze_stock_tema
from Func_app.Scoring.main_scoring import process_cluster_and_score
from Func_app.config import SET50_TICKERS
from Func_app.TA.technical_analysis import get_technical_history
from Func_app.TA.technical_analysis import get_technical_snapshot

app = FastAPI()

# ======================================================
# GLOBAL CACHES: ถังเก็บข้อมูล 3 ใบ
# ======================================================
CACHE_SCORING: Dict[str, dict] = {} # เก็บผลคะแนน (Scoring)
CACHE_TDTS: Dict[str, list] = {}    # เก็บประวัติ T-DTS รายตัว
CACHE_TEMA: Dict[str, list] = {}    # เก็บประวัติ TEMA รายตัว

@app.get("/")
def home():
    return {
        "status": "Online",
        "cache_status": {
            "scoring": len(CACHE_SCORING),
            "tdts": len(CACHE_TDTS),
            "tema": len(CACHE_TEMA)
        }
    }

# --- Endpoint Tax Calculation ---
class TaxInput(BaseModel):
    base_net_income: float
    dividend_amount: float
    corporate_tax_rate: float

@app.post("/main_app/calculate_tax")
def calculate_tax(payload: TaxInput):
    return optimize_dividend_tax(
        payload.base_net_income, 
        payload.dividend_amount, 
        payload.corporate_tax_rate
    )

# ======================================================
# MASTER POST: Update All Caches
# ======================================================
class BatchInput(BaseModel):
    start_year: int = Field(2022, description="ปีเริ่มต้น")
    end_year: int = Field(2024, description="ปีสิ้นสุด")
    window: int = Field(15, description="TEMA Window")
    threshold: float = Field(20.0, description="เกณฑ์ตัด Outlier")

@app.post("/main_app/update_scoring_cache")
def api_update_all_caches(payload: BatchInput):
    """
    [POST] คำนวณ SET50 ครั้งเดียว แล้วเก็บลง Cache ทั้ง 3 ถัง (Scoring, T-DTS, TEMA)
    """
    global CACHE_SCORING, CACHE_TDTS, CACHE_TEMA
    
    print("Starting Batch Process for SET50...")
    
    # 1. เรียก Process ใหญ่ (ได้ข้อมูลครบทุกอย่าง)
    result = process_cluster_and_score(
        tickers=None, # Force SET50
        start_year=payload.start_year,
        end_year=payload.end_year,
        window=payload.window,
        threshold=payload.threshold
    )
    
    if result.get('status') == 'error':
        return result

    # 2. Update CACHE_SCORING (เก็บเป็น Dict {StockName: Data})
    new_scoring = {}
    for item in result['data']:
        new_scoring[item['Stock']] = item
    CACHE_SCORING = new_scoring

    # 3. Update CACHE_TDTS (ต้อง Group ข้อมูลตามชื่อหุ้น)
    new_tdts = {}
    if 'raw_tdts' in result:
        for item in result['raw_tdts']:
            stock = item['Stock'].upper().replace('.BK', '')
            if stock not in new_tdts: new_tdts[stock] = []
            new_tdts[stock].append(item)
    CACHE_TDTS = new_tdts

    # 4. Update CACHE_TEMA (ต้อง Group ข้อมูลตามชื่อหุ้น)
    new_tema = {}
    if 'raw_tema' in result:
        for item in result['raw_tema']:
            stock = item['Stock'].upper().replace('.BK', '')
            if stock not in new_tema: new_tema[stock] = []
            new_tema[stock].append(item)
    CACHE_TEMA = new_tema
    
    return {
        "status": "success", 
        "message": "All caches updated successfully.", 
        "summary": {
            "stocks_scored": len(CACHE_SCORING),
            "stocks_with_tdts": len(CACHE_TDTS),
            "stocks_with_tema": len(CACHE_TEMA)
        },
        "top_5_picks": result['data'][:5]
    }

# ======================================================
# INDIVIDUAL GET ENDPOINTS (Check Cache First)
# ======================================================

# 1. Scoring (รายตัว)
@app.get("/main_app/stock_recommendation/{symbol}")
def api_get_stock_score(symbol: str):
    stock_key = symbol.upper().replace('.BK', '')
    
    # เช็ค Cache ก่อน
    if stock_key in CACHE_SCORING:
        return {"status": "success", "source": "cache", "data": CACHE_SCORING[stock_key]}
    
    raise HTTPException(status_code=404, detail="Stock not found in cache. Please run POST /update_scoring_cache.")

# 2. T-DTS (รายตัว)
@app.get("/main_app/analyze_tdts/{input_stock}")
def api_analyze_tdts(input_stock: str, threshold: float = 10.0, start_year: int = 2022, end_year: int = 2024):
    stock_key = input_stock.upper().replace('.BK', '')
    
    # เช็ค Cache ก่อน
    if stock_key in CACHE_TDTS:
        # [Adjusted] ปรับโครงสร้างให้เหมือนกับ Live Data (ใส่ clean_data ครอบไว้)
        return {
            "status": "success", 
            "source": "cache", 
            "data": CACHE_TDTS[stock_key]
        }
    
    # ถ้าไม่มีใน Cache ให้คำนวณสด
    return analyze_stock_tdts(input_stock, start_year, end_year, threshold)

# 3. TEMA (รายตัว)
@app.get("/main_app/analyze_tema/{input_stock}")
def api_analyze_tema(input_stock: str, threshold: float = 10.0, start_year: int = 2022, end_year: int = 2024, window: int = 15):
    stock_key = input_stock.upper().replace('.BK', '')
    
    # เช็ค Cache ก่อน
    if stock_key in CACHE_TEMA:
        # [Adjusted] ปรับโครงสร้างให้เหมือนกับ Live Data
        return {
            "status": "success", 
            "source": "cache", 
            "data": CACHE_TEMA[stock_key]
        }
        
    # ถ้าไม่มีใน Cache ให้คำนวณสด
    return analyze_stock_tema([input_stock], start_year, end_year, threshold, window)


@app.get("/main_app/technical_graph/{symbol}")
def api_technical_graph(symbol: str, period: str = "1y"):
    return get_technical_history(symbol, period)


@app.get("/main_app/technical_screener")
def api_technical_screener():
    # จะคืนค่าเฉพาะค่าล่าสุดของทุกตัวใน SET50
    return get_technical_snapshot()