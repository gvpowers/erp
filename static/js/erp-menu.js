/* ============================================
   GV Powers ERP - Reusable Dropdown/Menu System
   - Auto-initializes any [data-erp-menu]
   - Viewport-safe positioning (flips up / side)
   - One open menu at a time
   - Click-outside + ESC close
   - Keyboard navigation (ArrowUp/Down, Enter, Home/End)
   - Submenu flyouts
   Usage:
     <div class="erp-menu" data-erp-menu>
       <button class="erp-menu__trigger" data-erp-trigger aria-label="Actions" aria-haspopup="menu">
         <i data-lucide="ellipsis-vertical"></i>
       </button>
       <div class="erp-menu__panel" role="menu">
         <a class="erp-menu__item" href="..."><i data-lucide="eye"></i><span class="erp-menu__label">View</span></a>
         <div class="erp-menu__divider"></div>
         <button class="erp-menu__item danger" data-erp-action="..."><i data-lucide="trash-2"></i><span class="erp-menu__label">Delete</span></button>
       </div>
     </div>
   Submenu:
     <button class="erp-menu__item" data-erp-submenu="#subX"><...>Label<span class="erp-menu__arrow"><i data-lucide="chevron-right"></i></span></button>
     <div class="erp-submenu__panel" id="subX"> items </div>
   ============================================ */
(function () {
  'use strict';

  var openMenus = [];   // list of open {mount, trigger, panel, anchor, sub, subTrigger}
  var GAP = 6;
  var MARGIN = 10;

  function renderIcons(node) {
    if (window.lucide) {
      try { window.lucide.createIcons({ nodes: node }); } catch (e) {}
    }
  }

  /* ---------- close helpers ---------- */
  function closeMenu(entry) {
    var idx = openMenus.indexOf(entry);
    if (idx === -1) return;
    openMenus.splice(idx, 1);
    entry.panel && entry.panel.classList.remove('is-open');
    entry.panel && (entry.panel.style.left = '', entry.panel.style.top = '');
    if (entry.sub) { entry.sub.classList.remove('is-open'); entry.sub.style.left = ''; entry.sub.style.top = ''; }
    if (entry.trigger) entry.trigger.setAttribute('aria-expanded', 'false');
    if (typeof entry.onClose === 'function') entry.onClose();
  }

  function closeAll(except) {
    openMenus.slice().forEach(function (m) { if (m !== except) closeMenu(m); });
  }

  /* ---------- positioning ---------- */
  function position(panel, anchor, isSub) {
    if (!panel || !anchor) return;
    var r = anchor.getBoundingClientRect();
    var pw = panel.offsetWidth, ph = panel.offsetHeight;
    var vw = window.innerWidth, vh = window.innerHeight;
    var top, left;

    if (isSub) {
      // flyout right, flip left near right edge
      left = r.right + GAP;
      if (left + pw > vw - MARGIN) left = r.left - pw - GAP;
      left = Math.max(MARGIN, left);
      top = Math.max(MARGIN, Math.min(r.top, vh - MARGIN - ph));
    } else {
      // below trigger by default; flip above if near bottom
      var below = r.bottom + GAP;
      var above = r.top - ph - GAP;
      var placeUp = below + ph > vh - MARGIN && above > MARGIN;
      panel.classList.toggle('place-up', placeUp);
      top = placeUp ? above : Math.min(below, vh - MARGIN - ph);
      left = r.left >= MARGIN ? r.left : MARGIN;
      if (left + pw > vw - MARGIN) left = vw - MARGIN - pw;
      if (left < MARGIN) left = MARGIN;
    }
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
    panel.style.position = 'fixed';
  }

  function openMenu(entry) {
    closeAll();
    entry.panel && entry.panel.classList.add('is-open');
    position(entry.panel, entry.anchor, false);
    renderIcons(entry.panel);
    if (entry.trigger) entry.trigger.setAttribute('aria-expanded', 'true');
    openMenus.push(entry);
    requestAnimationFrame(function () {
      var first = entry.panel && entry.panel.querySelector('.erp-menu__item:not(:disabled):not(.is-disabled), .erp-submenu__item');
      if (first) { try { first.focus({ preventScroll: true }); } catch (e) {} }
    });
  }

  /* ---------- submenus ---------- */
  function toggleSubmenu(entry, trigger, sub) {
    if (entry.sub && entry.sub === sub && sub.classList.contains('is-open')) {
      sub.classList.remove('is-open'); entry.sub = null; entry.subTrigger = null; return;
    }
    if (entry.sub && entry.sub !== sub) { entry.sub.classList.remove('is-open'); }
    entry.sub = sub; entry.subTrigger = trigger;
    sub.classList.add('is-open');
    position(sub, trigger, true);
    renderIcons(sub);
  }

  /* ---------- keyboard ---------- */
  function onPanelKeydown(panel, getEntry) {
    return function (e) {
      var items = Array.prototype.slice.call(panel.querySelectorAll('.erp-menu__item:not(:disabled):not(.is-disabled)'));
      if (!items.length) return;
      var idx = items.indexOf(document.activeElement);

      if (e.key === 'ArrowDown') { e.preventDefault(); idx = idx < 0 ? 0 : (idx + 1) % items.length; }
      else if (e.key === 'ArrowUp') { e.preventDefault(); idx = idx < 0 ? items.length - 1 : (idx - 1 + items.length) % items.length; }
      else if (e.key === 'Home') { e.preventDefault(); idx = 0; }
      else if (e.key === 'End') { e.preventDefault(); idx = items.length - 1; }
      else if (e.key === 'Escape') { e.preventDefault(); var en = getEntry(); if (en) closeMenu(en); return; }
      else return;
      items[idx] && items[idx].focus({ preventScroll: true });
    };
  }

  /* ---------- global listeners ---------- */
  function onDocClick(e) {
    var inMount = e.target.closest && e.target.closest('[data-erp-menu], .erp-submenu__panel');
    openMenus.slice().forEach(function (entry) {
      var inside = inMount && (
        (inMount === entry.mount) ||
        (entry.mount && entry.mount.contains(inMount)) ||
        (entry.sub && entry.sub === inMount)
      );
      if (!inside) closeMenu(entry);
    });
  }

  function onDocKey(e) {
    if (e.key === 'Escape' && !e.defaultPrevented) closeAll();
  }

  function reflow() {
    openMenus.forEach(function (entry) {
      if (entry.panel) position(entry.panel, entry.anchor, false);
      if (entry.sub) position(entry.sub, entry.subTrigger, true);
    });
  }

  /* ---------- init a mount ---------- */
  function initMount(mount) {
    if (mount.getAttribute('data-erp-inited')) return;
    mount.setAttribute('data-erp-inited', '1');

    var trigger = mount.querySelector('[data-erp-trigger], .erp-menu__trigger');
    var panel = mount.querySelector('.erp-menu__panel');
    if (!trigger || !panel) return;

    var entry = { mount: mount, trigger: trigger, panel: panel, anchor: trigger, sub: null, subTrigger: null };

    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      if (panel.classList.contains('is-open')) { closeMenu(entry); return; }
      openMenu(entry);
    });

    panel.addEventListener('click', function (e) {
      var st = e.target.closest && e.target.closest('[data-erp-submenu]');
      if (st) {
        e.stopPropagation();
        var sel = st.getAttribute('data-erp-submenu') || '';
        // Accept both "#id" (selector style) and bare "id".
        var sub = sel.charAt(0) === '#' ? document.getElementById(sel.slice(1))
                                        : document.querySelector(sel);
        if (sub) toggleSubmenu(entry, st, sub);
        return;
      }
      // action item click: allow default but close menu
      if (e.target.closest('.erp-menu__item, .erp-menu__item:hover')) {
        // defer close so the click handler on anchors runs
        setTimeout(function () { closeMenu(entry); }, 80);
      }
    });

    panel.addEventListener('keydown', onPanelKeydown(panel, function () { return entry; }));
  }

  function autoInit() {
    var mounts = document.querySelectorAll('[data-erp-menu]');
    Array.prototype.forEach.call(mounts, initMount);
  }

  /* ---------- expose ---------- */
  window.ERP_MENU = { open: openMenu, close: closeMenu, closeAll: closeAll, reflow: reflow };

  window.addEventListener('click', onDocClick, true);
  // Submenu items (download/print links) don't reload the page; close menus after use.
  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('.erp-submenu__item')) {
      setTimeout(closeAll, 80);
    }
  }, true);
  window.addEventListener('keydown', onDocKey, true);
  window.addEventListener('scroll', reflow, true);
  window.addEventListener('resize', reflow);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoInit);
  } else { autoInit(); }
  window.addEventListener('load', autoInit);
})();