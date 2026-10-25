/**
 * GV Powers ERP - GST Calculation Utilities
 * Handles all Indian GST computations for invoices
 */

const GST = (() => {
    'use strict';

    // ── Standard Indian GST Rates ─────────────────────────────
    const RATES = [0, 0.25, 3, 5, 12, 18, 28];

    const HSN_TAXABILITY = {
        'exempt': 0,
        'zero_rated': 0,
        'nil_rated': 0,
        'standard': null
    };

    // ── Indian States with Codes ──────────────────────────────
    const STATES = [
        { code: '01', name: 'Jammu & Kashmir' },
        { code: '02', name: 'Himachal Pradesh' },
        { code: '03', name: 'Punjab' },
        { code: '04', name: 'Chandigarh' },
        { code: '05', name: 'Uttarakhand' },
        { code: '06', name: 'Haryana' },
        { code: '07', name: 'Delhi' },
        { code: '08', name: 'Rajasthan' },
        { code: '09', name: 'Uttar Pradesh' },
        { code: '10', name: 'Bihar' },
        { code: '11', name: 'Sikkim' },
        { code: '12', name: 'Arunachal Pradesh' },
        { code: '13', name: 'Nagaland' },
        { code: '14', name: 'Manipur' },
        { code: '15', name: 'Mizoram' },
        { code: '16', name: 'Tripura' },
        { code: '17', name: 'Meghalaya' },
        { code: '18', name: 'Assam' },
        { code: '19', name: 'West Bengal' },
        { code: '20', name: 'Jharkhand' },
        { code: '21', name: 'Odisha' },
        { code: '22', name: 'Chhattisgarh' },
        { code: '23', name: 'Madhya Pradesh' },
        { code: '24', name: 'Gujarat' },
        { code: '25', name: 'Daman & Diu' },
        { code: '26', name: 'Dadra & Nagar Haveli' },
        { code: '27', name: 'Maharashtra' },
        { code: '29', name: 'Karnataka' },
        { code: '30', name: 'Goa' },
        { code: '31', name: 'Lakshadweep' },
        { code: '32', name: 'Kerala' },
        { code: '33', name: 'Tamil Nadu' },
        { code: '34', name: 'Puducherry' },
        { code: '35', name: 'Andaman & Nicobar Islands' },
        { code: '36', name: 'Telangana' },
        { code: '37', name: 'Andhra Pradesh' },
        { code: '38', name: 'Ladakh' },
        { code: '97', name: 'Other Territory' }
    ];

    // ── Determine Intra or Inter State ────────────────────────
    function isInterState(sellerStateCode, customerStateCode) {
        if (!sellerStateCode || !customerStateCode) return false;
        const sc = String(sellerStateCode).padStart(2, '0');
        const cc = String(customerStateCode).padStart(2, '0');
        return sc !== cc;
    }

    // ── Round to 2 decimal places ─────────────────────────────
    function round2(num) {
        return Math.round((num + Number.EPSILON) * 100) / 100;
    }

    // ── Calculate Indian Round Off ────────────────────────────
    function calculateRoundOff(amount) {
        const rounded = Math.round(amount);
        return round2(rounded - amount);
    }

    // ── Calculate GST for a single item ───────────────────────
    function calculateItemGST(item, sellerStateCode, customerStateCode) {
        const qty = parseFloat(item.qty) || 0;
        const price = parseFloat(item.price) || parseFloat(item.unit_price) || 0;
        const discountPercent = parseFloat(item.discount_percent) || 0;
        const gstRate = parseFloat(item.gst_rate) || parseFloat(item.gst_rate_percent) || 0;

        const grossAmount = round2(qty * price);
        const discountAmount = round2(grossAmount * discountPercent / 100);
        const taxableAmount = round2(grossAmount - discountAmount);
        const taxAmount = round2(taxableAmount * gstRate / 100);

        const interState = isInterState(sellerStateCode, customerStateCode);

        let cgst = 0, sgst = 0, igst = 0;
        if (interState) {
            igst = taxAmount;
        } else {
            cgst = round2(taxAmount / 2);
            sgst = round2(taxAmount / 2);
            // Fix rounding: ensure cgst + sgst == taxAmount
            if (round2(cgst + sgst) !== taxAmount) {
                cgst = round2(taxAmount - sgst);
            }
        }

        const totalAmount = round2(taxableAmount + taxAmount);

        return {
            gross_amount: grossAmount,
            discount_amount: discountAmount,
            taxable_amount: taxableAmount,
            gst_rate: gstRate,
            cgst_rate: interState ? 0 : gstRate / 2,
            sgst_rate: interState ? 0 : gstRate / 2,
            igst_rate: interState ? gstRate : 0,
            cgst: cgst,
            sgst: sgst,
            igst: igst,
            tax_amount: taxAmount,
            total_amount: totalAmount,
            inter_state: interState
        };
    }

    // ── Calculate GST for all items (Main Function) ───────────
    function calculateGST(items, sellerStateCode, customerStateCode) {
        if (!Array.isArray(items) || items.length === 0) {
            return {
                items: [],
                subtotal: 0,
                total_discount: 0,
                total_taxable: 0,
                total_cgst: 0,
                total_sgst: 0,
                total_igst: 0,
                total_tax: 0,
                grand_total: 0,
                round_off: 0,
                grand_total_rounded: 0,
                inter_state: isInterState(sellerStateCode, customerStateCode)
            };
        }

        let subtotal = 0;
        let totalDiscount = 0;
        let totalTaxable = 0;
        let totalCgst = 0;
        let totalSgst = 0;
        let totalIgst = 0;
        let totalTax = 0;

        const calculatedItems = items.map((item) => {
            const result = calculateItemGST(item, sellerStateCode, customerStateCode);
            subtotal += result.gross_amount;
            totalDiscount += result.discount_amount;
            totalTaxable += result.taxable_amount;
            totalCgst += result.cgst;
            totalSgst += result.sgst;
            totalIgst += result.igst;
            totalTax += result.tax_amount;
            return { ...item, ...result };
        });

        const grandTotal = round2(totalTaxable + totalTax);
        const roundOff = calculateRoundOff(grandTotal);
        const grandTotalRounded = round2(grandTotal + roundOff);

        return {
            items: calculatedItems,
            subtotal: round2(subtotal),
            total_discount: round2(totalDiscount),
            total_taxable: round2(totalTaxable),
            total_cgst: round2(totalCgst),
            total_sgst: round2(totalSgst),
            total_igst: round2(totalIgst),
            total_tax: round2(totalTax),
            grand_total: grandTotal,
            round_off: roundOff,
            grand_total_rounded: grandTotalRounded,
            inter_state: isInterState(sellerStateCode, customerStateCode)
        };
    }

    // ── Format GST Amount for Display ─────────────────────────
    function formatGSTAmount(amount) {
        return (typeof UI !== 'undefined' && UI.formatCurrency) ? UI.formatCurrency(amount) : 'Rs. ' + round2(amount || 0).toFixed(2);
    }

    // ── Get State Name by Code ────────────────────────────────
    function getStateName(code) {
        const paddedCode = String(code).padStart(2, '0');
        const state = STATES.find((s) => s.code === paddedCode);
        return state ? state.name : '';
    }

    // ── Get State Code by Name ────────────────────────────────
    function getStateCode(name) {
        if (!name) return '';
        const normalized = name.trim().toLowerCase();
        const state = STATES.find((s) => s.name.toLowerCase() === normalized);
        return state ? state.code : '';
    }

    // ── Validate GSTIN Format ─────────────────────────────────
    function validateGSTIN(gstin) {
        if (!gstin) return { valid: false, message: 'GSTIN is required' };
        const pattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
        if (!pattern.test(gstin)) {
            return { valid: false, message: 'Invalid GSTIN format' };
        }
        const stateCode = gstin.substring(0, 2);
        const validState = STATES.find((s) => s.code === stateCode);
        if (!validState) {
            return { valid: false, message: 'Invalid state code in GSTIN' };
        }
        return {
            valid: true,
            state_code: stateCode,
            state_name: validState.name,
            pan: gstin.substring(2, 12),
            entity_number: gstin.substring(12, 13),
            checksum: gstin.substring(14, 15)
        };
    }

    // ── Get Place of Supply Options ───────────────────────────
    function getPlaceOfSupplyOptions() {
        return STATES.map((s) => ({
            value: s.code,
            label: `${s.code} - ${s.name}`
        }));
    }

    // ── Build GST Summary HTML ────────────────────────────────
    function buildGSTSummaryHTML(gstResult) {
        if (!gstResult) return '';
        const isInter = gstResult.inter_state;
        const taxLabel = isInter ? 'IGST' : 'CGST + SGST';
        return `
            <div class="gst-summary">
                <div class="d-flex justify-content-between mb-1">
                    <span>Subtotal</span>
                    <span>${formatGSTAmount(gstResult.subtotal)}</span>
                </div>
                ${gstResult.total_discount > 0 ? `
                <div class="d-flex justify-content-between mb-1 text-success">
                    <span>Discount</span>
                    <span>-${formatGSTAmount(gstResult.total_discount)}</span>
                </div>` : ''}
                <div class="d-flex justify-content-between mb-1">
                    <span>Taxable Amount</span>
                    <span>${formatGSTAmount(gstResult.total_taxable)}</span>
                </div>
                <hr class="my-1">
                ${isInter ? `
                <div class="d-flex justify-content-between mb-1">
                    <span>IGST</span>
                    <span>${formatGSTAmount(gstResult.total_igst)}</span>
                </div>` : `
                <div class="d-flex justify-content-between mb-1">
                    <span>CGST</span>
                    <span>${formatGSTAmount(gstResult.total_cgst)}</span>
                </div>
                <div class="d-flex justify-content-between mb-1">
                    <span>SGST</span>
                    <span>${formatGSTAmount(gstResult.total_sgst)}</span>
                </div>`}
                <hr class="my-1">
                ${gstResult.round_off !== 0 ? `
                <div class="d-flex justify-content-between mb-1">
                    <span>Round Off</span>
                    <span>${gstResult.round_off >= 0 ? '+' : ''}${formatGSTAmount(gstResult.round_off)}</span>
                </div>` : ''}
                <div class="d-flex justify-content-between mb-1 fw-bold fs-5">
                    <span>Grand Total</span>
                    <span>${formatGSTAmount(gstResult.grand_total_rounded)}</span>
                </div>
            </div>
        `;
    }

    // ── Amount to Words (Indian) ──────────────────────────────
    function amountInWords(amount) {
        if (!amount || amount === 0) return 'Zero';
        const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
            'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
            'Seventeen', 'Eighteen', 'Nineteen'];
        const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

        function convertBelow1000(n) {
            if (n === 0) return '';
            if (n < 20) return ones[n];
            if (n < 100) return tens[Math.floor(n / 10)] + (n % 10 ? ' ' + ones[n % 10] : '');
            return ones[Math.floor(n / 100)] + ' Hundred' + (n % 100 ? ' and ' + convertBelow1000(n % 100) : '');
        }

        const rupees = Math.floor(amount);
        const paise = Math.round((amount - rupees) * 100);
        let result = '';

        if (rupees >= 10000000) {
            result += convertBelow1000(Math.floor(rupees / 10000000)) + ' Crore ';
        }
        if (rupees >= 100000) {
            result += convertBelow1000(Math.floor((rupees % 10000000) / 100000)) + ' Lakh ';
        }
        if (rupees >= 1000) {
            result += convertBelow1000(Math.floor((rupees % 100000) / 1000)) + ' Thousand ';
        }
        if (rupees >= 100) {
            result += convertBelow1000(Math.floor(rupees % 1000)) + ' ';
        } else {
            result += convertBelow1000(rupees) + ' ';
        }

        result = result.trim() + ' Rupees';
        if (paise > 0) {
            result += ' and ' + convertBelow1000(paise) + ' Paise';
        }
        result += ' Only';
        return result;
    }

    // ── Public API ────────────────────────────────────────────
    return {
        RATES,
        STATES,
        isInterState,
        calculateItemGST,
        calculateGST,
        formatGSTAmount,
        getStateName,
        getStateCode,
        validateGSTIN,
        getPlaceOfSupplyOptions,
        buildGSTSummaryHTML,
        amountInWords,
        round2
    };
})();

if (typeof window !== 'undefined') window.GST = GST;
