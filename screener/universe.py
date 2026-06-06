"""Broad stock universe for dynamic screening.

Provides a large, pre-defined universe of liquid stocks across all
major sectors, plus a mapping to sector ETFs for rotation scoring.
"""

# ── Broad universe (~200 liquid stocks across all sectors) ────────────
# These are the stocks the screener evaluates each day.  The list is
# sorted alphabetically within each sector group.

BROAD_UNIVERSE = [
    # ── Technology ────────────────────────────────────────────────────
    "AAPL", "ADBE", "ADI", "ADSK", "AMD", "ANET", "APH", "CRM",
    "CSCO", "CTSH", "DELL", "FI", "FICO", "FTNT", "GDDY", "HPE",
    "IBM", "INTC", "INTU", "JNPR", "KLAC", "LRCX", "MCHP", "META",
    "MRVL", "MSFT", "MU", "NFLX", "NOW", "NVDA", "NXPI", "ORCL",
    "PANW", "PLTR", "QCOM", "ROP", "SNPS", "SPLK", "SQ", "STX",
    "TXN", "WDAY", "WDC", "ZBRA", "ZS",
    # ── Finance ───────────────────────────────────────────────────────
    "AIG", "AXP", "BAC", "BK", "BLK", "BRK.B", "C", "CB", "COF",
    "FDS", "FITB", "GDOT", "GS", "HIG", "JPM", "KEY", "MA", "MET",
    "MCO", "MSCI", "MTB", "NDAQ", "PGR", "PNC", "PYPL", "SCHW",
    "SIVBQ", "SPGI", "STT", "SYF", "TFC", "TRV", "USB", "V",
    "WFC", "WRB", "WTW",
    # ── Healthcare ────────────────────────────────────────────────────
    "ABBV", "ABT", "ALGN", "AMGN", "BAX", "BDX", "BIIB", "BMY",
    "BSX", "CI", "CNC", "CVS", "DHR", "DXCM", "ELV", "GEHC", "GILD",
    "HCA", "HUM", "IDXX", "ILMN", "INCY", "IQV", "ISRG", "JNJ",
    "LH", "LLY", "MDT", "MRNA", "MRK", "MTD", "NBIX", "PFE",
    "PODD", "REGN", "RMD", "SYK", "TMO", "UNH", "UTHR", "VRTX",
    "WAT", "ZTS",
    # ── Consumer / Retail ─────────────────────────────────────────────
    "AMZN", "BBY", "BKNG", "CCL", "CHTR", "CMG", "COST", "CPRT",
    "DAL", "DHI", "DKS", "DPZ", "DRI", "EBAY", "ETSY", "EXPE",
    "F", "GM", "HD", "KMX", "KO", "LEN", "LOW", "LULU", "MCD",
    "MAR", "MELI", "MNST", "NKE", "PEP", "RCL", "ROST", "SBUX",
    "SIRI", "TGT", "TSLA", "TSCO", "UAL", "ULTA", "WMT", "YUM",
    # ── Energy ────────────────────────────────────────────────────────
    "APA", "BKR", "COP", "CVX", "DVN", "EOG", "EXC", "HAL", "KMI",
    "MPC", "MRO", "OXY", "PCG", "PXD", "SLB", "TRGP", "VLO", "WMB",
    "XOM",
    # ── Industrial / Defense ──────────────────────────────────────────
    "BA", "CARR", "CAT", "CMI", "CSX", "DE", "DOW", "EMR", "ETN",
    "FDX", "GE", "GIS", "HON", "ITW", "LMT", "LHX", "MMM", "NOC",
    "NSC", "OTIS", "PCAR", "PH", "PNR", "PWR", "RTX", "TDG", "TT",
    "UBER", "UNP", "UPS", "WM",
    # ── Utilities ─────────────────────────────────────────────────────
    "AEP", "AWK", "CEG", "CMS", "CNP", "D", "DUK", "ED", "EIX",
    "ES", "ETR", "FE", "NEE", "NI", "PEG", "SO", "SRE", "VST", "WEC",
    "XEL",
    # ── Materials ─────────────────────────────────────────────────────
    "APD", "AVY", "BLL", "ECL", "FCX", "IP", "LYB", "MLM", "NEM",
    "NUE", "PPG", "SHW", "STE", "VMC",
    # ── Real Estate ───────────────────────────────────────────────────
    "AMT", "AVB", "CBRE", "CCI", "DLR", "EQIX", "EQR", "ESS",
    "IRM", "MAA", "O", "PLD", "PSA", "SBAC", "SPG", "UDR", "WELL",
    "WY",
    # ── Communication / Media ─────────────────────────────────────────
    "DIS", "DISH", "EA", "FOXA", "NWSA", "OMC", "PARA", "T",
    "TMUS", "TTWO", "VZ", "WBD", "WMG",
    # ── Broad-market ETFs ─────────────────────────────────────────────
    "IVV", "QQQ", "SPY", "VOO", "VTI",
    # ── Sector ETFs (for rotation scoring) ────────────────────────────
    "XLK", "XLF", "XLV", "XLY", "XLE", "XLI", "XLU", "XLB", "XLRE",
]

# ── Sector ETF mapping ───────────────────────────────────────────────
# Maps each ticker to its primary sector ETF for rotation scoring.
# The sector ETF's recent performance influences the stock's score.

SECTOR_ETF_MAP: dict[str, str] = {
    # Technology
    "AAPL": "XLK", "ADBE": "XLK", "ADI": "XLK", "ADSK": "XLK",
    "AMD": "XLK", "ANET": "XLK", "APH": "XLK", "CRM": "XLK",
    "CSCO": "XLK", "CTSH": "XLK", "DELL": "XLK", "FI": "XLK",
    "FICO": "XLK", "FTNT": "XLK", "GDDY": "XLK", "HPE": "XLK",
    "IBM": "XLK", "INTC": "XLK", "INTU": "XLK", "JNPR": "XLK",
    "KLAC": "XLK", "LRCX": "XLK", "MCHP": "XLK", "META": "XLK",
    "MRVL": "XLK", "MSFT": "XLK", "MU": "XLK", "NFLX": "XLK",
    "NOW": "XLK", "NVDA": "XLK", "NXPI": "XLK", "ORCL": "XLK",
    "PANW": "XLK", "PLTR": "XLK", "QCOM": "XLK", "ROP": "XLK",
    "SNPS": "XLK", "SPLK": "XLK", "SQ": "XLK", "STX": "XLK",
    "TXN": "XLK", "WDAY": "XLK", "WDC": "XLK", "ZBRA": "XLK",
    "ZS": "XLK",
    # Finance
    "AIG": "XLF", "AXP": "XLF", "BAC": "XLF", "BK": "XLF",
    "BLK": "XLF", "BRK.B": "XLF", "C": "XLF", "CB": "XLF",
    "COF": "XLF", "FDS": "XLF", "FITB": "XLF", "GDOT": "XLF",
    "GS": "XLF", "HIG": "XLF", "JPM": "XLF", "KEY": "XLF",
    "MA": "XLF", "MET": "XLF", "MCO": "XLF", "MSCI": "XLF",
    "MTB": "XLF", "NDAQ": "XLF", "PGR": "XLF", "PNC": "XLF",
    "PYPL": "XLF", "SCHW": "XLF", "SPGI": "XLF", "STT": "XLF",
    "SYF": "XLF", "TFC": "XLF", "TRV": "XLF", "USB": "XLF",
    "V": "XLF", "WFC": "XLF", "WRB": "XLF", "WTW": "XLF",
    # Healthcare
    "ABBV": "XLV", "ABT": "XLV", "ALGN": "XLV", "AMGN": "XLV",
    "BAX": "XLV", "BDX": "XLV", "BIIB": "XLV", "BMY": "XLV",
    "BSX": "XLV", "CI": "XLV", "CNC": "XLV", "CVS": "XLV",
    "DHR": "XLV", "DXCM": "XLV", "ELV": "XLV", "GEHC": "XLV",
    "GILD": "XLV", "HCA": "XLV", "HUM": "XLV", "IDXX": "XLV",
    "ILMN": "XLV", "INCY": "XLV", "IQV": "XLV", "ISRG": "XLV",
    "JNJ": "XLV", "LH": "XLV", "LLY": "XLV", "MDT": "XLV",
    "MRNA": "XLV", "MRK": "XLV", "MTD": "XLV", "NBIX": "XLV",
    "PFE": "XLV", "PODD": "XLV", "REGN": "XLV", "RMD": "XLV",
    "SYK": "XLV", "TMO": "XLV", "UNH": "XLV", "UTHR": "XLV",
    "VRTX": "XLV", "WAT": "XLV", "ZTS": "XLV",
    # Consumer / Retail (discretionary)
    "AMZN": "XLY", "BBY": "XLY", "BKNG": "XLY", "CCL": "XLY",
    "CHTR": "XLY", "CMG": "XLY", "COST": "XLY", "CPRT": "XLY",
    "DAL": "XLY", "DHI": "XLY", "DKS": "XLY", "DPZ": "XLY",
    "DRI": "XLY", "EBAY": "XLY", "ETSY": "XLY", "EXPE": "XLY",
    "F": "XLY", "GM": "XLY", "HD": "XLY", "KMX": "XLY",
    "LEN": "XLY", "LOW": "XLY", "LULU": "XLY", "MAR": "XLY",
    "MCD": "XLY", "MELI": "XLY", "MNST": "XLY", "NKE": "XLY",
    "RCL": "XLY", "ROST": "XLY", "SBUX": "XLY", "TGT": "XLY",
    "TSLA": "XLY", "TSCO": "XLY", "UAL": "XLY", "ULTA": "XLY",
    "WMT": "XLY", "YUM": "XLY",
    # Consumer staples (also XLP, but mapped to XLY for simplicity here)
    "KO": "XLY", "PEP": "XLY",
    # Energy
    "APA": "XLE", "BKR": "XLE", "COP": "XLE", "CVX": "XLE",
    "DVN": "XLE", "EOG": "XLE", "EXC": "XLE", "HAL": "XLE",
    "KMI": "XLE", "MPC": "XLE", "MRO": "XLE", "OXY": "XLE",
    "PCG": "XLE", "PXD": "XLE", "SLB": "XLE", "TRGP": "XLE",
    "VLO": "XLE", "WMB": "XLE", "XOM": "XLE",
    # Industrial / Defense
    "BA": "XLI", "CARR": "XLI", "CAT": "XLI", "CMI": "XLI",
    "CSX": "XLI", "DE": "XLI", "DOW": "XLI", "EMR": "XLI",
    "ETN": "XLI", "FDX": "XLI", "GE": "XLI", "GIS": "XLI",
    "HON": "XLI", "ITW": "XLI", "LMT": "XLI", "LHX": "XLI",
    "MMM": "XLI", "NOC": "XLI", "NSC": "XLI", "OTIS": "XLI",
    "PCAR": "XLI", "PH": "XLI", "PNR": "XLI", "PWR": "XLI",
    "RTX": "XLI", "TDG": "XLI", "TT": "XLI", "UBER": "XLI",
    "UNP": "XLI", "UPS": "XLI", "WM": "XLI",
    # Utilities
    "AEP": "XLU", "AWK": "XLU", "CEG": "XLU", "CMS": "XLU",
    "CNP": "XLU", "D": "XLU", "DUK": "XLU", "ED": "XLU",
    "EIX": "XLU", "ES": "XLU", "ETR": "XLU", "FE": "XLU",
    "NEE": "XLU", "NI": "XLU", "PEG": "XLU", "SO": "XLU",
    "SRE": "XLU", "VST": "XLU", "WEC": "XLU", "XEL": "XLU",
    # Materials
    "APD": "XLB", "AVY": "XLB", "BLL": "XLB", "ECL": "XLB",
    "FCX": "XLB", "IP": "XLB", "LYB": "XLB", "MLM": "XLB",
    "NEM": "XLB", "NUE": "XLB", "PPG": "XLB", "SHW": "XLB",
    "STE": "XLB", "VMC": "XLB",
    # Real Estate
    "AMT": "XLRE", "AVB": "XLRE", "CBRE": "XLRE", "CCI": "XLRE",
    "DLR": "XLRE", "EQIX": "XLRE", "EQR": "XLRE", "ESS": "XLRE",
    "IRM": "XLRE", "MAA": "XLRE", "O": "XLRE", "PLD": "XLRE",
    "PSA": "XLRE", "SBAC": "XLRE", "SPG": "XLRE", "UDR": "XLRE",
    "WELL": "XLRE", "WY": "XLRE",
    # Communication / Media
    "DIS": "XLK", "DISH": "XLK", "EA": "XLK", "FOXA": "XLK",
    "NWSA": "XLK", "OMC": "XLK", "PARA": "XLK", "T": "XLK",
    "TMUS": "XLK", "TTWO": "XLK", "VZ": "XLK", "WBD": "XLK",
    "WMG": "XLK",
}


def get_sector_etf(ticker: str) -> str:
    """Return the sector ETF ticker for *ticker*, defaulting to SPY."""
    return SECTOR_ETF_MAP.get(ticker, "XLK")


def sector_tickers(sector_etf: str) -> list[str]:
    """Return all tickers mapped to a given sector ETF."""
    return sorted(t for t, s in SECTOR_ETF_MAP.items() if s == sector_etf)
