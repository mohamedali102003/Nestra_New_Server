# utils.py
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from fastapi import HTTPException
from models import ActivityLog, User, IdeaStatus, Task
from database import activity_log_db, ACTIVITY_LOG_FILE, save_db, find_user_by_email, find_project_by_id, ideas_db

# إعدادات JWT
SECRET_KEY = "GH9283hHJS_7267ksA88Ajshh_7766HHHs#jsa"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def add_activity_log(user_identifier: str, action: str):
    user = find_user_by_email(user_identifier)
    user_name = user.name if user else user_identifier
    new_log = ActivityLog(
        id=str(uuid.uuid4()),
        user=user_name,
        action=action,
        timestamp=datetime.utcnow().isoformat()
    )
    activity_log_db.insert(0, new_log)
    save_db(activity_log_db, ACTIVITY_LOG_FILE)

def check_chat_permissions(user: User, project_id: str):
    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. الطالب
    if user.user_type == "Student":
        if user.project_id != project_id:
             raise HTTPException(status_code=403, detail="Not authorized. You are not in this team.")
        return True

    # 2. الطاقم
    if user.user_type in ["Assistant", "Doctor", "Staff"]:
        if project.assistant_email == user.email:
            return True
        
        if project.doctor_email == user.email:
            return True
        
        if user.user_type == "Doctor":
            relevant_idea = next((
                i for i in ideas_db 
                if i.linked_project_id == project_id 
                and i.staff_email == user.email 
                and i.idea_status == IdeaStatus.in_discussion
            ), None)
            if relevant_idea:
                return True

        raise HTTPException(status_code=403, detail="You do not have access to this team's chat.")
    return False