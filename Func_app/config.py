# --- Base Tickers
SET50_TICKERS_BASE = [
    "ADVANC", "AOT", "AWC", "BANPU", "BBL", "BDMS", "BEM", "BGRIM", "BH", "BJC",
    "BPP", "CPALL", "CPF", "CPN", "CRC", "DELTA", "EGCO", "BSRC", "GULF", "HMPRO",
    "IRPC", "KBANK", "KTB", "KTC", "LH", "MINT", "MTC", "OR", "OSP",
    "PTT", "PTTEP", "PTTGC", "RATCH", "SAWAD", "SCB", "SCC", "SCGP", "TISCO", "TLI",
    "TOP", "TTB", "TU", "VGI", "WHA", "GLOBAL", "BAM", "CPAXT", "GPSC", "BLA"
]

# --- Default Tickers for yfinance (เติม .BK ให้อัตโนมัติ) ---
SET50_TICKERS = [f"{ticker}.BK" for ticker in SET50_TICKERS_BASE]

# --- Helper Function ---
def get_tickers(suffix=".BK"):
    """
    ดึงรายชื่อหุ้น SET50 พร้อมต่อท้ายนามสกุลที่ต้องการ
    Example: get_tickers(suffix='') -> ได้ชื่อหุ้นเพียวๆ
    """
    return [f"{ticker}{suffix}" for ticker in SET50_TICKERS_BASE]