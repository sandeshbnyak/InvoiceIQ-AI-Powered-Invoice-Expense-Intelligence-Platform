from decimal import Decimal
from difflib import SequenceMatcher

from django.db.models import Avg

from invoices.models import Anomaly, Invoice


def evaluate_invoice_risk(invoice, validation_result):
    """Create repeatable rule-based anomalies and return a 0-100 risk score."""
    invoice.anomalies.all().delete()
    findings = []

    duplicate_score, duplicate_match = _duplicate_score(invoice)
    if duplicate_score >= 45:
        match_label = duplicate_match.invoice_number or f'Invoice {duplicate_match.pk}'
        findings.append((
            Anomaly.AnomalyType.DUPLICATE,
            Anomaly.Severity.HIGH if duplicate_score >= 70 else Anomaly.Severity.MEDIUM,
            duplicate_score,
            f'Potential duplicate of {match_label} with a similarity score of {duplicate_score}/100.',
        ))

    missing_fields = []
    if not invoice.vendor_id:
        missing_fields.append('vendor')
    if not invoice.invoice_number:
        missing_fields.append('invoice number')
    if not invoice.invoice_date:
        missing_fields.append('invoice date')
    if not invoice.gstin:
        missing_fields.append('GSTIN')
    if missing_fields:
        findings.append((
            Anomaly.AnomalyType.MISSING_FIELD,
            Anomaly.Severity.MEDIUM,
            min(30, len(missing_fields) * 10),
            f"Missing required fields: {', '.join(missing_fields)}.",
        ))

    if not validation_result['valid']:
        findings.append((
            Anomaly.AnomalyType.CALCULATION,
            Anomaly.Severity.HIGH,
            35,
            f"Expected total {validation_result['expected_total']} but found {validation_result['actual_total']}.",
        ))

    if invoice.total_amount is not None:
        historical = invoice.user.invoices.exclude(pk=invoice.pk).filter(
            total_amount__isnull=False,
        ).aggregate(average=Avg('total_amount'))['average']
        if historical and historical > 0 and invoice.total_amount >= historical * Decimal('2'):
            findings.append((
                Anomaly.AnomalyType.UNUSUAL_AMOUNT,
                Anomaly.Severity.MEDIUM,
                20,
                f'Invoice amount is substantially above the historical average of {historical:.2f}.',
            ))

    if _is_isolation_forest_outlier(invoice):
        findings.append((
            Anomaly.AnomalyType.UNUSUAL_AMOUNT,
            Anomaly.Severity.MEDIUM,
            25,
            'Invoice amount was identified as an outlier by the historical Isolation Forest model.',
        ))

    for anomaly_type, severity, score, description in findings:
        Anomaly.objects.create(
            invoice=invoice,
            anomaly_type=anomaly_type,
            severity=severity,
            score=score,
            description=description,
        )

    risk_score = min(100, sum(item[2] for item in findings))
    invoice.risk_score = risk_score
    invoice.status = Invoice.Status.FLAGGED if findings else Invoice.Status.VALIDATED
    invoice.save(update_fields=['risk_score', 'status', 'updated_at'])
    return risk_score


def _duplicate_score(invoice):
    candidates = invoice.user.invoices.exclude(pk=invoice.pk).select_related('vendor')
    best_score = 0
    best_match = None
    for candidate in candidates:
        score = 0
        if invoice.invoice_number and invoice.invoice_number.lower() == candidate.invoice_number.lower():
            score += 45
        if invoice.vendor_id and invoice.vendor_id == candidate.vendor_id:
            score += 20
        if invoice.invoice_date and invoice.invoice_date == candidate.invoice_date:
            score += 15
        if invoice.total_amount is not None and invoice.total_amount == candidate.total_amount:
            score += 15
        if invoice.raw_text and candidate.raw_text:
            similarity = SequenceMatcher(None, invoice.raw_text, candidate.raw_text).ratio()
            if similarity >= 0.85:
                score += 20
        if score > best_score:
            best_score = min(score, 100)
            best_match = candidate
    return best_score, best_match


def _is_isolation_forest_outlier(invoice):
    if invoice.total_amount is None:
        return False
    amounts = list(invoice.user.invoices.exclude(pk=invoice.pk).filter(
        total_amount__isnull=False,
    ).values_list('total_amount', flat=True))
    if len(amounts) < 5:
        return False
    try:
        from sklearn.ensemble import IsolationForest
        values = [[float(amount)] for amount in amounts] + [[float(invoice.total_amount)]]
        model = IsolationForest(contamination='auto', random_state=42)
        return model.fit_predict(values)[-1] == -1
    except (ImportError, ValueError):
        return False
