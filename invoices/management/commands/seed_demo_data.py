from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from ai_engine.risk import evaluate_invoice_risk
from ai_engine.validator import validate_totals
from invoices.models import Expense, Invoice, InvoiceItem, Vendor


VENDOR_NAMES = (
    'Acme Cloud Services', 'Nimbus Hardware India', 'Brightline Marketing',
    'Orbit Professional Services', 'Metro Office Supplies', 'Vertex Software',
    'Saffron Travel Desk', 'Grid Utilities', 'BluePeak Consulting',
    'Harbor Technologies', 'Cedar Legal Partners', 'Monsoon Networks',
)

ITEMS = (
    ('AWS infrastructure credits', InvoiceItem.Category.CLOUD, Decimal('18000.00')),
    ('Annual software subscription', InvoiceItem.Category.SOFTWARE, Decimal('24000.00')),
    ('Business laptops', InvoiceItem.Category.HARDWARE, Decimal('68000.00')),
    ('Office stationery bundle', InvoiceItem.Category.OFFICE, Decimal('8500.00')),
    ('Professional advisory services', InvoiceItem.Category.PROFESSIONAL, Decimal('32000.00')),
    ('Digital marketing campaign', InvoiceItem.Category.MARKETING, Decimal('27500.00')),
    ('Domestic travel booking', InvoiceItem.Category.TRAVEL, Decimal('14500.00')),
)


class Command(BaseCommand):
    help = 'Create a realistic, repeatable InvoiceIQ demo workspace.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='demo', help='User who owns the demo data.')
        parser.add_argument('--reset', action='store_true', help='Delete existing data for the demo user first.')

    def handle(self, *args, **options):
        username = options['username']
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        if created:
            user.set_password('demo-password')
            user.save(update_fields=['password'])
            self.stdout.write(f'Created user {username} with password demo-password.')

        if options['reset']:
            user.invoices.all().delete()
            user.vendors.all().delete()
        elif user.invoices.filter(invoice_number__startswith='DEMO-').exists():
            self.stdout.write(self.style.WARNING(
                f'Demo data already exists for {username}; use --reset to recreate it.'
            ))
            return

        vendors = [Vendor.objects.get_or_create(user=user, name=name)[0] for name in VENDOR_NAMES]
        created_invoices = []
        for index in range(60):
            vendor = vendors[index % len(vendors)]
            year = 2026
            month = (index % 12) + 1
            day = (index % 24) + 1
            invoice_date = date(year, month, day)
            description, category, unit_price = ITEMS[index % len(ITEMS)]
            quantity = Decimal((index % 3) + 1)
            subtotal = unit_price * quantity
            tax = (subtotal * Decimal('0.18')).quantize(Decimal('0.01'))
            total = subtotal + tax
            number = f'DEMO-{index + 1:04d}'
            invoice = Invoice.objects.create(
                user=user,
                vendor=vendor,
                invoice_number=number,
                invoice_date=invoice_date,
                due_date=date(year, month, min(day + 15, 28)),
                subtotal=subtotal,
                tax_amount=tax,
                total_amount=total,
                currency='INR',
                gstin='27ABCDE1234F1Z5',
                purchase_order_number=f'PO-{index + 1:04d}',
                status=Invoice.Status.VALIDATED,
                processing_status=Invoice.ProcessingStatus.COMPLETED,
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                total=subtotal,
                category=category,
            )
            Expense.objects.create(
                user=user,
                invoice=invoice,
                category=category,
                amount=total,
                expense_date=invoice_date,
                description=description,
            )
            created_invoices.append(invoice)

        duplicate = Invoice.objects.create(
            user=user,
            vendor=vendors[1],
            invoice_number='DEMO-0001',
            invoice_date=date(2026, 9, 15),
            subtotal=Decimal('42000.00'),
            tax_amount=Decimal('7560.00'),
            total_amount=Decimal('49560.00'),
            currency='INR',
            gstin='27ABCDE1234F1Z5',
            status=Invoice.Status.PROCESSED,
            processing_status=Invoice.ProcessingStatus.COMPLETED,
        )
        duplicate_result = validate_totals(duplicate.subtotal, duplicate.tax_amount, duplicate.total_amount)
        evaluate_invoice_risk(duplicate, duplicate_result)

        unusual = Invoice.objects.create(
            user=user,
            vendor=vendors[2],
            invoice_number='DEMO-UNUSUAL',
            invoice_date=date(2026, 9, 15),
            subtotal=Decimal('145000.00'),
            tax_amount=Decimal('26100.00'),
            total_amount=Decimal('171100.00'),
            currency='INR',
            gstin='27ABCDE1234F1Z5',
            status=Invoice.Status.PROCESSED,
            processing_status=Invoice.ProcessingStatus.COMPLETED,
        )
        unusual_result = validate_totals(unusual.subtotal, unusual.tax_amount, unusual.total_amount)
        evaluate_invoice_risk(unusual, unusual_result)

        mismatch = Invoice.objects.create(
            user=user,
            vendor=vendors[3],
            invoice_number='DEMO-MISMATCH',
            invoice_date=date(2026, 9, 14),
            subtotal=Decimal('50000.00'),
            tax_amount=Decimal('9000.00'),
            total_amount=Decimal('61000.00'),
            currency='INR',
            gstin='27ABCDE1234F1Z5',
            status=Invoice.Status.PROCESSED,
            processing_status=Invoice.ProcessingStatus.COMPLETED,
        )
        mismatch_result = validate_totals(mismatch.subtotal, mismatch.tax_amount, mismatch.total_amount)
        evaluate_invoice_risk(mismatch, mismatch_result)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(vendors)} vendors, {len(created_invoices) + 3} invoices, and demo risk alerts for {username}.'
        ))
