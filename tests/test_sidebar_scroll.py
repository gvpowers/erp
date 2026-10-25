"""Regression tests for sidebar scroll-position preservation (Bug #3)."""


def test_app_js_includes_sidebar_scroll_preservation(client):
    resp = client.get('/static/js/app.js')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'SIDEBAR_SCROLL_KEY' in body
    assert 'pagehide' in body
    assert 'pageshow' in body


def test_authenticated_pages_render_sidebar_nav(app, admin_login):
    for path in ['/dashboard', '/reports', '/reports/low-stock', '/settings']:
        resp = admin_login.get(path)
        assert resp.status_code == 200
        assert 'class="sidebar-nav"' in resp.get_data(as_text=True)


def test_login_page_has_no_sidebar_nav(app, client):
    resp = client.get('/login')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'class="sidebar-nav"' not in html
    assert 'js/app.js' in html
