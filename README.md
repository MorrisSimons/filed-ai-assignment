# AI Assignment
![top language](https://img.shields.io/github/languages/top/gpt-null/template)
![code size](https://img.shields.io/github/languages/code-size/gpt-null/template)
![last commit](https://img.shields.io/github/last-commit/gpt-null/template)
![issues](https://img.shields.io/github/issues/gpt-null/template)
![contributors](https://img.shields.io/github/contributors/gpt-null/template)
![License](https://img.shields.io/github/license/gpt-null/template)

Hi there 👋,

This is the take home assignment for Filed's AI engineer position. 
We recommend spending no more than 5–6 hours on it — we're not looking for perfection, but rather how you think and approach problems.

You can clone this repository into your github account and then complete it.

There is no set time to complete the assignment, but faster you complete higher the chances that the position is not filled by someone else. 

Once you're done, just reply back to the email you received with the link to your completed github repo and we'll get back to you shortly after.

PS: If its a private repo - please add atul@filed.com as the outside collaborator


## Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager

## Setup


0. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Clone this repo

2. Install dependencies using uv:
```bash
uv sync
```

3. Run the server:
```bash
uv run uvicorn Solution_2_server:app --host 0.0.0.0 --port 8000 --reload
```

4. You can now open the docs at http://0.0.0.0:8000/docs and run the endpoints

## API Endpoints

### Docs

http://0.0.0.0:8000/docs


### Document Classification
- `POST /classify` - Submit a document to be classified
- `GET /` - API information and supported document types

## Task 

Your task is to complete the /classify endpoint
The endpoint should 

1. Take in a PDF file as an input - Use the sample documents provided under sample directory
2. Classify the PDF as one of 

- "1040"
- "W2"
- "1099"
- "ID Card"
- "Handwritten note"
- "OTHER"

3. Also parse the year the document was issued

# My solution explained

## TL;DR
- Uses **PyMuPDF** to extract text with detailed metadata **(font, fontstyle color and location)**
- Google cloud document ai for id card detection
- GPT for handwritten note detection
- other documents are classified as OTHER

---

I've implemented a comprehensive document classification system that combines multiple approaches to accurately identify document types and extract years. Here's how it works:


## How to test it
1. Get the requirements from the requirements.txt file
2. Get a openai api_key and add it to the .env file
3. Get a google cloud api_key and add it to the .env file: set up a processor for Identity Document Proofing and get the processor details
4. Run solution_2_server.py
5. Run test_server.py

- Mabye later i will spin up a vercel app and deploy it there so in can be used by anyone.

## Classification Methods

### 1. Form-Based Classification (Primary Method)
Uses **PyMuPDF** to extract text with detailed metadata including:
- Font names and sizes
- Text positioning (bounding boxes)
- Text content and structure

#### Tax documents strategy
So for the tax documents we dont use any AI only mining the PDFs as these files are pretty standard and have text written in them. This is better than any AI model as this is 100% accurate and fast. Also low cost.

---

### 2. AI-Powered Classification 
- **ID Card Detection**: Uses Google Cloud Document AI to identify ID cards based on document entities
- **Handwritten Note Detection**: Leverages OpenAI GPT-4 Vision to analyze document images and detect handwritten content


#### ID card strategy
Here i went with google cloud document ai as it is fast and easy to use and very good, we can also scale up from here to check if ids are valid etc. We could also use Microsofts azure document intelligence as they have some edge soltions. Downside of this is that this is not on prem solution but its good and fast. Also it cost money.


#### Handwritten strategy
I used GPT-4 Vision for handwritten note detection because traditional text extraction and rule-based methods are unreliable for distinguishing handwritten content from typed or printed text, especially in scanned or photographed documents. Handwriting can vary greatly in style, structure, and legibility, making it difficult to detect using only font or layout analysis.

In summary, LLMS are good and fast to deploy for this task but can cost a bit and is not trained specifically for this task. you could train a model from scratch to classify this as not handwritten or handwritten.


---



### 3. Fallback Classification
Documents that don't match any known patterns are classified as "OTHER"


## Testing and Validation

The solution includes a comprehensive test suite (`test_server.py`) that:
- Tests all sample PDFs automatically


**Test Results Summary:**
- ✅ **f1040--2022.pdf** → "1040" with year "2022"
- ✅ **fw2.pdf** → "W2" with year "2024"  
- ✅ **f1098.pdf** → "1098" with year "2024"
- ✅ **f1099div.pdf** → "1099" with year extracted
- ✅ **f1099int.pdf** → "1099" with year extracted
- ✅ **f1099div-2031.pdf** → "1099" with year "2031"
- ✅ **handwritten.pdf** → "Handwritten Notes"
- ✅ **idcard.pdf** → "ID Card"
- ✅ **Morris_Simons_CV_EN.pdf** → "OTHER"



### General notes

- for the tax documents i like the solution, you can mix around with the details to make it better.

- for the ID card you can use a deeplearning model or mabye azure document intelligence api for ID to check if valid or not.

- If i understood the assigment correctly the handwritten check is what we wanted and not to check if its a receipt or invoice etc.