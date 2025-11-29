import shutil
import os
import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from models import Resource, ResourceType, User
from database import (
    resources_db, RESOURCES_FILE, save_db, 
    get_project_upload_dir, find_project_by_id
)
from dependencies import get_current_user
from utils import add_activity_log

router = APIRouter(prefix="/projects/{project_id}/resources")

# --- Helpers ---

def get_resource_type(filename: str, content_type: str) -> ResourceType:
    if not filename: return ResourceType.other
    ext = filename.split('.')[-1].lower() if '.' in filename else ""
    
    if content_type.startswith("image/") or ext in ["png", "jpg", "jpeg", "gif", "svg", "webp"]:
        return ResourceType.image
    if content_type == "application/pdf" or ext == "pdf":
        return ResourceType.pdf
    if ext in ["py", "js", "dart", "cpp", "html", "css", "java", "zip", "rar", "json", "sql"]:
        return ResourceType.code
    return ResourceType.other

def format_size(size_in_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} TB"

def check_access(user: User, project_id: str):
    """التحقق من أن المستخدم له حق الوصول لهذا المشروع"""
    project = find_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if user.user_type == "Student":
        if user.project_id != project_id:
            raise HTTPException(status_code=403, detail="Not authorized. You are not a member of this team.")
    
    elif user.user_type in ["Assistant", "Doctor", "Staff"]:
        if user.email not in [project.assistant_email, project.doctor_email] and user.user_type != "System User":
             raise HTTPException(status_code=403, detail="Not authorized to access this project's resources.")

# --- Endpoints ---

# 1. رفع ملف (Upload)
@router.post("", response_model=Resource)
async def upload_resource(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    check_access(current_user, project_id)

    # 1. تجهيز المسار
    project_dir = get_project_upload_dir(project_id)
    safe_filename = file.filename.replace(" ", "_")
    # اسم فريد للملف على السيرفر
    unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
    file_path = os.path.join(project_dir, unique_filename)
    
    # 2. حفظ الملف
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save error: {str(e)}")
    
    file_size = os.path.getsize(file_path)
    
    # 3. إنشاء السجل
    new_resource = Resource(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=file.filename, # الاسم الأصلي للعرض
        type=get_resource_type(file.filename, file.content_type),
        url=file_path,
        uploaded_by_name=current_user.name,
        uploaded_by_email=current_user.email,
        uploaded_at=datetime.utcnow().isoformat(),
        size=format_size(file_size),
        is_external_link=False
    )
    
    resources_db.insert(0, new_resource)
    save_db(resources_db, RESOURCES_FILE)
    
    add_activity_log(current_user.email, f"Uploaded resource: '{file.filename}'")
    
    return new_resource

# 2. إضافة رابط (Link)
@router.post("/link", response_model=Resource)
async def add_link_resource(
    project_id: str,
    title: str = Form(...),
    url: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    check_access(current_user, project_id)

    new_resource = Resource(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=title,
        type=ResourceType.link,
        url=url,
        uploaded_by_name=current_user.name,
        uploaded_by_email=current_user.email,
        uploaded_at=datetime.utcnow().isoformat(),
        size="-",
        is_external_link=True
    )
    
    resources_db.insert(0, new_resource)
    save_db(resources_db, RESOURCES_FILE)
    
    add_activity_log(current_user.email, f"Added link: '{title}'")
    return new_resource

# 3. عرض المصادر (List)
@router.get("", response_model=List[Resource])
async def get_project_resources(
    project_id: str, 
    current_user: User = Depends(get_current_user)
):
    check_access(current_user, project_id)
    # إرجاع مصادر هذا المشروع فقط
    return [r for r in resources_db if r.project_id == project_id]

# 4. تحميل ملف (Download)
# الرابط: /projects/{id}/resources/{res_id}/download
@router.get("/{resource_id}/download")
async def download_resource(
    project_id: str,
    resource_id: str,
):
    # البحث عن الملف
    resource = next((r for r in resources_db if r.id == resource_id and r.project_id == project_id), None)
    
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
        
    if resource.is_external_link:
        raise HTTPException(status_code=400, detail="Cannot download external link")
        
    if not os.path.exists(resource.url):
        raise HTTPException(status_code=404, detail="File missing on server")
    
    return FileResponse(
        path=resource.url, 
        filename=resource.title, 
        media_type='application/octet-stream'
    )

# 5. حذف مصدر (Delete)
@router.delete("/{resource_id}")
async def delete_resource(
    project_id: str, 
    resource_id: str, 
    current_user: User = Depends(get_current_user)
):
    check_access(current_user, project_id)

    resource = next((r for r in resources_db if r.id == resource_id and r.project_id == project_id), None)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # السماح بالحذف فقط لصاحب الملف أو المشرفين
    is_owner = resource.uploaded_by_email == current_user.email
    is_staff = current_user.user_type in ["Assistant", "Doctor", "Staff"]
    
    if not (is_owner or is_staff):
        raise HTTPException(status_code=403, detail="Delete permission denied")
    
    # حذف الملف الفعلي
    if not resource.is_external_link and os.path.exists(resource.url):
        try:
            os.remove(resource.url)
        except:
            pass 
        
    resources_db.remove(resource)
    save_db(resources_db, RESOURCES_FILE)
    
    add_activity_log(current_user.email, f"Deleted resource: '{resource.title}'")
    return {"message": "Deleted successfully"}