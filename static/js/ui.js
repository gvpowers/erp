/**
 * GV Powers ERP - UI Utilities
 * Common UI helper functions used across the application
 */

const UI = (() => {
    'use strict';

    // ── Debounce ──────────────────────────────────────────────
    function debounce(fn, delay = 300) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // ── Throttle ──────────────────────────────────────────────
    function throttle(fn, limit = 200) {
        let inThrottle = false;
        return function (...args) {
            if (!inThrottle) {
                fn.apply(this, args);
                inThrottle = true;
                setTimeout(() => { inThrottle = false; }, limit);
            }
        };
    }

    // ── Indian Currency Formatting ────────────────────────────
    function formatCurrency(amount) {
        if (amount === null || amount === undefined || isNaN(amount)) return 'Rs. 0.00';
        const num = parseFloat(amount);
        return num.toLocaleString('en-IN', {
            style: 'currency',
            currency: 'INR',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function formatNumber(num, decimals = 2) {
        if (num === null || num === undefined || isNaN(num)) return '0';
        return parseFloat(num).toLocaleString('en-IN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    // ── Date Formatting ───────────────────────────────────────
    function formatDate(dateStr, format = 'dd/mm/yyyy') {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        const shortMonth = d.toLocaleString('en-IN', { month: 'short' });
        const longMonth = d.toLocaleString('en-IN', { month: 'long' });
        switch (format) {
            case 'dd/mm/yyyy': return `${day}/${month}/${year}`;
            case 'mm/dd/yyyy': return `${month}/${day}/${year}`;
            case 'yyyy-mm-dd': return `${year}-${month}-${day}`;
            case 'dd-MMM-yyyy': return `${day}-${shortMonth}-${year}`;
            case 'dd MMMM yyyy': return `${day} ${longMonth} ${year}`;
            default: return `${day}/${month}/${year}`;
        }
    }

    // ── Loading Skeleton ──────────────────────────────────────
    function showSkeleton(container, rows = 5) {
        if (typeof container === 'string') container = document.querySelector(container);
        if (!container) return;
        const skeletonHtml = Array.from({ length: rows }, () => `
            <div class="skeleton-row d-flex align-items-center mb-2">
                <div class="skeleton-avatar rounded me-3"></div>
                <div class="flex-grow-1">
                    <div class="skeleton-line skeleton-line-lg mb-2"></div>
                    <div class="skeleton-line skeleton-line-sm"></div>
                </div>
            </div>
        `).join('');
        container.innerHTML = `<div class="skeleton-wrapper">${skeletonHtml}</div>`;
    }

    function hideSkeleton(container) {
        if (typeof container === 'string') container = document.querySelector(container);
        if (!container) return;
        const skeleton = container.querySelector('.skeleton-wrapper');
        if (skeleton) skeleton.remove();
    }

    // ── Confirm Dialog (Bootstrap Modal) ──────────────────────
    function confirm(message, options = {}) {
        return new Promise((resolve) => {
            const {
                title = 'Confirm',
                confirmText = 'Confirm',
                cancelText = 'Cancel',
                confirmClass = 'btn-danger',
                icon = 'alert-triangle'
            } = options;

            const existing = document.getElementById('uiConfirmModal');
            if (existing) existing.remove();

            const modalHtml = `
                <div class="modal fade" id="uiConfirmModal" tabindex="-1" aria-hidden="true">
                    <div class="modal-dialog modal-dialog-centered">
                        <div class="modal-content">
                            <div class="modal-header border-0">
                                <h5 class="modal-title d-flex align-items-center gap-2">
                                    <i data-lucide="${icon}" class="text-warning"></i>
                                    ${title}
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <p class="mb-0">${message}</p>
                            </div>
                            <div class="modal-footer border-0">
                                <button type="button" class="btn btn-light" data-bs-dismiss="modal" id="confirmCancelBtn">${cancelText}</button>
                                <button type="button" class="btn ${confirmClass}" id="confirmOkBtn">${confirmText}</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHtml);
            const modalEl = document.getElementById('uiConfirmModal');
            const modal = new bootstrap.Modal(modalEl);

            modalEl.querySelector('#confirmOkBtn').addEventListener('click', () => {
                modal.hide();
                resolve(true);
            });

            modalEl.querySelector('#confirmCancelBtn').addEventListener('click', () => {
                modal.hide();
                resolve(false);
            });

            modalEl.addEventListener('hidden.bs.modal', () => {
                modalEl.remove();
                resolve(false);
            });

            modal.show();
            if (typeof lucide !== 'undefined') lucide.createIcons();
        });
    }

    // ── Copy to Clipboard ─────────────────────────────────────
    async function copyToClipboard(text, successMsg = 'Copied to clipboard!') {
        try {
            await navigator.clipboard.writeText(text);
            showToast(successMsg, 'success');
            return true;
        } catch {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                showToast(successMsg, 'success');
                return true;
            } catch {
                showToast('Failed to copy', 'danger');
                return false;
            } finally {
                document.body.removeChild(textarea);
            }
        }
    }

    // ── Print Element ─────────────────────────────────────────
    function printElement(selector) {
        const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!el) {
            showToast('Element not found for printing', 'warning');
            return;
        }
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Print</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; }
                    @media print { body { padding: 0; } }
                </style>
            </head>
            <body>
                ${el.innerHTML}
                <script>
                    window.onload = function() { window.print(); window.close(); };
                <\/script>
            </body>
            </html>
        `);
        printWindow.document.close();
    }

    // ── Smooth Number Counter Animation ───────────────────────
    function animateCounter(element, target, duration = 1000, prefix = '', suffix = '') {
        if (typeof element === 'string') element = document.querySelector(element);
        if (!element) return;
        const start = parseFloat(element.textContent.replace(/[^0-9.-]/g, '')) || 0;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = start + (target - start) * eased;
            element.textContent = prefix + formatNumber(current) + suffix;
            if (progress < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    }

    // ── Lazy Loading for Images ───────────────────────────────
    function initLazyLoad() {
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                        }
                        img.classList.add('loaded');
                        observer.unobserve(img);
                    }
                });
            }, { rootMargin: '50px' });

            document.querySelectorAll('img[data-src]').forEach((img) => observer.observe(img));
        } else {
            document.querySelectorAll('img[data-src]').forEach((img) => {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                }
            });
        }
    }

    // ── Toast Helper (used internally) ────────────────────────
    function showToast(message, type = 'info', duration = 5000) {
        if (typeof window.showFlashToast === 'function') {
            window.showFlashToast(message, type, duration);
        }
    }

    // ── Public API ────────────────────────────────────────────
    return {
        debounce,
        throttle,
        formatCurrency,
        formatNumber,
        formatDate,
        showSkeleton,
        hideSkeleton,
        confirm,
        copyToClipboard,
        printElement,
        animateCounter,
        initLazyLoad,
        showToast
    };
})();

if (typeof window !== 'undefined') window.UI = UI;
