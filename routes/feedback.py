# routes/feedback.py
import shutil
import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException

from models import Feedback, User
from database import load_db, save_db, DATA_FOLDER, UPLOADS_FOLDER
from dependencies import get_current_user
from utils import add_activity_log

router = APIRouter(prefix="/feedback", tags=["Feedback"])

FEEDBACK_FILE = os.path.join(DATA_FOLDER, "feedback.json")
FEEDBACK_UPLOAD_DIR = os.path.join(UPLOADS_FOLDER, "feedback")
os.makedirs(FEEDBACK_UPLOAD_DIR, exist_ok=True)

# تحميل قاعدة بيانات الشكاوى
feedback_db: List[Feedback] = []
try:
    import json
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            feedback_db = [Feedback(**item) for item in data]
except:
    feedback_db = []

def save_feedback_db():
    save_db(feedback_db, FEEDBACK_FILE) # استخدام دالة الحفظ الموجودة في database.py

@router.post("", response_model=Feedback)
async def submit_feedback(
    description: str = Form(...),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    screenshot_path = None

    # 1. حفظ الصورة إن وجدت
    if file:
        safe_filename = f"{uuid.uuid4().hex[:8]}_{file.filename.replace(' ', '_')}"
        file_path = os.path.join(FEEDBACK_UPLOAD_DIR, safe_filename)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            screenshot_path = file_path
        except Exception as e:
            print(f"Error saving screenshot: {e}")

    # 2. إنشاء سجل الشكوى
    new_feedback = Feedback(
        id=str(uuid.uuid4()),
        user_email=current_user.email,
        user_name=current_user.name,
        description=description,
        screenshot_url=screenshot_path,
        timestamp=datetime.utcnow().isoformat()
    )

    feedback_db.insert(0, new_feedback)
    save_feedback_db()
    
    # 3. تسجيل النشاط (اختياري، يفضل عدم إزعاج السجل العام بالشكاوى الشخصية)
    # add_activity_log(current_user.email, "Submitted a feedback/issue report.")

    return new_feedback

@router.get("", response_model=List[Feedback])
async def get_all_feedback(current_user: User = Depends(get_current_user)):
    # السماح فقط للمسؤولين برؤية الشكاوى
    if current_user.user_type not in ["Staff", "System User", "Doctor", "Assistant"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return feedback_db