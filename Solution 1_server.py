import re
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, File, UploadFile
from PyPDF2 import PdfReader

app = FastAPI()


def classify_document(pdf_content: bytes) -> dict:
    """Simple document classification"""
    try:
        # Use BytesIO to handle bytes content
        pdf_stream = BytesIO(pdf_content)
        reader = PdfReader(pdf_stream)
        
        # Try to extract document type from PDF metadata title
        doc_type = "Unknown"
        title = ""
        if reader.metadata:
            title = reader.metadata.get('/Title', '')
            if title:
                title = title.strip()
                title_lower = title.lower()
                if "w-2" in title_lower or "w2" in title_lower:
                    doc_type = "w2"
                elif "1099-int" in title_lower or "1099int" in title_lower:
                    doc_type = "1099int"
                elif "1099-div" in title_lower or "1099div" in title_lower:
                    doc_type = "1099div"
                elif "1040" in title_lower:
                    doc_type = "1040"
                elif "1098" in title_lower:
                    doc_type = "1098"
                elif "id card" in title_lower or "identification" in title_lower:
                    doc_type = "id card"
                elif "handwritten" in title_lower or "note" in title_lower:
                    doc_type = "handwritten note"
                else:
                    doc_type = "OTHER"

        # Simple year extraction
        year_match = re.search(r'20\d{2}', title)
        year = year_match.group() if year_match else "Unknown"
        
        return {"document_type": doc_type, "year": year}
        
    except Exception as e:
        return {"document_type": "Error", "year": "Error", "debug": str(e)}


@app.post("/classify")
async def schedule_classify_task(file: Optional[UploadFile] = File(None)):
    """Endpoint to classify a document"""
    
    if not file:
        return {"error": "No file uploaded"}
    
    content = await file.read()
    return classify_document(content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)