"""Print pagination regression: a one-page invoice must stay one A4 page.

The sheet is a flex column pinned to the printable page height. Two things used
to push "This is a computer-generated invoice." onto a second page:

  * the UA stylesheet's 8px ``body`` margin survived into print (the reset was
    ``@media screen`` only), inset-ing the sheet into a page it exactly filled;
  * the sheet's print ``min-height`` was the full 297mm, leaving no tolerance for
    the sub-pixel rounding of 297mm -> 1122.52px at 96dpi.

Both are asserted here through the real renderer used by the PDF download, and
through the same canonical stylesheet the browser prints from.
"""
import os
import re

import pytest


def _build_print_html(app, inv, copy, all_copies=False):
    from flask import render_template
    from pathlib import Path
    from app import (_invoice_css_file_path, _invoice_logo_file_path,
                     amount_to_words)

    css = Path(_invoice_css_file_path()).resolve().as_uri()
    logo = _invoice_logo_file_path()
    extra = {'copies': ['owner', 'customer', 'gst']} if all_copies else {}
    with app.test_request_context('/invoices/%d/print/%s' % (inv.id, copy)):
        return render_template(
            'billing/print_all_copies.html' if all_copies else 'billing/print_invoice.html',
            invoice=inv, copy_type=copy, amount_words=amount_to_words(inv.grand_total),
            company={}, invoice_css_url=css,
            logo_url=Path(logo).resolve().as_uri() if logo else None,
            pdf_mode=True, **extra)


def _render(app, inv, copy, all_copies=False):
    from weasyprint import HTML
    html = _build_print_html(app, inv, copy, all_copies)
    return HTML(string=html, base_url=app.root_path, media_type='print').render()


@pytest.mark.parametrize('copy', ['owner', 'customer', 'gst'])
def test_single_page_invoice_is_one_page(app, make_invoice, copy):
    """The footer must not be stranded on a second page in ANY copy."""
    from app import db
    inv = make_invoice(products=[{'product': None, 'name': 'test product',
                                  'qty': 2, 'price': 59, 'gst_rate': 18}])
    inv.eway_bill_number = '123456789012'
    db.session.commit()

    doc = _render(app, inv, copy)
    assert len(doc.pages) == 1, '%s copy paginated to %d pages' % (copy, len(doc.pages))


@pytest.mark.parametrize('copy', ['owner', 'customer', 'gst'])
def test_footer_and_signatures_on_the_only_page(app, make_invoice, copy):
    """Footer, both signatures and Amount in Words all live on page 1."""
    from app import db
    inv = make_invoice(products=[{'product': None, 'name': 'test product',
                                  'qty': 2, 'price': 59, 'gst_rate': 18}])
    inv.eway_bill_number = '123456789012'
    db.session.commit()

    text = []
    doc = _render(app, inv, copy)
    _collect(doc.pages[0]._page_box, text)
    # the labels are CSS-uppercased, so compare case-insensitively
    flat = ' '.join(' '.join(text).split()).upper()

    assert 'THIS IS A COMPUTER-GENERATED INVOICE.' in flat
    assert 'CUSTOMER SIGNATURE' in flat
    assert 'AUTHORIZED SIGNATORY' in flat
    assert 'FOR GV POWERS' in flat
    assert 'AMOUNT IN WORDS' in flat
    assert '123456789012' in flat


def test_all_copies_document_is_exactly_three_pages(app, make_invoice):
    """One A4 page per copy, never a blank or extra page."""
    inv = make_invoice(products=[{'product': None, 'name': 'test product',
                                  'qty': 2, 'price': 59, 'gst_rate': 18}])
    doc = _render(app, inv, 'owner', all_copies=True)
    assert len(doc.pages) == 3, 'expected 3 pages, got %d' % len(doc.pages)


def test_print_stylesheet_reserves_page_slack(app):
    """The sheet must sit under the page height, and body must not be inset.

    Guards the two values that caused the overflow, so a future edit cannot
    silently reintroduce a second page.
    """
    from app import _invoice_css_file_path
    css = open(_invoice_css_file_path(), encoding='utf-8').read()
    block = css[css.index('@media print {'):]

    m = re.search(r'\.gvp-sheet\s*\{[^}]*min-height:\s*([\d.]+)mm', block)
    assert m, 'print .gvp-sheet has no mm min-height'
    assert float(m.group(1)) < 297, (
        'print min-height %smm fills the whole 297mm page; rounding will spill '
        'the footer onto page 2' % m.group(1))

    assert re.search(r'body\.gvp-print-doc\s*\{\s*margin:\s*0', block), (
        'print body margin is not reset; the UA 8px inset pushes the sheet off '
        'the page')


def _collect(box, out):
    t = getattr(box, 'text', None)
    if t:
        out.append(t)
    for child in getattr(box, 'children', []):
        _collect(child, out)
    return out
