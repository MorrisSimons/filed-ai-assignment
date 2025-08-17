#!/usr/bin/env python3
"""
PDF Title Extraction using PyMuPDF (fitz)
Extracts only titles/headers from PDF files
"""

import os
from pathlib import Path

import fitz  # PyMuPDF


def extract_pdf_titles(pdf_path):
    """Extract titles/headers from a PDF file using fitz"""
    try:
        doc = fitz.open(pdf_path)
        
        # Get titles from first page (usually contains the main title)
        titles = []
        if len(doc) > 0:
            page = doc.load_page(0)  # First page
            text_blocks = page.get_text("dict")
            
            for block in text_blocks["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            font_size = span["size"]
                            
                            # Consider larger text as potential titles
                            if font_size > 14 and text and len(text) > 2:
                                titles.append({
                                    'text': text,
                                    'size': font_size
                                })
        
        doc.close()
        return titles
        
    except Exception as e:
        return f"Error: {e}"

def main():
    """Process all PDFs in samples folder and show titles only"""
    samples_dir = Path('samples')
    
    if not samples_dir.exists():
        print("Samples folder not found!")
        return
    
    pdf_files = list(samples_dir.glob('*.pdf'))
    
    if not pdf_files:
        print("No PDF files found!")
        return
    
    print(f"📚 PDF Titles from {len(pdf_files)} files:")
    print("=" * 50)
    
    for pdf_file in pdf_files:
        print(f"\n📄 {pdf_file.name}")
        print("-" * 30)
        
        # Extract titles
        titles = extract_pdf_titles(pdf_file)
        
        if isinstance(titles, str) and titles.startswith("Error:"):
            print(f"❌ {titles}")
        elif titles:
            print("🔤 Titles found:")
            for title in titles:
                print(f"  • {title['text']} (Size: {title['size']})")
        else:
            print("📝 No titles detected")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()
