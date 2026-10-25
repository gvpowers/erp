/**
 * GV Powers ERP - Main Application JavaScript
 * Initialization, sidebar, toasts, search, notifications, and global behaviors
 */

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // ── Lucide Icons ──────────────────────────────────────────
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // ── CSRF Token Helper ─────────────────────────────────────
    window.getCsrfToken = function () {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        const input = document.querySelector('input[name="csrf_token"]');
        if (input) return input.value;
        const cookie = document.cookie.split(';').find((c) => c.trim().startsWith('csrf_token='));
        return cookie ? cookie.split('=')[1] : '';
    };

    window.apiHeaders = function (extra = {}) {
        return {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
            ...extra
        };
    };

    // ── Sidebar Toggle ────────────────────────────────────────
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.querySelectorAll('[data-sidebar-toggle]');
    const mainContent = document.querySelector('.main-content, .content-wrapper, #mainContent');

    sidebarToggle.forEach((btn) => {
        btn.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar?.classList.toggle('show');
                toggleOverlay(sidebar?.classList.contains('show'));
            } else {
                sidebar?.classList.toggle('collapsed');
                mainContent?.classList.toggle('sidebar-collapsed');
                localStorage.setItem('sidebar_collapsed', sidebar?.classList.contains('collapsed'));
            }
        });
    });

    // Restore sidebar state
    if (localStorage.getItem('sidebar_collapsed') === 'true' && window.innerWidth > 768) {
        sidebar?.classList.add('collapsed');
        mainContent?.classList.add('sidebar-collapsed');
    }

    // ── Mobile Sidebar Overlay ────────────────────────────────
    function toggleOverlay(show) {
        let overlay = document.getElementById('sidebarOverlay');
        if (show) {
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'sidebarOverlay';
                overlay.className = 'sidebar-overlay';
                overlay.addEventListener('click', () => {
                    sidebar?.classList.remove('show');
                    toggleOverlay(false);
                });
                document.body.appendChild(overlay);
            }
            requestAnimationFrame(() => overlay.classList.add('show'));
        } else if (overlay) {
            overlay.classList.remove('show');
            setTimeout(() => overlay.remove(), 300);
        }
    }

    // Close sidebar on resize to desktop
    const _resizeHandler = () => {
        if (window.innerWidth > 768) {
            sidebar?.classList.remove('show');
            toggleOverlay(false);
        }
    };
    window.addEventListener('resize', (typeof UI !== 'undefined' && UI.throttle) ? UI.throttle(_resizeHandler, 250) : _resizeHandler);

    // ── Flash Toast Notifications ─────────────────────────────
    function createToastContainer() {
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '11000';
            document.body.appendChild(container);
        }
        return container;
    }

    window.showFlashToast = function (message, type = 'info', duration = 5000) {
        const container = createToastContainer();
        const toastId = 'toast-' + Date.now();
        const iconMap = {
            success: 'check-circle',
            danger: 'x-circle',
            warning: 'alert-triangle',
            info: 'info',
            primary: 'bell'
        };
        const bsType = ['success', 'danger', 'warning', 'info', 'primary'].includes(type) ? type : 'info';

        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-bg-${bsType} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body d-flex align-items-center gap-2">
                        <i data-lucide="${iconMap[bsType] || 'info'}" style="width:18px;height:18px;flex-shrink:0;"></i>
                        <span>${message}</span>
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', toastHtml);
        const toastEl = document.getElementById(toastId);
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [toastEl] });
        const toast = new bootstrap.Toast(toastEl, { delay: duration });
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
        toast.show();
    };

    // Display server-side flash messages as toasts
    document.querySelectorAll('.alert-dismissible[data-flash]').forEach((el) => {
        const type = el.dataset.flashType || el.classList.contains('alert-success') ? 'success' :
            el.classList.contains('alert-danger') ? 'danger' :
                el.classList.contains('alert-warning') ? 'warning' : 'info';
        showFlashToast(el.textContent.trim(), type);
        el.remove();
    });

    // Auto-dismiss Bootstrap alerts
    document.querySelectorAll('.alert-dismissible:not([data-flash])').forEach((alert) => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });

    // ── Theme Initialization ──────────────────────────────────
    // Always light mode - unified enterprise design system
    document.documentElement.setAttribute('data-bs-theme', 'light');
    localStorage.setItem('theme', 'light');

    // ── CTRL+K Global Search Modal ────────────────────────────
    const searchModal = document.getElementById('globalSearchModal');
    const searchInput = document.getElementById('globalSearchInput');
    const searchResults = document.getElementById('globalSearchResults');
    let searchDebounceTimer = null;

    function openSearchModal() {
        if (!searchModal) return;
        const modal = bootstrap.Modal.getOrCreateInstance(searchModal);
        modal.show();
        setTimeout(() => searchInput?.focus(), 150);
    }

    function closeSearchModal() {
        if (!searchModal) return;
        const modal = bootstrap.Modal.getInstance(searchModal);
        modal?.hide();
        if (searchInput) searchInput.value = '';
        if (searchResults) searchResults.innerHTML = '';
    }

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            openSearchModal();
        }
        if (e.key === 'Escape' && searchModal?.classList.contains('show')) {
            closeSearchModal();
        }
    });

    document.querySelectorAll('[data-search-toggle]').forEach((btn) => {
        btn.addEventListener('click', openSearchModal);
    });

    if (searchInput) {
        async function handleSearchInput(e) {
            const query = e.target.value.trim();
            if (!searchResults) return;
            if (query.length < 2) {
                searchResults.innerHTML = '<div class="text-muted text-center py-4">Type to search...</div>';
                return;
            }
            searchResults.innerHTML = '<div class="text-center py-4"><div class="spinner-border spinner-border-sm text-primary"></div> Searching...</div>';
            try {
                const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}`, { headers: apiHeaders() });
                if (!resp.ok) throw new Error('Search failed');
                const data = await resp.json();
                renderSearchResults(data, query);
            } catch (err) {
                searchResults.innerHTML = '<div class="text-danger text-center py-4">Search failed. Please try again.</div>';
            }
        }
        searchInput.addEventListener('input', (typeof UI !== 'undefined' && UI.debounce) ? UI.debounce(handleSearchInput, 350) : handleSearchInput);
    }

    function renderSearchResults(data, query) {
        if (!searchResults) return;
        if (!data || !data.results || data.results.length === 0) {
            searchResults.innerHTML = '<div class="text-muted text-center py-4">No results found</div>';
            return;
        }
        const grouped = {};
        data.results.forEach((item) => {
            const cat = item.type || item.category || 'Other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(item);
        });

        let html = '';
        const catIcons = {
            invoice: 'file-text', customer: 'users', product: 'package',
            payment: 'credit-card', purchase: 'shopping-cart', report: 'bar-chart-2'
        };
        for (const [category, items] of Object.entries(grouped)) {
            html += `<div class="search-result-group mb-3">
                <div class="search-group-title text-uppercase text-muted small fw-bold px-2 mb-1">
                    <i data-lucide="${catIcons[category.toLowerCase()] || 'layers'}" style="width:14px;height:14px;" class="me-1"></i>
                    ${category}
                </div>`;
            items.forEach((item, idx) => {
                const highlighted = item.name || item.title || item.label || 'Untitled';
                html += `<a href="${item.url || '#'}" class="search-result-item d-flex align-items-center px-3 py-2 text-decoration-none"
                            data-index="${idx}">
                    <div class="search-result-info flex-grow-1">
                        <div class="text-body">${highlighted}</div>
                        ${item.subtitle ? `<div class="text-muted small">${item.subtitle}</div>` : ''}
                    </div>
                    <i data-lucide="arrow-right" style="width:14px;height:14px;" class="text-muted"></i>
                </a>`;
            });
            html += '</div>';
        }
        searchResults.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [searchResults] });
    }

    // Keyboard navigation in search results
    if (searchInput && searchResults) {
        let activeIndex = -1;
        searchInput.addEventListener('keydown', (e) => {
            const items = searchResults.querySelectorAll('.search-result-item');
            if (!items.length) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = Math.min(activeIndex + 1, items.length - 1);
                items.forEach((el, i) => el.classList.toggle('active', i === activeIndex));
                items[activeIndex]?.scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = Math.max(activeIndex - 1, 0);
                items.forEach((el, i) => el.classList.toggle('active', i === activeIndex));
                items[activeIndex]?.scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'Enter' && activeIndex >= 0) {
                e.preventDefault();
                items[activeIndex]?.click();
            }
        });
    }

    // ── Notification Bell ─────────────────────────────────────
    const notifBell = document.getElementById('notificationBell');
    const notifDropdown = document.getElementById('notificationDropdown');
    const notifList = document.getElementById('notificationList');
    const notifBadge = document.getElementById('notificationBadge');

    async function fetchNotifications() {
        if (!notifList) return;
        try {
            const resp = await fetch('/api/notifications', { headers: apiHeaders() });
            if (!resp.ok) return;
            const data = await resp.json();
            renderNotifications(data.notifications || data);
        } catch (err) {
            console.warn('Failed to fetch notifications:', err);
        }
    }

    function renderNotifications(notifications) {
        if (!notifList) return;
        if (!notifications || notifications.length === 0) {
            notifList.innerHTML = '<div class="text-muted text-center py-3">No notifications</div>';
            if (notifBadge) notifBadge.style.display = 'none';
            return;
        }
        const unread = notifications.filter((n) => !n.read).length;
        if (notifBadge) {
            notifBadge.textContent = unread;
            notifBadge.style.display = unread > 0 ? '' : 'none';
        }
        notifList.innerHTML = notifications.slice(0, 20).map((n) => `
            <a href="${n.url || '#'}" class="dropdown-item py-2 ${n.read ? '' : 'bg-light bg-opacity-10'}">
                <div class="d-flex align-items-start gap-2">
                    <i data-lucide="${n.icon || 'bell'}" style="width:16px;height:16px;" class="mt-1 text-${n.type || 'primary'}"></i>
                    <div class="flex-grow-1">
                        <div class="small ${n.read ? 'text-muted' : 'fw-semibold'}">${n.message || n.title || ''}</div>
                        <div class="text-muted" style="font-size:0.7rem;">${n.time || ''}</div>
                    </div>
                </div>
            </a>
        `).join('');
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [notifList] });
    }

    if (notifBell) {
        notifBell.addEventListener('show.bs.dropdown', fetchNotifications);
        // Custom ERP menu system: fetch notifications when the bell menu opens
        const bellTrigger = notifBell.querySelector('[data-erp-trigger]');
        if (bellTrigger) {
            bellTrigger.addEventListener('click', function () {
                // Defer so the ERP menu toggle has applied before we check panel state
                setTimeout(function () {
                    const panel = notifBell.querySelector('.erp-menu__panel');
                    if (panel && panel.classList.contains('is-open')) {
                        fetchNotifications();
                    }
                }, 20);
            });
        } else {
            notifBell.addEventListener('click', fetchNotifications);
        }
    }

    document.querySelectorAll('[data-mark-all-read]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            try {
                await fetch('/api/notifications/read', {
                    method: 'POST',
                    headers: apiHeaders()
                });
                if (notifBadge) notifBadge.style.display = 'none';
                if (notifList) {
                    notifList.querySelectorAll('.bg-light').forEach((el) => el.classList.remove('bg-light', 'bg-opacity-10'));
                }
                showFlashToast('All notifications marked as read', 'success');
            } catch (err) {
                console.warn('Failed to mark notifications as read');
            }
        });
    });

    // ── Form Validation Helpers ───────────────────────────────
    window.FormValidator = {
        isRequired(value) {
            return value !== null && value !== undefined && String(value).trim() !== '';
        },
        isEmail(value) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
        },
        isMobile(value) {
            return /^[6-9]\d{9}$/.test(value.replace(/\s|-/g, ''));
        },
        isGSTIN(value) {
            return /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(value);
        },
        isPAN(value) {
            return /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(value);
        },
        isNumeric(value) {
            return !isNaN(parseFloat(value)) && isFinite(value);
        },
        minLength(value, min) {
            return String(value).length >= min;
        },
        maxLength(value, max) {
            return String(value).length <= max;
        },
        showFieldError(field, message) {
            field.classList.add('is-invalid');
            let feedback = field.parentNode.querySelector('.invalid-feedback');
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                field.parentNode.appendChild(feedback);
            }
            feedback.textContent = message;
        },
        clearFieldError(field) {
            field.classList.remove('is-invalid');
            const feedback = field.parentNode?.querySelector('.invalid-feedback');
            if (feedback) feedback.remove();
        },
        clearAllErrors(form) {
            if (typeof form === 'string') form = document.querySelector(form);
            if (!form) return;
            form.querySelectorAll('.is-invalid').forEach((f) => f.classList.remove('is-invalid'));
            form.querySelectorAll('.invalid-feedback').forEach((f) => f.remove());
        },
        validateForm(form) {
            if (typeof form === 'string') form = document.querySelector(form);
            if (!form) return false;
            this.clearAllErrors(form);
            let valid = true;
            form.querySelectorAll('[required]').forEach((field) => {
                if (!this.isRequired(field.value)) {
                    this.showFieldError(field, 'This field is required');
                    valid = false;
                }
            });
            form.querySelectorAll('[type="email"]').forEach((field) => {
                if (field.value && !this.isEmail(field.value)) {
                    this.showFieldError(field, 'Please enter a valid email');
                    valid = false;
                }
            });
            form.querySelectorAll('[data-mobile]').forEach((field) => {
                if (field.value && !this.isMobile(field.value)) {
                    this.showFieldError(field, 'Please enter a valid 10-digit mobile number');
                    valid = false;
                }
            });
            return valid;
        }
    };

    // ── Confirmation Dialogs ──────────────────────────────────
    document.querySelectorAll('[data-confirm]').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const message = btn.dataset.confirm || 'Are you sure?';
            const confirmed = (typeof UI !== 'undefined' && UI.confirm)
                ? await UI.confirm(message, {
                    title: btn.dataset.confirmTitle || 'Confirm',
                    confirmText: btn.dataset.confirmText || 'Yes',
                    cancelText: btn.dataset.cancelText || 'Cancel',
                    confirmClass: btn.dataset.confirmClass || 'btn-danger'
                })
                : window.confirm(message);
            if (confirmed) {
                if (btn.dataset.href) {
                    window.location.href = btn.dataset.href;
                } else if (btn.form) {
                    btn.form.submit();
                } else {
                    btn.click();
                }
            }
        });
    });

    // Delete buttons with confirmation
    document.querySelectorAll('[data-delete]').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            const name = btn.dataset.deleteName || 'this item';
            const confirmed = (typeof UI !== 'undefined' && UI.confirm)
                ? await UI.confirm(`Are you sure you want to delete <strong>${name}</strong>? This action cannot be undone.`, {
                    title: 'Delete Confirmation',
                    confirmText: 'Delete',
                    confirmClass: 'btn-danger',
                    icon: 'trash-2'
                })
                : window.confirm(`Are you sure you want to delete ${name}? This action cannot be undone.`);
            if (confirmed && btn.dataset.deleteUrl) {
                try {
                    const resp = await fetch(btn.dataset.deleteUrl, {
                        method: 'DELETE',
                        headers: apiHeaders()
                    });
                    if (resp.ok) {
                        showFlashToast('Deleted successfully', 'success');
                        if (btn.dataset.redirect) {
                            window.location.href = btn.dataset.redirect;
                        } else {
                            const row = btn.closest('tr, .list-item');
                            if (row) {
                                row.style.transition = 'opacity 0.3s, transform 0.3s';
                                row.style.opacity = '0';
                                row.style.transform = 'translateX(-20px)';
                                setTimeout(() => row.remove(), 300);
                            }
                        }
                    } else {
                        const data = await resp.json().catch(() => ({}));
                        showFlashToast(data.message || 'Delete failed', 'danger');
                    }
                } catch (err) {
                    showFlashToast('Network error. Please try again.', 'danger');
                }
            }
        });
    });

    // ── Smooth Scroll ─────────────────────────────────────────
    document.querySelectorAll('a[href^="#"]').forEach((link) => {
        link.addEventListener('click', (e) => {
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ── Initialize Bootstrap Tooltips & Popovers ──────────────
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
        new bootstrap.Tooltip(el);
    });
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach((el) => {
        new bootstrap.Popover(el);
    });

    // ── Lazy Loading ──────────────────────────────────────────
    if (typeof UI !== 'undefined') {
        UI.initLazyLoad();
    }

    // ── Preserve Sidebar Scroll Position ──────────────────────
    // The sidebar nav (`.sidebar-nav`, overflow-y:auto) is the scroll container.
    // Save its position before leaving the page and restore it after reload so
    // navigation between pages keeps the sidebar where the user left it.
    const sidebarNav = document.querySelector('.sidebar-nav');
    const SIDEBAR_SCROLL_KEY = 'sidebar_scroll';

    function saveSidebarScroll() {
        try {
            sessionStorage.setItem(SIDEBAR_SCROLL_KEY, String(sidebarNav.scrollTop));
        } catch (err) { /* storage unavailable - ignore */ }
    }
    function restoreSidebarScroll() {
        if (!sidebarNav) return;
        try {
            const pos = parseInt(sessionStorage.getItem(SIDEBAR_SCROLL_KEY), 10);
            if (Number.isFinite(pos) && pos > 0) sidebarNav.scrollTop = pos;
        } catch (err) { /* storage unavailable - ignore */ }
    }

    if (sidebarNav) {
        // Save while scrolling (throttled to avoid blocking on sessionStorage writes).
        let scrollSaveTimer = null;
        sidebarNav.addEventListener('scroll', () => {
            if (scrollSaveTimer) return;
            scrollSaveTimer = setTimeout(() => { scrollSaveTimer = null; saveSidebarScroll(); }, 120);
        });
        // Save synchronously right before a sidebar link navigates away.
        document.addEventListener('click', (e) => {
            const link = e.target && e.target.closest ? e.target.closest('a') : null;
            if (link && link.target !== '_blank' && sidebarNav.contains(link)) saveSidebarScroll();
        }, true);
        // Fallback for refresh, Back/Forward and form submits (e.g. Logout).
        window.addEventListener('pagehide', saveSidebarScroll);
        restoreSidebarScroll();
        // Re-apply on BFCache restores (Back/Forward) where DOMContentLoaded does not re-fire.
        window.addEventListener('pageshow', restoreSidebarScroll);
    } else {
        // No sidebar here (login, error or print page): drop any stale position
        // so a fresh login never restores a previous session's scroll offset.
        try { sessionStorage.removeItem(SIDEBAR_SCROLL_KEY); } catch (err) { /* ignore */ }
    }

    // ── Print Buttons ─────────────────────────────────────────
    document.querySelectorAll('[data-print]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.print || 'body';
            if (typeof UI !== 'undefined' && UI.printElement) {
                UI.printElement(target);
            } else {
                window.print();
            }
        });
    });

    // ── Copy Buttons ──────────────────────────────────────────
    document.querySelectorAll('[data-copy]').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (typeof UI !== 'undefined' && UI.copyToClipboard) {
                UI.copyToClipboard(btn.dataset.copy, btn.dataset.copyMsg || 'Copied!');
            } else if (navigator.clipboard) {
                navigator.clipboard.writeText(btn.dataset.copy);
            }
        });
    });

    // ── Form Reset Clear Errors ───────────────────────────────
    document.querySelectorAll('form').forEach((form) => {
        form.addEventListener('reset', () => {
            setTimeout(() => FormValidator.clearAllErrors(form), 10);
        });
    });

    console.log('GV Powers ERP initialized');
});
