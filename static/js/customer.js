/**
 * GV Powers ERP - Customer Module
 * Customer search, form validation, auto-fill, and mobile validation
 */

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // ── Indian States for Dropdowns ───────────────────────────
    const STATES = (typeof GST !== 'undefined' && GST.STATES) ? GST.STATES : [
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

    // ── Populate State Dropdown ───────────────────────────────
    function populateStates(selectEl) {
        if (!selectEl || selectEl.options.length > 1) return;
        STATES.forEach((state) => {
            const opt = document.createElement('option');
            opt.value = state.code;
            opt.textContent = `${state.code} - ${state.name}`;
            selectEl.appendChild(opt);
        });
    }

    document.querySelectorAll('#state, #customerState, [name="state"], [name="state_code"]').forEach(populateStates);

    // ── Customer Search / Autocomplete ────────────────────────
    const customerSearchInputs = document.querySelectorAll('.customer-autocomplete, [data-customer-search]');

    customerSearchInputs.forEach((input) => {
        const dropdownId = input.dataset.dropdown || input.id + 'Dropdown';
        let dropdown = document.getElementById(dropdownId);

        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.id = dropdownId;
            dropdown.className = 'dropdown-menu w-100';
            dropdown.style.cssText = 'max-height:300px;overflow-y:auto;display:none;';
            input.parentNode.style.position = 'relative';
            input.parentNode.appendChild(dropdown);
        }

        const debounceFn = (typeof UI !== 'undefined' && UI.debounce) ? UI.debounce : (fn, ms) => { let t; return function(...a) { clearTimeout(t); t = setTimeout(() => fn.apply(this, a), ms); }; };
        input.addEventListener('input', debounceFn(async function () {
            const query = this.value.trim();
            if (query.length < 2) {
                dropdown.style.display = 'none';
                return;
            }

            try {
                const resp = await fetch(`/api/customers/search?q=${encodeURIComponent(query)}`, {
                    headers: apiHeaders()
                });
                if (!resp.ok) throw new Error('Search failed');
                const data = await resp.json();
                const customers = data.customers || data.results || data;
                renderCustomerDropdown(dropdown, customers, input);
            } catch (err) {
                console.error('Customer search error:', err);
                dropdown.style.display = 'none';
            }
        }, 300));

        input.addEventListener('focus', function () {
            if (this.value.trim().length >= 2 && dropdown.children.length > 0) {
                dropdown.style.display = 'block';
            }
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    });

    function renderCustomerDropdown(dropdown, customers, searchInput) {
        if (!customers || customers.length === 0) {
            dropdown.innerHTML = `
                <div class="dropdown-item text-muted py-2">No customers found</div>
                <div class="dropdown-divider"></div>
                <a href="/customers/create?name=${encodeURIComponent(searchInput.value)}" class="dropdown-item py-2 text-primary">
                    <i data-lucide="plus" style="width:14px;height:14px;" class="me-1"></i> Add New Customer
                </a>
            `;
            dropdown.style.display = 'block';
            if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [dropdown] });
            return;
        }

        dropdown.innerHTML = customers.map((c) => `
            <a href="#" class="dropdown-item py-2 px-3 customer-select-item" data-customer='${JSON.stringify(c).replace(/'/g, "&#39;")}'>
                <div class="d-flex justify-content-between">
                    <div>
                        <div class="fw-semibold">${escapeHtml(c.name)}</div>
                        <small class="text-muted">${escapeHtml(c.mobile || c.phone || '')} ${c.email ? '| ' + escapeHtml(c.email) : ''}</small>
                    </div>
                    <div class="text-end">
                        ${c.gstin ? `<div class="small text-muted">GSTIN: ${escapeHtml(c.gstin)}</div>` : ''}
                        ${c.state ? `<span class="badge bg-secondary">${escapeHtml(c.state)}</span>` : ''}
                    </div>
                </div>
            </a>
        `).join('');

        dropdown.querySelectorAll('.customer-select-item').forEach((item) => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const customer = JSON.parse(item.dataset.customer);
                applyCustomerData(customer, searchInput);
                dropdown.style.display = 'none';
            });
        });

        dropdown.style.display = 'block';
    }

    function applyCustomerData(customer, searchInput) {
        const form = searchInput?.closest('form');
        if (!form) return;

        const fieldMap = {
            id: ['customer_id', 'customerId'],
            name: ['customer_name', 'customerName', 'name'],
            mobile: ['customer_mobile', 'customerMobile', 'phone', 'mobile'],
            email: ['customer_email', 'customerEmail', 'email'],
            address: ['customer_address', 'customerAddress', 'address'],
            state: ['customer_state', 'customerState', 'state_code', 'state'],
            gstin: ['customer_gstin', 'customerGstin', 'gstin'],
            pan: ['customer_pan', 'customerPan', 'pan']
        };

        Object.entries(fieldMap).forEach(([key, fieldNames]) => {
            const value = customer[key] || '';
            for (const fieldName of fieldNames) {
                const field = form.querySelector(`[name="${fieldName}"], #${fieldName}`);
                if (field) {
                    field.value = value;
                    if (key === 'name' && searchInput && field !== searchInput) {
                        searchInput.value = value;
                    }
                    break;
                }
            }
        });

        if (typeof UI !== 'undefined') {
            UI.showToast('Customer data loaded', 'success', 2000);
        }
    }

    // ── Customer Form Validation ──────────────────────────────
    const customerForm = document.getElementById('customerForm');

    if (customerForm) {
        customerForm.addEventListener('submit', (e) => {
            let valid = true;

            // Clear previous errors
            if (typeof FormValidator !== 'undefined') {
                FormValidator.clearAllErrors(customerForm);
            }

            // Name validation
            const nameField = customerForm.querySelector('[name="name"], #name');
            if (nameField && !nameField.value.trim()) {
                showFieldError(nameField, 'Customer name is required');
                valid = false;
            }

            // Mobile validation
            const mobileField = customerForm.querySelector('[name="mobile"], #mobile');
            if (mobileField && mobileField.value.trim()) {
                if (!validateIndianMobile(mobileField.value.trim())) {
                    showFieldError(mobileField, 'Enter a valid 10-digit Indian mobile number starting with 6-9');
                    valid = false;
                }
            }

            // Email validation (optional)
            const emailField = customerForm.querySelector('[name="email"], #email');
            if (emailField && emailField.value.trim()) {
                if (!validateEmail(emailField.value.trim())) {
                    showFieldError(emailField, 'Enter a valid email address');
                    valid = false;
                }
            }

            // GSTIN validation (optional)
            const gstinField = customerForm.querySelector('[name="gstin"], #gstin');
            if (gstinField && gstinField.value.trim()) {
                if (typeof GST !== 'undefined') {
                    const result = GST.validateGSTIN(gstinField.value.trim().toUpperCase());
                    if (!result.valid) {
                        showFieldError(gstinField, result.message);
                        valid = false;
                    }
                } else {
                    const pattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
                    if (!pattern.test(gstinField.value.trim().toUpperCase())) {
                        showFieldError(gstinField, 'Invalid GSTIN format');
                        valid = false;
                    }
                }
            }

            // PAN validation (optional)
            const panField = customerForm.querySelector('[name="pan"], #pan');
            if (panField && panField.value.trim()) {
                if (!validatePAN(panField.value.trim().toUpperCase())) {
                    showFieldError(panField, 'Invalid PAN format (e.g., ABCDE1234F)');
                    valid = false;
                }
            }

            if (!valid) {
                e.preventDefault();
                showFlashToast('Please fix the errors in the form', 'danger');
            }
        });
    }

    // ── Mobile Number Validation (Indian Format) ──────────────
    function validateIndianMobile(value) {
        const cleaned = value.replace(/[\s\-\(\)\+]/g, '');
        if (/^91[6-9]\d{8}$/.test(cleaned)) return true;
        if (/^[6-9]\d{9}$/.test(cleaned)) return true;
        return false;
    }

    function formatIndianMobile(value) {
        const cleaned = value.replace(/\D/g, '');
        if (cleaned.length === 10 && /^[6-9]/.test(cleaned)) {
            return cleaned;
        }
        if (cleaned.length === 12 && cleaned.startsWith('91')) {
            return cleaned.substring(2);
        }
        return cleaned;
    }

    // Mobile field auto-formatting
    document.querySelectorAll('[name="mobile"], #mobile, [data-mobile]').forEach((field) => {
        field.addEventListener('blur', function () {
            const formatted = formatIndianMobile(this.value);
            if (formatted !== this.value && formatted.length >= 10) {
                this.value = formatted;
            }
        });

        field.addEventListener('input', function () {
            this.value = this.value.replace(/[^\d\+\-\s]/g, '');
            if (this.value.replace(/\D/g, '').length === 10) {
                this.classList.remove('is-invalid');
                const feedback = this.parentNode?.querySelector('.invalid-feedback');
                if (feedback) feedback.remove();
            }
        });
    });

    // ── Auto-fill State from GSTIN ────────────────────────────
    const gstinField = document.querySelector('[name="gstin"], #gstin');
    if (gstinField) {
        gstinField.addEventListener('input', debounceFn(function () {
            const gstin = this.value.trim().toUpperCase();
            if (gstin.length >= 2) {
                const stateCode = gstin.substring(0, 2);
                const stateField = customerForm?.querySelector('[name="state_code"], [name="state"], #state, #stateCode');
                if (stateField) {
                    const validState = STATES.find((s) => s.code === stateCode);
                    if (validState) {
                        stateField.value = stateCode;
                    }
                }
            }
        }, 300));
    }

    // ── Email Validation ──────────────────────────────────────
    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    // ── PAN Validation ────────────────────────────────────────
    function validatePAN(pan) {
        return /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(pan);
    }

    // ── Show Field Error ──────────────────────────────────────
    function showFieldError(field, message) {
        if (typeof FormValidator !== 'undefined') {
            FormValidator.showFieldError(field, message);
        } else {
            field.classList.add('is-invalid');
            let feedback = field.parentNode?.querySelector('.invalid-feedback');
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                field.parentNode?.appendChild(feedback);
            }
            feedback.textContent = message;
        }
    }

    // ── Customer List Search/Filter ───────────────────────────
    const customerListSearch = document.getElementById('customerListSearch');
    const customerTable = document.getElementById('customerTable');

    if (customerListSearch && customerTable) {
        customerListSearch.addEventListener('input', debounceFn(function () {
            const query = this.value.toLowerCase();
            customerTable.querySelectorAll('tbody tr').forEach((row) => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        }, 200));
    }

    // ── Customer Quick View ───────────────────────────────────
    document.querySelectorAll('[data-customer-id]').forEach((el) => {
        el.addEventListener('click', async (e) => {
            const id = el.dataset.customerId;
            if (!id) return;

            const resp = await fetch(`/api/customers/${id}`, {
                headers: apiHeaders()
            }).catch(() => null);

            if (!resp || !resp.ok) return;

            const data = await resp.json();
            const modal = document.getElementById('customerDetailModal');
            if (!modal) return;

            modal.querySelector('.customer-detail-name').textContent = data.name || '';
            modal.querySelector('.customer-detail-mobile').textContent = data.mobile || '';
            modal.querySelector('.customer-detail-email').textContent = data.email || '-';
            modal.querySelector('.customer-detail-address').textContent = data.address || '-';
            modal.querySelector('.customer-detail-gstin').textContent = data.gstin || '-';
            modal.querySelector('.customer-detail-state').textContent = data.state || '-';
            modal.querySelector('.customer-detail-pan').textContent = data.pan || '-';
            modal.querySelector('.customer-detail-balance').textContent = (typeof UI !== 'undefined' && UI.formatCurrency) ? UI.formatCurrency(data.balance || 0) : 'Rs. ' + (data.balance || 0).toFixed(2);

            bootstrap.Modal.getOrCreateInstance(modal).show();
        });
    });

    // ── Helper ────────────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function apiHeaders(extra = {}) {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return {
            'Content-Type': 'application/json',
            'X-CSRFToken': meta ? meta.getAttribute('content') : '',
            'X-Requested-With': 'XMLHttpRequest',
            ...extra
        };
    }

    // ── Public API ────────────────────────────────────────────
    window.Customer = {
        validateIndianMobile,
        formatIndianMobile,
        validateEmail,
        validatePAN,
        populateStates,
        applyCustomerData
    };
});
