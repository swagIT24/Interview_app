import fitz  # pymupdf

def extract_text_from_pdf(file_bytes: bytes) -> str:
    # open PDF from bytes
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    text = ""
    for page in doc:
        text += page.get_text()
    
    return text