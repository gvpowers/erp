"""
GV Powers ERP - Shared Utilities Module
Indian GST state codes, validation helpers, number generators,
currency formatting, amount-to-words, input sanitization.
"""

import re
import secrets
from calendar import isleap
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import session, current_app, request

# ---------------------------------------------------------------------------
# Indian GST State Codes (all 38 post-2020 amendment)
# Dadra & Nagar Haveli and Daman & Diu merged into code 26
# ---------------------------------------------------------------------------

GST_STATE_CODES: Dict[int, str] = {
    1:  "Jammu & Kashmir",
    2:  "Himachal Pradesh",
    3:  "Punjab",
    4:  "Chandigarh",
    5:  "Uttarakhand",
    6:  "Haryana",
    7:  "Delhi",
    8:  "Rajasthan",
    9:  "Uttar Pradesh",
    10: "Bihar",
    11: "Sikkim",
    12: "Arunachal Pradesh",
    13: "Nagaland",
    14: "Manipur",
    15: "Mizoram",
    16: "Tripura",
    17: "Meghalaya",
    18: "Assam",
    19: "West Bengal",
    20: "Jharkhand",
    21: "Odisha",
    22: "Chhattisgarh",
    23: "Madhya Pradesh",
    24: "Gujarat",
    25: "Daman & Diu",
    26: "Dadra & Nagar Haveli and Daman & Diu",
    27: "Maharashtra",
    28: "Andhra Pradesh (old code - Telangana)",
    29: "Karnataka",
    30: "Goa",
    31: "Lakshadweep",
    32: "Kerala",
    33: "Tamil Nadu",
    34: "Puducherry",
    35: "Andaman & Nicobar Islands",
    36: "Telangana",
    37: "Andhra Pradesh",
    38: "Ladakh",
    97: "Other Territory",
}

GST_STATE_NAMES_TO_CODES: Dict[str, int] = {
    name: code for code, name in GST_STATE_CODES.items()
}

VALID_GST_RATES: Tuple[Decimal, ...] = (
    Decimal("0"), Decimal("0.25"), Decimal("3"),
    Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28"),
)

VALID_GST_RATE_FLOATS: Tuple[float, ...] = (0.0, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0)


# ---------------------------------------------------------------------------
# GSTIN Validation
# Format: 2-digit state code + 10-char PAN + 1 entity code + Z + 1 checksum
# Total: 15 alphanumeric characters
# ---------------------------------------------------------------------------

_GSTIN_RE = re.compile(
    r"^[0-9]{2}"
    r"[A-Z]{5}[0-9]{4}[A-Z]{1}"
    r"[A-Z0-9]{1}Z[A-Z0-9]{1}$",
    re.IGNORECASE,
)

_GSTIN_CHECKSUM_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def validate_gstIN(gstin: str) -> bool:
    """Validate a 15-character Indian GSTIN including Luhn-like checksum."""
    if not gstin or len(gstin) != 15:
        return False
    gstin = gstin.strip().upper()
    if not _GSTIN_RE.match(gstin):
        return False
    state_code = int(gstin[:2])
    if state_code not in GST_STATE_CODES and state_code != 97:
        return False
    return _verify_gstIN_checksum(gstin)


def _verify_gstIN_checksum(gstin: str) -> bool:
    """Verify the 15th character of GSTIN using the Factor/Modulo algorithm."""
    factor = 2
    total = 0
    for idx, char in enumerate(gstin[:14]):
        digit = _GSTIN_CHECKSUM_CHARS.index(char)
        if idx % 2 == 0:
            total += _lmod(digit * factor)
        else:
            total += digit
    remainder = total % 36
    check_code = (36 - remainder) % 36
    return _GSTIN_CHECKSUM_CHARS[check_code] == gstin[14].upper()


def _lmod(value: int) -> int:
    quotient = value // 36
    return value - 36 * quotient


# ---------------------------------------------------------------------------
# PAN Validation
# Format: AAAAA9999A  (5 letters + 4 digits + 1 letter)
# ---------------------------------------------------------------------------

_PAN_RE = re.compile(
    r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    re.IGNORECASE,
)

_PAN_INVALID_CHARS = ("ABF", "IOS", "IDK", "XYZ", "ALK", "AZB", "CID", "DTN",
                       "EOG", "EXH", "FFU", "FJI", "FLK", "FNR", "GBA", "GCU",
                       "GFC", "GFX", "GHA", "GMH", "GMU", "GNC", "GNN", "GNR",
                       "GOA", "GOE", "GPA", "GPH", "GPM", "GPN", "GPR", "GPU",
                       "GPV", "GPW", "GTY", "GZA", "GZB", "GZL", "GZO", "GZP",
                       "GZT", "HFA", "HFM", "HGS", "HHC", "HHU", "HIH", "HJI",
                       "HJL", "HJQ", "HNR", "HOP", "HPK", "HPM", "HPN", "HPR",
                       "HRH", "HRL", "HSB", "HUP", "HWF", "HWG", "HWR", "JAL",
                       "JEW", "JJL", "JMY", "JNA", "JNZ", "JPY", "JRO", "JSL",
                       "JWN", "KGA", "KGM", "KGN", "KGS", "KHA", "KHC", "KHD",
                       "KHN", "KHR", "KHS", "KJC", "KJD", "KJM", "KJN", "KJR",
                       "KJT", "KJW", "KLB", "KLC", "KLD", "KLG", "KLH", "KLI",
                       "KLJ", "KLK", "KLL", "KLN", "KLR", "KLS", "KLT", "KMA",
                       "KMB", "KMC", "KMD", "KME", "KMF", "KMG", "KMH", "KMI",
                       "KMJ", "KMK", "KML", "KMM", "KMN", "KMO", "KMP", "KMQ",
                       "KMR", "KMS", "KMT", "KMU", "KMV", "KMW", "KMZ", "KNA",
                       "KNB", "KNC", "KND", "KNE", "KNF", "KNG", "KNH", "KNI",
                       "KNJ", "KNK", "KNL", "KNM", "KNN", "KNO", "KNP", "KNQ",
                       "KNR", "KNS", "KNT", "KNU", "KNV", "KNW", "KNX", "KNY",
                       "KNZ", "KPA", "KPB", "KPC", "KPD", "KPE", "KPF", "KPG",
                       "KPH", "KPI", "KPJ", "KPK", "KPL", "KPM", "KPN", "KPO",
                       "KPP", "KPQ", "KPR", "KPS", "KPT", "KPU", "KPV", "KPW",
                       "KPX", "KPY", "KPZ", "KRA", "KRB", "KRC", "KRD", "KRE",
                       "KRF", "KRG", "KRH", "KRI", "KRJ", "KRK", "KRL", "KRM",
                       "KRN", "KRO", "KRP", "KRQ", "KRR", "KRS", "KRT", "KRU",
                       "KRV", "KRW", "KRX", "KRY", "KRZ", "KSA", "KSB", "KSC",
                       "KSD", "KSE", "KSF", "KSG", "KSH", "KSI", "KSJ", "KSK",
                       "KSL", "KSM", "KSN", "KSO", "KSP", "KSQ", "KSR", "KSS",
                       "KST", "KSU", "KSV", "KSW", "KSX", "KSY", "KSZ", "KTA",
                       "KTB", "KTC", "KTD", "KTE", "KTF", "KTG", "KTH", "KTI",
                       "KTJ", "KTK", "KTL", "KTM", "KTN", "KTO", "KTP", "KTQ",
                       "KTR", "KTS", "KTT", "KTU", "KTV", "KTW", "KTX", "KTY",
                       "KTZ", "KUA", "KUB", "KUC", "KUD", "KUE", "KUF", "KUG",
                       "KUH", "KUI", "KUJ", "KUK", "KUL", "KUM", "KUN", "KUO",
                       "KUP", "KUQ", "KUR", "KUS", "KUT", "KUU", "KUV", "KUW",
                       "KUX", "KUY", "KUZ", "KVA", "KVB", "KVC", "KVD", "KVE",
                       "KVF", "KVG", "KVH", "KVI", "KVJ", "KVK", "KVL", "KVM",
                       "KVN", "KVO", "KVP", "KVQ", "KVR", "KVS", "KVT", "KVU",
                       "KVV", "KVW", "KVX", "KVY", "KVZ", "KWA", "KWB", "KWC",
                       "KWD", "KWE", "KWF", "KWG", "KWH", "KWI", "KWJ", "KWK",
                       "KWL", "KWM", "KWN", "KWO", "KWP", "KWQ", "KWR", "KWS",
                       "KWT", "KWU", "KWV", "KWW", "KWX", "KWY", "KWZ", "KXA",
                       "KXB", "KXC", "KXD", "KXE", "KXF", "KXG", "KXH", "KXI",
                       "KXJ", "KXK", "KXL", "KXM", "KXN", "KXO", "KXP", "KXQ",
                       "KXR", "KXS", "KXT", "KXU", "KXV", "KXW", "KXX", "KXY",
                       "KXZ", "KYA", "KYB", "KYC", "KYD", "KYE", "KYF", "KYG",
                       "KYH", "KYI", "KYJ", "KYK", "KYL", "KYM", "KYN", "KYO",
                       "KYP", "KYQ", "KYR", "KYS", "KYT", "KYU", "KYV", "KYW",
                       "KYX", "KYY", "KYZ", "KZA", "KZB", "KZC", "KZD", "KZE",
                       "KZF", "KZG", "KZH", "KZI", "KZJ", "KZK", "KZL", "KZM",
                       "KZN", "KZO", "KZP", "KZQ", "KZR", "KZS", "KZT", "KZU",
                       "KZV", "KZW", "KZX", "KZY", "KZZ")

_PAN_VALID_THIRD_CHAR = ("A", "B", "C", "F", "G", "H", "L", "J", "P", "T")


def validate_pan(pan: str) -> bool:
    """Validate an Indian Permanent Account Number (10-character alphanumeric)."""
    if not pan or len(pan.strip()) != 10:
        return False
    pan = pan.strip().upper()
    if not _PAN_RE.match(pan):
        return False
    if pan[:3] in _PAN_INVALID_CHARS:
        return False
    if pan[3] not in _PAN_VALID_THIRD_CHAR:
        return False
    return True


# ---------------------------------------------------------------------------
# Indian Mobile Number Validation
# ---------------------------------------------------------------------------

_MOBILE_RE = re.compile(
    r"^(\+91[\-\s]?)?[6-9]\d{9}$"
)


def validate_mobile(mobile: str) -> bool:
    """Validate an Indian mobile number (10 digits starting with 6-9, optional +91)."""
    if not mobile:
        return False
    cleaned = mobile.strip().replace(" ", "").replace("-", "")
    return bool(_MOBILE_RE.match(cleaned))


# ---------------------------------------------------------------------------
# Amount to Words (Indian Numbering: Crore / Lakh / Thousand)
# ---------------------------------------------------------------------------

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]

_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty",
    "Sixty", "Seventy", "Eighty", "Ninety",
]


def _chunk_to_words(n: int) -> str:
    """Convert a number under 1000 to English words."""
    if n == 0:
        return ""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return (_TENS[n // 10] + " " + _ONES[n % 10]).strip()
    return (_ONES[n // 100] + " Hundred " + _chunk_to_words(n % 100)).strip()


def amount_to_words(amount: Union[int, float, Decimal, str]) -> str:
    """
    Convert a numeric amount to Indian Rupees in words using
    Crore / Lakh / Thousand grouping, with paise support.

    Always derived from the FINAL GRAND TOTAL.

    Examples:
        amount_to_words(1234567) -> "Rupees Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven Only"
        amount_to_words(5900.75) -> "Rupees Five Thousand Nine Hundred and Seventy Five Paise Only"
        amount_to_words(0)       -> "Rupees Zero Only"
    """
    if isinstance(amount, str):
        try:
            amount = Decimal(amount)
        except InvalidOperation:
            return "Rupees Zero Only"
    elif amount is None:
        return "Rupees Zero Only"
    elif not isinstance(amount, Decimal):
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            return "Rupees Zero Only"
    if amount < 0:
        return "Minus " + amount_to_words(-amount)

    def _rupees_words(n: int) -> str:
        words = ""
        if n >= 1_00_00_000:
            words += _chunk_to_words(n // 1_00_00_000) + " Crore "
            n %= 1_00_00_000
        if n >= 1_00_000:
            words += _chunk_to_words(n // 1_00_000) + " Lakh "
            n %= 1_00_000
        if n >= 1_000:
            words += _chunk_to_words(n // 1_000) + " Thousand "
            n %= 1_000
        if n > 0:
            words += _chunk_to_words(n) + " "
        return words.strip()

    total_paise = int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    rupees, paise = divmod(total_paise, 100)
    if total_paise == 0:
        return "Rupees Zero Only"
    rupee_words = _rupees_words(rupees)
    if paise == 0:
        if rupees == 1:
            return "Rupee One Only"
        return f"Rupees {rupee_words} Only"
    paise_words = _rupees_words(paise)
    if rupees == 0:
        return f"Rupees {paise_words} Paise Only"
    return f"Rupees {rupee_words} and {paise_words} Paise Only"


# ---------------------------------------------------------------------------
# Financial Year Helpers
# ---------------------------------------------------------------------------

def get_financial_year(dt: Optional[date] = None) -> Tuple[date, date]:
    """
    Return (start_date, end_date) for the Indian financial year
    containing the given date. FY runs April 1 to March 31.

    Example: get_financial_year(date(2025, 7, 15)) -> (date(2025,4,1), date(2026,3,31))
    """
    if dt is None:
        dt = date.today()
    if isinstance(dt, datetime):
        dt = dt.date()
    if dt.month >= 4:
        fy_start = date(dt.year, 4, 1)
        fy_end = date(dt.year + 1, 3, 31)
    else:
        fy_start = date(dt.year - 1, 4, 1)
        fy_end = date(dt.year, 3, 31)
    return fy_start, fy_end


def get_financial_year_code(dt: Optional[date] = None) -> str:
    """
    Return the FY label like '2025-26'.
    """
    if dt is None:
        dt = date.today()
    if dt.month >= 4:
        return f"{dt.year}-{(dt.year + 1) % 100:02d}"
    return f"{dt.year - 1}-{dt.year % 100:02d}"


def get_financial_year_prefix(dt: Optional[date] = None) -> str:
    """
    Return the 4-digit year used in document number prefixes.
    For FY 2025-26, returns '2526'.
    """
    if dt is None:
        dt = date.today()
    if dt.month >= 4:
        return f"{dt.year % 100:02d}{(dt.year + 1) % 100:02d}"
    return f"{(dt.year - 1) % 100:02d}{dt.year % 100:02d}"


# ---------------------------------------------------------------------------
# Invoice / Quotation / PO Number Generators
# ---------------------------------------------------------------------------

def generate_invoice_number(existing_numbers: Optional[List[str]] = None) -> str:
    """
    Generate invoice number: GVP-YYYY-NNNNNN
    Resets on April 1 each financial year.
    YYYY = 4-digit FY code (e.g., 2526 for FY 2025-26)
    """
    fy_code = get_financial_year_prefix()
    prefix = f"GVP-{fy_code}-"
    seq = 1
    if existing_numbers:
        seq = _next_sequence(existing_numbers, prefix) + 1
    return f"{prefix}{seq:06d}"


def generate_quotation_number(existing_numbers: Optional[List[str]] = None) -> str:
    """
    Generate quotation number: QTN-YYYY-NNNNNN
    Resets on April 1 each financial year.
    """
    fy_code = get_financial_year_prefix()
    prefix = f"QTN-{fy_code}-"
    seq = 1
    if existing_numbers:
        seq = _next_sequence(existing_numbers, prefix) + 1
    return f"{prefix}{seq:06d}"


def generate_purchase_order_number(existing_numbers: Optional[List[str]] = None) -> str:
    """
    Generate purchase order number: PO-YYYY-NNNNNN
    Resets on April 1 each financial year.
    """
    fy_code = get_financial_year_prefix()
    prefix = f"PO-{fy_code}-"
    seq = 1
    if existing_numbers:
        seq = _next_sequence(existing_numbers, prefix) + 1
    return f"{prefix}{seq:06d}"


def _next_sequence(existing_numbers: List[str], prefix: str) -> int:
    """Find the highest sequence number among existing numbers with the given prefix."""
    max_seq = 0
    for num in existing_numbers:
        if num and num.startswith(prefix):
            try:
                seq_part = num[len(prefix):]
                seq_int = int(seq_part)
                if seq_int > max_seq:
                    max_seq = seq_int
            except (ValueError, IndexError):
                continue
    return max_seq


# ---------------------------------------------------------------------------
# Input Sanitization Helpers
# ---------------------------------------------------------------------------

_XSS_PATTERNS = [
    re.compile(r"<script\b[^>]*>", re.IGNORECASE),
    re.compile(r"</script>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"<iframe\b", re.IGNORECASE),
    re.compile(r"<object\b", re.IGNORECASE),
    re.compile(r"<embed\b", re.IGNORECASE),
    re.compile(r"<link\b", re.IGNORECASE),
    re.compile(r"<style\b", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"<\s*img\b[^>]+onerror", re.IGNORECASE),
    re.compile(r"<\s*svg\b[^>]+onload", re.IGNORECASE),
]

_SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|EXEC|EXECUTE|UNION|FETCH|DECLARE|EXEC)\b)", re.IGNORECASE),
    re.compile(r"(--|#|/\*|\*/)", re.IGNORECASE),
    re.compile(r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)", re.IGNORECASE),
    re.compile(r"['\";]\s*(OR|AND)\s+['\"]", re.IGNORECASE),
    re.compile(r"\bWAITFOR\s+DELAY\b", re.IGNORECASE),
    re.compile(r"\bBENCHMARK\s*\(", re.IGNORECASE),
    re.compile(r"\bSLEEP\s*\(", re.IGNORECASE),
    re.compile(r"\bLOAD_FILE\s*\(", re.IGNORECASE),
    re.compile(r"\bINTO\s+(OUT|DUMP)FILE\b", re.IGNORECASE),
]


def sanitize_input(value: str) -> str:
    """Strip potentially dangerous HTML/script tags and SQL patterns."""
    if not value:
        return ""
    cleaned = str(value).strip()
    cleaned = _strip_xss(cleaned)
    cleaned = _strip_sql_patterns(cleaned)
    return cleaned


def _strip_xss(value: str) -> str:
    """Remove HTML tags that could enable XSS attacks."""
    for pattern in _XSS_PATTERNS:
        value = pattern.sub("", value)
    value = re.sub(r"<[^>]+>", "", value)
    return value


def _strip_sql_patterns(value: str) -> str:
    """Flag or strip obvious SQL injection patterns. Returns the original
    value with dangerous sequences removed (best-effort, parameterized
    queries are the primary defense)."""
    for pattern in _SQL_INJECTION_PATTERNS:
        value = pattern.sub("", value)
    return value


def contains_xss(value: str) -> bool:
    """Return True if the value contains potential XSS payload."""
    if not value:
        return False
    for pattern in _XSS_PATTERNS:
        if pattern.search(value):
            return True
    return bool(re.search(r"<\s*/?\s*(script|iframe|object|embed|frame|meta|link|style|base)\b", value, re.IGNORECASE))


def contains_sql_injection(value: str) -> bool:
    """Return True if the value contains obvious SQL injection patterns."""
    if not value:
        return False
    for pattern in _SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            return True
    return False


# ---------------------------------------------------------------------------
# Indian Currency Formatting
# ---------------------------------------------------------------------------

def format_indian_currency(
    amount: Union[int, float, Decimal, str],
    symbol: bool = True,
    decimal_places: int = 2,
) -> str:
    """
    Format amount in Indian numbering system (lakhs/crores).
    Example: format_indian_currency(1234567.50) -> "Rs. 12,34,567.50"
    """
    if isinstance(amount, str):
        try:
            amount = Decimal(amount)
        except InvalidOperation:
            return "0.00"

    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))

    if decimal_places == 0:
        amount = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    else:
        places = Decimal(10) ** -decimal_places
        amount = amount.quantize(places, rounding=ROUND_HALF_UP)

    negative = amount < 0
    amount = abs(amount)

    int_part = int(amount)
    frac_str = ""
    if decimal_places > 0:
        frac_part = amount - int(int_part)
        frac_str = str(frac_part)[1:]  # includes "0."

    int_str = str(int_part)
    if len(int_str) <= 3:
        formatted_int = int_str
    else:
        last_three = int_str[-3:]
        remaining = int_str[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        formatted_int = ",".join(reversed(groups)) + "," + last_three

    result = formatted_int
    if decimal_places > 0:
        result += frac_str

    if negative:
        result = "-" + result

    if symbol:
        result = f"Rs. {result}"

    return result


# ---------------------------------------------------------------------------
# CSRF Token Helper for AJAX
# ---------------------------------------------------------------------------

def get_csrf_token() -> str:
    """Get the CSRF token for use in AJAX requests."""
    try:
        from flask_wtf.csrf import generate_csrf
        return generate_csrf()
    except (ImportError, RuntimeError):
        return session.get("csrf_token", "")


def get_csrf_headers() -> Dict[str, str]:
    """Return headers dict to include in AJAX requests for CSRF protection."""
    return {
        "X-CSRFToken": get_csrf_token(),
        "X-Requested-With": "XMLHttpRequest",
    }


# ---------------------------------------------------------------------------
# Utility: State code from GSTIN
# ---------------------------------------------------------------------------

def extract_state_code_from_gstin(gstin: str) -> Optional[int]:
    """Extract the 2-digit state code from a GSTIN."""
    if not gstin or len(gstin) < 2:
        return None
    try:
        code = int(gstin[:2])
        if code in GST_STATE_CODES:
            return code
    except (ValueError, TypeError):
        pass
    return None


def get_state_name_from_code(code: int) -> Optional[str]:
    """Return the state/UT name for a given GST state code."""
    return GST_STATE_CODES.get(code)


def get_state_code_from_name(name: str) -> Optional[int]:
    """Return the GST state code for a given state/UT name (case-insensitive)."""
    name_lower = name.strip().lower()
    for state_name, code in GST_STATE_NAMES_TO_CODES.items():
        if state_name.lower() == name_lower:
            return code
    return None


# ---------------------------------------------------------------------------
# B2B vs B2C Determination
# ---------------------------------------------------------------------------

def determine_business_type(
    customer_gstin: Optional[str] = None,
    turnover_threshold: Optional[Decimal] = None,
) -> str:
    """
    Determine if a transaction is B2B or B2C.
    B2B: Business-to-Business (customer has GSTIN)
    B2C: Business-to-Consumer (no GSTIN)
    """
    if customer_gstin and validate_gstIN(customer_gstin):
        return "B2B"
    return "B2C"
