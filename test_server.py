#!/usr/bin/env python3
"""
Test script for the document classification server
"""

import os
from pathlib import Path

import requests


def test_classification_endpoint():
    """Test the classification endpoint with sample PDFs"""
    
    # Server URL
    base_url = "https://filed.morrissimons.com/"
    
    # Test the root endpoint first
    try:
        response = requests.get(f"{base_url}/")
        print("✓ Root endpoint working")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"✗ Root endpoint failed: {e}")
        return
    
    # Test with sample PDFs
    samples_dir = Path("samples")
    if not samples_dir.exists():
        print("✗ Samples directory not found")
        return
    
    pdf_files = list(samples_dir.glob("*.pdf"))
    if not pdf_files:
        print("✗ No PDF files found in samples directory")
        return
    
    print(f"\nFound {len(pdf_files)} PDF files to test")
    
    for pdf_file in pdf_files:
        print(f"\n--- Testing {pdf_file.name} ---")
        
        try:
            with open(pdf_file, 'rb') as f:
                files = {'file': (pdf_file.name, f, 'application/pdf')}
                
                response = requests.post(f"{base_url}/classify", files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ Success: {result}")
                else:
                    print(f"✗ Error {response.status_code}: {response.text}")
                    
        except Exception as e:
            print(f"✗ Failed to test {pdf_file.name}: {e}")

if __name__ == "__main__":
    print("Testing Document Classification Server")
    print("Make sure the server is running on http://localhost:8000")
    print("=" * 50)
    
    test_classification_endpoint()
