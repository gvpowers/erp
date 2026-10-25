/* GV POWERS ERP — Settings page behaviour
   Nav switching, dirty tracking, auto-save validation, file previews, toasts. */

(function () {
    'use strict';

    const app = document.getElementById('settingsApp');
    if (!app) return;

    const form = app.querySelector('[data-gv-form]');
    const publish = app.querySelector('[data-gv-publish]');
    const publishText = app.querySelector('[data-gv-publish-text]');

    // localStorage may throw (cookies blocked, private mode) — never abort.
    function storageGet(key) { try { return window.localStorage.getItem(key); } catch (e) { return null; } }
    function storageSet(key, val) { try { window.localStorage.setItem(key, val); } catch (e) { /* ignore */ } }

    // Validation rules: name -> [type, module]
    const RULES = {
        // Company identity fields are FIXED (read-only) — no client validation needed.
    };

    const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}Z[0-9A-Z]{1}$/;

    const CHECKS = {
        required: function (v) { return v.length > 0; },
        gstin:    function (v) { return GSTIN_RE.test(v); },
        email:    function (v) { return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v); },
        phone:    function (v) { return /^[0-9+()\-.\s]{10,18}$/.test(v); },
        url:      function (v) { return /^(https?:\/\/)?([\w-]+\.)+[\w-]+(\/\S*)?$/.test(v); },
        number:   function (v) { return /^\d+$/.test(v); },
        pincode:  function (v) { return /^\d{6}$/.test(v); },
    };

    const CHMESSAGES = {
        gstin: 'Invalid GSTIN — must be 15 characters (e.g. 33AGEPV1534G2ZJ).',
        email: 'Please enter a valid email address.',
        phone: 'Please enter a valid phone number.',
        url: 'Please enter a valid website URL.',
        number: 'Please enter a number.',
        pincode: 'Please enter a valid 6-digit pincode.',
    };

    // Auto-uppercase identity fields as the user types (handles pasted text too).
    app.querySelectorAll('input[data-upper]').forEach(function (inp) {
        inp.addEventListener('input', function () {
            var start = inp.selectionStart, end = inp.selectionEnd;
            inp.value = inp.value.toUpperCase();
            inp.setSelectionRange(start, end);
        });
    });

    // ---- Nav ----
    const navItems = app.querySelectorAll('[data-gv-nav]');
    const mods = app.querySelectorAll('[data-gv-module]');
    const actions = app.querySelector('.gv-actions');
    const savedKey = storageGet('gv_settings_active');

    function showModule(key) {
        let found = false;
        mods.forEach(function (m) {
            const show = m.getAttribute('data-gv-module') === key;
            m.classList.toggle('is-show', show);
            if (show) found = true;
        });
        navItems.forEach(function (n) {
            n.classList.toggle('is-active', n.getAttribute('data-gv-nav') === key && found);
        });
        if (actions) {
            // Company identity is fixed/read-only — hide the save/reset bar.
            actions.classList.toggle('gv-actions--hidden', key === 'company');
        }
        if (found) storageSet('gv_settings_active', key);
    }

    if (mods.length && navItems.length) {
        let has = false;
        mods.forEach(function (m) {
            if (m.getAttribute('data-gv-module') === savedKey) has = true;
        });
        showModule(has ? savedKey : mods[0].getAttribute('data-gv-module'));
        navItems.forEach(function (n) {
            n.addEventListener('click', function () {
                showModule(n.getAttribute('data-gv-nav'));
            });
        });
    }

    // ---- Dirty tracking + publish indicator ----
    let timers = { input: null };
    let dirty = false;

    function setPublish(state) {
        if (!publish) return;
        publish.classList.remove('is-dirty', 'is-saving', 'is-saved');
        if (state) publish.classList.add(state);
        if (publishText) {
            if (state === 'is-dirty') publishText.textContent = 'Unsaved changes';
            else if (state === 'is-saving') publishText.textContent = 'Saving...';
            else publishText.textContent = 'All changes saved';
        }
    }
    setPublish('is-saved');

    function activeModule() {
        var act = null;
        mods.forEach(function (m) {
            if (m.classList.contains('is-show')) act = m;
        });
        return act || (mods.length ? mods[0] : null);
    }

    function collectData() {
        if (!form) return {};
        var scope = activeModule();
        var o = {};
        var fd = new FormData(form);
        fd.forEach(function (v, k) {
            if (k.indexOf('file_') === 0) return;
            if (scope && !scope.querySelector('[name="' + k + '"]')) return; // only active module
            o[k] = v || '';
        });
        return o;
    }

    // Build the POST body using only the active module's controls.
    function activeFormData() {
        var scope = activeModule();
        var fd = new FormData();
        fd.set('csrf_token', (form.querySelector('[name="csrf_token"]') || {}).value || '');
        if (scope) {
            scope.querySelectorAll('input, select, textarea').forEach(function (el) {
                if (!el.name || el.name.indexOf('_file_') === 0 || el.type === 'file') return;
                if (el.type === 'checkbox' || el.type === 'radio') {
                    if (el.checked) fd.append(el.name, el.value);
                } else {
                    fd.append(el.name, el.value);
                }
            });
        }
        return fd;
    }

    function validate(data) {
        // reset all error states
        app.querySelectorAll('.gv-field.is-error').forEach(function (el) { el.classList.remove('is-error'); });
        app.querySelectorAll('input.is-invalid, select.is-invalid, textarea.is-invalid').forEach(function (el) {
            el.classList.remove('is-invalid');
        });
        var ok = true;
        Object.keys(RULES).forEach(function (key) {
            var type = RULES[key][0];
            var v = (data[key] || '').toString().trim();
            var pass = !v || !CHECKS[type] || CHECKS[type](v);
            if (!pass) {
                ok = false;
                var field = form.querySelector('[name="' + key + '"]');
                if (!field) return;
                if (field.classList.contains('is-invalid')) return; // already flagged on duplicate name
                field.classList.add('is-invalid');
                var box = field.closest('.gv-field');
                if (box) {
                    box.classList.add('is-error');
                    var msg = box.querySelector('.gv-error');
                    if (msg && CHMESSAGES[type]) msg.textContent = CHMESSAGES[type];
                }
            }
        });
        return ok;
    }

    function doSave() {
        var data = collectData();
        if (!validate(data)) {
            setPublish('is-dirty');
            var pub = document.querySelector('[data-gv-publish-text]');
            if (pub) pub.textContent = 'Please fix the highlighted fields';
            toast('Please fix the highlighted fields', false);
            // focus the first invalid field
            var firstBad = form.querySelector('input.is-invalid, select.is-invalid, textarea.is-invalid');
            if (firstBad && firstBad.focus) firstBad.focus();
            return;
        }
        setPublish('is-saving');
        var fd = activeFormData();
        var xhr = new XMLHttpRequest();
        xhr.open('POST', (form.getAttribute('action') || ''), true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.onload = function () {
            var resp = null;
            try { resp = JSON.parse(xhr.responseText); } catch (e) { /* non-JSON */ }
            if (xhr.status === 200 && resp && resp.success) {
                setPublish('is-saved');
                toast('Settings saved successfully.', true);
                if (typeof resp.settings === 'object') {
                    appliedValues(resp.settings); // reload saved values into the form
                }
            } else if (xhr.status === 200 && resp && !resp.success) {
                setPublish('is-dirty');
                toast(resp.error || 'Database error.', false);
            } else if (xhr.status === 400) {
                setPublish('is-dirty');
                toast('Invalid request (CSRF token expired). Reload the page.', false);
            } else {
                setPublish('is-dirty');
                toast('Database error. Please try again.', false);
            }
        };
        xhr.onerror = function () { setPublish('is-dirty'); toast('Network error. Please try again.', false); };
        xhr.send(fd);
    }

    // Reload the freshly-saved values back into the form so it reflects the DB.
    function appliedValues(map) {
        if (!map) return;
        Object.keys(map).forEach(function (k) {
            var inp = form.querySelector('[name="' + k + '"]');
            if (inp && typeof map[k] === 'string') {
                if (inp.tagName === 'TEXTAREA') inp.value = map[k];
                else if (inp.type === 'checkbox' || inp.type === 'radio') inp.checked = (map[k] === '1' || map[k] === 'true' || map[k] === 'on');
                else inp.value = map[k];
            }
        });
    }

    function scheduleSave() {
        setPublish('is-dirty');
        clearTimeout(timers.input);
        timers.input = setTimeout(doSave, 1200);
    }

    form.addEventListener('input', scheduleSave);
    form.addEventListener('change', function () {
        setPublish('is-dirty');
        clearTimeout(timers.input);
        timers.input = setTimeout(doSave, 700);
    });

    // Native submit path: always saves even if autosave JS was interrupted.
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        clearTimeout(timers.input);
        doSave();
    });

    // Buttons
    var saveBtn = document.querySelector('[data-gv-save]');
    if (saveBtn) saveBtn.addEventListener('click', function (e) {
        e.preventDefault();
        clearTimeout(timers.input);
        doSave();
    });

    var resetBtn = document.querySelector('[data-gv-reset]');
    if (resetBtn) resetBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (confirm('Reset all settings to their previous saved values?')) window.location.reload();
    });

    var previewBtn = document.querySelector('[data-gv-preview]');
    if (previewBtn) previewBtn.addEventListener('click', function (e) {
        e.preventDefault();
        var u = previewBtn.getAttribute('data-preview-url');
        if (u) window.open(u, '_blank');
    });

    // File upload previews
    app.querySelectorAll('input[type="file"]').forEach(function (file) {
        file.addEventListener('change', function () {
            var sel = file.getAttribute('data-preview');
            var img = sel ? app.querySelector(sel) : null;
            var f = file.files && file.files[0];
            if (img && f && f.type && f.type.indexOf('image/') === 0) {
                var rd = new FileReader();
                rd.onload = function (ev) { img.src = ev.target.result; };
                rd.readAsDataURL(f);
            }
            scheduleSave();
        });
    });

    // Logo preview lightbox (read-only company profile)
    var logoPreviewBtn = app.querySelector('[data-gv-logo-preview]');
    var logoModal = app.querySelector('[data-gv-logo-modal]');
    if (logoPreviewBtn && logoModal) {
        logoPreviewBtn.addEventListener('click', function () { logoModal.hidden = false; });
        logoModal.querySelectorAll('[data-gv-logo-close]').forEach(function (el) {
            el.addEventListener('click', function () { logoModal.hidden = true; });
        });
        document.addEventListener('keydown', function (e) { if (e.key === 'Escape') logoModal.hidden = true; });
    }

    // ---- Toast ----
    var tEl = document.createElement('div');
    tEl.className = 'gv-toast';
    document.body.appendChild(tEl);
    var tTimer = null;
    function toast(msg, ok) {
        tEl.textContent = msg;
        tEl.className = 'gv-toast is-show' + (ok ? ' gv-toast--ok' : ' gv-toast--err');
        clearTimeout(tTimer);
        tTimer = setTimeout(function () { tEl.classList.remove('is-show'); }, 2600);
    }
})();