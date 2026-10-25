"""
GV Powers ERP - Indian GST Calculation Service
Complete GST computation with intra/inter-state logic, HSN taxability,
B2B/B2C determination, Place of Supply, tax-inclusive/exclusive calculations.
Uses Decimal arithmetic throughout for financial precision.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, InvalidContext
from typing import Any, Dict, List, Optional, Tuple, Union

from utils import (
    GST_STATE_CODES,
    GST_STATE_NAMES_TO_CODES,
    VALID_GST_RATES,
    VALID_GST_RATE_FLOATS,
    determine_business_type,
    get_state_name_from_code,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROUNDING_PRECISION = Decimal("0.01")
TAX_ROUNDING_PRECISION = Decimal("1")   # Indian GST: tax rounded to nearest rupee

# Exempt / nil-rated HSN categories (representative, not exhaustive)
EXEMPT_HSN_PREFIXES: List[str] = [
    "0401", "0402", "0403", "0404",  # Dairy
    "0901",                            # Coffee
    "1001", "1002", "1003", "1004",  # Cereals
    "1005", "1006", "1007", "1008",  # More cereals
    "1101", "1102", "1103", "1104",  # Cereal preparations
    "2501",                            # Salt
    "2523",                            # Cement (special)
    "3006",                            # Pharmaceutical
    "4901", "4902", "4903", "4904",  # Books & newspapers
    "4905", "4906", "4907", "4908",  # More printed material
    "4909", "4910", "4911",          # More printed material
    "6101", "6102",                   # Woven garments (some exemptions)
    "6302",                           # Bed linen
    "8471",                           # Computer (some exemptions)
]

# HSN to GST rate mapping (representative, commonly traded goods)
# In production, use HSN master from GST portal
HSN_RATE_MAP: Dict[str, Decimal] = {
    # 0% - Exempt
    "0401": Decimal("0"), "0402": Decimal("0"), "1001": Decimal("0"),
    "1006": Decimal("0"), "2501": Decimal("0"), "4901": Decimal("0"),
    "4902": Decimal("0"), "4903": Decimal("0"), "4907": Decimal("0"),
    # 0.25% - Precious stones, uncut
    "7102": Decimal("0.25"), "7103": Decimal("0.25"),
    # 3% - Gold, silver, precious metals
    "7106": Decimal("3"), "7107": Decimal("3"), "7108": Decimal("3"),
    "7109": Decimal("3"), "7110": Decimal("3"), "7111": Decimal("3"),
    "7113": Decimal("3"), "7114": Decimal("3"),
    # 5% - Packaged food, footwear under 1000, transport
    "0701": Decimal("5"), "0713": Decimal("5"), "1905": Decimal("5"),
    "1904": Decimal("5"), "2009": Decimal("5"), "2201": Decimal("5"),
    "6403": Decimal("5"), "6404": Decimal("5"),
    "8711": Decimal("5"), "8703": Decimal("5"),
    # 12% - Processed food, business class air tickets
    "0801": Decimal("12"), "0802": Decimal("12"),
    "1101": Decimal("12"), "1901": Decimal("12"),
    "1902": Decimal("12"), "2001": Decimal("12"),
    "2106": Decimal("12"), "2202": Decimal("12"),
    "8471": Decimal("12"),
    # 18% - IT services, most goods (default)
    "7318": Decimal("18"), "7326": Decimal("18"),
    "7616": Decimal("18"), "8301": Decimal("18"),
    "8415": Decimal("18"), "8418": Decimal("18"),
    "8443": Decimal("18"), "8471": Decimal("18"),
    "8504": Decimal("18"), "8507": Decimal("18"),
    "8528": Decimal("18"), "8541": Decimal("18"),
    "9028": Decimal("18"), "9405": Decimal("18"),
    "9503": Decimal("18"),
    # 28% - Luxury goods, automobiles, tobacco
    "2203": Decimal("28"), "2402": Decimal("28"),
    "2403": Decimal("28"), "8703": Decimal("28"),
    "8711": Decimal("28"),
}


# ---------------------------------------------------------------------------
# Data Classes for Calculation Results
# ---------------------------------------------------------------------------

@dataclass
class GSTLineItem:
    """Input data for a single line item GST calculation."""
    product_name: str = ""
    hsn: str = ""
    qty: Union[int, float, Decimal] = 1
    unit: str = "Pcs"
    rate: Union[int, float, Decimal] = Decimal("0.00")
    discount_percent: Union[int, float, Decimal] = Decimal("0.00")
    gst_rate: Union[int, float, Decimal] = Decimal("18")
    cess_rate: Union[int, float, Decimal] = Decimal("0.00")
    is_exempt: bool = False
    is_non_gst: bool = False
    product_id: Optional[int] = None

    def __post_init__(self):
        self.qty = Decimal(str(self.qty or 1))
        self.rate = Decimal(str(self.rate or 0))
        self.discount_percent = Decimal(str(self.discount_percent or 0))
        self.gst_rate = Decimal(str(self.gst_rate or 18))
        self.cess_rate = Decimal(str(self.cess_rate or 0))


@dataclass
class GSTLineResult:
    """Output result for a single line item after GST calculation."""
    product_name: str = ""
    hsn: str = ""
    qty: Decimal = Decimal("0")
    unit: str = "Pcs"
    rate: Decimal = Decimal("0.00")
    discount_percent: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    gross_amount: Decimal = Decimal("0.00")
    taxable_value: Decimal = Decimal("0.00")
    gst_rate: Decimal = Decimal("0.00")
    cgst_rate: Decimal = Decimal("0.00")
    sgst_rate: Decimal = Decimal("0.00")
    igst_rate: Decimal = Decimal("0.00")
    cgst: Decimal = Decimal("0.00")
    sgst: Decimal = Decimal("0.00")
    igst: Decimal = Decimal("0.00")
    cess: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    is_exempt: bool = False
    is_non_gst: bool = False
    is_intra_state: bool = True
    product_id: Optional[int] = None


@dataclass
class GSTSummary:
    """Aggregated GST summary across all line items."""
    total_gross: Decimal = Decimal("0.00")
    total_discount: Decimal = Decimal("0.00")
    total_taxable: Decimal = Decimal("0.00")
    total_cgst: Decimal = Decimal("0.00")
    total_sgst: Decimal = Decimal("0.00")
    total_igst: Decimal = Decimal("0.00")
    total_cess: Decimal = Decimal("0.00")
    total_tax: Decimal = Decimal("0.00")
    round_off: Decimal = Decimal("0.00")
    grand_total: Decimal = Decimal("0.00")
    is_intra_state: bool = True
    b2b: bool = False
    b2c: bool = True
    supplier_state_code: int = 0
    supplier_state_name: str = ""
    place_of_supply_code: int = 0
    place_of_supply_name: str = ""
    reverse_charge: bool = False
    line_items: List[GSTLineResult] = field(default_factory=list)


@dataclass
class GSTCalculationInput:
    """Full input for GST calculation across all line items."""
    supplier_state_code: int = 29
    place_of_supply_code: int = 29
    customer_gstin: Optional[str] = None
    customer_pan: Optional[str] = None
    reverse_charge: bool = False
    is_export: bool = False
    items: List[GSTLineItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# GST Calculation Service
# ---------------------------------------------------------------------------

class GSTService:
    """Complete Indian GST calculation service."""

    def __init__(self, supplier_state_code: int = 29):
        self.supplier_state_code = supplier_state_code
        self.supplier_state_name = GST_STATE_CODES.get(supplier_state_code, "Unknown")

    def calculate(
        self, calculation_input: GSTCalculationInput
    ) -> GSTSummary:
        """
        Calculate GST for all line items and return a full summary.

        Parameters:
            calculation_input: GSTCalculationInput with all line items and context.

        Returns:
            GSTSummary with per-item breakdown and totals.
        """
        supplier_code = calculation_input.supplier_state_code
        pos_code = calculation_input.place_of_supply_code
        is_intra = supplier_code == pos_code
        customer_gstin = calculation_input.customer_gstin
        is_export = calculation_input.is_export

        summary = GSTSummary(
            is_intra_state=is_intra,
            supplier_state_code=supplier_code,
            supplier_state_name=GST_STATE_CODES.get(supplier_code, ""),
            place_of_supply_code=pos_code,
            place_of_supply_name=GST_STATE_CODES.get(pos_code, ""),
            reverse_charge=calculation_input.reverse_charge,
            b2b=determine_business_type(customer_gstin) == "B2B",
            b2c=determine_business_type(customer_gstin) == "B2C",
        )

        if is_export:
            summary.is_intra_state = False
            is_intra = False

        for item in calculation_input.items:
            line_result = self._calculate_line_item(item, is_intra)
            summary.line_items.append(line_result)
            summary.total_gross += line_result.gross_amount
            summary.total_discount += line_result.discount_amount
            summary.total_taxable += line_result.taxable_value
            summary.total_cgst += line_result.cgst
            summary.total_sgst += line_result.sgst
            summary.total_igst += line_result.igst
            summary.total_cess += line_result.cess
            summary.total_tax += line_result.tax_amount

        summary.round_off, summary.grand_total = self._calculate_round_off(
            summary.total_taxable + summary.total_cgst + summary.total_sgst +
            summary.total_igst + summary.total_cess
        )

        return summary

    def calculate_simple(
        self,
        customer_state_code: int,
        items: List[Dict[str, Any]],
        supplier_state_code: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Simple calculation interface compatible with the existing app.py
        calculate_gst() function signature. Accepts a list of dicts.

        Parameters:
            customer_state_code: 2-digit GST state code of the buyer.
            items: List of dicts with keys: qty, price, discount, gst_rate.
            supplier_state_code: Defaults to self.supplier_state_code.

        Returns:
            Dict with totals: is_intra_state, total_taxable, total_cgst,
            total_sgst, total_igst, total_discount, round_off, grand_total,
            and enriched item dicts with taxable_value, cgst, sgst, igst, etc.
        """
        if supplier_state_code is None:
            supplier_state_code = self.supplier_state_code
        is_intra = supplier_state_code == customer_state_code

        total_taxable = Decimal("0.00")
        total_cgst = Decimal("0.00")
        total_sgst = Decimal("0.00")
        total_igst = Decimal("0.00")
        total_discount = Decimal("0.00")

        for item in items:
            qty = Decimal(str(item.get("qty", 0)))
            price = Decimal(str(item.get("price", 0)))
            discount_pct = Decimal(str(item.get("discount", 0)))
            gst_rate = Decimal(str(item.get("gst_rate", 18)))

            gross = qty * price
            disc_amount = (gross * discount_pct / Decimal("100")).quantize(
                ROUNDING_PRECISION, rounding=ROUND_HALF_UP
            )
            taxable = gross - disc_amount

            total_gst = (taxable * gst_rate / Decimal("100")).quantize(
                ROUNDING_PRECISION, rounding=ROUND_HALF_UP
            )

            if is_intra:
                half = (total_gst / Decimal("2")).quantize(
                    ROUNDING_PRECISION, rounding=ROUND_HALF_UP
                )
                cgst = half
                sgst = total_gst - cgst
                igst = Decimal("0.00")
            else:
                cgst = Decimal("0.00")
                sgst = Decimal("0.00")
                igst = total_gst

            total_taxable += taxable
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
            total_discount += disc_amount

            item["taxable_value"] = float(taxable)
            item["cgst"] = float(cgst)
            item["sgst"] = float(sgst)
            item["igst"] = float(igst)
            item["tax_amount"] = float(total_gst)
            item["total"] = float(taxable + total_gst)

        grand_pre = total_taxable + total_cgst + total_sgst + total_igst
        round_off, grand_total = self._calculate_round_off(grand_pre)

        return {
            "is_intra_state": is_intra,
            "total_taxable": float(total_taxable),
            "total_cgst": float(total_cgst),
            "total_sgst": float(total_sgst),
            "total_igst": float(total_igst),
            "total_discount": float(total_discount),
            "round_off": float(round_off),
            "grand_total": float(grand_total),
        }

    def _calculate_line_item(
        self, item: GSTLineItem, is_intra: bool
    ) -> GSTLineResult:
        """Calculate GST for a single line item."""
        result = GSTLineResult(
            product_name=item.product_name,
            hsn=item.hsn,
            qty=item.qty,
            unit=item.unit,
            rate=item.rate,
            discount_percent=item.discount_percent,
            gst_rate=item.gst_rate,
            is_exempt=item.is_exempt,
            is_non_gst=item.is_non_gst,
            is_intra_state=is_intra,
            product_id=item.product_id,
        )

        result.gross_amount = (item.qty * item.rate).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )

        result.discount_amount = (
            result.gross_amount * item.discount_percent / Decimal("100")
        ).quantize(ROUNDING_PRECISION, rounding=ROUND_HALF_UP)

        result.taxable_value = (result.gross_amount - result.discount_amount).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )

        if item.is_exempt or item.is_non_gst or item.gst_rate == Decimal("0"):
            result.tax_amount = Decimal("0.00")
            result.total = result.taxable_value
            return result

        gst_rate = item.gst_rate / Decimal("100")
        total_tax = (result.taxable_value * gst_rate).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )

        if is_intra:
            half_rate = gst_rate / Decimal("2")
            result.cgst_rate = half_rate * Decimal("100")
            result.sgst_rate = half_rate * Decimal("100")
            result.igst_rate = Decimal("0.00")

            cgst = (result.taxable_value * half_rate).quantize(
                ROUNDING_PRECISION, rounding=ROUND_HALF_UP
            )
            result.cgst = cgst
            result.sgst = (total_tax - cgst).quantize(
                ROUNDING_PRECISION, rounding=ROUND_HALF_UP
            )
            result.igst = Decimal("0.00")
        else:
            result.cgst_rate = Decimal("0.00")
            result.sgst_rate = Decimal("0.00")
            result.igst_rate = gst_rate * Decimal("100")

            result.cgst = Decimal("0.00")
            result.sgst = Decimal("0.00")
            result.igst = total_tax

        result.tax_amount = result.cgst + result.sgst + result.igst

        if item.cess_rate > Decimal("0"):
            result.cess = (result.taxable_value * item.cess_rate / Decimal("100")).quantize(
                ROUNDING_PRECISION, rounding=ROUND_HALF_UP
            )
            result.tax_amount += result.cess

        result.total = (result.taxable_value + result.tax_amount).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )

        return result

    def _calculate_round_off(
        self, raw_total: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate round-off and final grand total.
        Indian practice: round to nearest rupee. Fractional part <= 0.50
        rounds down (subtracted), > 0.50 rounds up (added).
        """
        rounded = raw_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        diff = rounded - raw_total
        return diff, rounded

    # -------------------------------------------------------------------
    # HSN-based taxability lookup
    # -------------------------------------------------------------------

    @staticmethod
    def get_gst_rate_for_hsn(hsn: str) -> Decimal:
        """Look up the GST rate for an HSN code. Defaults to 18% if not found."""
        if not hsn:
            return Decimal("18")
        hsn = hsn.strip()

        # Direct lookup
        if hsn in HSN_RATE_MAP:
            return HSN_RATE_MAP[hsn]

        # Prefix lookup (try progressively shorter prefixes)
        for length in range(len(hsn) - 1, 3, -1):
            prefix = hsn[:length]
            if prefix in HSN_RATE_MAP:
                return HSN_RATE_MAP[prefix]

        # Check exempt list
        for exempt_prefix in EXEMPT_HSN_PREFIXES:
            if hsn.startswith(exempt_prefix):
                return Decimal("0")

        return Decimal("18")  # Default GST rate

    @staticmethod
    def is_hsn_exempt(hsn: str) -> bool:
        """Check if an HSN code is exempt from GST."""
        if not hsn:
            return False
        rate = GSTService.get_gst_rate_for_hsn(hsn.strip())
        return rate == Decimal("0")

    @staticmethod
    def is_hsn_non_gst(hsn: str) -> bool:
        """Check if an HSN code is outside GST (petroleum, alcohol, etc.)."""
        if not hsn:
            return False
        # Non-GST items: petroleum crude, high-speed diesel, petrol,
        # natural gas, aviation turbine fuel, alcohol for human consumption
        non_gst_prefixes = [
            "2709", "2710", "2711", "2714",  # Petroleum
            "2203", "2204", "2205", "2206",  # Alcohol
            "2207", "2208",
        ]
        return any(hsn.startswith(p) for p in non_gst_prefixes)

    # -------------------------------------------------------------------
    # Place of Supply Logic
    # -------------------------------------------------------------------

    @staticmethod
    def determine_place_of_supply(
        supplier_state_code: int,
        customer_state_code: Optional[int] = None,
        customer_gstin: Optional[str] = None,
        shipping_state_code: Optional[int] = None,
    ) -> int:
        """
        Determine the Place of Supply as per GST rules:
        - For inter-state B2B: Place of Supply = State of delivery,
          or if different, the state where GSTIN is registered.
        - For intra-state: Place of Supply = Supplier's state.
        """
        if shipping_state_code and shipping_state_code != supplier_state_code:
            return shipping_state_code
        if customer_state_code and customer_state_code != supplier_state_code:
            return customer_state_code
        return supplier_state_code

    @staticmethod
    def is_intra_state(supplier_state_code: int, place_of_supply_code: int) -> bool:
        """Check if the supply is intra-state (same state)."""
        return supplier_state_code == place_of_supply_code

    @staticmethod
    def is_reverse_charge_applicable(
        supplier_gstin: Optional[str] = None,
        customer_gstin: Optional[str] = None,
        hsn: str = "",
    ) -> bool:
        """
        Determine if reverse charge mechanism is applicable.
        Cases: import of services, notified goods/services under RCM,
        GTA, legal services, sponsorships, etc.
        """
        # Import of services (no Indian GSTIN of supplier)
        if customer_gstin and not supplier_gstin:
            return True

        # Specific HSN categories under RCM
        rcm_hsn = [
            "9964",   # Transport of goods by road (GTA)
            "9966",   # Rent-a-cab
            "9971",   # Legal services
            "9972",   # Sponsorship services
            "9982",   # Services by government
            "9986",   # Services by government
        ]
        if hsn and any(hsn.startswith(p) for p in rcm_hsn):
            return True

        return False

    # -------------------------------------------------------------------
    # Tax Inclusive / Tax Exclusive Calculations
    # -------------------------------------------------------------------

    @staticmethod
    def calculate_tax_exclusive(
        amount: Union[int, float, Decimal],
        gst_rate: Union[int, float, Decimal],
    ) -> Dict[str, Decimal]:
        """
        Calculate tax on a tax-exclusive amount.
        Given the base amount, compute GST components.

        Returns: {taxable_value, cgst, sgst, igst, total_gst, total_inclusive}
        """
        taxable = Decimal(str(amount))
        rate = Decimal(str(gst_rate))
        total_gst = (taxable * rate / Decimal("100")).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )
        half = (total_gst / Decimal("2")).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )
        return {
            "taxable_value": taxable,
            "cgst": half,
            "sgst": total_gst - half,
            "igst": total_gst,
            "total_gst": total_gst,
            "total_inclusive": taxable + total_gst,
        }

    @staticmethod
    def calculate_tax_inclusive(
        amount: Union[int, float, Decimal],
        gst_rate: Union[int, float, Decimal],
    ) -> Dict[str, Decimal]:
        """
        Extract tax from a tax-inclusive amount.
        Given the total (inclusive of GST), compute the base and GST.

        Returns: {taxable_value, cgst, sgst, igst, total_gst}
        """
        inclusive = Decimal(str(amount))
        rate = Decimal(str(gst_rate))
        divisor = Decimal("1") + rate / Decimal("100")
        taxable = (inclusive / divisor).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )
        total_gst = inclusive - taxable
        half = (total_gst / Decimal("2")).quantize(
            ROUNDING_PRECISION, rounding=ROUND_HALF_UP
        )
        return {
            "taxable_value": taxable,
            "cgst": half,
            "sgst": total_gst - half,
            "igst": total_gst,
            "total_gst": total_gst,
        }

    @staticmethod
    def get_effective_rate(
        inclusive_amount: Union[int, float, Decimal],
        exclusive_amount: Union[int, float, Decimal],
    ) -> Decimal:
        """Calculate the effective GST rate from inclusive and exclusive amounts."""
        inc = Decimal(str(inclusive_amount))
        exc = Decimal(str(exclusive_amount))
        if exc <= Decimal("0"):
            return Decimal("0")
        rate = ((inc - exc) / exc * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return rate

    # -------------------------------------------------------------------
    # GST Rate Validation
    # -------------------------------------------------------------------

    @staticmethod
    def validate_gst_rate(rate: Union[int, float, Decimal, str]) -> bool:
        """Validate that a GST rate is one of the officially allowed rates."""
        try:
            decimal_rate = Decimal(str(rate))
        except (InvalidOperation, ValueError):
            return False
        return decimal_rate in VALID_GST_RATES

    @staticmethod
    def get_valid_rates() -> List[float]:
        """Return list of valid GST rates as floats."""
        return list(VALID_GST_RATE_FLOATS)

    # -------------------------------------------------------------------
    # B2B / B2C Determination
    # -------------------------------------------------------------------

    @staticmethod
    def is_b2b(customer_gstin: Optional[str] = None) -> bool:
        """Determine if a transaction is B2B (has valid GSTIN)."""
        if customer_gstin:
            from utils import validate_gstIN
            return validate_gstIN(customer_gstin)
        return False

    @staticmethod
    def is_b2c(customer_gstin: Optional[str] = None) -> bool:
        """Determine if a transaction is B2C (no GSTIN or invalid GSTIN)."""
        return not GSTService.is_b2b(customer_gstin)

    # -------------------------------------------------------------------
    # Utility: Breakdown for a single item (convenience)
    # -------------------------------------------------------------------

    @staticmethod
    def calculate_single_item(
        qty: Union[int, float, Decimal],
        rate: Union[int, float, Decimal],
        gst_rate: Union[int, float, Decimal] = Decimal("18"),
        discount_percent: Union[int, float, Decimal] = Decimal("0"),
    ) -> Dict[str, Decimal]:
        """
        Quick single-item GST calculation.
        Returns a dict with taxable_value, cgst, sgst, igst, tax_amount, total.
        """
        item = GSTLineItem(
            qty=qty,
            rate=rate,
            gst_rate=gst_rate,
            discount_percent=discount_percent,
        )
        service = GSTService()
        result = service._calculate_line_item(item, is_intra=True)
        return {
            "gross_amount": result.gross_amount,
            "discount_amount": result.discount_amount,
            "taxable_value": result.taxable_value,
            "gst_rate": result.gst_rate,
            "cgst_rate": result.cgst_rate,
            "sgst_rate": result.sgst_rate,
            "cgst": result.cgst,
            "sgst": result.sgst,
            "igst": result.igst,
            "tax_amount": result.tax_amount,
            "total": result.total,
        }


# ---------------------------------------------------------------------------
# Module-level convenience instance
# ---------------------------------------------------------------------------

default_gst_service = GSTService()


def calculate_gst(
    customer_state_code: int,
    items: List[Dict[str, Any]],
    supplier_state_code: int = 29,
) -> Dict[str, Any]:
    """
    Drop-in replacement for the app.py calculate_gst() function.
    Uses GSTService under the hood for consistent, production-grade logic.
    """
    service = GSTService(supplier_state_code=supplier_state_code)
    return service.calculate_simple(
        customer_state_code=customer_state_code,
        items=items,
        supplier_state_code=supplier_state_code,
    )
