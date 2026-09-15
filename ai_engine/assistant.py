import re
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from invoices.models import Anomaly, Expense, Invoice


BLOCKED_TERMS = re.compile(r'\b(drop|delete|update|insert|alter|truncate|create|grant|revoke)\b', re.I)


def answer_query(user, question):
    question = (question or '').strip()
    if not question:
        return {'intent': 'empty', 'answer': 'Ask a question about your invoices, expenses, vendors, or risks.'}
    if BLOCKED_TERMS.search(question):
        return {
            'intent': 'blocked',
            'answer': 'I can only answer read-only finance questions. Data-changing operations are blocked.',
        }

    normalized = question.lower()
    if 'duplicate' in normalized:
        duplicates = Anomaly.objects.filter(
            invoice__user=user,
            anomaly_type=Anomaly.AnomalyType.DUPLICATE,
        ).select_related('invoice', 'invoice__vendor')[:10]
        if not duplicates:
            return {'intent': 'duplicates', 'answer': 'No potentially duplicated invoices were found.', 'results': []}
        results = [
            {'invoice': item.invoice.invoice_number, 'vendor': item.invoice.vendor.name if item.invoice.vendor else 'Unknown', 'score': item.score}
            for item in duplicates
        ]
        return {'intent': 'duplicates', 'answer': f'Found {len(results)} potentially duplicated invoice(s).', 'results': results}

    if 'highest payment' in normalized or 'top vendor' in normalized or 'most' in normalized and 'vendor' in normalized:
        row = Invoice.objects.filter(user=user, vendor__isnull=False).values('vendor__name').annotate(total=Sum('total_amount')).order_by('-total').first()
        if not row:
            return {'intent': 'top_vendor', 'answer': 'There is not enough invoice data to identify a top vendor.'}
        return {'intent': 'top_vendor', 'answer': f"{row['vendor__name']} received the highest recorded payment: ₹{row['total']:,.2f}."}

    if 'above' in normalized or 'over' in normalized or 'lakh' in normalized:
        threshold = Decimal('100000')
        matches = Invoice.objects.filter(user=user, total_amount__gte=threshold).select_related('vendor').order_by('-total_amount')[:20]
        results = [
            {'invoice': invoice.invoice_number, 'vendor': invoice.vendor.name if invoice.vendor else 'Unknown', 'total': invoice.total_amount}
            for invoice in matches
        ]
        return {'intent': 'high_value', 'answer': f'Found {len(results)} invoice(s) at or above ₹1,00,000.', 'results': results}

    if 'cloud' in normalized:
        total = Expense.objects.filter(user=user, category='cloud').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return {'intent': 'cloud_spend', 'answer': f'Cloud infrastructure spending recorded so far is ₹{total:,.2f}.', 'total': total}

    if 'expense' in normalized or 'spend' in normalized or 'spending' in normalized:
        total = Expense.objects.filter(user=user).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return {'intent': 'total_spend', 'answer': f'Total recorded spending is ₹{total:,.2f}.', 'total': total}

    return {
        'intent': 'unsupported',
        'answer': 'I can answer questions about cloud spending, total expenses, top vendors, invoices above ₹1 lakh, and duplicate invoices.',
    }
