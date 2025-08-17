from typing import Optional

from fastapi import FastAPI, File, UploadFile

app = FastAPI()


@app.post("/classify")
async def schedule_classify_task(file: Optional[UploadFile] = File(None)):
    """Endpoint to classify a document into "w2", "1099int", etc"""

    return {"document_type": "NOT IMPLEMENTED", "year": "NOT IMPLEMENTED"}