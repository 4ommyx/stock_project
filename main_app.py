# ไฟล์: main_app.py (หรือ main.py)
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, List
from fastapi import HTTPException

# Import Logic
from Func_app.calculate_text import optimize_dividend_tax 
from Func_app.t_dts_socring import analyze_stock_tdts
from Func_app.tema_socring import analyze_stock_tema
from Func_app.main_scoring import process_cluster_and_score

app = FastAPI()

@app.get("/")
def home():
    return {"health_check": "OK"}

# --- Endpoint 1: Tax Calculation ---
class TaxInput(BaseModel):
    base_net_income: float
    dividend_amount: float
    corporate_tax_rate: float

@app.post("/main_app/calculate_tax")
def calculate_tax(payload: TaxInput):
    result = optimize_dividend_tax(
        payload.base_net_income, 
        payload.dividend_amount, 
        payload.corporate_tax_rate
    )
    return result

# --- Endpoint 2: t-DTS Analysis ---
@app.get("/main_app/analyze_tdts/{input_stock}")
def api_analyze_tdts(
    input_stock: str, 
    threshold: float = 10.0,
    start_year: int = 2022,
    end_year: int = 2024
):
    result = analyze_stock_tdts(
        symbol=input_stock,
        start_year=start_year,
        end_year=end_year,
        threshold=threshold
    ) 
    return result

# --- Endpoint 3: TEMA Analysis (Single Stock) ---
@app.get("/main_app/analyze_tema/{input_stock}")
def api_analyze_tema(
    input_stock: str, 
    threshold: float = 10.0,   
    start_year: int = 2022,    
    end_year: int = 2024,      
    window: int = 15           
):
    """
    วิเคราะห์ TEMA รายตัว
    """
    # [CORRECTED] ส่งเป็น tickers=[input_stock] เพื่อให้ตรงกับ Logic ใหม่
    result = analyze_stock_tema(
        tickers=[input_stock],  # แก้จาก symbol=input_stock เป็น tickers=[...]
        start_year=start_year,
        end_year=end_year,
        threshold=threshold,
        window=window
    ) 
    return result

# --- Endpoint 4: Cluster Scoring Recommendation ---

class BatchInput(BaseModel):
    start_year: int = Field(2022, description="ปีเริ่มต้น")
    end_year: int = Field(2024, description="ปีสิ้นสุด")
    window: int = Field(15, description="TEMA Window")
    threshold: float = Field(20.0, description="เกณฑ์ตัด Outlier")

@app.post("/main_app/update_scoring_cache")
def api_update_scoring_cache(payload: BatchInput):
    """
    [Heavy Task] สั่งคำนวณหุ้น SET50 ทั้งหมด แล้วเก็บลง Cache
    - ต้องกดปุ่มนี้ก่อน 1 ครั้ง เพื่อให้ระบบมีข้อมูล
    - หรือกดเพื่อ Refresh ข้อมูลใหม่
    """
    global SCORING_CACHE
    
    # 1. เรียก Logic คำนวณทั้ง SET50 (ตามไฟล์ main_scoring.py ที่แก้ไปล่าสุด)
    result = process_cluster_and_score(
        tickers=None, # บังคับใช้ SET50 ใน Logic แล้ว
        start_year=payload.start_year,
        end_year=payload.end_year,
        window=payload.window,
        threshold=payload.threshold
    )
    
    if result.get('status') == 'error':
        return result

    # 2. แปลง List เป็น Dict เพื่อให้ค้นหารายตัวได้ง่าย
    # จากเดิม: [{'Stock': 'ADVANC', ...}, {'Stock': 'AOT', ...}]
    # เป็น: {'ADVANC': {...}, 'AOT': {...}}
    new_cache = {}
    for item in result['data']:
        stock_name = item['Stock'].upper().replace('.BK', '')
        new_cache[stock_name] = item
        
    # อัปเดตลง Global Variable
    SCORING_CACHE = new_cache
    
    return {
        "status": "success",
        "message": "Batch processing complete. Data cached.",
        "total_stocks_processed": len(SCORING_CACHE)
    }

@app.get("/main_app/stock_recommendation/{symbol}")
def api_get_stock_score(symbol: str):
    """
    [Fast Task] ดึงผลลัพธ์หุ้นรายตัว จากข้อมูลที่คำนวณทิ้งไว้แล้ว
    Ex: /main_app/stock_recommendation/SCB
    """
    # จัด Format ชื่อหุ้นให้ตรงกับ Key ใน Cache
    stock_key = symbol.upper().replace('.BK', '')
    
    # เช็คว่ามีข้อมูลใน Cache หรือยัง
    if not SCORING_CACHE:
        raise HTTPException(status_code=400, detail="Cache is empty. Please run POST /update_scoring_cache first.")
        
    # ค้นหาหุ้น
    data = SCORING_CACHE.get(stock_key)
    
    if not data:
        raise HTTPException(status_code=404, detail=f"Stock '{stock_key}' not found in SET50 analysis results.")
        
    return {
        "status": "success",
        "symbol": stock_key,
        "data": data
    }