from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from ai_engine.ocr import DocumentProcessingError

from .models import Anomaly, Expense, Invoice, Vendor
from .services import process_invoice


def _money(value):
	return float(value or Decimal('0'))


@login_required
def dashboard(request):
	invoices = Invoice.objects.filter(user=request.user).select_related('vendor')
	expenses = Expense.objects.filter(user=request.user)
	monthly = (
		expenses.annotate(month=TruncMonth('expense_date'))
		.values('month')
		.annotate(total=Sum('amount'))
		.order_by('month')[:12]
	)
	categories = (
		expenses.values('category')
		.annotate(total=Sum('amount'))
		.order_by('-total')[:7]
	)
	context = {
		'invoice_count': invoices.count(),
		'spending_total': _money(expenses.aggregate(total=Sum('amount'))['total']),
		'tax_total': _money(invoices.aggregate(total=Sum('tax_amount'))['total']),
		'vendor_count': Vendor.objects.filter(user=request.user).count(),
		'recent_invoices': invoices[:8],
		'alerts': Anomaly.objects.filter(invoice__user=request.user).select_related('invoice', 'invoice__vendor')[:5],
		'monthly_labels': [item['month'].strftime('%b') for item in monthly if item['month']],
		'monthly_values': [_money(item['total']) for item in monthly],
		'category_labels': [item['category'].replace('_', ' ').title() for item in categories],
		'category_values': [_money(item['total']) for item in categories],
	}
	return render(request, 'dashboard.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def invoice_upload(request):
	if request.method == 'POST':
		uploaded_file = request.FILES.get('file')
		allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg'}
		if not uploaded_file:
			return render(request, 'invoices/upload.html', {'error': 'Choose an invoice file to upload.'})
		if uploaded_file.size == 0:
			return render(request, 'invoices/upload.html', {'error': 'The selected file is empty.'})
		if uploaded_file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
			return render(request, 'invoices/upload.html', {'error': f'Choose a file smaller than {settings.MAX_UPLOAD_SIZE_MB} MB.'})
		if Path(uploaded_file.name).suffix.lower() not in allowed_extensions:
			return render(request, 'invoices/upload.html', {'error': 'Upload a PDF, PNG, JPG, or JPEG invoice.'})

		if uploaded_file:
			invoice = Invoice.objects.create(user=request.user, file=uploaded_file)
			try:
				process_invoice(invoice)
			except DocumentProcessingError:
				# The service records the failed state; the detail page can explain it.
				pass
			return redirect('invoice_detail', pk=invoice.pk)
	return render(request, 'invoices/upload.html')


@login_required
def invoice_detail(request, pk):
	invoice = get_object_or_404(
		Invoice.objects.select_related('vendor').prefetch_related('items', 'anomalies'),
		pk=pk,
		user=request.user,
	)
	return render(request, 'invoices/detail.html', {'invoice': invoice})


@login_required
def ai_assistant(request):
	return render(request, 'assistant.html')


def _workspace_context(request, active_page, page_title, page_subtitle):
	user_invoices = Invoice.objects.filter(user=request.user)
	context = {
		'active_page': active_page,
		'page_title': page_title,
		'page_subtitle': page_subtitle,
		'alerts': Anomaly.objects.filter(invoice__user=request.user).select_related('invoice', 'invoice__vendor')[:20],
	}
	if active_page == 'vendors':
		context['vendors'] = Vendor.objects.filter(user=request.user).annotate(
			invoice_count=Count('invoices'),
			total_paid=Sum('invoices__total_amount'),
		)
	elif active_page == 'expenses':
		context['expenses'] = Expense.objects.filter(user=request.user).select_related('invoice')[:100]
	elif active_page == 'analytics':
		expenses = Expense.objects.filter(user=request.user)
		context['spending_total'] = _money(expenses.aggregate(total=Sum('amount'))['total'])
		context['tax_total'] = _money(user_invoices.aggregate(total=Sum('tax_amount'))['total'])
		context['monthly'] = expenses.annotate(month=TruncMonth('expense_date')).values('month').annotate(total=Sum('amount')).order_by('month')
		context['categories'] = expenses.values('category').annotate(total=Sum('amount')).order_by('-total')
	else:
		context['alerts'] = context['alerts']
	return context


@login_required
def vendors(request):
	return render(request, 'workspace.html', _workspace_context(request, 'vendors', 'Vendors', 'Manage the partners behind your invoice stream.'))


@login_required
def expenses(request):
	return render(request, 'workspace.html', _workspace_context(request, 'expenses', 'Expenses', 'Review categorized spending captured from invoices.'))


@login_required
def analytics(request):
	return render(request, 'workspace.html', _workspace_context(request, 'analytics', 'Analytics', 'Compare spending patterns across time and category.'))


@login_required
def risk_alerts(request):
	return render(request, 'workspace.html', _workspace_context(request, 'risk', 'Risk alerts', 'Review duplicates, outliers, and validation exceptions.'))

# Create your views here.
