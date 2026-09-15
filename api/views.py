from pathlib import Path

from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from ai_engine.assistant import answer_query
from ai_engine.llm import explain_result
from ai_engine.ocr import DocumentProcessingError
from invoices.models import Anomaly, Expense, Invoice, Vendor
from invoices.services import process_invoice

from .serializers import AnomalySerializer, ExpenseSerializer, InvoiceSerializer, VendorSerializer


class UserScopedMixin:
    permission_classes = [permissions.IsAuthenticated]


class InvoiceListCreateView(UserScopedMixin, generics.ListCreateAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user).select_related('vendor').prefetch_related('items')

    def perform_create(self, serializer):
        invoice = serializer.save(user=self.request.user)
        if invoice.file:
            try:
                process_invoice(invoice)
            except DocumentProcessingError:
                pass


class InvoiceDetailView(UserScopedMixin, generics.RetrieveDestroyAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user).select_related('vendor').prefetch_related('items')


class InvoiceUploadView(UserScopedMixin, APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg'}
        if not uploaded_file:
            return Response({'detail': 'Choose an invoice file to upload.'}, status=status.HTTP_400_BAD_REQUEST)
        if uploaded_file.size == 0:
            return Response({'detail': 'The selected file is empty.'}, status=status.HTTP_400_BAD_REQUEST)
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            return Response(
                {'detail': f'Choose a file smaller than {settings.MAX_UPLOAD_SIZE_MB} MB.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Path(uploaded_file.name).suffix.lower() not in allowed_extensions:
            return Response({'detail': 'Upload a PDF, PNG, JPG, or JPEG invoice.'}, status=status.HTTP_400_BAD_REQUEST)

        invoice = Invoice.objects.create(user=request.user, file=uploaded_file)
        try:
            process_invoice(invoice)
        except DocumentProcessingError:
            invoice.refresh_from_db()
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


class InvoiceAnalyzeView(UserScopedMixin, APIView):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        if not invoice.file:
            return Response({'detail': 'This invoice has no uploaded document.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            process_invoice(invoice)
        except DocumentProcessingError:
            invoice.refresh_from_db()
        return Response(InvoiceSerializer(invoice).data)


class VendorListView(UserScopedMixin, generics.ListAPIView):
    serializer_class = VendorSerializer

    def get_queryset(self):
        return Vendor.objects.filter(user=self.request.user)


class ExpenseListView(UserScopedMixin, generics.ListAPIView):
    serializer_class = ExpenseSerializer
    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user).select_related('invoice')


class MonthlyAnalyticsView(UserScopedMixin, APIView):
    def get(self, request):
        rows = (
            Expense.objects.filter(user=request.user)
            .annotate(month=TruncMonth('expense_date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )
        return Response([
            {'month': row['month'].strftime('%Y-%m'), 'total': row['total']}
            for row in rows if row['month']
        ])


class CategoryAnalyticsView(UserScopedMixin, APIView):
    def get(self, request):
        rows = (
            Expense.objects.filter(user=request.user)
            .values('category')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        return Response(list(rows))


class VendorAnalyticsView(UserScopedMixin, APIView):
    def get(self, request):
        rows = (
            Invoice.objects.filter(user=request.user, vendor__isnull=False)
            .values('vendor_id', 'vendor__name')
            .annotate(total=Sum('total_amount'))
            .order_by('-total')
        )
        return Response([
            {'vendor': row['vendor_id'], 'vendor_name': row['vendor__name'], 'total': row['total']}
            for row in rows
        ])


class AnomalyListView(UserScopedMixin, generics.ListAPIView):
    serializer_class = AnomalySerializer

    def get_queryset(self):
        return Anomaly.objects.filter(invoice__user=self.request.user).select_related('invoice', 'invoice__vendor')


class AIQueryView(UserScopedMixin, APIView):
    def post(self, request):
        question = request.data.get('question', '')
        result = answer_query(request.user, question)
        explanation = explain_result(question, result)
        if explanation:
            result['answer'] = explanation
            result['llm_enhanced'] = True
        else:
            result['llm_enhanced'] = False
        return Response(result)
