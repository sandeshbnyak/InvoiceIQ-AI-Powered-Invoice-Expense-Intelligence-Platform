from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from unittest.mock import patch
from rest_framework.test import APIClient

from invoices.models import Anomaly, Expense, Invoice, Vendor


class AnalyticsApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='api-user')
        other_user = user_model.objects.create_user(username='other-user')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        vendor = Vendor.objects.create(user=self.user, name='Acme Cloud')
        invoice = Invoice.objects.create(
            user=self.user,
            vendor=vendor,
            invoice_number='INV-100',
            invoice_date=date(2026, 9, 15),
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('18.00'),
            total_amount=Decimal('118.00'),
        )
        Expense.objects.create(
            user=self.user,
            invoice=invoice,
            category='cloud',
            amount=Decimal('118.00'),
            expense_date=date(2026, 9, 15),
            description='Cloud invoice',
        )
        Anomaly.objects.create(
            invoice=invoice,
            anomaly_type=Anomaly.AnomalyType.CALCULATION,
            severity=Anomaly.Severity.HIGH,
            score=35,
            description='Test alert',
        )

        other_vendor = Vendor.objects.create(user=other_user, name='Private Vendor')
        Invoice.objects.create(
            user=other_user,
            vendor=other_vendor,
            invoice_number='PRIVATE-1',
            total_amount=Decimal('9999.00'),
        )

    def test_monthly_categories_and_vendor_analytics_are_aggregated(self):
        monthly = self.client.get('/api/analytics/monthly/')
        categories = self.client.get('/api/analytics/categories/')
        vendors = self.client.get('/api/analytics/vendors/')

        self.assertEqual(monthly.status_code, 200)
        self.assertEqual(monthly.data[0]['month'], '2026-09')
        self.assertEqual(monthly.data[0]['total'], Decimal('118.00'))
        self.assertEqual(categories.data[0]['category'], 'cloud')
        self.assertEqual(categories.data[0]['total'], Decimal('118.00'))
        self.assertEqual(vendors.data[0]['vendor_name'], 'Acme Cloud')
        self.assertEqual(vendors.data[0]['total'], Decimal('118.00'))

    def test_anomalies_are_user_scoped_and_serialized(self):
        response = self.client.get('/api/anomalies/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['invoice_number'], 'INV-100')
        self.assertEqual(response.data[0]['vendor_name'], 'Acme Cloud')

    def test_analytics_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get('/api/analytics/monthly/')

        self.assertEqual(response.status_code, 403)


class AssistantApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='assistant-user')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        vendor = Vendor.objects.create(user=self.user, name='Cloud Vendor')
        invoice = Invoice.objects.create(
            user=self.user,
            vendor=vendor,
            invoice_number='AI-1',
            total_amount=Decimal('125000.00'),
        )
        Expense.objects.create(
            user=self.user,
            invoice=invoice,
            category='cloud',
            amount=Decimal('125000.00'),
            expense_date=date(2026, 9, 15),
            description='Cloud hosting',
        )

    def test_answers_supported_read_only_questions(self):
        response = self.client.post('/api/ai/query/', {'question': 'How much did we spend on cloud services?'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['intent'], 'cloud_spend')
        self.assertIn('125,000.00', response.data['answer'])
        self.assertFalse(response.data['llm_enhanced'])

    def test_blocks_destructive_questions(self):
        response = self.client.post('/api/ai/query/', {'question': 'DELETE all invoices'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['intent'], 'blocked')
        self.assertEqual(Invoice.objects.filter(user=self.user).count(), 1)

    def test_assistant_page_requires_login(self):
        self.client.force_authenticate(user=None)

        response = self.client.get('/ai-assistant/')

        self.assertEqual(response.status_code, 302)


class InvoiceWorkflowApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='workflow-user')
        self.other_user = get_user_model().objects.create_user(username='workflow-other')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('api.views.process_invoice')
    def test_upload_endpoint_creates_invoice_from_multipart_file(self, process_invoice):
        response = self.client.post(
            '/api/invoices/upload/',
            {'file': SimpleUploadedFile('invoice.pdf', b'pdf-bytes')},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['processing_status'], 'uploaded')
        process_invoice.assert_called_once()

    def test_upload_endpoint_rejects_invalid_extension(self):
        response = self.client.post(
            '/api/invoices/upload/',
            {'file': SimpleUploadedFile('invoice.txt', b'text')},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Invoice.objects.filter(user=self.user).count(), 0)

    @patch('api.views.process_invoice')
    def test_analyze_endpoint_reprocesses_owned_invoice(self, process_invoice):
        invoice = Invoice.objects.create(
            user=self.user,
            file=SimpleUploadedFile('invoice.pdf', b'pdf-bytes'),
        )

        response = self.client.post(f'/api/invoices/{invoice.pk}/analyze/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], invoice.pk)
        process_invoice.assert_called_once_with(invoice)

    def test_analyze_endpoint_hides_other_users_invoice(self):
        invoice = Invoice.objects.create(
            user=self.other_user,
            file=SimpleUploadedFile('invoice.pdf', b'pdf-bytes'),
        )

        response = self.client.post(f'/api/invoices/{invoice.pk}/analyze/')

        self.assertEqual(response.status_code, 404)
