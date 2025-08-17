#!/usr/bin/env python3
"""
Test script to verify the new security features:
- File size limits
- Content type validation
- Rate limiting per file
"""

import requests
import time
import os
from pathlib import Path

# Server configuration
BASE_URL = "http://localhost:8000"
TEST_PDF_PATH = "samples/f1040--2022.pdf"

def test_file_size_limit():
    """Test file size limit enforcement"""
    print("Testing file size limit...")
    
    # Create a large file (over 10MB)
    large_file_path = "test_large_file.pdf"
    with open(large_file_path, "wb") as f:
        f.write(b"0" * (11 * 1024 * 1024))  # 11MB file
    
    try:
        with open(large_file_path, "rb") as f:
            files = {"file": ("large_file.pdf", f, "application/pdf")}
            response = requests.post(f"{BASE_URL}/classify", files=files)
        
        if response.status_code == 413:
            print("✅ File size limit working correctly")
        else:
            print(f"❌ File size limit not working. Status: {response.status_code}")
            print(f"Response: {response.text}")
    
    finally:
        # Clean up
        if os.path.exists(large_file_path):
            os.remove(large_file_path)

def test_content_type_validation():
    """Test content type validation"""
    print("Testing content type validation...")
    
    # Test with a text file renamed to .pdf
    fake_pdf_path = "test_fake.pdf"
    with open(fake_pdf_path, "w") as f:
        f.write("This is not a PDF file")
    
    try:
        with open(fake_pdf_path, "rb") as f:
            files = {"file": ("fake.pdf", f, "application/pdf")}
            response = requests.post(f"{BASE_URL}/classify", files=files)
        
        if response.status_code == 400:
            print("✅ Content type validation working correctly")
        else:
            print(f"❌ Content type validation not working. Status: {response.status_code}")
            print(f"Response: {response.text}")
    
    finally:
        # Clean up
        if os.path.exists(fake_pdf_path):
            os.remove(fake_pdf_path)

def test_rate_limiting_per_file():
    """Test rate limiting per file"""
    print("Testing rate limiting per file...")
    
    if not os.path.exists(TEST_PDF_PATH):
        print(f"❌ Test PDF not found at {TEST_PDF_PATH}")
        return
    
    # Upload the same file multiple times to trigger rate limiting
    for i in range(6):  # Try 6 times (limit is 5 per day)
        with open(TEST_PDF_PATH, "rb") as f:
            files = {"file": (f"test_{i}.pdf", f, "application/pdf")}
            response = requests.post(f"{BASE_URL}/classify", files=files)
        
        print(f"Upload {i+1}: Status {response.status_code}")
        
        if response.status_code == 429:
            print("✅ Rate limiting per file working correctly")
            break
        elif response.status_code == 200:
            print(f"Upload {i+1} successful")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            print(f"Response: {response.text}")
            break
        
        time.sleep(0.1)  # Small delay between uploads

def test_valid_pdf():
    """Test that valid PDFs still work"""
    print("Testing valid PDF upload...")
    
    if not os.path.exists(TEST_PDF_PATH):
        print(f"❌ Test PDF not found at {TEST_PDF_PATH}")
        return
    
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"file": ("valid.pdf", f, "application/pdf")}
        response = requests.post(f"{BASE_URL}/classify", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Valid PDF upload working correctly")
        print(f"   Document type: {result.get('document_type')}")
        print(f"   Year: {result.get('year')}")
        print(f"   File size: {result.get('file_size_mb')} MB")
    else:
        print(f"❌ Valid PDF upload failed. Status: {response.status_code}")
        print(f"Response: {response.text}")

def test_api_info():
    """Test API info endpoint to see security features"""
    print("Testing API info endpoint...")
    
    response = requests.get(f"{BASE_URL}/")
    
    if response.status_code == 200:
        info = response.json()
        print("✅ API info endpoint working")
        print(f"   Version: {info.get('version')}")
        
        security = info.get('security_features', {})
        if security:
            print("   Security features:")
            print(f"     Max file size: {security.get('max_file_size_mb')} MB")
            print(f"     Rate limit requests/day: {security.get('rate_limit_requests_per_day')}")
            print(f"     Rate limit file uploads/day: {security.get('rate_limit_file_uploads_per_day')}")
            print(f"     Content validation: {security.get('content_validation')}")
        else:
            print("   ❌ No security features info found")
    else:
        print(f"❌ API info endpoint failed. Status: {response.status_code}")

def main():
    """Run all tests"""
    print("🧪 Testing Document Classification API Security Features")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ Server not responding properly")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on localhost:8000")
        return
    
    print("✅ Server is running")
    print()
    
    # Run tests
    test_api_info()
    print()
    
    test_valid_pdf()
    print()
    
    test_file_size_limit()
    print()
    
    test_content_type_validation()
    print()
    
    test_rate_limiting_per_file()
    print()
    
    print("🎯 Security feature testing completed!")

if __name__ == "__main__":
    main()
