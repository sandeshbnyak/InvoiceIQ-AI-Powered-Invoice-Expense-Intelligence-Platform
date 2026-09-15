from ai_engine.ocr import DocumentProcessingError, extract_text
from ai_engine.parser import parse_invoice_text
from ai_engine.risk import evaluate_invoice_risk
from ai_engine.validator import validate_totals

from .models import Expense, Invoice, InvoiceItem, Vendor


def process_invoice(invoice):
    invoice.processing_status = Invoice.ProcessingStatus.EXTRACTING
    invoice.save(update_fields=['processing_status', 'updated_at'])
    try:
        text, _source = extract_text(invoice.file.path)
        parsed = parse_invoice_text(text)
        vendor = None
        if parsed['vendor_name']:
            vendor, _created = Vendor.objects.get_or_create(
                user=invoice.user,
                name=parsed['vendor_name'],
            )
        invoice.vendor = vendor
        invoice.invoice_number = parsed['invoice_number']
        invoice.invoice_date = parsed['invoice_date']
        invoice.due_date = parsed['due_date']
        invoice.currency = parsed['currency']
        invoice.gstin = parsed['gstin']
        invoice.purchase_order_number = parsed['purchase_order_number']
        invoice.subtotal = parsed['subtotal']
        invoice.tax_amount = parsed['tax_amount']
        invoice.total_amount = parsed['total_amount']
        invoice.raw_text = text
        invoice.processing_status = Invoice.ProcessingStatus.COMPLETED
        invoice.status = Invoice.Status.PROCESSED
        invoice.save(update_fields=[
            'vendor', 'invoice_number', 'invoice_date', 'due_date', 'currency',
            'gstin', 'purchase_order_number', 'subtotal', 'tax_amount',
            'total_amount', 'raw_text', 'processing_status', 'status', 'updated_at',
        ])
        validation_result = validate_invoice(invoice)
        evaluate_invoice_risk(invoice, validation_result)
        invoice.items.all().delete()
        invoice.expenses.all().delete()
        for item in parsed['items']:
            invoice_item = InvoiceItem.objects.create(invoice=invoice, **item)
            invoice.expenses.create(
                user=invoice.user,
                category=invoice_item.category,
                amount=invoice_item.total,
                expense_date=invoice.invoice_date or invoice.created_at.date(),
                description=invoice_item.description,
            )
        if not parsed['items'] and invoice.total_amount is not None:
            invoice.expenses.update_or_create(
                description='Invoice total',
                defaults={
                    'user': invoice.user,
                    'category': 'other',
                    'amount': invoice.total_amount,
                    'expense_date': invoice.invoice_date or invoice.created_at.date(),
                },
            )
        return invoice
    except (DocumentProcessingError, OSError):
        invoice.processing_status = Invoice.ProcessingStatus.FAILED
        invoice.status = Invoice.Status.FLAGGED
        invoice.save(update_fields=['processing_status', 'status', 'updated_at'])
        raise


def validate_invoice(invoice):
    result = validate_totals(invoice.subtotal, invoice.tax_amount, invoice.total_amount)
    invoice.status = Invoice.Status.VALIDATED if result['valid'] else Invoice.Status.FLAGGED
    invoice.save(update_fields=['status', 'updated_at'])
    return result
