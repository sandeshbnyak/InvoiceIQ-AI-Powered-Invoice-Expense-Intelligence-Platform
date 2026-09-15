import os
from pathlib import Path


class DocumentProcessingError(Exception):
    pass


def _configure_tesseract():
    import pytesseract

    configured_path = os.getenv('TESSERACT_CMD', '').strip()
    windows_default = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if configured_path:
        pytesseract.pytesseract.tesseract_cmd = configured_path
    elif os.name == 'nt' and Path(windows_default).exists():
        pytesseract.pytesseract.tesseract_cmd = windows_default


def extract_text(file_path, minimum_text_length=40):
    path = Path(file_path)
    if not path.exists() or path.stat().st_size == 0:
        raise DocumentProcessingError('The uploaded document is empty or unavailable.')

    suffix = path.suffix.lower()
    if suffix == '.pdf':
        text = _extract_pdf_text(path)
        if len(text.strip()) >= minimum_text_length:
            return text, 'pdf'
        return _extract_scanned_pdf(path), 'ocr'
    if suffix in {'.png', '.jpg', '.jpeg'}:
        return _extract_image_text(path), 'ocr'
    raise DocumentProcessingError('Unsupported document format.')


def _extract_pdf_text(path):
    try:
        import pymupdf
        document = pymupdf.open(path)
        return '\n'.join(page.get_text() for page in document)
    except Exception as exc:
        raise DocumentProcessingError('Unable to read the PDF document.') from exc


def _extract_scanned_pdf(path):
    try:
        import pymupdf
        import pytesseract
        from PIL import Image
        from io import BytesIO
        _configure_tesseract()
        document = pymupdf.open(path)
        pages = []
        for page in document:
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            pages.append(pytesseract.image_to_string(Image.open(BytesIO(pixmap.tobytes('png')))))
        return '\n'.join(pages)
    except Exception as exc:
        raise DocumentProcessingError('OCR could not process the scanned PDF.') from exc


def _extract_image_text(path):
    try:
        import pytesseract
        from PIL import Image, ImageOps

        _configure_tesseract()
        image = Image.open(path).convert('L')
        prepared = ImageOps.autocontrast(image).point(lambda pixel: 255 if pixel > 180 else 0)
        return pytesseract.image_to_string(prepared)
    except Exception as exc:
        raise DocumentProcessingError('OCR could not process the image.') from exc
