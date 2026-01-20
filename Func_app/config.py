# --- Base Tickers
SET50_TICKERS_BASE = [
    "ADVANC", "AOT", "AWC", "BANPU", "BBL", "BDMS", "BEM", "BGRIM", "BH", "BJC",
    "BPP", "CPALL", "CPF", "CPN", "CRC", "DELTA", "EGCO", "BSRC", "GULF", "HMPRO",
    "IRPC", "KBANK", "KTB", "KTC", "LH", "MINT", "MTC", "OR", "OSP",
    "PTT", "PTTEP", "PTTGC", "RATCH", "SAWAD", "SCB", "SCC", "SCGP", "TISCO", "TLI",
    "TOP", "TTB", "TU", "VGI", "WHA", "GLOBAL", "BAM", "CPAXT", "GPSC", "BLA"
]

SET50_TICKERS = [f"{ticker}.BK" for ticker in SET50_TICKERS_BASE]

# --- Helper Function ---
def get_tickers(suffix=".BK"):

    return [f"{ticker}{suffix}" for ticker in SET50_TICKERS_BASE]