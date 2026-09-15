from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from ai_engine.parser import parse_invoice_text

from .models import Invoice
from .models import Anomaly, Vendor
from .services import process_invoice
from ai_engine.risk import evaluate_invoice_risk


class InvoiceParserTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='parser-user')

	def test_parses_labeled_invoice_fields(self):
		parsed = parse_invoice_text(
			'''Vendor: Acme Cloud Services
			Invoice Number: INV-2041
			Invoice Date: 15/09/2026
			Due Date: 30/09/2026
			GSTIN: 27ABCDE1234F1Z5
			Subtotal: ₹42,000.00
			GST: ₹7,560.00
			Grand Total: ₹49,560.00'''
		)

		self.assertEqual(parsed['vendor_name'], 'Acme Cloud Services')
		self.assertEqual(parsed['invoice_number'], 'INV-2041')
		self.assertEqual(parsed['invoice_date'].isoformat(), '2026-09-15')
		self.assertEqual(parsed['gstin'], '27ABCDE1234F1Z5')
		self.assertEqual(parsed['subtotal'], Decimal('42000.00'))
		self.assertEqual(parsed['tax_amount'], Decimal('7560.00'))
		self.assertEqual(parsed['total_amount'], Decimal('49560.00'))

	def test_parses_and_classifies_line_items(self):
		parsed = parse_invoice_text(
			'''Items
			Cloud hosting | 1 | 49560.00 | 0 | 49560.00
			Subtotal: 49560.00'''
		)

		self.assertEqual(len(parsed['items']), 1)
		self.assertEqual(parsed['items'][0]['description'], 'Cloud hosting')
		self.assertEqual(parsed['items'][0]['category'], 'cloud')
		self.assertEqual(parsed['items'][0]['total'], Decimal('49560.00'))

	def test_parses_numbered_commercial_invoice_fields(self):
		parsed = parse_invoice_text(
			'''[FORM FIELD] Text4: 14/08/2023
			[FORM FIELD] Text5: F1000876/23
			[FORM FIELD] Text8: LOCAL STORE
			[FORM FIELD] Text20: Conveyor Belt 25"
			[FORM FIELD] Text22: 88565.2252
			[FORM FIELD] Text23: 2
			[FORM FIELD] Text24: 200
			[FORM FIELD] Text25: 400
			[FORM FIELD] Text26: Pole with bracket
			[FORM FIELD] Text28: 88565.2545
			[FORM FIELD] Text29: 1
			[FORM FIELD] Text30: 85
			[FORM FIELD] Text31: 85
			[FORM FIELD] Text54: 485
			[FORM FIELD] Text57: 117
			[FORM FIELD] Text58: 702'''
		)

		self.assertEqual(parsed['vendor_name'], 'LOCAL STORE')
		self.assertEqual(parsed['invoice_number'], 'F1000876/23')
		self.assertEqual(parsed['invoice_date'].isoformat(), '2023-08-14')
		self.assertEqual(parsed['subtotal'], Decimal('485'))
		self.assertEqual(parsed['tax_amount'], Decimal('117'))
		self.assertEqual(parsed['total_amount'], Decimal('702'))
		self.assertEqual(len(parsed['items']), 2)
		self.assertEqual(parsed['items'][1]['description'], 'Pole with bracket')

	def test_parses_indian_gst_proforma_invoice(self):
		parsed = parse_invoice_text(
			'''For Gujarat Freight Tools
			Authorised Signatory
			GSTIN : 24HDE7487RE5RT4
			Proforma No. 201 Proforma Date 05-Mar-2020
			1 Stanley Hammer Claw Hammer Steel Shaft (Black and Chrome) 82052000 3.00 PCS 499.00 1,497.00 18.00 269.46 1,766.46
			2 Automatic Saw 60 mm 400 W 8202 1.00 PCS 1,883.00 1,883.00 18.00 338.94 2,221.94
			Taxable Amount 3,380.00
			Total Tax 608.40
			Total Amount After Tax ₹ 3,988.00'''
		)

		self.assertEqual(parsed['vendor_name'], 'Gujarat Freight Tools')
		self.assertEqual(parsed['invoice_number'], '201')
		self.assertEqual(parsed['invoice_date'].isoformat(), '2020-03-05')
		self.assertEqual(parsed['gstin'], '24HDE7487RE5RT4')
		self.assertEqual(parsed['subtotal'], Decimal('3380.00'))
		self.assertEqual(parsed['tax_amount'], Decimal('608.40'))
		self.assertEqual(parsed['total_amount'], Decimal('3988.00'))
		self.assertEqual(len(parsed['items']), 2)

	def test_processing_persists_parsed_fields_and_expense(self):
		invoice = Invoice.objects.create(
			user=self.user,
			file=SimpleUploadedFile('invoice.pdf', b'placeholder'),
		)
		text = '''Vendor: Acme Cloud Services
		Invoice Number: INV-2041
		Invoice Date: 15/09/2026
		GSTIN: 27ABCDE1234F1Z5
		Items
		Cloud hosting | 1 | 49560.00 | 0 | 49560.00
		Subtotal: ₹42,000.00
		GST: ₹7,560.00
		Grand Total: ₹49,560.00'''

		with patch('invoices.services.extract_text', return_value=(text, 'pdf')):
			process_invoice(invoice)

		invoice.refresh_from_db()
		self.assertEqual(invoice.vendor.name, 'Acme Cloud Services')
		self.assertEqual(invoice.invoice_number, 'INV-2041')
		self.assertEqual(invoice.status, Invoice.Status.VALIDATED)
		self.assertEqual(invoice.items.get().category, 'cloud')
		self.assertEqual(invoice.expenses.get().amount, Decimal('49560.00'))

	def test_duplicate_risk_uses_multiple_invoice_signals(self):
		first_vendor = Vendor.objects.create(user=self.user, name='First Vendor')
		second_vendor = Vendor.objects.create(user=self.user, name='Second Vendor')
		first = Invoice.objects.create(
			user=self.user,
			vendor=first_vendor,
			invoice_number='DUP-1',
			invoice_date=date(2026, 9, 15),
			total_amount=Decimal('1000.00'),
			raw_text='DUP-1 First Vendor 1000.00',
		)
		second = Invoice.objects.create(
			user=self.user,
			vendor=second_vendor,
			invoice_number='DUP-1',
			invoice_date=date(2026, 9, 15),
			total_amount=Decimal('1000.00'),
			raw_text='DUP-1 First Vendor 1000.00',
		)

		evaluate_invoice_risk(first, {'valid': True, 'expected_total': Decimal('1000.00'), 'actual_total': Decimal('1000.00')})
		evaluate_invoice_risk(second, {'valid': True, 'expected_total': Decimal('1000.00'), 'actual_total': Decimal('1000.00')})

		self.assertEqual(second.anomalies.get(anomaly_type=Anomaly.AnomalyType.DUPLICATE).score, 95)


class InvoiceUploadTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='analyst',
			password='strong-test-password',
		)
		self.client.force_login(self.user)

	def test_rejects_unsupported_file_type_before_creating_invoice(self):
		response = self.client.post(
			'/invoices/upload/',
			{'file': SimpleUploadedFile('invoice.txt', b'invoice')},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Upload a PDF, PNG, JPG, or JPEG invoice.')
		self.assertFalse(Invoice.objects.exists())

	def test_rejects_empty_file_before_creating_invoice(self):
		response = self.client.post(
			'/invoices/upload/',
			{'file': SimpleUploadedFile('invoice.pdf', b'')},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'The selected file is empty.')
		self.assertFalse(Invoice.objects.exists())

	def test_marks_unreadable_document_as_failed(self):
		response = self.client.post(
			'/invoices/upload/',
			{'file': SimpleUploadedFile('invoice.pdf', b'not a real pdf')},
		)

		invoice = Invoice.objects.get(user=self.user)
		self.assertRedirects(response, f'/invoices/{invoice.pk}/')
		self.assertEqual(invoice.processing_status, Invoice.ProcessingStatus.FAILED)
		self.assertEqual(invoice.status, Invoice.Status.FLAGGED)

	def test_dashboard_exposes_chart_data_as_arrays(self):
		response = self.client.get('/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['monthly_labels'], [])
		self.assertEqual(response.context['monthly_values'], [])
		self.assertEqual(response.context['category_labels'], [])
		self.assertEqual(response.context['category_values'], [])

	def test_workspace_pages_render_for_authenticated_user(self):
		for path in ('/vendors/', '/expenses/', '/analytics/', '/risk-alerts/'):
			with self.subTest(path=path):
				response = self.client.get(path)
				self.assertEqual(response.status_code, 200)


class DemoDataCommandTests(TestCase):
	def test_seed_command_is_populated_and_rerun_safe(self):
		call_command('seed_demo_data', username='seeded-demo')
		user = get_user_model().objects.get(username='seeded-demo')

		self.assertEqual(Vendor.objects.filter(user=user).count(), 12)
		self.assertEqual(Invoice.objects.filter(user=user).count(), 63)
		anomaly_types = set(Anomaly.objects.filter(invoice__user=user).values_list('anomaly_type', flat=True))
		self.assertGreaterEqual(len(anomaly_types), 3)
		self.assertTrue({
			Anomaly.AnomalyType.DUPLICATE,
			Anomaly.AnomalyType.UNUSUAL_AMOUNT,
			Anomaly.AnomalyType.CALCULATION,
		}.issubset(anomaly_types))

		call_command('seed_demo_data', username='seeded-demo')
		self.assertEqual(Invoice.objects.filter(user=user).count(), 63)

# Create your tests here.
