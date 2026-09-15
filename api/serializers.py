from rest_framework import serializers

from invoices.models import Anomaly, Expense, Invoice, InvoiceItem, Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ('id', 'name', 'email', 'phone', 'address', 'gstin')
        read_only_fields = ('id',)


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ('id', 'description', 'quantity', 'unit_price', 'discount', 'tax_rate', 'tax_amount', 'total', 'category')
        read_only_fields = ('id',)


class InvoiceSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = ('id', 'vendor', 'vendor_name', 'invoice_number', 'invoice_date', 'due_date', 'subtotal', 'tax_amount', 'total_amount', 'currency', 'gstin', 'purchase_order_number', 'file', 'status', 'processing_status', 'risk_score', 'items', 'created_at', 'updated_at')
        read_only_fields = ('id', 'status', 'processing_status', 'risk_score', 'created_at', 'updated_at')


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ('id', 'invoice', 'category', 'amount', 'expense_date', 'description', 'created_at')
        read_only_fields = ('id', 'created_at')


class AnomalySerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    vendor_name = serializers.CharField(source='invoice.vendor.name', read_only=True)

    class Meta:
        model = Anomaly
        fields = ('id', 'invoice', 'invoice_number', 'vendor_name', 'anomaly_type', 'severity', 'score', 'description', 'created_at')
        read_only_fields = fields
