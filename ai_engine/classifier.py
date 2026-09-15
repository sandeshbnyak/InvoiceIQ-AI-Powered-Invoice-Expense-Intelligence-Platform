from invoices.models import InvoiceItem


_RULES = {
    InvoiceItem.Category.SOFTWARE: ('software', 'license', 'subscription', 'saas', 'application'),
    InvoiceItem.Category.HARDWARE: ('laptop', 'monitor', 'server', 'keyboard', 'hardware', 'device'),
    InvoiceItem.Category.CLOUD: ('cloud', 'aws', 'azure', 'gcp', 'hosting', 'infrastructure'),
    InvoiceItem.Category.TRAVEL: ('flight', 'hotel', 'travel', 'taxi', 'transport'),
    InvoiceItem.Category.OFFICE: ('stationery', 'office', 'paper', 'chair', 'supplies'),
    InvoiceItem.Category.MARKETING: ('advertising', 'campaign', 'marketing', 'seo'),
    InvoiceItem.Category.PROFESSIONAL: ('consulting', 'legal', 'audit', 'professional'),
    InvoiceItem.Category.UTILITIES: ('electricity', 'internet', 'utility', 'utilities'),
}


def classify_description(description):
    value = (description or '').lower()
    for category, keywords in _RULES.items():
        if any(keyword in value for keyword in keywords):
            return category
    return InvoiceItem.Category.OTHER
