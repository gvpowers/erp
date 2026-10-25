"""Invoice rendering regression tests.

These assert on the ACTUAL rendered artefacts, not on the presence of CSS
declarations. They are the executable form of the invoice rendering
requirements:

  * ONE canonical template + ONE canonical stylesheet shared by the ERP
    preview, the browser print views and the WeasyPrint PDF.
  * The required 13-column header table, the approved GV POWERS header block,
    the required sections and the three exact copy labels.
  * Numbers must never wrap or spill out of their column.
  * Every downloaded copy is a single A4 portrait page with the official logo
    and the signature block pinned to the foot of the page.
"""
import os
import re
from datetime import date
from decimal import Decimal

import pytest

pymupdf = pytest.importorskip("pymupdf")

from app import (  # noqa: E402
    Invoice, InvoiceItem, generate_invoice_pdf, db,
    _COPY_LABELS, _COPY_TYPES, OFFICIAL_LOGO_PATH,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL_TEMPLATE = os.path.join('templates', 'invoices', 'standard_invoice.html')
CANONICAL_CSS = os.path.join('static', 'css', 'invoice.css')
RETIRED_TEMPLATE = os.path.join('templates', 'partials', 'invoice_standard.html')
RETIRED_CSS = os.path.join('static', 'css', 'invoice_print.css')

# The 13 required columns and their colgroup widths, mirroring the canonical
# template. Widths must total 100%.
ITEM_COLUMNS = [
    ('SI. NO.', 4.49), ('DESCRIPTION OF GOODS AND SERVICES', 21.87),
    ('HSN/SAC', 7.65), ('QTY', 3.22), ('UNIT', 3.31), ('RATE', 7.73),
    ('DISC. %', 6.75), ('GST %', 5.86), ('TAXABLE', 9.98), ('CGST', 7.73),
    ('SGST', 7.73), ('IGST', 3.70), ('AMOUNT', 9.98),
]
REQUIRED_SECTIONS = [
    'BILL TO', 'INVOICE DETAILS', 'HSN / GST SUMMARY', 'PAYMENT INFORMATION',
    'INVOICE SUMMARY', 'AMOUNT IN WORDS', 'CUSTOMER SIGNATURE',
    'FOR GV POWERS', 'AUTHORIZED SIGNATORY',
]
REQUIRED_TOTAL_LABELS = ['SUBTOTAL', 'TAXABLE', 'CGST', 'SGST', 'IGST',
                         'GRAND TOTAL', 'AMOUNT IN WORDS']
REQUIRED_HEADER_LINES = [
    'No. 10, Kadharkhan Street, Opp. Railway Junction,',
    'Salem - 636005, Tamil Nadu, India',
    'Phone: +91 98940 79090',
    'Mobile: +91 98940 79095',
    'Email: gvpowerssalem@gmail.com',
    'GSTIN: 33AGEPV1534G2ZJ',
]
# Values that previously wrapped onto two lines or split inside a column.
MUST_NOT_WRAP = [
    '1,08,640.00', '1,52,300.00', '1,34,000.00', '9,150.00', '43,660.00',
    '85044034', '85414300', '18.00%', '12.00%', '0.00%',
]

# A4 in PDF points. The 9mm side inset is what the sheet's own padding provides;
# the @page margin is deliberately zero (see the test below), so the printable
# width is the page width minus that inset.
A4_W, A4_H = 595.276, 841.89
PAGE_MARGIN_PT = 9 / 25.4 * 72


@pytest.fixture
def invoice(app, make_customer):
    """A two-item invoice exercising the widest values in the layout."""
    from datetime import date

    c = make_customer('Sri Balaji Solar Works', mobile='9876501234',
                      email='balaji@example.in',
                      address='12, Trichy Road, Coimbatore 641012',
                      state='Tamil Nadu', state_code=33, gstin='33ABCDE1234F1Z5')
    inv = Invoice(invoice_number='INV-20260928-0001', customer_id=c.id,
                  customer_name=c.name, customer_mobile=c.mobile,
                  customer_email=c.email, customer_address=c.address,
                  customer_gstin=c.gstin, customer_state=c.state,
                  customer_state_code=c.state_code, is_intra_state=True,
                  invoice_date=date(2026, 9, 28),
                  status='confirmed', payment_status='due', amount_paid=0)
    items = [
        ('Luminous Solar NXG Hybrid Inverter 1100/12V', '85044034', 2, 'Nos',
         Decimal('18500'), Decimal('0'), Decimal('18'), Decimal('37000'),
         Decimal('3330'), Decimal('3330'), Decimal('0'), Decimal('43660')),
        ('Waaree 545WP Mono PERC Solar Panel', '85414300', 4, 'Nos',
         Decimal('24250'), Decimal('0'), Decimal('12'), Decimal('97000'),
         Decimal('5820'), Decimal('5820'), Decimal('0'), Decimal('108640')),
    ]
    db.session.add(inv)
    db.session.flush()
    for (name, hsn, qty, unit, price, disc, rate, taxable, cgst, sgst, igst,
         total) in items:
        db.session.add(InvoiceItem(
            invoice_id=inv.id, product_name=name, hsn=hsn, qty=qty, unit=unit,
            price=price, discount=disc, gst_rate=rate, taxable_value=taxable,
            cgst=cgst, sgst=sgst, igst=igst, total=total))
    inv.subtotal = Decimal('134000')
    inv.total_taxable = Decimal('134000')
    inv.total_cgst = Decimal('9150')
    inv.total_sgst = Decimal('9150')
    inv.total_igst = Decimal('0')
    inv.grand_total = Decimal('152300')
    inv.balance_due = Decimal('152300')
    db.session.commit()
    return inv


def _pdf(client, inv_id, copy):
    r = client.get('/invoices/%d/pdf/%s' % (inv_id, copy))
    assert r.status_code == 200, 'PDF route returned %s' % r.status_code
    assert r.mimetype == 'application/pdf'
    data = r.get_data()
    assert data[:5] == b'%PDF-'
    return data


def _open(data):
    return pymupdf.open(stream=data, filetype='pdf')


# ---------------------------------------------------------------------------
# single source of truth
# ---------------------------------------------------------------------------

def test_canonical_template_and_css_exist():
    assert os.path.isfile(os.path.join(PROJECT_ROOT, CANONICAL_TEMPLATE))
    assert os.path.isfile(os.path.join(PROJECT_ROOT, CANONICAL_CSS))


def test_retired_invoice_template_and_css_are_gone():
    assert not os.path.exists(os.path.join(PROJECT_ROOT, RETIRED_TEMPLATE))
    assert not os.path.exists(os.path.join(PROJECT_ROOT, RETIRED_CSS))


def test_no_source_file_references_the_retired_invoice_assets():
    offenders = []
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {'.venv', '__pycache__', '.git', 'instance',
                                    'backups', 'node_modules'}]
        for name in filenames:
            if not name.endswith(('.py', '.html', '.css', '.js')):
                continue
            path = os.path.join(dirpath, name)
            # normalise to posix so the exclusions below match on any OS
            rel = os.path.relpath(path, PROJECT_ROOT).replace(os.sep, '/')
            if rel in ('tests/test_invoice_rendering.py', CANONICAL_CSS.replace('\\', '/')):
                continue
            with open(path, encoding='utf-8', errors='replace') as fh:
                body = fh.read()
            if 'invoice_print.css' in body or 'partials/invoice_standard' in body:
                offenders.append(rel)
    assert offenders == [], 'retired invoice assets still referenced by: %s' % offenders


def test_copy_labels_are_exactly_as_specified():
    assert _COPY_LABELS == {
        'owner': 'ADMIN / OWNER COPY',
        'customer': 'CUSTOMER COPY',
        'gst': 'GST TAX COPY',
    }


def test_item_column_widths_total_one_hundred_percent():
    assert abs(sum(w for _, w in ITEM_COLUMNS) - 100.0) < 0.005


def test_colgroup_widths_match_the_canonical_css():
    """The widths in this test must be the ones the stylesheet actually ships,
    so a future tweak to invoice.css cannot silently invalidate the checks."""
    css = open(os.path.join(PROJECT_ROOT, CANONICAL_CSS), encoding='utf-8').read()
    for index, (head, pct) in enumerate(ITEM_COLUMNS):
        name = ['si', 'desc', 'hsn', 'qty', 'unit', 'rate', 'disc', 'gst',
                'tax', 'cgst', 'sgst', 'igst', 'amt'][index]
        m = re.search(r'col\.c-%s\s*\{\s*width:\s*([\d.]+)%%' % name, css)
        assert m, 'no col.c-%s width in the canonical CSS' % name
        assert abs(float(m.group(1)) - pct) < 0.005, \
            'col.c-%s is %s%% in the CSS but %s%% here' % (name, m.group(1), pct)


def _selectors(css):
    """Return every leaf selector in a stylesheet, ignoring at-rule preludes."""
    body = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out, i, n = [], 0, len(body)
    while i < n:
        j = body.find('{', i)
        if j == -1:
            break
        prelude = body[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if body[k] == '{':
                depth += 1
            elif body[k] == '}':
                depth -= 1
            k += 1
        if prelude and not prelude.startswith('@'):
            out.extend(part.strip() for part in prelude.split(','))
        i = k
    return out


def test_invoice_css_has_no_global_reset():
    """The canonical CSS is also loaded inside the ERP admin preview, so it must
    never contain an unscoped element or universal selector. Every rule has to be
    anchored to a .gvp-* (or col .c-*) class, so the stylesheet can only ever
    reach the invoice itself and never the surrounding ERP chrome."""
    css = open(os.path.join(PROJECT_ROOT, CANONICAL_CSS), encoding='utf-8').read()
    offenders = []
    for selector in _selectors(css):
        for part in selector.split(','):
            part = part.strip()
            if not part:
                continue
            if not re.search(r'\.(gvp|c)-', part):
                offenders.append(part)
    assert offenders == [], \
        'unscoped selector(s) %s could style the surrounding ERP UI' % offenders

    # @page must be declared, and only inside the print media query
    body = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    assert re.search(r'@page', body), 'canonical CSS must declare @page'
    print_block = body[body.index('@media print'):]
    assert '@page' in print_block, '@page must live inside @media print'
    assert body.index('@page') > body.index('@media print'), \
        '@page must not apply to the on-screen preview'


def test_page_margin_is_zero_so_the_browser_adds_no_header_or_footer():
    """The printed page must contain the invoice and nothing else.

    Browsers draw their own "Headers and footers" -- the date and time, the page
    title, the page number and the URL (which carries the invoice id, e.g.
    /invoices/12/print/owner) -- inside the @page margin box. Only a zero page
    margin removes that box and suppresses them, so a non-zero margin here is
    what makes a browser print an invoice with someone else's id and today's
    date stapled to it.
    """
    css = open(os.path.join(PROJECT_ROOT, CANONICAL_CSS), encoding='utf-8').read()
    body = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    rule = re.search(r'@page\s*\{([^}]*)\}', body)
    assert rule, 'canonical CSS must declare @page'
    margin = re.search(r'margin\s*:\s*([^;]+);', rule.group(1))
    assert margin, '@page must set an explicit margin'
    assert [v.strip() for v in margin.group(1).split()] in ([], ['0']), \
        ('@page margin must be 0 to suppress the browser header/footer, '
         'found %r' % margin.group(1))

    # The inset the zero @page margin gives up must be carried by the sheet's
    # own padding, so the ink still lands where the downloaded PDF puts it.
    # Note the print layer has two .gvp-sheet rules (one shared with .gvp-page
    # for colour and font, one for the box itself); the padding lives in the
    # latter, so scan them all rather than assuming which comes first.
    print_block = body[body.index('@media print'):]
    paddings = [m.group(1).strip()
                for m in re.finditer(r'\.gvp-sheet\s*\{([^}]*)\}', print_block)
                for m in [re.search(r'padding\s*:\s*([^;]+);', m.group(1))]
                if m]
    assert paddings, 'the print .gvp-sheet must restore the page inset'
    # The top and side insets are exactly the margins @page gave up, so the ink
    # lands where the downloaded PDF puts it. The bottom reserve is 28mm rather
    # than 31mm: the sheet's min-height sits 3mm under the 297mm page to survive
    # sub-pixel rounding, and the bottom padding gives back that same 3mm, which
    # leaves the content box (and therefore the ink) exactly where it was. It
    # must still comfortably clear the signature block and footer.
    top_side = [p for p in ([v.strip() for v in p.split()] for p in paddings)
                if p[0] == '10mm' and p[1] == '9mm']
    assert top_side, ('print sheet padding should include the 10mm/9mm page '
                      'inset, found %r' % paddings)
    bottom_mm = float(re.match(r'([\d.]+)mm$', top_side[0][2]).group(1))
    assert bottom_mm >= 20, \
        'print sheet bottom reserve must keep the footer clear, found %s' % top_side[0][2]


# ---------------------------------------------------------------------------
# ERP preview + browser print views
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_preview_links_the_canonical_stylesheet(admin_login, invoice, copy):
    page = admin_login.get('/invoices/%d?copy=%s' % (invoice.id, copy))
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'css/invoice.css' in body, 'ERP preview must load the canonical CSS'
    assert 'invoice_print.css' not in body
    assert 'gvp-sheet' in body
    assert _COPY_LABELS[copy] in body


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_print_view_links_the_canonical_stylesheet(admin_login, invoice, copy):
    page = admin_login.get('/invoices/%d/print/%s' % (invoice.id, copy))
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'css/invoice.css' in body
    assert 'invoice_print.css' not in body
    assert body.count('gvp-sheet') == 1
    assert _COPY_LABELS[copy] in body
    # the browser print dialog must not get an ERP page title
    assert '<title></title>' in body or '<title>\n</title>' in body


def test_print_all_renders_three_labelled_sheets(admin_login, invoice):
    page = admin_login.get('/invoices/%d/print/all' % invoice.id)
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert body.count('gvp-sheet') == 3
    for label in _COPY_LABELS.values():
        assert body.count(label) == 1, '%r must appear exactly once' % label


# ---------------------------------------------------------------------------
# the downloaded PDF
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_pdf_is_a4_portrait_and_logged_in(admin_login, invoice, copy):
    doc = _open(_pdf(admin_login, invoice.id, copy))
    try:
        assert doc.page_count == 1, 'a short invoice must be one page, got %d' % doc.page_count
        page = doc[0]
        assert abs(page.rect.width - A4_W) < 2
        assert abs(page.rect.height - A4_H) < 2
        assert page.get_images(full=True), 'the official logo must be embedded'
    finally:
        doc.close()


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_pdf_contains_the_required_header_sections_and_columns(
        admin_login, invoice, copy):
    doc = _open(_pdf(admin_login, invoice.id, copy))
    try:
        text = doc[0].get_text()
    finally:
        doc.close()
    assert _COPY_LABELS[copy] in text
    for line in REQUIRED_HEADER_LINES:
        assert line in text, 'missing approved header line %r' % line
    for section in REQUIRED_SECTIONS:
        assert section in text, 'missing required section %r' % section
    # Totals row labels are matched case-insensitively: the template capitalises
    # them for display ("Subtotal") and the stylesheet's text-transform supplies
    # the visual uppercase, so the on-page glyph case is a styling detail rather
    # than part of the content contract.
    flat = ' '.join(text.split()).lower()
    for label in REQUIRED_TOTAL_LABELS:
        assert label.lower() in flat, 'missing totals row %r' % label
    for head, _ in ITEM_COLUMNS:
        # Flattened and case-insensitive: the description header is a
        # deliberate two-line label, so it arrives as two spans separated by a
        # newline, and the stylesheet applies the visual uppercase.
        assert head.lower() in flat, 'missing required column %r' % head


@pytest.mark.parametrize('value', MUST_NOT_WRAP)
def test_pdf_values_never_wrap_or_split(admin_login, invoice, value):
    for copy in _COPY_TYPES:
        doc = _open(_pdf(admin_login, invoice.id, copy))
        try:
            assert value in doc[0].get_text(), \
                '%r was split or wrapped in the %s copy' % (value, copy)
        finally:
            doc.close()


def _column_edges(page):
    """The real item-table column boundaries.

    Taken from the vertical cell rules the renderer actually painted, anchored on
    the header row. This measures the shipped layout rather than re-deriving it
    from the colgroup percentages, so the test cannot pass while the layout
    is wrong.
    """
    words = page.get_text('words')
    si = [w for w in words if w[4] == 'SI.']
    assert si, 'item-table header not found'
    header_y = si[0][1]

    drawings = [d['rect'] for d in page.get_drawings() if d.get('rect') is not None]
    rules = [r for r in drawings if r.height <= 0.8 and r.width >= 1]
    above = [r.y0 for r in rules if r.y0 <= header_y + 1]
    assert above, 'no rule found above the item-table header'
    grid_y = max(above)

    edges = sorted({round(r.x0, 1) for r in drawings
                    if r.width <= 0.8 and r.height >= 1
                    and abs(r.y0 - grid_y) <= 3})
    assert len(edges) == len(ITEM_COLUMNS) + 1, \
        'expected %d column boundaries, found %d: %s' % (
            len(ITEM_COLUMNS) + 1, len(edges), edges)
    return edges


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_pdf_numbers_stay_inside_their_own_column(admin_login, invoice, copy):
    doc = _open(_pdf(admin_login, invoice.id, copy))
    try:
        page = doc[0]
        words = page.get_text('words')
        edges = _column_edges(page)
        header_y = [w for w in words if w[4] == 'SI.'][0][1]
        offenders = []
        for w in words:
            if not (header_y - 1 <= w[1] <= header_y + 60):
                continue
            bare = w[4].replace(',', '').replace('.', '').replace('%', '')
            if not bare.isdigit():
                continue
            idx = max(i for i, e in enumerate(edges) if e <= w[0] + 0.6)
            if idx + 1 >= len(edges):
                continue
            if w[2] > edges[idx + 1] + 0.6:
                offenders.append('%r (x %.1f..%.1f) overflows %r'
                                 % (w[4], w[0], w[2], ITEM_COLUMNS[idx][0]))
        assert offenders == [], '%s copy: %s' % (copy, offenders)
    finally:
        doc.close()


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_pdf_page_is_not_wrapped_in_a_grey_band(admin_login, invoice, copy):
    """A regression guard: when the sheet lost its page-sized height the PDF
    body background bled past the sheet and framed it in grey."""
    doc = _open(_pdf(admin_login, invoice.id, copy))
    try:
        for drawing in doc[0].get_drawings():
            fill = drawing.get('fill')
            rect = drawing.get('rect')
            if not fill or rect is None or rect.height < 700:
                continue
            assert tuple(round(c, 3) for c in fill) == (1.0, 1.0, 1.0), \
                'full-page fill %s is not pure white' % (fill,)
    finally:
        doc.close()


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_pdf_signature_block_sits_at_the_foot_of_the_page(
        admin_login, invoice, copy):
    doc = _open(_pdf(admin_login, invoice.id, copy))
    try:
        page = doc[0]
        words = page.get_text('words')
        sig = [w for w in words if w[4] in ('AUTHORIZED', 'SIGNATORY', 'CUSTOMER')]
        assert sig, 'signature text missing'
        assert max(w[3] for w in sig) > page.rect.height * 0.80, \
            'signature block is not pinned to the bottom of the page'
        names = {w[4] for w in sig}
        assert 'SIGNATORY' in names and 'CUSTOMER' in names
    finally:
        doc.close()


def test_the_three_pdfs_differ_only_by_the_copy_label(admin_login, invoice):
    texts = {}
    for copy in _COPY_TYPES:
        doc = _open(_pdf(admin_login, invoice.id, copy))
        try:
            texts[copy] = doc[0].get_text().replace(_COPY_LABELS[copy], '@@')
        finally:
            doc.close()
    assert texts['owner'] == texts['customer']
    assert texts['owner'] == texts['gst']


def test_official_logo_file_is_the_one_that_renders():
    assert os.path.isfile(OFFICIAL_LOGO_PATH), \
        'the official logo %s is missing' % OFFICIAL_LOGO_PATH


# ---------------------------------------------------------------------------
# the sizing bound the column widths were fitted against
# ---------------------------------------------------------------------------

#: Widest invoice line the layout supports: an 11-character money figure
#: ("11,30,000.00" = 10 lakh per line), an 8-digit HSN/SAC code, a 3-digit
#: quantity and a "100.00%" discount.
WIDE_ITEMS = [
    ('Luminous Solar NXG Hybrid Inverter 1100/12V', '85044034', 120, 'Nos',
     Decimal('25000.00'), Decimal('100.00'), Decimal('18'),
     Decimal('1000000.00'), Decimal('90000.00'), Decimal('90000.00'),
     Decimal('0.00'), Decimal('1130000.00')),
    ('Waaree 545WP Mono PERC Solar Panel', '85414300', 400, 'Nos',
     Decimal('25000.00'), Decimal('0.00'), Decimal('12'),
     Decimal('1000000.00'), Decimal('60000.00'), Decimal('60000.00'),
     Decimal('0.00'), Decimal('1130000.00')),
]


@pytest.fixture
def wide_invoice(app, make_customer):
    c = make_customer('Sri Balaji Solar Works')
    inv = Invoice(invoice_number='INV-WIDE-0001', customer_id=c.id,
                  customer_name=c.name, customer_mobile=c.mobile,
                  customer_email=c.email, customer_address=c.address,
                  customer_gstin=c.gstin, customer_state=c.state,
                  customer_state_code=c.state_code, is_intra_state=True,
                  invoice_date=date(2026, 9, 28), status='confirmed',
                  payment_status='due', amount_paid=0)
    db.session.add(inv)
    db.session.flush()
    for row in WIDE_ITEMS:
        db.session.add(InvoiceItem(
            invoice_id=inv.id, product_name=row[0], hsn=row[1], qty=row[2],
            unit=row[3], price=row[4], discount=row[5], gst_rate=row[6],
            taxable_value=row[7], cgst=row[8], sgst=row[9], igst=row[10],
            total=row[11]))
    inv.subtotal = Decimal('2000000.00')
    inv.total_taxable = Decimal('2000000.00')
    inv.total_cgst = Decimal('150000.00')
    inv.total_sgst = Decimal('150000.00')
    inv.total_igst = Decimal('0')
    inv.grand_total = Decimal('2360000.00')
    inv.balance_due = Decimal('2360000.00')
    db.session.commit()
    return inv


def _table_span(page):
    """(y_top, y_bottom) of the item table, from its own drawn rules.

    The table runs from the rule above the header row to the rule below the LAST
    item row. Row height grows with wrapped description text, so the rules are
    walked forward while the gap stays plausibly row-sized. Using a fixed small
    window here would measure only the header row and pass while every real
    data value overflowed, so the window is deliberately generous and the walk
    stops at the first non-row-sized gap.
    """
    rules = sorted({round(r['rect'].y0, 1) for r in page.get_drawings()
                    if r.get('rect') is not None
                    and r['rect'].height <= 0.8 and r['rect'].width >= 1})
    si = [w for w in page.get_text('words') if w[4] == 'SI.'][0]
    top = max(r for r in rules if r <= si[1] + 1)
    bottom = top
    for y in rules:
        if y <= top + 0.5:
            continue
        if y - bottom <= 60.0:
            bottom = y
        else:
            break
    return top, bottom


def _crossings(page, edges, y0, y1):
    """Per-CHARACTER cell-border crossings inside the item table.

    Character boxes are used rather than words or text spans because PyMuPDF
    merges neighbouring same-baseline cells into one span; a character knows
    exactly which column it belongs to, so a spill is detected with no false
    positives from the columns next door.
    """
    offenders = []
    data = page.get_text('rawdict')
    for block in data['blocks']:
        if block.get('type') != 0:
            continue
        for line in block['lines']:
            for span in line['spans']:
                for ch in span['chars']:
                    if not ch['c'].strip():
                        continue
                    x0, cy0, x1, cy1 = ch['bbox']
                    if not (y0 <= cy0 and cy1 <= y1):
                        continue
                    idx = max((i for i, e in enumerate(edges) if e <= x0 + 0.6),
                              default=None)
                    if idx is None or idx + 1 >= len(edges):
                        continue
                    if x1 > edges[idx + 1]:
                        offenders.append(
                            '%r in %s by %.2fpt'
                            % (ch['c'], ITEM_COLUMNS[idx][0],
                               x1 - edges[idx + 1]))
    return offenders


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_only_the_description_header_wraps(admin_login, invoice, copy):
    """Every column header must sit on ONE line, except the description label.

    A wrapped header is a real defect: "SI." over "NO." reads as two separate
    labels and the two-line stack makes the header row taller and the columns
    ambiguous. The description label is the one deliberate two-line header.
    """
    doc = _open(_pdf(admin_login, invoice.id, copy))
    try:
        page = doc[0]
        edges = _column_edges(page)
        top, _ = _table_span(page)
        rules = sorted({round(r['rect'].y0, 1) for r in page.get_drawings()
                        if r.get('rect') is not None
                        and r['rect'].height <= 0.8 and r['rect'].width >= 1})
        header_bottom = min(y for y in rules if y > top + 0.5)
        baselines = [set() for _ in range(13)]
        for block in page.get_text('rawdict')['blocks']:
            if block.get('type') != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    for ch in span['chars']:
                        if not ch['c'].strip():
                            continue
                        x0, y0 = ch['bbox'][0], ch['bbox'][1]
                        if not (top <= y0 < header_bottom):
                            continue
                        idx = max((i for i, e in enumerate(edges)
                                   if e <= x0 + 0.6), default=None)
                        if idx is not None and idx + 1 < len(edges):
                            baselines[idx].add(round(y0, 0))
        wrapped = [ITEM_COLUMNS[i][0] for i in range(13)
                   if len(baselines[i]) > 1]
        assert wrapped == ['DESCRIPTION OF GOODS AND SERVICES'], \
            'only the description header may wrap, but these did: %s' % wrapped
    finally:
        doc.close()


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_widest_supported_values_never_cross_a_cell_border(
        admin_login, wide_invoice, copy):
    doc = _open(_pdf(admin_login, wide_invoice.id, copy))
    try:
        page = doc[0]
        edges = _column_edges(page)
        y0, y1 = _table_span(page)
        offenders = _crossings(page, edges, y0, y1)
        assert offenders == [], \
            '%s copy: glyphs cross a cell border: %s' % (copy, offenders)
    finally:
        doc.close()


@pytest.mark.parametrize('copy', _COPY_TYPES)
def test_widest_supported_values_stay_on_one_page(admin_login, wide_invoice, copy):
    doc = _open(_pdf(admin_login, wide_invoice.id, copy))
    try:
        assert doc.page_count == 1
    finally:
        doc.close()
