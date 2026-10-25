/**
 * GV Powers ERP - Global Search
 * Category-based result grouping, keyboard navigation, search history
 */

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // ── Configuration ─────────────────────────────────────────
    const SEARCH_DEBOUNCE_MS = 300;
    const MAX_HISTORY = 10;
    const MAX_RESULTS_PER_CATEGORY = 5;
    const STORAGE_KEY = 'gv_search_history';

    // ── Elements ──────────────────────────────────────────────
    const searchModal = document.getElementById('globalSearchModal');
    const searchInput = document.getElementById('globalSearchInput');
    const searchResults = document.getElementById('globalSearchResults');
    const searchHistory = document.getElementById('searchHistory');

    // ── Category Config ───────────────────────────────────────
    const CATEGORIES = {
        invoice: { label: 'Invoices', icon: 'file-text', color: 'primary', url: (item) => `/invoices/${item.id}/preview` },
        customer: { label: 'Customers', icon: 'users', color: 'success', url: (item) => `/customers/${item.id}` },
        product: { label: 'Products', icon: 'package', color: 'warning', url: (item) => `/products/${item.id}/edit` },
        payment: { label: 'Payments', icon: 'credit-card', color: 'info', url: (item) => `/payments/${item.id}` },
        purchase: { label: 'Purchases', icon: 'shopping-cart', color: 'purple', url: (item) => `/purchases/${item.id}` },
        category: { label: 'Categories', icon: 'tag', color: 'secondary', url: () => '/categories' },
        report: { label: 'Reports', icon: 'bar-chart-2', color: 'teal', url: (item) => item.url || '/reports' },
        other: { label: 'Other', icon: 'layers', color: 'secondary', url: (item) => item.url || '#' }
    };

    // ── Search History ────────────────────────────────────────
    function getHistory() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
        } catch {
            return [];
        }
    }

    function addToHistory(query, resultUrl, resultTitle) {
        if (!query || query.trim().length < 2) return;
        let history = getHistory();
        history = history.filter((h) => h.query !== query.trim());
        history.unshift({
            query: query.trim(),
            url: resultUrl || '',
            title: resultTitle || '',
            timestamp: Date.now()
        });
        history = history.slice(0, MAX_HISTORY);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    }

    function clearHistory() {
        localStorage.removeItem(STORAGE_KEY);
        if (searchHistory) {
            searchHistory.innerHTML = '<div class="text-muted text-center py-3">No recent searches</div>';
        }
    }

    function renderHistory() {
        if (!searchHistory) return;
        const history = getHistory();
        if (history.length === 0) {
            searchHistory.innerHTML = '<div class="text-muted text-center py-3 small">No recent searches</div>';
            return;
        }
        let html = '<div class="d-flex justify-content-between align-items-center px-3 mb-1"><span class="text-muted small fw-bold">Recent</span><button class="btn btn-link btn-sm p-0 text-muted" id="clearHistoryBtn">Clear</button></div>';
        history.forEach((item) => {
            html += `<a href="${item.url || '#'}" class="dropdown-item py-2 px-3 history-item d-flex align-items-center gap-2">
                <i data-lucide="clock" style="width:14px;height:14px;" class="text-muted flex-shrink-0"></i>
                <div class="flex-grow-1 text-truncate">
                    <span class="text-body">${escapeHtml(item.query)}</span>
                    ${item.title ? `<span class="text-muted small ms-1">in ${escapeHtml(item.title)}</span>` : ''}
                </div>
            </a>`;
        });
        searchHistory.innerHTML = html;

        const clearBtn = document.getElementById('clearHistoryBtn');
        if (clearBtn) clearBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); clearHistory(); });

        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [searchHistory] });
    }

    // ── Search State ──────────────────────────────────────────
    let activeResultIndex = -1;
    let allResultLinks = [];
    let lastQuery = '';

    // ── Show Initial State (History) ──────────────────────────
    function showInitialState() {
        if (!searchResults) return;
        renderHistory();
        if (searchHistory) searchHistory.style.display = '';
        searchResults.innerHTML = '';
        activeResultIndex = -1;
        allResultLinks = [];
    }

    // ── Perform Search ────────────────────────────────────────
    const searchDebounce = (typeof UI !== 'undefined' && UI.debounce) ? UI.debounce : (fn, ms) => { let t; return function(...a) { clearTimeout(t); t = setTimeout(() => fn.apply(this, a), ms); }; };
    const performSearch = searchDebounce(async (query) => {
        if (!searchResults) return;

        if (query.length < 2) {
            showInitialState();
            return;
        }

        if (searchHistory) searchHistory.style.display = 'none';
        searchResults.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <div class="text-muted small mt-2">Searching...</div>
            </div>`;
        activeResultIndex = -1;
        allResultLinks = [];

        try {
            const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!resp.ok) throw new Error('Search failed');
            const data = await resp.json();
            lastQuery = query;
            renderSearchResults(data, query);
        } catch (err) {
            console.error('Search error:', err);
            searchResults.innerHTML = `
                <div class="text-center py-4">
                    <i data-lucide="alert-circle" style="width:32px;height:32px;" class="text-danger mb-2"></i>
                    <div class="text-muted">Search failed. Please try again.</div>
                </div>`;
            if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [searchResults] });
        }
    }, SEARCH_DEBOUNCE_MS);

    // ── Render Search Results (Grouped by Category) ───────────
    function renderSearchResults(data, query) {
        if (!searchResults) return;

        const results = data.results || data.items || data;

        if (!results || results.length === 0) {
            searchResults.innerHTML = `
                <div class="text-center py-4">
                    <i data-lucide="search-x" style="width:40px;height:40px;" class="text-muted mb-2"></i>
                    <div class="text-muted">No results found for "<strong>${escapeHtml(query)}</strong>"</div>
                    <div class="text-muted small mt-1">Try different keywords</div>
                </div>`;
            if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [searchResults] });
            return;
        }

        // Group results by category
        const grouped = {};
        results.forEach((item) => {
            const cat = (item.type || item.category || 'other').toLowerCase();
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(item);
        });

        let html = '';
        let globalIndex = 0;

        for (const [category, items] of Object.entries(grouped)) {
            const catConfig = CATEGORIES[category] || CATEGORIES.other;
            const displayItems = items.slice(0, MAX_RESULTS_PER_CATEGORY);

            html += `
                <div class="search-category-group mb-2">
                    <div class="search-category-header d-flex align-items-center gap-2 px-3 py-1 text-uppercase small fw-bold" style="color: var(--bs-${catConfig.color});">
                        <i data-lucide="${catConfig.icon}" style="width:14px;height:14px;"></i>
                        <span>${catConfig.label}</span>
                        <span class="badge bg-secondary bg-opacity-25 text-body-secondary ms-auto" style="font-size:0.65rem;">${items.length}</span>
                    </div>`;

            displayItems.forEach((item) => {
                const url = catConfig.url(item);
                const title = item.name || item.title || item.label || 'Untitled';
                const subtitle = item.subtitle || item.description || item.mobile || item.invoice_number || '';
                const badge = item.badge || item.status || '';

                html += `
                    <a href="${escapeAttr(url)}" class="search-result-link d-flex align-items-center px-3 py-2 text-decoration-none"
                       data-index="${globalIndex}" data-url="${escapeAttr(url)}" data-title="${escapeAttr(title)}">
                        <div class="search-result-icon me-3 flex-shrink-0">
                            <div class="rounded d-flex align-items-center justify-content-center" style="width:32px;height:32px;background:var(--bs-${catConfig.color}-bg-subtle,var(--bs-secondary-bg-subtle));">
                                <i data-lucide="${catConfig.icon}" style="width:16px;height:16px;color:var(--bs-${catConfig.color});"></i>
                            </div>
                        </div>
                        <div class="search-result-text flex-grow-1 min-width-0">
                            <div class="text-body fw-medium text-truncate">${highlightMatch(title, query)}</div>
                            ${subtitle ? `<div class="text-muted small text-truncate">${highlightMatch(subtitle, query)}</div>` : ''}
                        </div>
                        ${badge ? `<span class="badge bg-${catConfig.color} bg-opacity-10 text-${catConfig.color} ms-2 flex-shrink-0">${escapeHtml(badge)}</span>` : ''}
                    </a>`;
                globalIndex++;
            });

            if (items.length > MAX_RESULTS_PER_CATEGORY) {
                html += `<div class="px-3 py-1 text-muted small">+${items.length - MAX_RESULTS_PER_CATEGORY} more...</div>`;
            }

            html += '</div>';
        }

        searchResults.innerHTML = html;
        allResultLinks = searchResults.querySelectorAll('.search-result-link');

        // Click to navigate and add to history
        allResultLinks.forEach((link) => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const url = link.dataset.url;
                const title = link.dataset.title;
                addToHistory(query, url, title);
                if (url && url !== '#') window.location.href = url;
            });
        });

        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [searchResults] });
    }

    // ── Highlight Search Match ────────────────────────────────
    function highlightMatch(text, query) {
        if (!query || !text) return escapeHtml(text);
        const escaped = escapeHtml(text);
        const queryWords = query.trim().split(/\s+/).filter((w) => w.length >= 2);
        if (queryWords.length === 0) return escaped;
        const regex = new RegExp(`(${queryWords.map(escapeRegex).join('|')})`, 'gi');
        return escaped.replace(regex, '<mark class="bg-warning bg-opacity-50 rounded px-1">$1</mark>');
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // ── Keyboard Navigation ───────────────────────────────────
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            performSearch(e.target.value.trim());
        });

        searchInput.addEventListener('keydown', (e) => {
            const count = allResultLinks.length;
            if (count === 0) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeResultIndex = Math.min(activeResultIndex + 1, count - 1);
                updateActiveResult();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeResultIndex = Math.max(activeResultIndex - 1, 0);
                updateActiveResult();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (activeResultIndex >= 0 && allResultLinks[activeResultIndex]) {
                    allResultLinks[activeResultIndex].click();
                } else if (lastQuery) {
                    addToHistory(lastQuery);
                }
            }
        });
    }

    function updateActiveResult() {
        allResultLinks.forEach((link, idx) => {
            link.classList.toggle('active', idx === activeResultIndex);
            if (idx === activeResultIndex) {
                link.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
        });
    }

    // ── Modal Events ──────────────────────────────────────────
    if (searchModal) {
        searchModal.addEventListener('show.bs.modal', () => {
            showInitialState();
            setTimeout(() => searchInput?.focus(), 150);
        });

        searchModal.addEventListener('hidden.bs.modal', () => {
            if (searchInput) searchInput.value = '';
            activeResultIndex = -1;
            allResultLinks = [];
            lastQuery = '';
            if (searchResults) searchResults.innerHTML = '';
        });
    }

    // ── Helpers ───────────────────────────────────────────────
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
    window.GlobalSearch = {
        performSearch: (q) => performSearch(q),
        clearHistory,
        getHistory
    };
});
