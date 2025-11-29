# routes/auth.py
from fastapi import APIRouter, Form, HTTPException, Depends
from typing import Optional
from datetime import timedelta
from models import User, UserPublic, UserProfileUpdate, IdeaStatus
from database import users_db, USERS_FILE, save_db, find_user_by_email, find_project_by_id, ideas_db
from utils import hash_password, create_access_token, add_activity_log, ACCESS_TOKEN_EXPIRE_MINUTES
from dependencies import get_current_user

router = APIRouter()

@router.post("/register")
async def register_user(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    user_type: str = Form(...)
):
    if find_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=name,
        email=email,
        password=hash_password(password),
        user_type=user_type,
        project_id=None 
    )
    users_db.append(new_user)
    save_db(users_db, USERS_FILE)
    add_activity_log(new_user.email, f"New user registered: {new_user.name} (Type: {new_user.user_type})")
    return {"message": "Registration successful"}

@router.post("/login")
async def login_user(
    email: str = Form(...),
    password: str = Form(...),
    user_type: str = Form(...)
):
    user = find_user_by_email(email)
    hashed = hash_password(password)
    
    if not user or user.password != hashed or user.user_type != user_type:
        add_activity_log(email, f"Failed login attempt for email: {email} (Type: {user_type})")
        if user and user.password == hashed and user.user_type != user_type:
            raise HTTPException(status_code=401, detail="Invalid user type selected")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    project_name: Optional[str] = None
    idea_id: Optional[str] = None
    
    if user.project_id:
        project = find_project_by_id(user.project_id)
        if project:
            project_name = project.name
        
        linked_idea = next((
            idea for idea in ideas_db 
            if idea.linked_project_id == user.project_id and idea.idea_status != IdeaStatus.available
        ), None)
        
        if linked_idea:
            idea_id = linked_idea.id

    access_token = create_access_token(
        data={"sub": user.email, "user_type": user.user_type, "project_id": user.project_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    add_activity_log(user.email, f"User logged in: {user.name}")
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "name": user.name,
        "project_id": user.project_id,
        "project_name": project_name, 
        "idea_id": idea_id            
    }

@router.put("/users/profile", response_model=UserPublic)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user)
):
    user_index = next((i for i, u in enumerate(users_db) if u.email == current_user.email), None)
    
    if user_index is None:
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[user_index]
    user.tracks = profile_data.tracks
    user.skills = profile_data.skills
    user.github_link = profile_data.github_link
    user.meeting_preference = profile_data.meeting_preference
    user.daily_hours = profile_data.daily_hours
    user.readiness_status = profile_data.readiness_status
    
    save_db(users_db, USERS_FILE)
    add_activity_log(current_user.email, f"Updated profile preferences & skills.")
    
    return UserPublic(**user.model_dump())

# ---------------------------------------------------------
# [جديد] نقطة النهاية لتغيير كلمة المرور
# ---------------------------------------------------------
@router.put("/change-password")
async def change_password(
    email: str = Form(...),
    old_password: str = Form(...),
    new_password: str = Form(...),
    user_type: str = Form(...)
):
    # 1. البحث عن المستخدم
    user = find_user_by_email(email)
    
    # 2. التحقق من وجود المستخدم ونوع الحساب
    if not user or user.user_type != user_type:
        # رسالة غامضة قليلاً لأسباب أمنية
        raise HTTPException(status_code=404, detail="User not found or incorrect credentials")
    
    # 3. التحقق من كلمة المرور القديمة
    hashed_old = hash_password(old_password)
    if user.password != hashed_old:
        add_activity_log(email, "Failed password change attempt (Wrong old password)")
        raise HTTPException(status_code=401, detail="Incorrect old password")
    
    # 4. تحديث كلمة المرور بالجديدة (بعد التشفير)
    user.password = hash_password(new_password)
    
    # 5. حفظ التغييرات في قاعدة البيانات
    save_db(users_db, USERS_FILE)
    
    add_activity_log(email, "Password changed successfully")
    
    return {"message": "Password updated successfully. Please login with new password."}