import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .classifier import classify_description


_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d-%b-%Y', '%d %b %Y', '%d %B %Y')


def parse_invoice_text(text):
    """Extract common labeled invoice fields into a stable structured payload."""
    text = text or ''
    form_fields = _extract_form_fields(text)
    proforma = _parse_proforma_fields(text)
    return {
        'vendor_name': _find_value(text, ('vendor', 'supplier', 'seller')) or form_fields.get(8, '') or proforma.get('vendor_name', ''),
        'invoice_number': _find_value(text, ('invoice number', 'invoice no', 'invoice #')) or form_fields.get(5, '') or proforma.get('invoice_number', ''),
        'invoice_date': _parse_date(_find_value(text, ('invoice date', 'date')) or form_fields.get(4, '') or proforma.get('invoice_date', '')),
        'due_date': _parse_date(_find_value(text, ('due date', 'payment due'))),
        'currency': _find_currency(text),
        'gstin': _find_value(text, ('gstin', 'gstin no', 'tax id')) or proforma.get('gstin', ''),
        'purchase_order_number': _find_value(text, ('purchase order', 'po number', 'po no')),
        'subtotal': _parse_amount(_find_value(text, ('subtotal', 'sub total'))) or _parse_amount(form_fields.get(54)) or proforma.get('subtotal'),
        'tax_amount': proforma.get('tax_amount') or _parse_amount(_find_value(text, ('tax', 'gst', 'vat'))) or _parse_amount(form_fields.get(57)),
        'total_amount': proforma.get('total_amount') or _parse_amount(_find_value(text, ('grand total', 'total amount', 'total'))) or _parse_amount(form_fields.get(58)),
        'items': _parse_items(text, form_fields) or _parse_proforma_items(text),
    }


def _find_value(text, labels):
    label_pattern = '|'.join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    match = re.search(rf'(?im)^\s*(?:{label_pattern})(?![A-Za-z0-9])\s*[:#-]?\s*(.+?)\s*$', text)
    return match.group(1).strip() if match else ''


def _find_currency(text):
    if '₹' in text or re.search(r'(?i)\bINR\b', text):
        return 'INR'
    if re.search(r'(?i)\bUSD\b|\$', text):
        return 'USD'
    if re.search(r'(?i)\bEUR\b|€', text):
        return 'EUR'
    return 'INR'


def _parse_amount(value):
    if not value:
        return None
    cleaned = re.sub(r'[^0-9.-]', '', value.replace(',', ''))
    try:
        return Decimal(cleaned) if cleaned else None
    except InvalidOperation:
        return None


def _parse_date(value):
    if not value:
        return None
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    return None


def _extract_form_fields(text):
    return {
        int(number): value.strip()
        for number, value in re.findall(r'(?im)^\s*\[FORM FIELD\]\s*Text(\d+)\s*:\s*(.*?)\s*$', text)
    }


def _parse_proforma_fields(text):
    def value(pattern):
        match = re.search(pattern, text, re.I)
        return match.group(1).strip() if match else ''

    seller_gstin = value(r'GSTIN\s*:\s*([A-Z0-9]+)')
    vendor_match = re.search(r'For\s+(.+?)\s*\n\s*Authorised Signatory', text, re.I)
    subtotal = _parse_amount(value(r'Taxable Amount\s+([\d,]+(?:\.\d+)?)'))
    tax = _parse_amount(value(r'(?:Add\s*:\s*IGST|Total Tax)\s+([\d,]+(?:\.\d+)?)'))
    total = _parse_amount(value(r'Total Amount After Tax\s*₹?\s*([\d,]+(?:\.\d+)?)'))
    return {
        'vendor_name': vendor_match.group(1).strip() if vendor_match else '',
        'invoice_number': value(r'Proforma No\.\s*([\w/-]+)'),
        'invoice_date': value(r'Proforma Date\s+([\d]{1,2}-[A-Za-z]{3}-[\d]{4})'),
        'gstin': seller_gstin,
        'subtotal': subtotal,
        'tax_amount': tax,
        'total_amount': total,
    }


def _parse_proforma_items(text):
    items = []
    pattern = re.compile(
        r'(?m)^\s*\d+\s+(.+?)\s+(\d{4,8})\s+([\d,.]+)\s+PCS\s+'
        r'([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s*$'
    )
    for match in pattern.finditer(text):
        description, _hsn, quantity, unit_price, taxable, _tax_rate, _tax, total = match.groups()
        items.append({
            'description': description.strip(),
            'quantity': _parse_amount(quantity) or Decimal('1'),
            'unit_price': _parse_amount(unit_price) or Decimal('0'),
            'discount': Decimal('0'),
            'tax_rate': _parse_amount(_tax_rate),
            'tax_amount': _parse_amount(_tax),
            'total': _parse_amount(total) or _parse_amount(taxable) or Decimal('0'),
            'category': classify_description(description),
        })
    return items


def _parse_items(text, form_fields=None):
    items = []
    in_items_section = False
    for line in text.splitlines():
        normalized = line.strip()
        if re.search(r'(?i)^(items?|description)\b', normalized):
            in_items_section = True
            continue
        if in_items_section and re.search(r'(?i)^(subtotal|tax|gst|grand total|total)\b', normalized):
            break
        if not in_items_section or '|' not in normalized:
            continue
        columns = [column.strip() for column in normalized.split('|')]
        if len(columns) < 4 or not columns[0] or not _parse_amount(columns[-1]):
            continue
        quantity = _parse_amount(columns[1]) or Decimal('1')
        unit_price = _parse_amount(columns[2]) or Decimal('0')
        total = _parse_amount(columns[-1]) or Decimal('0')
        items.append({
            'description': columns[0],
            'quantity': quantity,
            'unit_price': unit_price,
            'discount': _parse_amount(columns[3]) or Decimal('0'),
            'tax_rate': None,
            'tax_amount': None,
            'total': total,
            'category': classify_description(columns[0]),
        })
    if items or not form_fields:
        return items
    form_item_groups = ((20, 22, 23, 24, 25), (26, 28, 29, 30, 31))
    for description_key, hs_key, quantity_key, price_key, total_key in form_item_groups:
        description = form_fields.get(description_key, '')
        total = _parse_amount(form_fields.get(total_key))
        if not description or total is None:
            continue
        items.append({
            'description': description,
            'quantity': _parse_amount(form_fields.get(quantity_key)) or Decimal('1'),
            'unit_price': _parse_amount(form_fields.get(price_key)) or Decimal('0'),
            'discount': Decimal('0'),
            'tax_rate': None,
            'tax_amount': None,
            'total': total,
            'category': classify_description(description),
        })
    return items
