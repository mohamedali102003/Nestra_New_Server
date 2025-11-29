# routes/projects.py
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Optional
import uuid, os
from pydantic import BaseModel # استدعاء BaseModel
from models import Project, User, IdeaStatus
from database import (
    projects_db, PROJECTS_FILE, users_db, USERS_FILE, ideas_db, save_db, 
    find_project_by_id, find_user_by_email, get_project_tasks_file, get_project_chat_file
)
from utils import add_activity_log
from dependencies import get_current_staff_user

router = APIRouter()

# --- Request Models (نماذج البيانات الجديدة لإصلاح الخطأ) ---
class CreateProjectRequest(BaseModel):
    name: str
    student_emails: List[str]

class ManageStudentsRequest(BaseModel):
    project_id: str
    student_emails: List[str]

class UpdateProjectRequest(BaseModel):
    name: str
# -------------------------------------------------------

@router.get("/projects", response_model=List[Project])
async def get_projects(current_user: User = Depends(get_current_staff_user)):
    my_projects = []
    for p in projects_db:
        if p.assistant_email == current_user.email or p.doctor_email == current_user.email:
            my_projects.append(p)
    
    response_projects: List[Project] = []
    for project in my_projects:
        linked_idea = next((
            idea for idea in ideas_db 
            if idea.linked_project_id == project.id and idea.idea_status != IdeaStatus.available
        ), None)
        
        project_response = Project(
            id=project.id,
            name=project.name,
            assistant_email=project.assistant_email,
            doctor_email=project.doctor_email,
            idea_id=linked_idea.id if linked_idea else None
        )
        response_projects.append(project_response)
            
    return response_projects

# [تم الإصلاح] استقبال JSON بدلاً من Form
@router.post("/projects", response_model=Project)
async def create_project(
    request: CreateProjectRequest,  # استخدام الموديل الجديد
    current_user: User = Depends(get_current_staff_user)
):
    if current_user.user_type != "Assistant":
        raise HTTPException(status_code=403, detail="Only Assistants (TAs) can create teams.")

    # البيانات تأتي جاهزة الآن ولا تحتاج json.loads
    student_emails = request.student_emails
    name = request.name

    if not name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty")
        
    safe_id = "".join(c for c in name.lower().replace(" ", "_") if c.isalnum() or c == '_')
    new_project_id = f"proj_{safe_id}_{uuid.uuid4().hex[:4]}"
    
    if find_project_by_id(new_project_id):
        raise HTTPException(status_code=400, detail="Project ID conflict, try again")

    new_project = Project(
        id=new_project_id, 
        name=name, 
        assistant_email=current_user.email,
        doctor_email=None 
    )
    projects_db.append(new_project)
    
    updated_count = 0
    for email in student_emails: 
        user = find_user_by_email(email)
        if user and user.user_type == "Student" and user.project_id is None:
            user.project_id = new_project_id
            updated_count += 1
            
    save_db(projects_db, PROJECTS_FILE)
    save_db(users_db, USERS_FILE) 
    
    add_activity_log(current_user.email, f"Assistant created project '{name}' ({new_project_id}) and assigned {updated_count} students.")
    return new_project

# [تم الإصلاح] استقبال JSON
@router.put("/projects/{project_id}", response_model=Project)
async def update_project_name(
    project_id: str,
    request: UpdateProjectRequest, # استخدام الموديل
    current_user: User = Depends(get_current_staff_user)
):
    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.email != project.assistant_email and current_user.email != project.doctor_email:
        raise HTTPException(status_code=403, detail="Not authorized to modify this project")
    
    old_name = project.name
    project.name = request.name
    save_db(projects_db, PROJECTS_FILE)
    
    add_activity_log(current_user.email, f"Renamed project '{old_name}' to '{request.name}' (ID: {project_id})")
    return project

@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_staff_user)
):
    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.assistant_email != current_user.email:
        raise HTTPException(status_code=403, detail="Only the creating Assistant can delete this project")

    projects_db.remove(project)
    
    reset_count = 0
    for user in users_db:
        if user.project_id == project_id:
            user.project_id = None
            reset_count += 1
            
    try:
        tasks_file = get_project_tasks_file(project_id)
        if os.path.exists(tasks_file):
            os.remove(tasks_file)
        
        chat_file = get_project_chat_file(project_id)
        if os.path.exists(chat_file):
            os.remove(chat_file)

    except Exception as e:
        add_activity_log("System", f"Failed to delete tasks/chat file for {project_id}: {e}")

    save_db(projects_db, PROJECTS_FILE)
    save_db(users_db, USERS_FILE)
    
    add_activity_log(current_user.email, f"Deleted project '{project.name}'. Reset {reset_count} students to pending.")
    return {"message": "Project deleted and students reset to pending"}

# [تم الإصلاح] استقبال JSON
@router.post("/projects/assign-students")
async def assign_students_to_project(
    request: ManageStudentsRequest, # استخدام الموديل
    current_user: User = Depends(get_current_staff_user)
):
    # البيانات جاهزة
    project_id = request.project_id
    student_emails = request.student_emails

    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if project.assistant_email != current_user.email:
        raise HTTPException(status_code=403, detail="Not authorized to assign students to this project")

    updated_count = 0
    for email in student_emails: 
        user = find_user_by_email(email)
        if user and user.user_type == "Student":
            user.project_id = project_id
            updated_count += 1
            
    save_db(users_db, USERS_FILE)
    add_activity_log(current_user.email, f"Assigned {updated_count} students to project '{project.name}'.")
    return {"message": f"Assigned {updated_count} students successfully."}

# [تم الإصلاح] استقبال JSON
@router.post("/projects/remove-students")
async def remove_students_from_project(
    request: ManageStudentsRequest, # استخدام الموديل
    current_user: User = Depends(get_current_staff_user)
):
    project_id = request.project_id
    student_emails = request.student_emails
    
    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if project.assistant_email != current_user.email:
        raise HTTPException(status_code=403, detail="Not authorized to remove students from this project")

    removed_count = 0
    for email in student_emails: 
        user = find_user_by_email(email)
        if user and user.user_type == "Student" and user.project_id == project_id:
            user.project_id = None
            removed_count += 1
            
    save_db(users_db, USERS_FILE)
    add_activity_log(current_user.email, f"Removed {removed_count} students from project '{project.name}'.")
    return {"message": f"Removed {removed_count} students successfully. They are now pending."}