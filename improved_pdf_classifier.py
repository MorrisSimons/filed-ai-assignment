#!/usr/bin/env python3
"""
Improved PDF Classifier with Better Year Extraction
Uses box coordinates with margins for more robust year detection
"""

import os
import shutil
from typing import Dict, List, Optional

import fitz


def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extract text content from a PDF using the same method as before
    Returns a list of text spans with their properties and also complete lines
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
                                "bbox": span.get("bbox", None),  # Include bbox for coordinate-based detection
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

def analyze_form_content_improved(text_spans: List[Dict], lines: List[Dict]) -> Optional[str]:
    """
    Improved analyze_form_content function with better year extraction using box coordinates and margins
    """
    for line in lines:
        text = line["text"].strip()
        
        # Check for various form types with their specific font requirements
        if text == "Form 1098":
            if len(line["spans"]) == 2 and line["spans"][0]["text"] == "Form" and line["spans"][1]["text"] == "1098":
                form_span, num_span = line["spans"][0], line["spans"][1]
                if (abs(form_span["font_size"] - 7.0) <= 2 and form_span["font_name"] == "HelveticaNeueLTStd-Roman" and
                    abs(num_span["font_size"] - 14.0) <= 2 and num_span["font_name"] == "HelveticaNeueLTStd-Bd"):

                    # Get year from the document by looking for a span with text "24" in the expected box area, font, and size
                    year = ""
                    # The expected box for the year "24" is approximately:
                    # [437.46307373046875, 98.37499237060547, 444.1362609863281, 104.37500762939453]
                    year_bbox = [437.46, 98.37, 444.14, 104.38]
                    # Add margin to make detection more robust (increased from 1.5 to 3.0)
                    margin = 3.0
                    
                    for l in lines:
                        for s in l.get("spans", []):
                            bbox = s.get("bbox", None)
                            # First, check if bbox is available and matches the expected area with margin
                            if bbox and all(abs(b - e) < margin for b, e in zip(bbox, year_bbox)):
                                # Now check if the text is a 2-digit year (e.g., "24", "21", "22"), font is Helvetica, and size is about 6
                                text_val = s.get("text", "")
                                if (
                                    text_val.isdigit() and len(text_val) == 2
                                    and abs(s.get("font_size", 0) - 6.0) < 2  # Increased tolerance from 1 to 2
                                    and "Helvetica" in s.get("font_name", "")  # More flexible font matching
                                ):
                                    # Add millennium prefix
                                    year = "20" + text_val
                                    break
                        if year:
                            break
                    print(f"this is the  Year: {year}")
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
                    
                    # Method 2: Look for 2-digit years and convert
                    if not year:
                        for l in lines:
                            for s in l.get("spans", []):
                                text_val = s.get("text", "").strip()
                                if text_val.isdigit() and len(text_val) == 2 and text_val.startswith("2"):
                                    year = "20" + text_val
                                    break
                            if year:
                                break

                    return "1099", year
        
        elif text == "Form W-2":
            if len(line["spans"]) == 2 and line["spans"][0]["text"] == "Form" and line["spans"][1]["text"] == "W-2":
                form_span, num_span = line["spans"][0], line["spans"][1]
                if (abs(form_span["font_size"] - 7.0) <= 2 and form_span["font_name"] == "HelveticaNeueLTStd-Bd" and
                    abs(num_span["font_size"] - 24.0) <= 2 and num_span["font_name"] == "HelveticaNeueLTStd-BlkCn"):

                    # Get year from the document - look for year in various formats
                    year = ""
                    
                    # Method 1: Look for 4-digit years with large font size
                    for l in lines:
                        for s in l.get("spans", []):
                            text_val = s.get("text", "").strip()
                            if (text_val.isdigit() and len(text_val) == 4 and text_val.startswith("20") and
                                s.get("font_size", 0) > 15):  # Large font size
                                year = text_val
                                break
                        if year:
                            break
                    
                    # Method 2: Look for any 4-digit year
                    if not year:
                        for l in lines:
                            for s in l.get("spans", []):
                                text_val = s.get("text", "").strip()
                                if text_val.isdigit() and len(text_val) == 4 and text_val.startswith("20"):
                                    year = text_val
                                    break
                            if year:
                                break

                    return "W2", year
        
        elif text.startswith("Form 1040"):
            if len(line["spans"]) >= 2 and line["spans"][0]["text"] == "Form" and line["spans"][1]["text"] == "1040":
                form_span, num_span = line["spans"][0], line["spans"][1]
                if (abs(form_span["font_size"] - 6.0) <= 2 and form_span["font_name"] == "HelveticaNeueLTStd-Roman" and
                    abs(num_span["font_size"] - 9.0) <= 2 and num_span["font_name"] == "HelveticaNeueLTStd-Bd"):

                    # Get year from the document - look for year in various formats
                    year = ""
                    
                    # Method 1: Look for year in the form title (e.g., "Form 1040 (2022)")
                    line_text = line["text"]
                    if "(" in line_text and ")" in line_text:
                        # Extract year from parentheses
                        start = line_text.find("(") + 1
                        end = line_text.find(")")
                        if start < end:
                            year_text = line_text[start:end].strip()
                            if year_text.isdigit() and len(year_text) == 4 and year_text.startswith("20"):
                                year = year_text
                    
                    # Method 2: Look for 4-digit years in the document
                    if not year:
                        for l in lines:
                            for s in l.get("spans", []):
                                text_val = s.get("text", "").strip()
                                if text_val.isdigit() and len(text_val) == 4 and text_val.startswith("20"):
                                    year = text_val
                                    break
                            if year:
                                break
                    
                    # Method 3: Look for 2-digit years and convert
                    if not year:
                        for l in lines:
                            for s in l.get("spans", []):
                                text_val = s.get("text", "").strip()
                                if text_val.isdigit() and len(text_val) == 2 and text_val.startswith("2"):
                                    year = "20" + text_val
                                    break
                            if year:
                                break

                    return "1040", year
    
    return None, None


def classify_and_copy_pdfs_improved(samples_dir: str = "samples", output_base_dir: str = "classified_pdfs"):
    """
    Main function to classify PDFs and copy them to appropriate folders using improved year extraction
    """
    # Create output base directory
    os.makedirs(output_base_dir, exist_ok=True)
    
    # Process each PDF in the samples directory
    for filename in os.listdir(samples_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(samples_dir, filename)
            print(f"\nProcessing: {filename}")
            
            try:
                # Extract text content
                text_spans, lines = extract_text_from_pdf(pdf_path)
                
                # Analyze content to determine form type using improved function
                document_type, year = analyze_form_content_improved(text_spans, lines)
                
                if document_type:
                    # Create form-specific directory
                    form_dir = os.path.join(output_base_dir, document_type)
                    os.makedirs(form_dir, exist_ok=True)
                    
                    # Copy PDF to form directory
                    destination = os.path.join(form_dir, filename)
                    shutil.copy2(pdf_path, destination)
                    print(f"✓ Copied {filename} to {form_dir}/")
                    print(f"✓ Year: {year}")
                else:
                    # If no form type detected, put in "unknown" folder
                    unknown_dir = os.path.join(output_base_dir, "Other")
                    os.makedirs(unknown_dir, exist_ok=True)
                    destination = os.path.join(unknown_dir, filename)
                    shutil.copy2(pdf_path, destination)
                    print(f"? No form type detected for {filename}, copied to Other/")
                    
            except Exception as e:
                print(f"✗ Error processing {filename}: {str(e)}")
    
    print(f"\nClassification complete! Check the '{output_base_dir}' directory for results.")


if __name__ == "__main__":
    print("Testing improved year extraction with box coordinates and margins...")
    classify_and_copy_pdfs_improved()
