# routes/users.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from models import UserPublic, User, TeamMember
from database import users_db, find_project_by_id
from dependencies import get_current_staff_user, get_current_user

router = APIRouter()

# --- [إضافة جديدة] Endpoint لجلب بيانات المستخدم الحالي ---
@router.get("/users/me", response_model=UserPublic)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    يسترجع بيانات المستخدم الحالي (بما في ذلك project_id) بناءً على التوكن.
    يستخدم هذا الرابط في التطبيق عند الفتح (Splash Screen) لتوجيه الطالب.
    """
    return current_user
# ---------------------------------------------------------

@router.get("/users/pending", response_model=List[UserPublic])
async def get_pending_students(current_user: User = Depends(get_current_staff_user)):
    pending = [
        UserPublic(**u.model_dump()) for u in users_db 
        if u.user_type == "Student" and u.project_id is None
    ]
    return pending

@router.get("/projects/{project_id}/students", response_model=List[UserPublic])
async def get_students_in_project(
    project_id: str,
    current_user: User = Depends(get_current_staff_user)
):
    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if current_user.email != project.assistant_email and current_user.email != project.doctor_email:
        raise HTTPException(status_code=403, detail="Not authorized to view students for this project")

    students_in_project = [
        UserPublic(**u.model_dump()) for u in users_db 
        if u.user_type == "Student" and u.project_id == project_id
    ]
    return students_in_project

@router.get("/projects/{project_id}/team-members", response_model=List[TeamMember])
async def get_project_team_members(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    is_authorized = False
    if current_user.user_type == "Student" and current_user.project_id == project_id:
        is_authorized = True
    elif current_user.user_type in ["Assistant", "Doctor", "Staff"]:
        if current_user.email == project.assistant_email or current_user.email == project.doctor_email:
            is_authorized = True
            
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Not authorized to view this team")
    
    team_members = []
    for user in users_db:
        if user.user_type == "Student" and user.project_id == project_id:
            team_members.append(TeamMember(
                name=user.name, 
                email=user.email,
                tracks=user.tracks
            ))
    return team_members