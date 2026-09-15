from django.contrib import admin

from .models import Anomaly, Expense, Invoice, InvoiceItem, Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
	list_display = ('name', 'user', 'gstin', 'created_at')
	search_fields = ('name', 'gstin', 'email')
	list_filter = ('created_at',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
	list_display = ('invoice_number', 'vendor', 'user', 'total_amount', 'status', 'risk_score', 'created_at')
	search_fields = ('invoice_number', 'gstin', 'purchase_order_number')
	list_filter = ('status', 'processing_status', 'currency', 'created_at')
	list_select_related = ('user', 'vendor')


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
	list_display = ('description', 'invoice', 'category', 'total')
	list_filter = ('category',)
	search_fields = ('description',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
	list_display = ('description', 'user', 'category', 'amount', 'expense_date')
	list_filter = ('category', 'expense_date')
	search_fields = ('description',)


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
	list_display = ('invoice', 'anomaly_type', 'severity', 'score', 'created_at')
	list_filter = ('anomaly_type', 'severity')
	search_fields = ('description',)
