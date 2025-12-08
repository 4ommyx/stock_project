def calculate_thai_income_tax(net_income: float) -> float:
    """
    ฟังก์ชันช่วยคำนวณภาษีเงินได้บุคคลธรรมดา (แบบขั้นบันได)
    """
    # อัตราภาษีปีปัจจุบัน (เงินได้สุทธิ, อัตราภาษี)
    tax_brackets = [
        (150000, 0.00),   # 0 - 150,000 ยกเว้น
        (300000, 0.05),   # 150,001 - 300,000 ร้อยละ 5
        (500000, 0.10),   # 300,001 - 500,000 ร้อยละ 10
        (750000, 0.15),
        (1000000, 0.20),
        (2000000, 0.25),
        (5000000, 0.30),
        (float('inf'), 0.35)
    ]
    
    tax = 0.0
    previous_limit = 0.0
    
    for limit, rate in tax_brackets:
        if net_income > previous_limit:
            # คำนวณยอดเงินที่ตกอยู่ในช่วงนี้
            taxable_amount = min(net_income, limit) - previous_limit
            tax += taxable_amount * rate
            previous_limit = limit
        else:
            break
            
    return tax

def optimize_dividend_tax(base_net_income: float, dividend_amount: float, corporate_tax_rate: float):
    """
    Logic: คำนวณเปรียบเทียบ Final Tax vs เครดิตภาษีเงินปันผล
    """
    
    # --- Option 1: Final Tax (หัก ณ ที่จ่าย 10% จบเลย) ---
    withholding_tax = dividend_amount * 0.10
    net_dividend_received = dividend_amount - withholding_tax
    
    # คำนวณภาษีจากรายได้ปกติ (ไม่รวมปันผล)
    tax_normal = calculate_thai_income_tax(base_net_income)
    
    # ความมั่งคั่งสุทธิ (รายได้ปกติหลังภาษี + ปันผลหลังหัก ณ ที่จ่าย)
    wealth_option1 = (base_net_income - tax_normal) + net_dividend_received

    # --- Option 2: ยื่นภาษี (ใช้สิทธิเครดิตภาษี) ---
    if corporate_tax_rate > 0:
        # สูตรเครดิตภาษี = ปันผล * (อัตราภาษี / (100 - อัตราภาษี))
        tax_credit_ratio = corporate_tax_rate / (100 - corporate_tax_rate)
        tax_credit_val = dividend_amount * tax_credit_ratio
    else:
        tax_credit_val = 0 

    # รายได้รวมเพื่อคำนวณภาษี = รายได้ปกติ + ปันผล + เครดิตภาษี
    gross_dividend = dividend_amount + tax_credit_val
    total_assessable_income = base_net_income + gross_dividend
    
    total_tax_liability = calculate_thai_income_tax(total_assessable_income)
    
    # ความมั่งคั่งสุทธิ = รายได้รวมทั้งหมด - ภาษีที่ต้องจ่ายจริง
    wealth_option2 = total_assessable_income - total_tax_liability

    # --- เปรียบเทียบ ---
    diff = wealth_option2 - wealth_option1

    return {
        "input": {
            "base_income": base_net_income,
            "dividend": dividend_amount,
            "cit_rate": corporate_tax_rate
        },
        "option1_final_tax": {
            "description": "Withholding Tax 10%",
            "net_wealth": round(wealth_option1, 2)
        },
        "option2_credit_tax": {
            "description": "Tax Credit Claim",
            "net_wealth": round(wealth_option2, 2),
            "tax_credit_amount": round(tax_credit_val, 2)
        },
        "analysis": {
            "difference": round(diff, 2),
            "recommendation": "✅ Should Claim Credit (ยื่นภาษี)" if diff > 0 else "❌ Final Tax (ไม่ต้องยื่น)"
        }
    }