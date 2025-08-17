import base64
import io
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pdf2image import convert_from_path
from PIL import Image

# Try to import optional dependencies
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google.api_core.client_options import ClientOptions
    from google.cloud import documentai_v1
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

app = FastAPI(title="Document Classification API", version="1.0.0")


def extract_text_from_pdf(pdf_path: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Extract text content from a PDF using PyMuPDF
    Returns a tuple of (text_spans, lines)
    """
    doc = fitz.open(pdf_path)
    results = []
    lines = []
    
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")
        
        # Clean blocks for JSON serialization
        def remove_bytes(obj):
            if isinstance(obj, dict):
                return {k: remove_bytes(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [remove_bytes(i) for i in obj]
            elif isinstance(obj, bytes):
                return obj.decode(errors="replace")
            else:
                return obj

        # Extract text spans and complete lines
        for block in blocks["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    line_spans = []
                    
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:
                            span_info = {
                                "text": text,
                                "font_name": span["font"],
                                "font_size": span["size"],
                                "font_color": span["color"],
                                "bbox": span.get("bbox", None),
                                "page": page_num + 1
                            }
                            results.append(span_info)
                            line_spans.append(span_info)
                            line_text += text + " "
                    
                    if line_text.strip():
                        lines.append({
                            "text": line_text.strip(),
                            "spans": line_spans,
                            "page": page_num + 1
                        })
    
    doc.close()
    return results, lines


def analyze_form_content(text_spans: List[Dict], lines: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
    """
    Analyze text content to determine form type and year
    Returns a tuple of (document_type, year)
    """
    for line in lines:
        text = line["text"].strip()
        
        # Check for various form types with their specific font requirements
        if text == "Form 1098":
            if len(line["spans"]) == 2 and line["spans"][0]["text"] == "Form" and line["spans"][1]["text"] == "1098":
                form_span, num_span = line["spans"][0], line["spans"][1]
                if (abs(form_span["font_size"] - 7.0) <= 2 and form_span["font_name"] == "HelveticaNeueLTStd-Roman" and
                    abs(num_span["font_size"] - 14.0) <= 2 and num_span["font_name"] == "HelveticaNeueLTStd-Bd"):

                    # Get year from the document by looking for a span with text "24" in the expected box area
                    year = ""
                    year_bbox = [437.46, 98.37, 444.14, 104.38]
                    tolerance = 20
                    
                    for l in lines:
                        for s in l.get("spans", []):
                            bbox = s.get("bbox", None)
                            if bbox and all(abs(b - e) < tolerance for b, e in zip(bbox, year_bbox)):
                                text_val = s.get("text", "")
                                if (
                                    text_val.isdigit() and len(text_val) == 2
                                    and abs(s.get("font_size", 0) - 6.0) < 2
                                    and "Helvetica" in s.get("font_name", "")
                                ):
                                    year = "20" + text_val
                                    break
                        if year:
                            break

                    return "1098", year

        elif text in ["Form 1099-INT", "Form 1099-DIV"]:
            if len(line["spans"]) == 2 and line["spans"][0]["text"] == "Form":
                form_span, num_span = line["spans"][0], line["spans"][1]
                document_type = num_span["text"]  # "1099-INT" or "1099-DIV"
                
                # Common font requirements for 1099 forms
                if (
                    abs(form_span["font_size"] - 7.0) <= 2
                    and form_span["font_name"] == "HelveticaNeueLTStd-Roman"
                    and abs(num_span["font_size"] - 12.0) <= 2
                    and num_span["font_name"] == "HelveticaNeueLTStd-Bd"
                    and text in ["Form 1099-INT", "Form 1099-DIV"]
                ):

                    # Get year from the document - look for year in various formats
                    year = ""

                    # Method 1: Look for 4-digit years in the document
                    for l in lines:
                        for s in l.get("spans", []):
                            text_val = s.get("text", "").strip()
                            if text_val.isdigit() and len(text_val) == 4 and text_val.startswith("20"):
                                year = text_val
                                break
                        if year:
                            break

                    return "1099", year
        
        elif text == "Form W-2":
            if len(line["spans"]) == 2 and line["spans"][0]["text"] == "Form" and line["spans"][1]["text"] == "W-2":
                form_span, num_span = line["spans"][0], line["spans"][1]
                if (abs(form_span["font_size"] - 7.0) <= 2 and form_span["font_name"] == "HelveticaNeueLTStd-Bd" and
                    abs(num_span["font_size"] - 24.0) <= 2 and num_span["font_name"] == "HelveticaNeueLTStd-BlkCn"):

                    # Get year from the document
                    year = ""
                    for l in lines:
                        for s in l.get("spans", []):
                            if (
                                abs(s.get("font_size", 0) - 24.0) <= 2
                                and s.get("font_name", "") == "OCRAStd"
                                and s.get("text", "").isdigit()
                                and len(s.get("text", "")) == 4
                            ):
                                year = s["text"]
                                break
                        if year:
                            break

                    return "W2", year
        
        elif text.startswith("Form 1040"):
            if len(line["spans"]) >= 2 and line["spans"][0]["text"] == "Form" and line["spans"][1]["text"] == "1040":
                form_span, num_span = line["spans"][0], line["spans"][1]
                if (abs(form_span["font_size"] - 6.0) <= 2 and form_span["font_name"] == "HelveticaNeueLTStd-Roman" and
                    abs(num_span["font_size"] - 9.0) <= 2 and num_span["font_name"] == "HelveticaNeueLTStd-Bd"):

                    # Get year from the document - look for year in the form title
                    year = ""
                    line_text = line["text"]
                    if "(" in line_text and ")" in line_text:
                        start = line_text.find("(") + 1
                        end = line_text.find(")")
                        if start < end:
                            year_text = line_text[start:end].strip()
                            if year_text.isdigit() and len(year_text) == 4 and year_text.startswith("20"):
                                year = year_text

                    return "1040", year
    
    return None, None


def id_check(pdf_path: str) -> Optional[str]:
    """
    Check if the PDF is an ID card using Google Document AI
    Returns "ID Card" if detected, None otherwise
    """
    if not GOOGLE_AI_AVAILABLE:
        return None
        
    try:
        # Get environment variables
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        location = os.getenv("GOOGLE_CLOUD_LOCATION")
        processor_id = os.getenv("GOOGLE_CLOUD_PROCESSOR_ID")
        
        if not all([project_id, location, processor_id]):
            print("Google Cloud Document AI credentials not configured")
            return None
        
        # Set `api_endpoint` if you use a location other than "us".
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        
        # Initialize Document AI client.
        client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)
        
        # Build request
        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
        
        # Read the file into memory.
        with open(pdf_path, "rb") as file:
            file_content = file.read()
        
        # Load binary data.
        raw_document = documentai_v1.RawDocument(
            content=file_content,
            mime_type="application/pdf",
        )
        
        # Send a request and get the processed document.
        request = documentai_v1.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document

        # Check if document contains ID-related entities
        if document.entities:
            for entity in document.entities:
                if entity.mention_text:
                    mention_text = entity.mention_text.strip().upper()
                    if mention_text == "PASS":
                        print(f"ID Card detected: {mention_text}")
                        return "ID Card"
                    elif mention_text == "NOT_AN_ID":
                        print(f"Not an ID card: {mention_text}")
                        return None
        return None
        
    except Exception as e:
        print(f"Error in ID check: {str(e)}")
        return None


def handwritten_check(pdf_path: str) -> Optional[str]:
    """Use OpenAI GPT to check if the PDF contains handwritten notes"""
    if not OPENAI_AVAILABLE:
        return None
        
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("OpenAI API key not found in environment variables")
            return None
            
        # Convert PDF to image (first page only for quick check)
        images = convert_from_path(pdf_path, first_page=1, last_page=1) # could be a problem????; just one page
        if not images:
            return None
            
        # Convert image to base64
        img = images[0]
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Create OpenAI client
        client = openai.OpenAI(api_key=openai_api_key)
        
        # Send request to GPT-4 Vision
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini as it's more available
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Look at this document image. Is this a handwritten notes? Answer with just 'YES' if it's mostly handwritten, or 'NO' if it's something else or typed."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip().upper()
        
        if result == "YES":
            print(f"Handwritten document detected via GPT-4 Vision")
            return "Handwritten Notes"
        else:
            print(f"Not primarily handwritten (GPT-4 Vision result: {result})")
            return None
            
    except Exception as e:
        print(f"Error in handwritten check: {str(e)}")
        return None


def classify_document(pdf_path: str) -> Tuple[str, Optional[str]]:
    """
    Main function to classify a PDF document
    Returns a tuple of (document_type, year)
    """
    try:
        # Extract text content
        text_spans, lines = extract_text_from_pdf(pdf_path)
        
        # Analyze content to determine form type
        document_type, year = analyze_form_content(text_spans, lines)
        
        if not document_type:
            document_type = id_check(pdf_path)  # Check ID

        if not document_type:
            document_type = handwritten_check(pdf_path)  # Check Handwritten

        if not document_type:
            document_type = "OTHER"
            
        return document_type, year
        
    except Exception as e:
        print(f"Error processing document: {str(e)}")
        return "OTHER", None


@app.post("/classify")
async def classify_document_endpoint(file: Optional[UploadFile] = File(None)):
    """
    Endpoint to classify a document into document types and extract year
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Create a temporary file to save the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
        
        # Classify the document
        document_type, year = classify_document(temp_path)
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        return {
            "document_type": document_type,
            "year": year,
            "filename": file.filename
        }
        
    except Exception as e:
        # Clean up temporary file if it exists
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Document Classification API",
        "version": "1.0.0",
        "endpoints": {
            "POST /classify": "Classify a PDF document and extract year",
            "GET /docs": "API documentation (Swagger UI)"
        },
        "supported_document_types": [
            "1040", "W2", "1098", "1099", "ID Card", "Handwritten Notes", "OTHER"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)