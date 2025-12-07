# ไฟล์: logic.py

def calculate_thai_income_tax(net_income: float) -> float:
    """ฟังก์ชันช่วยคำนวณภาษีขั้นบันได"""
    tax_brackets = [
        (150000, 0.00),
        (300000, 0.05),
        (500000, 0.10),
        (750000, 0.15),
        (1000000, 0.20),
        (2000000, 0.25),
        (5000000, 0.30),
        (float('inf'), 0.35)
    ]
    
    tax = 0.0
    previous_bracket_limit = 0.0
    
    for limit, rate in tax_brackets:
        if net_income > previous_bracket_limit:
            taxable_amount = min(net_income, limit) - previous_bracket_limit
            tax += taxable_amount * rate
            previous_bracket_limit = limit
        else:
            break
    return tax

def optimize_dividend_tax(base_net_income, dividend_amount, corporate_tax_rate):
    """ฟังก์ชันหลัก: คำนวณความคุ้มค่าเครดิตภาษี"""
    
    # 1. Final Tax
    withholding_tax = dividend_amount * 0.10
    net_received_final_tax = dividend_amount - withholding_tax
    tax_base_case = calculate_thai_income_tax(base_net_income)
    total_net_wealth_option1 = (base_net_income - tax_base_case) + net_received_final_tax

    # 2. Tax Credit
    if corporate_tax_rate > 0:
        tax_credit_ratio = corporate_tax_rate / (100 - corporate_tax_rate)
        tax_credit_value = dividend_amount * tax_credit_ratio
    else:
        tax_credit_value = 0 

    gross_dividend_income = dividend_amount + tax_credit_value
    total_net_income_option2 = base_net_income + gross_dividend_income
    total_tax_liability = calculate_thai_income_tax(total_net_income_option2)
    total_net_wealth_option2 = (base_net_income + gross_dividend_income) - total_tax_liability

    diff = total_net_wealth_option2 - total_net_wealth_option1

    result = {
        "dividend_received": dividend_amount,
        "cit_rate": corporate_tax_rate,
        "option1_final_tax_wealth": round(total_net_wealth_option1, 2),
        "option2_credit_tax_wealth": round(total_net_wealth_option2, 2),
        "difference": round(diff, 2),
        "recommendation": "Should Claim Credit" if diff > 0 else "Final Tax"
    }

    return result