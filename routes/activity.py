# routes/activity.py
from fastapi import APIRouter, Depends, UploadFile, Form, Query
from typing import List
import os, uuid
import whisper
from models import ActivityLog, User
from database import activity_log_db
from dependencies import get_current_staff_user
from utils import add_activity_log

router = APIRouter()

# تحميل موديل Whisper مرة واحدة (ملاحظة: قد يأخذ وقتًا عند بدء التشغيل)
model = whisper.load_model("tiny")

@router.get("/activity-log", response_model=List[ActivityLog])
async def get_activity_log(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_staff_user)
):
    return activity_log_db[:limit]

@router.post("/transcribe")
async def transcribe(file: UploadFile, language: str = Form(...)):
    temp_path = f"temp_{uuid.uuid4().hex}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    try:
        result = model.transcribe(temp_path, language=language.lower())
        text = result.get("text", "")
        summary = text[:200] + "..." if len(text) > 200 else text
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
    add_activity_log("System (Transcribe)", f"Transcribed file: {file.filename} (Language: {language})")
    return {"transcript": text, "summary": summary}