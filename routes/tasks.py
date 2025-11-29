# routes/tasks.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
# [تعديل] يجب استيراد TaskStatus لاستخدامه في التحقق من الحالة
from models import Task, TokenData, User, TaskStatus 
# [تعديل] أضفنا users_db, find_project_by_id, projects_db لـ logic الإشعار
from database import load_db, save_db, find_project_by_id, get_project_tasks_file, users_db, projects_db
from utils import add_activity_log
from dependencies import get_current_token_data, get_current_user
# [إضافة] استيراد المانجر للـ WebSockets
from routes.realtime import manager

router = APIRouter()

def persist_tasks_and_log(tasks_db: List[Task], project_file: str, action: str, user_email: str, task: Optional[Task] = None):
    save_db(tasks_db, project_file)
    project_id = project_file.split("tasks_")[1].replace('.json', '') # simple extraction
    if task:
        add_activity_log(user_email, f"{action} in '{project_id}': '{task.title}' (Status: {getattr(task.status, 'value', '')})")
    else:
        add_activity_log(user_email, f"{action} in '{project_id}'")

@router.get("/tasks", response_model=List[Task])
async def get_tasks(
    project_id: Optional[str] = Query(None),
    token_data: TokenData = Depends(get_current_token_data) 
):
    target_project_id = None
    
    if token_data.user_type == "Student":
        target_project_id = token_data.project_id
        if not target_project_id:
            raise HTTPException(status_code=403, detail="Student token missing project_id or not assigned")
    
    elif token_data.user_type in ["Assistant", "Doctor", "Staff"]:
        target_project_id = project_id
        if not target_project_id:
            raise HTTPException(status_code=400, detail="Staff must provide a project_id query parameter")
        
        project = find_project_by_id(target_project_id)
        if not project or (project.assistant_email != token_data.email and project.doctor_email != token_data.email):
             raise HTTPException(status_code=403, detail="Not authorized to view this project's tasks")
    
    else:
         raise HTTPException(status_code=403, detail="User type cannot access tasks")

    project_file = get_project_tasks_file(target_project_id)
    project_tasks_db = load_db(Task, project_file)
    return project_tasks_db

@router.post("/tasks", response_model=Task)
async def add_or_update_task(
    task: Task, 
    project_id_query: Optional[str] = Query(None, alias="project_id"),
    token_data: TokenData = Depends(get_current_token_data),
    current_user: User = Depends(get_current_user)
):
    target_project_id = None
    
    if token_data.user_type == "Student":
        target_project_id = token_data.project_id
    
    elif token_data.user_type in ["Assistant", "Doctor", "Staff"]:
        target_project_id = project_id_query
        if not target_project_id:
            raise HTTPException(status_code=400, detail="Staff must provide a project_id query parameter")

        project_check = find_project_by_id(target_project_id)
        if not project_check or (project_check.assistant_email != token_data.email and project_check.doctor_email != token_data.email):
            raise HTTPException(status_code=403, detail="Not authorized to modify tasks for this project")
    
    else:
        raise HTTPException(status_code=403, detail="User type cannot manage tasks")

    if not target_project_id:
        raise HTTPException(status_code=400, detail="Could not determine target project")

    project_file = get_project_tasks_file(target_project_id)
    project_tasks_db = load_db(Task, project_file)
    
    # [تعديل] نحتاج هذه المتغيرات لتتبع حالة المهمة والإشعار
    existing_task_index = next((i for i, t in enumerate(project_tasks_db) if t.id == task.id), None)
    old_status: Optional[str] = None
    
    action = ""
    if existing_task_index is not None:
        old_status = project_tasks_db[existing_task_index].status.value # حفظ الحالة القديمة
        project_tasks_db[existing_task_index] = task
        action = "Updated task"
    else:
        project_tasks_db.append(task)
        action = "Added task"
        
    persist_tasks_and_log(project_tasks_db, project_file, action, current_user.email, task)

    # ---------------------------------------------------------
    # [الإشعار] منطق إرسال الـ WebSocket
    # ---------------------------------------------------------
    try:
        project = find_project_by_id(target_project_id)
        if not project:
            raise Exception("Project not found, cannot notify.")

        # 1. إشعار عند تعيين مهمة جديدة (Added task)
        if action == "Added task" and task.assignee != "All":
            target_user = next((u for u in users_db if u.name == task.assignee), None)
            
            if target_user:
                await manager.send_personal_message(
                    f"New Task Assigned: {task.title}", 
                    target_user.email
                )

        # 2. إشعار عند تغيير الحالة (Updated task)
        elif action == "Updated task" and old_status != task.status.value and task.status == TaskStatus.done:
            
            notification_body = f"Task '{task.title}' completed by {task.assignee}"
            
            # تجميع إيميلات المشرفين
            staff_emails = {project.assistant_email, project.doctor_email}
            staff_recipients = [u for u in users_db if u.email in staff_emails]
            
            for staff_member in staff_recipients:
                if staff_member.email != current_user.email: # لا ترسل لنفسك لو كنت أنت المشرف
                    await manager.send_personal_message(
                        notification_body, 
                        staff_member.email
                    )
            
        # 3. إشعار للطالب عند تحديث حالته بواسطة مشرف
        elif action == "Updated task" and old_status != task.status.value and task.assignee != "All":
            if current_user.user_type in ["Assistant", "Doctor", "Staff"]:
                target_user = next((u for u in users_db if u.name == task.assignee), None)
                if target_user and target_user.email != current_user.email:
                    await manager.send_personal_message(
                        f"Task '{task.title}' status changed to {task.status.value}",
                        target_user.email
                    )

    except Exception as e:
        # هذا لن يوقف الـ POST request
        pass 
    # ---------------------------------------------------------

    return task

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    project_id_query: Optional[str] = Query(None, alias="project_id"),
    token_data: TokenData = Depends(get_current_token_data),
    current_user: User = Depends(get_current_user)
):
    target_project_id = None

    if token_data.user_type == "Student":
        target_project_id = token_data.project_id
    elif token_data.user_type in ["Assistant", "Doctor", "Staff"]:
        target_project_id = project_id_query
        project = find_project_by_id(target_project_id)
        if not project or (project.assistant_email != token_data.email and project.doctor_email != token_data.email):
            raise HTTPException(status_code=403, detail="Not authorized")
    
    if not target_project_id:
         raise HTTPException(status_code=400, detail="Invalid project context")
    
    project_file = get_project_tasks_file(target_project_id)
    project_tasks_db = load_db(Task, project_file)
    
    task_to_delete = next((t for t in project_tasks_db if t.id == task_id), None)
    if task_to_delete is None:
        raise HTTPException(status_code=404, detail="Task not found")
        
    project_tasks_db.remove(task_to_delete)
    
    persist_tasks_and_log(project_tasks_db, project_file, "Deleted task", current_user.email, task_to_delete)
    
    # ---------------------------------------------------------
    # إرسال إشعار عند حذف المهمة
    # ---------------------------------------------------------
    try:
        project = find_project_by_id(target_project_id)
        if task_to_delete.assignee != "All":
            target_user = next((u for u in users_db if u.name == task_to_delete.assignee), None)
            
            if target_user:
                await manager.send_personal_message(
                    f"Task Deleted: {task_to_delete.title}", 
                    target_user.email
                )
    except Exception as e:
        pass # Silence the notification failure
    # ---------------------------------------------------------
    
    return {"message": "Task deleted successfully"}