# ไฟล์: main.py
from fastapi import FastAPI
from pydantic import BaseModel


from Func_app.calculate_text import optimize_dividend_tax 
from Func_app.t_dts_socring import analyze_stock_tdts

app = FastAPI()

@app.get("/")
def home():
    return {"health_check": "OK"}

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

# t-DTS Analysis Endpoint
@app.get("/main_app/analyze_tdts/{input_stock}")
def api_analyze_tdts(
    input_stock: str, 
    threshold: float = 10.0,   # รับเป็น Query Param (ถ้าไม่ใส่จะใช้ค่า 10)
    start_year: int = 2022,    # รับเป็น Query Param
    end_year: int = 2024       # รับเป็น Query Param
):
    """
    เรียกใช้โดยใส่ชื่อหุ้นต่อท้าย URL
    Ex : /analyze_tdts/SCB.BK
    """
    
    # เรียกใช้ Logic (ส่ง input_stock เข้าไปเป็น symbol)
    result = analyze_stock_tdts(
        symbol=input_stock,
        start_year=start_year,
        end_year=end_year,
        threshold=threshold
    ) 
    return result