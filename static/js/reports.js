/* =========================================================
   GV Powers ERP — Shared Reports JavaScript
   ========================================================= */
(function () {
  'use strict';

  var RP = window.RP || {};
  window.RP = RP;

  /* ---------- Print ---------- */
  RP.printPage = function () {
    window.print();
  };
  RP.printHtml = function (elId, title) {
    var el = document.getElementById(elId);
    if (!el) { window.print(); return; }
    var w = window.open('', '_blank', 'width=1100,height=800');
    w.document.write('<!doctype html><html><head><title>' + (title || 'Report') + '</title>');
    w.document.write('<style>body{font-family:Segoe UI,Arial,sans-serif;padding:20px;color:#1f2937}table{width:100%;border-collapse:collapse;font-size:12px}td,th{border:1px solid #d1d5db;padding:6px 8px;text-align:left}th{background:#eef2ff;color:#111}</style>');
    w.document.write('</head><body>' + el.innerHTML + '</body></html>');
    w.document.close();
    w.focus();
    w.print();
  };

  /* ---------- Formats ---------- */
  function fmtMoney(v) {
    var n = parseFloat(v);
    if (isNaN(n)) return '0.00';
    return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtInt(v) {
    var n = parseInt(v, 10);
    if (isNaN(n)) return '0';
    return n.toLocaleString('en-IN');
  }
  function fmtNumber(v, dec) {
    var n = parseFloat(v);
    if (isNaN(n)) return '0';
    dec = dec === undefined ? 2 : dec;
    return n.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }
  RP.fmtMoney = fmtMoney;
  RP.fmtInt = fmtInt;
  RP.fmtNumber = fmtNumber;

  /* =============================================================
     Report table component
     Wrap: <div data-report-table>
       <div class="rpt-toolbar">... .rpt-search, .rpt-count, .rpt-perpage ...</div>
       <div class="rpt-scroll"><table class="rpt-table">...</table></div>
       <div class="rpt-pager"></div>
     =========================================================== */
  function initTable(wrap) {
    var table = wrap.querySelector('table.rpt-table');
    if (!table) return;
    var thead = table.querySelector('thead');
    var tbody = table.querySelector('tbody');
    if (!thead || !tbody) return;

    var paginator = wrap.querySelector('.rpt-pager');
    var infoEl = wrap.querySelector('.rpt-count');
    var searchInput = wrap.querySelector('.rpt-search input');
    var perPageSel = wrap.querySelector('.rpt-perpage select');
    var filterRow = wrap.querySelector('.rpt-colfilters');

    var originalRows = Array.prototype.slice.call(tbody.rows);
    var total = originalRows.length;
    var colCount = (thead.rows[0]) ? thead.rows[0].cells.length : 0;

    var currentPage = 1;
    var perPage = (perPageSel && parseFloat(perPageSel.value)) || 20;
    var sortIdx = -1;
    var sortAsc = true;

    function pageCount(n) { return Math.max(1, Math.ceil(n / perPage)); }

    function visibleRows() {
      var q = searchInput ? (searchInput.value || '').trim().toLowerCase() : '';
      var colQ = [];
      if (filterRow) {
        filterRow.querySelectorAll('input,select').forEach(function (el) {
          var ci = parseInt(el.dataset.col, 10);
          colQ[ci] = (el.value || '').trim().toLowerCase();
        });
      }
      var list = originalRows.filter(function (r) {
        var hay = r.textContent.toLowerCase();
        if (q && hay.indexOf(q) === -1) return false;
        for (var i = 0; i < colQ.length; i++) {
          if (!colQ[i]) continue;
          var cell = r.cells[i];
          if (!cell || cell.textContent.toLowerCase().indexOf(colQ[i]) === -1) return false;
        }
        return true;
      });
      if (sortIdx >= 0) {
        list.sort(comparator(sortIdx, sortAsc));
      }
      return list;
    }

    function comparator(idx, asc) {
      var isNum = thead.rows[0].cells[idx] ? thead.rows[0].cells[idx].classList.contains('tar') : false;
      return function (a, b) {
        var av = a.cells[idx] ? a.cells[idx].textContent.trim() : '';
        var bv = b.cells[idx] ? b.cells[idx].textContent.trim() : '';
        var res;
        if (isNum) {
          var an = parseFloat(String(av).replace(/Rs\.|[₹,LR%s]/g, '')) || 0;
          var bn = parseFloat(String(bv).replace(/Rs\.|[₹,LR%s]/g, '')) || 0;
          res = an - bn;
        } else {
          res = String(av).localeCompare(String(bv));
        }
        return asc ? res : -res;
      };
    }

    function render() {
      var vis = visibleRows();
      var pages = pageCount(vis.length);
      if (currentPage > pages) currentPage = pages;
      if (currentPage < 1) currentPage = 1;
      var start = (currentPage - 1) * perPage;
      var slice = vis.slice(start, start + perPage);
      tbody.innerHTML = '';
      if (slice.length) {
        slice.forEach(function (r) { tbody.appendChild(r); });
      } else {
        var tr = document.createElement('tr');
        tr.className = 'empty-row';
        tr.innerHTML = '<td colspan="' + colCount + '">No matching records found</td>';
        tbody.appendChild(tr);
      }
      if (infoEl) infoEl.textContent = vis.length + ' record' + (vis.length === 1 ? '' : 's');
      renderPager(pages, vis.length);
    }

    function renderPager(pages, shown) {
      if (!paginator) return;
      paginator.innerHTML = '';
      var info = document.createElement('span');
      info.className = 'rpt-pinfo';
      info.textContent = 'Page ' + currentPage + ' of ' + pages;
      paginator.appendChild(info);

      function addBtn(label, page, active, disabled) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = label;
        if (active) b.classList.add('on');
        if (disabled) b.disabled = true;
        b.addEventListener('click', function () {
          if (disabled) return;
          currentPage = page;
          render();
        });
        paginator.appendChild(b);
      }
      addBtn('‹', currentPage - 1, false, currentPage === 1);
      var windowStart = Math.max(1, currentPage - 2);
      var windowEnd = Math.min(pages, windowStart + 4);
      windowStart = Math.max(1, windowEnd - 4);
      for (var p = windowStart; p <= windowEnd; p++) addBtn(p, p, p === currentPage, false);
      addBtn('›', currentPage + 1, false, currentPage === pages);
    }

    function bindSort() {
      var ths = thead.rows[0].cells;
      Array.prototype.forEach.call(ths, function (th, idx) {
        th.addEventListener('click', function () {
          if (sortIdx === idx) sortAsc = !sortAsc; else { sortIdx = idx; sortAsc = true; }
          Array.prototype.forEach.call(ths, function (c) { c.classList.remove('sorted-asc', 'sorted-desc'); });
          th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
          currentPage = 1;
          render();
        });
      });
    }
    if (thead.rows[0]) bindSort();

    if (perPageSel) perPageSel.addEventListener('change', function () {
      perPage = parseFloat(this.value) || 20;
      currentPage = 1;
      render();
    });
    if (searchInput) searchInput.addEventListener('input', function () { currentPage = 1; render(); });
    if (filterRow) filterRow.addEventListener('input', function () { currentPage = 1; render(); });
    render();
  }
  RP.initTable = initTable;

  /* =============================================================
     Charts
     cfg = { el:<canvas>, type:<string>, labels:[], datasets:[
        {label,data,backgroundColor,borderColor,fill,...} ],
       options:{},
       money:bool, currency:bool, legend:bool, categoryPercent:bool }
     =========================================================== */
  var chartInstances = {};
  function withChart(cb) {
    if (window.Chart) { cb(); return; }
    var s = document.createElement('script');
    s.src = RP.chartJsUrl || '/static/vendor/chart.js';
    document.head.appendChild(s);
    s.onload = cb;
  }

  RP.drawChart = function (cfg) {
    withChart(function () {
      var el = cfg.el;
      if (!el) return;
      if (chartInstances[el.id]) chartInstances[el.id].destroy();

      if (cfg.type === 'line' || cfg.type === 'bar') {
        cfg.options = cfg.options || {};
        cfg.options.scales = cfg.options.scales || {};
        if (cfg.money !== false) {
          cfg.options.scales.y = {
            ticks: { callback: function (v) { return 'Rs. ' + fmtInt(v); } },
            grid: { color: 'rgba(0,0,0,.05)' }
          };
        } else {
          cfg.options.scales.y = { beginAtZero: true, grid: { color: 'rgba(0,0,0,.05)' } };
        }
      }
      if (cfg.type === 'doughnut') { cfg.options = cfg.options || {}; cfg.options.cutout = (cfg.cutout !== undefined ? cfg.cutout : '62%'); }
      if (cfg.type === 'pie') { cfg.options = cfg.options || {}; cfg.options.cutout = 0; }

      cfg.options.maintainAspectRatio = false;
      cfg.options.responsive = true;
      cfg.options.animation = { duration: 400 };
      cfg.options.plugins = cfg.options.plugins || {};
      cfg.options.plugins.legend = cfg.options.plugins.legend || { display: !!cfg.legend, position: 'bottom', labels: { boxWidth: 12, boxHeight: 12, usePointStyle: true, padding: 16 } };
      if (cfg.title) cfg.options.plugins.title = { display: true, text: cfg.title, font: { size: 13, weight: '700' } };
      if (cfg.money !== false) {
        cfg.options.plugins.tooltip = { callbacks: { label: function (ctx) {
          var v = ctx.parsed !== undefined && ctx.parsed.y != null ? ctx.parsed.y : (ctx.parsed !== undefined ? ctx.parsed : NaN);
          return ' ' + (cfg.currency !== false ? 'Rs. ' : '') + fmtNumber(v);
        } } };
      }

      chartInstances[el.id] = new Chart(el, {
        type: cfg.type,
        data: { labels: cfg.labels || [], datasets: cfg.datasets || [] },
        options: cfg.options || {}
      });
    });
  };

  RP.destroyCharts = function () {
    Object.keys(chartInstances).forEach(function (k) { chartInstances[k].destroy(); });
    chartInstances = {};
  };

  /* ---------- Theme convenience for charts ---------- */
  RP.hexA = function (hex, alpha) {
    if (alpha >= 1) return hex;
    var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  };
  RP.PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#f43f5e', '#84cc16', '#6366f1', '#22c55e'];

  /* ---------- global boot: run initTable for descendant tables -------- */
  function boot() {
    document.querySelectorAll('[data-report-table]').forEach(function (w) { initTable(w); });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();