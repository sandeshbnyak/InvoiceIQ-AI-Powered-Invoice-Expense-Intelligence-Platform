from decimal import Decimal


def validate_totals(subtotal, tax_amount, total_amount, tolerance=Decimal('0.01')):
    subtotal = Decimal(str(subtotal or 0))
    tax_amount = Decimal(str(tax_amount or 0))
    total_amount = Decimal(str(total_amount or 0))
    expected_total = subtotal + tax_amount
    difference = abs(expected_total - total_amount)
    return {
        'valid': difference <= tolerance,
        'expected_total': expected_total,
        'actual_total': total_amount,
        'difference': difference,
    }
