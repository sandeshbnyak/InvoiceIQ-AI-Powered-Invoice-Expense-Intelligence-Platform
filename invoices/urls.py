from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('invoices/upload/', views.invoice_upload, name='invoice_upload'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('ai-assistant/', views.ai_assistant, name='ai-assistant'),
    path('vendors/', views.vendors, name='vendors'),
    path('expenses/', views.expenses, name='expenses'),
    path('analytics/', views.analytics, name='analytics'),
    path('risk-alerts/', views.risk_alerts, name='risk-alerts'),
]