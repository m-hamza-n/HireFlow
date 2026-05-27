import io
from pypdf import PdfReader  # or PyPDF2

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text from a PDF byte stream safely."""
    try:
        # Wrap raw bytes in a stream that pypdf can cleanly read from start to finish
        pdf_stream = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_stream)
        
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                
        return text.strip()
    except Exception as e:
        # Catch extraction issues explicitly
        raise ValueError(f"Failed to parse PDF content: {str(e)}")