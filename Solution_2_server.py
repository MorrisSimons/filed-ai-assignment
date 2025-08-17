import base64
import io
import json
import os
import shutil
import tempfile
import time
import magic  # python-magic for content type validation
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import fitz  # PyMuPDF
from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_path
from PIL import Image
import requests

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

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Security and rate limiting configuration
MAX_FILE_SIZE = 4 * 1024 * 1024  # 4MB file size limit
ALLOWED_MIME_TYPES = ["application/pdf"]
RATE_LIMIT_REQUESTS = 100  # requests per 48 hours
RATE_LIMIT_WINDOW = 172800  # 24 hours in seconds
RATE_LIMIT_PER_FILE = 10  # max uploads of same file per 48 hours
RATE_LIMIT_FILE_WINDOW = 172800  # 24 hours in seconds

# In-memory storage for rate limiting (use Redis in production)
request_counts = defaultdict(list)
file_upload_counts = defaultdict(lambda: defaultdict(list))

def validate_file_content(file_content: bytes, filename: str) -> bool:
    """
    Validate file content using magic numbers, not just file extension
    Returns True if file is a valid PDF, False otherwise
    """
    try:
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Check MIME type using magic numbers
        mime_type = magic.from_buffer(file_content, mime=True)
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Expected PDF, got {mime_type}. File: {filename}"
            )
        
        # Additional PDF header validation
        if not file_content.startswith(b'%PDF'):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid PDF file. File does not contain valid PDF header. File: {filename}"
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Error validating file content: {str(e)}"
        )


def send_discord_notification(filename: str, document_type: str, year: Optional[str], file_size_mb: float, success: bool = True, error_msg: str = None):
    """
    Send a Discord webhook notification about document classification results
    """
    try:
        webhook_url = os.getenv("DISCORDWEBHOOK")
        if not webhook_url:
            print("Discord webhook URL not configured")
            return
        
        # Create the message content
        if success:
            color = 0x00ff00  # Green for success
            title = "📄 Document Classified Successfully"
            description = f"**File:** {filename}\n**Type:** {document_type}\n**Year:** {year if year else 'Not detected'}\n**Size:** {file_size_mb} MB"
        else:
            color = 0xff0000  # Red for error
            title = "❌ Document Classification Failed"
            description = f"**File:** {filename}\n**Error:** {error_msg}\n**Size:** {file_size_mb} MB"
        
        # Create Discord embed
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {
                "text": "Document Classification API"
            }
        }
        
        # Send webhook with embed only
        payload = {
            "embeds": [embed]
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 204:
            print(f"Discord notification sent successfully for {filename}")
        else:
            print(f"Failed to send Discord notification: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error sending Discord notification: {str(e)}")


def rate_limit_check(request: Request):
    """Rate limiting middleware function for general requests"""
    client_ip = request.client.host
    current_time = time.time()
    
    # Clean old requests outside the window (older than 24 hours)
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip] 
        if current_time - req_time < RATE_LIMIT_WINDOW
    ]
    
    # Check if client has exceeded rate limit
    if len(request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per day."
        )
    
    # Add current request
    request_counts[client_ip].append(current_time)
    
    return True

def rate_limit_file_check(file_content: bytes, filename: str):
    """Rate limiting per file to prevent rapid uploads of the same file"""
    # Create a hash of the file content for tracking
    import hashlib
    file_hash = hashlib.md5(file_content).hexdigest()
    
    current_time = time.time()
    
    # Clean old uploads outside the window
    file_upload_counts[file_hash] = [
        upload_time for upload_time in file_upload_counts[file_hash]
        if current_time - upload_time < RATE_LIMIT_FILE_WINDOW
    ]
    
    # Check if this file has been uploaded too many times recently
    if len(file_upload_counts[file_hash]) >= RATE_LIMIT_PER_FILE:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for this file. Maximum {RATE_LIMIT_PER_FILE} uploads of the same file per day."
        )
    
    # Add current upload
    file_upload_counts[file_hash].append(current_time)
    
    return True


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
                    
                    if year == "":
                        return "1098", None
                    else:
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

                    if year == "":
                        return "1098", None
                    else:
                        return "1098", year
        
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

                    if year == "":
                        return "1098", None
                    else:
                        return "1098", year
        
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

                    if year == "":
                        return "1098", None
                    else:
                        return "1098", year
    
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
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us")
        processor_id = os.getenv("GOOGLE_CLOUD_PROCESSOR_ID")
        
        # Check if we have JSON credentials
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        
        if not project_id or not processor_id:
            print("Google Cloud Document AI credentials not configured")
            return None
        
        # Set `api_endpoint` if you use a location other than "us".
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        
        # Initialize Document AI client with credentials if available
        if credentials_json:
            import json
            from google.oauth2 import service_account
            
            # Parse the JSON credentials
            credentials_info = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            client = documentai_v1.DocumentProcessorServiceClient(
                credentials=credentials,
                client_options=opts
            )
        else:
            # Use default credentials
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
            
        # Convert PDF to image using PyMuPDF (first page only for quick check)
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            doc.close()
            return None
            
        page = doc.load_page(0)  # Load first page (index 0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Higher resolution for better OCR
        
        # Convert PyMuPDF pixmap to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        doc.close()
        
        if not img:
            return None
            
        # Convert image to base64
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
async def classify_document_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    rate_limit: bool = Depends(rate_limit_check)
):
    """
    Endpoint to classify a document into document types and extract year
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    try:
        # Read file content for validation
        file_content = await file.read()
        
        # Validate file content (size, MIME type, PDF header)
        validate_file_content(file_content, file.filename)
        
        # Rate limit per file to prevent rapid uploads
        rate_limit_file_check(file_content, file.filename)
        
        # Create a temporary file to save the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name
        
        # Classify the document
        document_type, year = classify_document(temp_path)
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        # Send Discord notification for successful classification
        file_size_mb = round(len(file_content) / (1024 * 1024), 2)
        send_discord_notification(file.filename, document_type, year, file_size_mb, success=True)
        
        return {
            "document_type": document_type,
            "year": year,
            "filename": file.filename,
            "file_size_bytes": len(file_content),
            "file_size_mb": file_size_mb
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up temporary file if it exists
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        
        # Send Discord notification for failed classification
        file_size_mb = round(len(file_content) / (1024 * 1024), 2)
        send_discord_notification(file.filename, "ERROR", None, file_size_mb, success=False, error_msg=str(e))
        
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.get("/")
async def root(rate_limit: bool = Depends(rate_limit_check)):
    """Root endpoint with API information"""
    return {
        "message": "Document Classification API",
        "version": "1.0.0",
        "endpoints": {
            "POST /classify": "Classify a PDF document and extract year",
            "GET /drop": "Drag and drop file upload interface",
            "GET /docs": "API documentation (Swagger UI)"
        },
        "supported_document_types": [
            "1040", "W2", "1098", "1099", "ID Card", "Handwritten Notes", "OTHER"
        ],
        "security_features": {
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "allowed_mime_types": ALLOWED_MIME_TYPES,
            "rate_limit_requests_per_day": RATE_LIMIT_REQUESTS,
            "rate_limit_file_uploads_per_day": RATE_LIMIT_PER_FILE,
            "content_validation": "PDF header validation + MIME type checking"
        }
    }

@app.get("/drop", response_class=HTMLResponse)
async def drop_interface(request: Request):
    """Serve the drag-and-drop file upload interface"""
    return templates.TemplateResponse("drop.html", {"request": request})




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)