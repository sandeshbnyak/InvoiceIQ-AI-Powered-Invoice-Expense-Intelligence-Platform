from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Vendor(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vendors')
	name = models.CharField(max_length=255)
	phone = models.CharField(max_length=32, blank=True)
	email = models.EmailField(blank=True)
	address = models.TextField(blank=True)
	gstin = models.CharField(max_length=32, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['name']
		constraints = [
			models.UniqueConstraint(fields=['user', 'name'], name='unique_vendor_per_user'),
		]

	def __str__(self):
		return self.name


class Invoice(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Pending'
		PROCESSED = 'processed', 'Processed'
		VALIDATED = 'validated', 'Validated'
		FLAGGED = 'flagged', 'Flagged'
		REJECTED = 'rejected', 'Rejected'

	class ProcessingStatus(models.TextChoices):
		UPLOADED = 'uploaded', 'Uploaded'
		EXTRACTING = 'extracting', 'Extracting'
		PROCESSING = 'processing', 'Processing'
		COMPLETED = 'completed', 'Completed'
		FAILED = 'failed', 'Failed'

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices')
	vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
	invoice_number = models.CharField(max_length=128, blank=True)
	invoice_date = models.DateField(null=True, blank=True)
	due_date = models.DateField(null=True, blank=True)
	currency = models.CharField(max_length=3, default='INR')
	subtotal = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
	tax_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
	total_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
	file = models.FileField(upload_to='invoices/%Y/%m/', blank=True)
	raw_text = models.TextField(blank=True)
	gstin = models.CharField(max_length=32, blank=True)
	purchase_order_number = models.CharField(max_length=128, blank=True)
	status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
	processing_status = models.CharField(max_length=16, choices=ProcessingStatus.choices, default=ProcessingStatus.UPLOADED)
	risk_score = models.PositiveSmallIntegerField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.UniqueConstraint(
				fields=['user', 'vendor', 'invoice_number'],
				condition=~models.Q(invoice_number=''),
				name='unique_number_per_user_vendor',
			),
		]

	def __str__(self):
		return self.invoice_number or f'Invoice {self.pk}'


class InvoiceItem(models.Model):
	class Category(models.TextChoices):
		SOFTWARE = 'software', 'Software'
		HARDWARE = 'hardware', 'Hardware'
		CLOUD = 'cloud', 'Cloud Infrastructure'
		TRAVEL = 'travel', 'Travel'
		OFFICE = 'office', 'Office Supplies'
		MARKETING = 'marketing', 'Marketing'
		PROFESSIONAL = 'professional', 'Professional Services'
		UTILITIES = 'utilities', 'Utilities'
		OTHER = 'other', 'Other'

	invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
	description = models.CharField(max_length=255)
	quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0)])
	unit_price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
	discount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
	tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
	tax_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
	total = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
	category = models.CharField(max_length=24, choices=Category.choices, default=Category.OTHER)

	def __str__(self):
		return self.description


class Expense(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expenses')
	invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='expenses')
	category = models.CharField(max_length=24, choices=InvoiceItem.Category.choices, default=InvoiceItem.Category.OTHER)
	amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
	expense_date = models.DateField()
	description = models.CharField(max_length=255)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-expense_date', '-created_at']


class Anomaly(models.Model):
	class AnomalyType(models.TextChoices):
		DUPLICATE = 'duplicate', 'Duplicate Invoice'
		UNUSUAL_AMOUNT = 'unusual_amount', 'Unusual Amount'
		MISSING_FIELD = 'missing_field', 'Missing Field'
		CALCULATION = 'calculation', 'Calculation Mismatch'
		VENDOR = 'vendor', 'Vendor Anomaly'
		GST = 'gst', 'GST Anomaly'
		OTHER = 'other', 'Other'

	class Severity(models.TextChoices):
		LOW = 'low', 'Low'
		MEDIUM = 'medium', 'Medium'
		HIGH = 'high', 'High'
		CRITICAL = 'critical', 'Critical'

	invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='anomalies')
	anomaly_type = models.CharField(max_length=24, choices=AnomalyType.choices)
	severity = models.CharField(max_length=16, choices=Severity.choices)
	score = models.PositiveSmallIntegerField(default=0)
	description = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
