/**
 * GV Powers ERP - Billing Workspace (CRITICAL)
 * Complete invoice creation workflow with GST calculations
 */

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // ── Indian States ─────────────────────────────────────────
    const INDIAN_STATES = GST ? GST.STATES : [
        { code: '01', name: 'Jammu & Kashmir' }, { code: '02', name: 'Himachal Pradesh' },
        { code: '03', name: 'Punjab' }, { code: '04', name: 'Chandigarh' },
        { code: '05', name: 'Uttarakhand' }, { code: '06', name: 'Haryana' },
        { code: '07', name: 'Delhi' }, { code: '08', name: 'Rajasthan' },
        { code: '09', name: 'Uttar Pradesh' }, { code: '10', name: 'Bihar' },
        { code: '11', name: 'Sikkim' }, { code: '12', name: 'Arunachal Pradesh' },
        { code: '13', name: 'Nagaland' }, { code: '14', name: 'Manipur' },
        { code: '15', name: 'Mizoram' }, { code: '16', name: 'Tripura' },
        { code: '17', name: 'Meghalaya' }, { code: '18', name: 'Assam' },
        { code: '19', name: 'West Bengal' }, { code: '20', name: 'Jharkhand' },
        { code: '21', name: 'Odisha' }, { code: '22', name: 'Chhattisgarh' },
        { code: '23', name: 'Madhya Pradesh' }, { code: '24', name: 'Gujarat' },
        { code: '25', name: 'Daman & Diu' }, { code: '26', name: 'Dadra & Nagar Haveli' },
        { code: '27', name: 'Maharashtra' }, { code: '29', name: 'Karnataka' },
        { code: '30', name: 'Goa' }, { code: '31', name: 'Lakshadweep' },
        { code: '32', name: 'Kerala' }, { code: '33', name: 'Tamil Nadu' },
        { code: '34', name: 'Puducherry' }, { code: '35', name: 'Andaman & Nicobar Islands' },
        { code: '36', name: 'Telangana' }, { code: '37', name: 'Andhra Pradesh' },
        { code: '38', name: 'Ladakh' }, { code: '97', name: 'Other Territory' }
    ];

    // ── Company State (from global or data attribute) ─────────
    function getCompanyStateCode() {
        if (typeof company !== 'undefined' && company.state_code) return String(company.state_code).padStart(2, '0');
        const el = document.getElementById('invWrapper');
        return el?.dataset?.companyStateCode || '27';
    }

    function getCustomerStateCode() {
        return customerStateCodeInput?.value || customerStateSelect?.value || '';
    }

    // ── Currency Formatting ───────────────────────────────────
    function fmtCurrency(amount) {
        if (typeof UI !== 'undefined') return UI.formatCurrency(amount);
        const num = parseFloat(amount) || 0;
        return num.toLocaleString('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 });
    }

    function fmtNum(num, decimals = 2) {
        if (typeof UI !== 'undefined') return UI.formatNumber(num, decimals);
        return (parseFloat(num) || 0).toFixed(decimals);
    }

    // ── Billing Form Elements ─────────────────────────────────
    const billingForm = document.getElementById('invoiceForm');
    const customerSearchInput = document.getElementById('customerSearch');
    const customerDropdown = document.getElementById('customerDropdown');
    const customerIdInput = document.getElementById('customer_id');
    const customerNameInput = document.getElementById('custName');
    const customerMobileInput = document.getElementById('custMobile');
    const customerAddressInput = document.getElementById('custAddress');
    const customerStateSelect = document.getElementById('custState');
    const customerGstinInput = document.getElementById('custGstin');
    const customerStateCodeInput = document.getElementById('custStateCode');
    const productSearchInput = document.getElementById('productSearch');
    const productDropdown = document.getElementById('productDropdown');
    const itemsTableBody = document.getElementById('itemsBody');
    const addItemBtn = document.getElementById('addItemBtn');
    const generateBtn = document.getElementById('btnGenerate');
    const stateDropdown = document.getElementById('stateDropdown');

    // ── Populate State Dropdown ───────────────────────────────
    function populateStateDropdown(select) {
        if (!select) return;
        if (select.options.length > 1) return;
        INDIAN_STATES.forEach((state) => {
            const opt = document.createElement('option');
            opt.value = state.code;
            opt.textContent = `${state.code} - ${state.name}`;
            select.appendChild(opt);
        });
    }
    populateStateDropdown(customerStateSelect);
    populateStateDropdown(stateDropdown);

    // ── Customer Search with Debounced Autocomplete ───────────
    let customerSearchTimeout = null;

    if (customerSearchInput) {
        customerSearchInput.addEventListener('input', function () {
            clearTimeout(customerSearchTimeout);
            const query = this.value.trim();
            if (query.length < 2) {
                hideDropdown(customerDropdown);
                return;
            }
            customerSearchTimeout = setTimeout(async () => {
                try {
                    const resp = await fetch(`/api/customers/search?q=${encodeURIComponent(query)}`, {
                        headers: apiHeaders()
                    });
                    if (!resp.ok) throw new Error('Search failed');
                    const data = await resp.json();
                    renderCustomerResults(data.customers || data.results || data);
                } catch (err) {
                    console.error('Customer search error:', err);
                    hideDropdown(customerDropdown);
                }
            }, 300);
        });

        customerSearchInput.addEventListener('focus', function () {
            if (this.value.trim().length >= 2 && customerDropdown?.children.length > 0) {
                showDropdown(customerDropdown);
            }
        });

        document.addEventListener('click', (e) => {
            if (!customerSearchInput.contains(e.target) && !customerDropdown?.contains(e.target)) {
                hideDropdown(customerDropdown);
            }
        });
    }

    function renderCustomerResults(customers) {
        if (!customerDropdown) return;
        if (!customers || customers.length === 0) {
            customerDropdown.innerHTML = '<div class="dropdown-item text-muted py-2">No customers found</div>';
            showDropdown(customerDropdown);
            return;
        }
        customerDropdown.innerHTML = customers.map((c) => `
            <a href="#" class="dropdown-item py-2 px-3 customer-result" data-customer='${JSON.stringify(c).replace(/'/g, "&#39;")}'>
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="fw-semibold">${escapeHtml(c.name || '')}</div>
                        <div class="text-muted small">${escapeHtml(c.mobile || c.phone || '')} ${c.gstin ? '| GSTIN: ' + escapeHtml(c.gstin) : ''}</div>
                    </div>
                    <span class="badge bg-secondary">${escapeHtml(c.state || '')}</span>
                </div>
            </a>
        `).join('');

        customerDropdown.querySelectorAll('.customer-result').forEach((item) => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const customer = JSON.parse(item.dataset.customer);
                selectCustomer(customer);
                hideDropdown(customerDropdown);
            });
        });
        showDropdown(customerDropdown);
    }

    function selectCustomer(customer) {
        if (customerIdInput) customerIdInput.value = customer.id || '';
        if (customerNameInput) customerNameInput.value = customer.name || '';
        if (customerMobileInput) customerMobileInput.value = customer.mobile || customer.phone || '';
        if (customerAddressInput) customerAddressInput.value = customer.address || '';
        if (customerGstinInput) customerGstinInput.value = customer.gstin || '';
        if (customerSearchInput) customerSearchInput.value = customer.name || '';

        const stateCode = customer.state_code || '';
        if (customerStateSelect) {
            customerStateSelect.value = stateCode;
        }
        if (customerStateCodeInput) {
            customerStateCodeInput.value = stateCode;
        }

        // Trigger GST recalculation on state change
        recalculateAll();
    }

    // ── Product Search with Debounced Autocomplete ────────────
    let productSearchTimeout = null;

    if (productSearchInput) {
        productSearchInput.addEventListener('input', function () {
            clearTimeout(productSearchTimeout);
            const query = this.value.trim();
            if (query.length < 2) {
                hideDropdown(productDropdown);
                return;
            }
            productSearchTimeout = setTimeout(async () => {
                try {
                    const resp = await fetch(`/api/products/search?q=${encodeURIComponent(query)}`, {
                        headers: apiHeaders()
                    });
                    if (!resp.ok) throw new Error('Search failed');
                    const data = await resp.json();
                    renderProductResults(data.products || data.results || data);
                } catch (err) {
                    console.error('Product search error:', err);
                    hideDropdown(productDropdown);
                }
            }, 300);
        });

        productSearchInput.addEventListener('focus', function () {
            if (this.value.trim().length >= 2 && productDropdown?.children.length > 0) {
                showDropdown(productDropdown);
            }
        });

        document.addEventListener('click', (e) => {
            if (!productSearchInput.contains(e.target) && !productDropdown?.contains(e.target)) {
                hideDropdown(productDropdown);
            }
        });
    }

    function renderProductResults(products) {
        if (!productDropdown) return;
        if (!products || products.length === 0) {
            productDropdown.innerHTML = '<div class="dropdown-item text-muted py-2">No products found</div>';
            showDropdown(productDropdown);
            return;
        }
        productDropdown.innerHTML = products.map((p) => {
            const stock = parseFloat(p.stock || p.quantity || 0);
            const stockClass = stock <= 0 ? 'text-danger' : stock <= 5 ? 'text-warning' : 'text-success';
            const stockLabel = stock <= 0 ? 'Out of Stock' : `${stock} in stock`;
            return `
            <a href="#" class="dropdown-item py-2 px-3 product-result" data-product='${JSON.stringify(p).replace(/'/g, "&#39;")}'>
                <div class="d-flex align-items-center gap-3">
                    ${p.image || p.image_url ? `<img src="${escapeHtml(p.image || p.image_url)}" alt="" class="rounded" style="width:40px;height:40px;object-fit:cover;">` :
                    `<div class="rounded bg-secondary d-flex align-items-center justify-content-center" style="width:40px;height:40px;"><i data-lucide="package" style="width:18px;height:18px;"></i></div>`}
                    <div class="flex-grow-1">
                        <div class="fw-semibold">${escapeHtml(p.name || p.product_name || '')}</div>
                        <div class="text-muted small">SKU: ${escapeHtml(p.sku || p.code || 'N/A')} ${p.hsn ? '| HSN: ' + escapeHtml(p.hsn) : ''}</div>
                    </div>
                    <div class="text-end">
                        <div class="fw-bold">${fmtCurrency(p.price || p.selling_price || p.unit_price || 0)}</div>
                        <div class="${stockClass} small">${stockLabel}</div>
                    </div>
                </div>
            </a>`;
        }).join('');

        productDropdown.querySelectorAll('.product-result').forEach((item) => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const product = JSON.parse(item.dataset.product);
                addInvoiceItem(product);
                hideDropdown(productDropdown);
                productSearchInput.value = '';
                productSearchInput.focus();
            });
        });
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [productDropdown] });
        showDropdown(productDropdown);
    }

    // ── Dropdown Helpers ──────────────────────────────────────
    function showDropdown(el) {
        if (!el) return;
        el.classList.add('show');
        el.style.display = 'block';
    }

    function hideDropdown(el) {
        if (!el) return;
        el.classList.remove('show');
        el.style.display = 'none';
    }

    // ── Invoice Items Table Management ────────────────────────
    let itemCounter = 0;

    function addInvoiceItem(product) {
        if (!itemsTableBody) return;
        itemCounter++;
        const itemId = `item_${itemCounter}`;
        const price = parseFloat(product.price || product.selling_price || product.unit_price || 0);
        const gstRate = parseFloat(product.gst_rate || product.gst_rate_percent || 18);
        const stock = parseFloat(product.stock || product.quantity || 0);
        const productId = product.id || product.product_id || '';
        const productName = product.name || product.product_name || '';
        const sku = product.sku || product.code || '';
        const hsn = product.hsn || product.hsn_code || '';

        const row = document.createElement('tr');
        row.id = itemId;
        row.className = 'invoice-item-row';
        row.innerHTML = `
            <td class="text-center" style="width:40px;">
                <span class="item-number">${itemsTableBody.children.length + 1}</span>
            </td>
            <td>
                <input type="hidden" name="items[${itemId}][product_id]" value="${escapeAttr(productId)}">
                <input type="hidden" name="items[${itemId}][product_name]" value="${escapeAttr(productName)}">
                <input type="hidden" name="items[${itemId}][sku]" value="${escapeAttr(sku)}">
                <input type="hidden" name="items[${itemId}][hsn]" value="${escapeAttr(hsn)}">
                <div class="fw-semibold">${escapeHtml(productName)}</div>
                <small class="text-muted">SKU: ${escapeHtml(sku)}${hsn ? ' | HSN: ' + escapeHtml(hsn) : ''}</small>
            </td>
            <td style="width:100px;">
                <input type="number" name="items[${itemId}][qty]" class="form-control form-control-sm item-qty"
                       value="1" min="1" max="${stock || 9999}" step="1"
                       data-price="${price}" data-gst-rate="${gstRate}" data-stock="${stock}"
                       onchange="window.Billing.recalculateRow('${itemId}')"
                       oninput="window.Billing.recalculateRow('${itemId}')">
            </td>
            <td style="width:120px;">
                <div class="input-group input-group-sm">
                    <span class="input-group-text">Rs.</span>
                    <input type="number" name="items[${itemId}][price]" class="form-control form-control-sm item-price"
                           value="${fmtNum(price)}" min="0" step="0.01"
                           onchange="window.Billing.recalculateRow('${itemId}')"
                           oninput="window.Billing.recalculateRow('${itemId}')">
                </div>
            </td>
            <td style="width:80px;">
                <select name="items[${itemId}][discount_type]" class="form-select form-select-sm item-discount-type"
                        onchange="window.Billing.recalculateRow('${itemId}')">
                    <option value="percent">%</option>
                    <option value="fixed">Rs.</option>
                </select>
            </td>
            <td style="width:90px;">
                <input type="number" name="items[${itemId}][discount_value]" class="form-control form-control-sm item-discount-value"
                       value="0" min="0" step="0.01"
                       onchange="window.Billing.recalculateRow('${itemId}')"
                       oninput="window.Billing.recalculateRow('${itemId}')">
            </td>
            <td style="width:80px;">
                <select name="items[${itemId}][gst_rate]" class="form-select form-select-sm item-gst-rate"
                        onchange="window.Billing.recalculateRow('${itemId}')">
                    ${GST ? GST.RATES.map((r) => `<option value="${r}" ${r === gstRate ? 'selected' : ''}>${r}%</option>`).join('') :
                [0, 5, 12, 18, 28].map((r) => `<option value="${r}" ${r === gstRate ? 'selected' : ''}>${r}%</option>`).join('')}
                </select>
            </td>
            <td class="text-end item-taxable" style="width:110px;">${fmtCurrency(price)}</td>
            <td class="text-end item-tax" style="width:90px;">${fmtCurrency(price * gstRate / 100)}</td>
            <td class="text-end item-total fw-bold" style="width:120px;">${fmtCurrency(price + price * gstRate / 100)}</td>
            <td class="text-center" style="width:50px;">
                <button type="button" class="btn btn-outline-danger btn-sm remove-item" onclick="window.Billing.removeItem('${itemId}')" title="Remove">
                    <i data-lucide="x" style="width:14px;height:14px;"></i>
                </button>
            </td>
        `;

        itemsTableBody.appendChild(row);
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [row] });

        // Animate entry
        row.style.opacity = '0';
        row.style.transform = 'translateY(-10px)';
        requestAnimationFrame(() => {
            row.style.transition = 'opacity 0.2s, transform 0.2s';
            row.style.opacity = '1';
            row.style.transform = 'translateY(0)';
        });

        recalculateAll();
    }

    function removeItem(itemId) {
        const row = document.getElementById(itemId);
        if (!row) return;
        row.style.transition = 'opacity 0.2s, transform 0.2s';
        row.style.opacity = '0';
        row.style.transform = 'translateX(20px)';
        setTimeout(() => {
            row.remove();
            renumberRows();
            recalculateAll();
        }, 200);
    }

    function renumberRows() {
        if (!itemsTableBody) return;
        itemsTableBody.querySelectorAll('tr').forEach((row, idx) => {
            const numSpan = row.querySelector('.item-number');
            if (numSpan) numSpan.textContent = idx + 1;
        });
    }

    // ── Row Recalculation ─────────────────────────────────────
    function recalculateRow(itemId) {
        const row = document.getElementById(itemId);
        if (!row) return;

        const qtyInput = row.querySelector('.item-qty');
        const priceInput = row.querySelector('.item-price');
        const discountType = row.querySelector('.item-discount-type');
        const discountValue = row.querySelector('.item-discount-value');
        const gstRateSelect = row.querySelector('.item-gst-rate');

        const qty = parseFloat(qtyInput?.value) || 0;
        const price = parseFloat(priceInput?.value) || 0;
        const dType = discountType?.value || 'percent';
        const dValue = parseFloat(discountValue?.value) || 0;
        const gstRate = parseFloat(gstRateSelect?.value) || 0;

        const grossAmount = qty * price;
        let discountAmount = 0;
        if (dType === 'percent') {
            discountAmount = grossAmount * dValue / 100;
        } else {
            discountAmount = dValue * qty;
        }
        const taxable = Math.max(0, grossAmount - discountAmount);
        const tax = taxable * gstRate / 100;

        const taxableEl = row.querySelector('.item-taxable');
        const taxEl = row.querySelector('.item-tax');
        const totalEl = row.querySelector('.item-total');

        if (taxableEl) taxableEl.textContent = fmtCurrency(taxable);
        if (taxEl) taxEl.textContent = fmtCurrency(tax);
        if (totalEl) totalEl.textContent = fmtCurrency(taxable + tax);

        recalculateAll();
    }

    // ── Grand Totals Recalculation ────────────────────────────
    function recalculateAll() {
        const sellerStateCode = getCompanyStateCode();
        const customerState = customerStateSelect?.value || customerStateCodeInput?.value || '';
        const customerStateCode = String(customerState).padStart(2, '0');
        const interState = sellerStateCode !== customerStateCode;

        let subtotal = 0;
        let totalDiscount = 0;
        let totalTaxable = 0;
        let totalCgst = 0;
        let totalSgst = 0;
        let totalIgst = 0;

        const rows = itemsTableBody?.querySelectorAll('.invoice-item-row') || [];
        rows.forEach((row) => {
            const qty = parseFloat(row.querySelector('.item-qty')?.value) || 0;
            const price = parseFloat(row.querySelector('.item-price')?.value) || 0;
            const dType = row.querySelector('.item-discount-type')?.value || 'percent';
            const dValue = parseFloat(row.querySelector('.item-discount-value')?.value) || 0;
            const gstRate = parseFloat(row.querySelector('.item-gst-rate')?.value) || 0;

            const gross = qty * price;
            let disc = 0;
            if (dType === 'percent') {
                disc = gross * dValue / 100;
            } else {
                disc = dValue * qty;
            }
            const taxable = Math.max(0, gross - disc);
            const tax = taxable * gstRate / 100;

            subtotal += gross;
            totalDiscount += disc;
            totalTaxable += taxable;

            if (interState) {
                totalIgst += tax;
            } else {
                totalCgst += tax / 2;
                totalSgst += tax / 2;
            }
        });

        const totalTax = totalCgst + totalSgst + totalIgst;
        const grandTotal = totalTaxable + totalTax;
        const roundOff = Math.round(grandTotal) - grandTotal;
        const grandTotalRounded = grandTotal + roundOff;

        // Update summary elements
        updateSummaryElement('totSubtotal', fmtCurrency(subtotal));
        updateSummaryElement('totDiscount', '-' + fmtCurrency(totalDiscount));
        updateSummaryElement('totTaxable', fmtCurrency(totalTaxable));
        updateSummaryElement('totCgst', fmtCurrency(totalCgst));
        updateSummaryElement('totSgst', fmtCurrency(totalSgst));
        updateSummaryElement('totIgst', fmtCurrency(totalIgst));
        updateSummaryElement('totRoundOff', (roundOff >= 0 ? '+' : '') + fmtCurrency(roundOff));
        updateSummaryElement('totGrand', fmtCurrency(grandTotalRounded));

        // Toggle CGST/SGST vs IGST display
        const cgstRow = document.getElementById('cgstRow');
        const sgstRow = document.getElementById('sgstRow');
        const igstRow = document.getElementById('igstRow');
        if (cgstRow) cgstRow.style.display = interState ? 'none' : '';
        if (sgstRow) sgstRow.style.display = interState ? 'none' : '';
        if (igstRow) {
            igstRow.style.display = interState ? '' : 'none';
            const igstLabel = igstRow.querySelector('.igst-label');
            if (igstLabel) {
                const rateText = rows.length > 0 ? ' (varies)' : '';
                igstLabel.textContent = `IGST${rateText}`;
            }
        }

        // Update GST type indicator
        const gstTypeBadge = document.getElementById('gstTypeIndicator');
        if (gstTypeBadge) {
            gstTypeBadge.textContent = interState ? 'Inter-State (IGST)' : 'Intra-State (CGST+SGST)';
            gstTypeBadge.className = `badge ${interState ? 'bg-warning' : 'bg-info'} mb-2`;
        }

        // Amount in words
        const amountWordsEl = document.getElementById('amountInWords');
        if (amountWordsEl && typeof GST !== 'undefined') {
            amountWordsEl.textContent = GST.amountInWords(grandTotalRounded);
        } else if (amountWordsEl) {
            amountWordsEl.textContent = numberToWordsIndian(Math.round(grandTotalRounded));
        }
    }

    function updateSummaryElement(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    // ── Generate Invoice ──────────────────────────────────────
    if (generateBtn) {
        generateBtn.addEventListener('click', async () => {
            // Validate
            const custName = customerNameInput?.value?.trim();
            if (!customerIdInput?.value && !custName) {
                showFlashToast('Please search for a customer or enter a name to create a new one', 'warning');
                customerSearchInput?.focus();
                return;
            }
            const rows = itemsTableBody?.querySelectorAll('.invoice-item-row');
            if (!rows || rows.length === 0) {
                showFlashToast('Please add at least one item to the invoice', 'warning');
                productSearchInput?.focus();
                return;
            }

            // Collect items data
            const items = [];
            rows.forEach((row) => {
                items.push({
                    product_id: row.querySelector('input[name$="[product_id]"]')?.value || '',
                    product_name: row.querySelector('input[name$="[product_name]"]')?.value || '',
                    sku: row.querySelector('input[name$="[sku]"]')?.value || '',
                    hsn: row.querySelector('input[name$="[hsn]"]')?.value || '',
                    qty: parseFloat(row.querySelector('.item-qty')?.value) || 1,
                    price: parseFloat(row.querySelector('.item-price')?.value) || 0,
                    discount_type: row.querySelector('.item-discount-type')?.value || 'percent',
                    discount_value: parseFloat(row.querySelector('.item-discount-value')?.value) || 0,
                    gst_rate: parseFloat(row.querySelector('.item-gst-rate')?.value) || 0
                });
            });

            const formData = {
                customer_id: customerIdInput.value,
                customer_name: customerNameInput?.value || '',
                customer_mobile: customerMobileInput?.value || '',
                customer_email: document.getElementById('custEmail')?.value || '',
                customer_address: customerAddressInput?.value || '',
                customer_state: customerStateSelect?.value || '',
                customer_state_code: customerStateCodeInput?.value || customerStateSelect?.value || '',
                customer_gstin: customerGstinInput?.value || '',
                eway_bill_number: document.getElementById('ewayBillNumber')?.value?.trim() || '',
                invoice_type: document.getElementById('invoiceType')?.value || 'sales',
                reference_no: document.getElementById('referenceNo')?.value || '',
                notes: document.getElementById('invoiceNotes')?.value || '',
                items: items
            };

            // Loading state
            const originalText = generateBtn.innerHTML;
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generating...';

            try {
                const resp = await fetch('/invoices/create', {
                    method: 'POST',
                    headers: apiHeaders(),
                    body: JSON.stringify(formData)
                });

                const data = await resp.json();

                if (resp.ok && data.success !== false) {
                    showFlashToast('Invoice created successfully!', 'success');
                    if (data.redirect_url || data.invoice_id) {
                        window.location.href = data.redirect_url || `/invoices/${data.invoice_id}/preview`;
                    } else if (data.id) {
                        window.location.href = `/invoices/${data.id}/preview`;
                    }
                } else {
                    showFlashToast(data.message || data.error || 'Failed to create invoice', 'danger');
                    if (data.errors) {
                        Object.values(data.errors).flat().forEach((msg) => {
                            showFlashToast(msg, 'danger');
                        });
                    }
                }
            } catch (err) {
                console.error('Invoice creation error:', err);
                showFlashToast('Network error. Please try again.', 'danger');
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = originalText;
            }
        });
    }

    // ── Add Item Button ───────────────────────────────────────
    if (addItemBtn) {
        addItemBtn.addEventListener('click', () => {
            productSearchInput?.focus();
            if (productSearchInput) {
                productSearchInput.dispatchEvent(new Event('focus'));
            }
        });
    }

    // ── Customer State Change Listener ────────────────────────
    if (customerStateSelect) {
        customerStateSelect.addEventListener('change', () => {
            if (customerStateCodeInput) customerStateCodeInput.value = customerStateSelect.value;
            recalculateAll();
        });
    }

    // ── Barcode Scanner Support ───────────────────────────────
    let barcodeBuffer = '';
    let barcodeTimer = null;
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' && e.target.id !== 'productSearch' && e.target.id !== 'customerSearch') return;
        if (e.target.id === 'productSearch') return;

        clearTimeout(barcodeTimer);
        barcodeBuffer += e.key;
        barcodeTimer = setTimeout(() => { barcodeBuffer = ''; }, 100);

        if (barcodeBuffer.length >= 8 && (e.key === 'Enter' || e.keyCode === 13)) {
            const barcode = barcodeBuffer.slice(0, -1);
            barcodeBuffer = '';
            searchProductByBarcode(barcode);
        }
    });

    async function searchProductByBarcode(barcode) {
        try {
            const resp = await fetch(`/api/products/search?q=${encodeURIComponent(barcode)}&by_barcode=true`, {
                headers: apiHeaders()
            });
            if (!resp.ok) return;
            const data = await resp.json();
            const products = data.products || data.results || data;
            if (products && products.length > 0) {
                addInvoiceItem(products[0]);
                showFlashToast(`Added: ${products[0].name || products[0].product_name}`, 'success');
            } else {
                showFlashToast(`No product found for barcode: ${barcode}`, 'warning');
            }
        } catch (err) {
            console.warn('Barcode search error:', err);
        }
    }

    // ── Simple Number to Words Fallback ───────────────────────
    function numberToWordsIndian(num) {
        if (typeof GST !== 'undefined') return GST.amountInWords(num);
        if (num === 0) return 'Zero';
        return 'Rupees ' + num.toLocaleString('en-IN') + ' Only';
    }

    // ── Escape Helpers ────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeAttr(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ── Public API ────────────────────────────────────────────
    window.Billing = {
        addInvoiceItem,
        removeItem,
        recalculateRow,
        recalculateAll,
        selectCustomer,
        getCompanyStateCode,
        getCustomerStateCode,
        INDIAN_STATES
    };
});
