from django.urls import path

from .views import (
    AnomalyListView,
    AIQueryView,
    CategoryAnalyticsView,
    ExpenseListView,
    InvoiceDetailView,
    InvoiceListCreateView,
    InvoiceAnalyzeView,
    InvoiceUploadView,
    MonthlyAnalyticsView,
    VendorAnalyticsView,
    VendorListView,
)

urlpatterns = [
    path('invoices/upload/', InvoiceUploadView.as_view(), name='api-invoice-upload'),
    path('invoices/', InvoiceListCreateView.as_view(), name='api-invoices'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='api-invoice-detail'),
    path('invoices/<int:pk>/analyze/', InvoiceAnalyzeView.as_view(), name='api-invoice-analyze'),
    path('vendors/', VendorListView.as_view(), name='api-vendors'),
    path('expenses/', ExpenseListView.as_view(), name='api-expenses'),
    path('analytics/monthly/', MonthlyAnalyticsView.as_view(), name='api-analytics-monthly'),
    path('analytics/categories/', CategoryAnalyticsView.as_view(), name='api-analytics-categories'),
    path('analytics/vendors/', VendorAnalyticsView.as_view(), name='api-analytics-vendors'),
    path('anomalies/', AnomalyListView.as_view(), name='api-anomalies'),
    path('ai/query/', AIQueryView.as_view(), name='api-ai-query'),
]