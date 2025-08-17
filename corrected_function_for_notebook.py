# COPY THIS FUNCTION INTO YOUR NOTEBOOK - IT INCLUDES BBOX SUPPORT

def extract_text_from_pdf_corrected(pdf_path: str) -> List[Dict]:
    """
    Extract text content from a PDF with bbox coordinates for year detection
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
                                "bbox": span.get("bbox", None),  # CRITICAL: Include bbox for coordinate-based detection
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

# ALSO UPDATE YOUR classify_and_copy_pdfs FUNCTION TO USE THIS:
def classify_and_copy_pdfs_corrected(samples_dir: str = "samples", output_base_dir: str = "classified_pdfs"):
    """
    Main function to classify PDFs and copy them to appropriate folders using corrected function
    """
    # Create output base directory
    os.makedirs(output_base_dir, exist_ok=True)
    
    # Process each PDF in the samples directory
    for filename in os.listdir(samples_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(samples_dir, filename)
            print(f"\nProcessing: {filename}")
            
            try:
                # Extract text content using corrected function with bbox
                text_spans, lines = extract_text_from_pdf_corrected(pdf_path)
                
                # Analyze content to determine form type
                document_type, year = analyze_form_content(text_spans, lines)
                
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

# INSTRUCTIONS:
# 1. Copy the extract_text_from_pdf_corrected function to your notebook
# 2. Replace your classify_and_copy_pdfs function with classify_and_copy_pdfs_corrected
# 3. Or just change the line in your existing function from:
#    text_spans, lines = extract_text_from_pdf(pdf_path)
#    to:
#    text_spans, lines = extract_text_from_pdf_corrected(pdf_path)
