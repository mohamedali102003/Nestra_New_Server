# database.py
import json
import os
from typing import List, Any, Callable, Optional
from models import Project, User, ActivityLog, Idea, Task, DiscussionMessage, Resource

# إعداد المسارات
DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)

PROJECTS_FILE = os.path.join(DATA_FOLDER, "projects.json") 
USERS_FILE = os.path.join(DATA_FOLDER, "users_data.json")
ACTIVITY_LOG_FILE = os.path.join(DATA_FOLDER, "activity_log.json")
IDEAS_FILE = os.path.join(DATA_FOLDER, "ideas.json")
RESOURCES_FILE = os.path.join(DATA_FOLDER, "resources.json") # [جديد]

# [جديد] مجلد الرفع الرئيسي
UPLOADS_FOLDER = "uploads"
os.makedirs(UPLOADS_FOLDER, exist_ok=True)

# أدوات I/O
def load_json(filename: str) -> List[Any]:
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except json.JSONDecodeError:
        return []

def save_json(filename: str, data: List[Any]):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_db(model: Callable[[dict], Any], filename: str) -> List[Any]:
    return [model(**item) for item in load_json(filename)]

def save_db(objects: List[Any], filename: str):
    save_json(filename, [o.model_dump() for o in objects])

# تحميل القوائم العامة (Global Memory)
projects_db: List[Project] = [Project(**p) for p in load_json(PROJECTS_FILE)]
users_db: List[User] = load_db(User, USERS_FILE)
activity_log_db: List[ActivityLog] = load_db(ActivityLog, ACTIVITY_LOG_FILE)
ideas_db: List[Idea] = load_db(Idea, IDEAS_FILE)
resources_db: List[Resource] = load_db(Resource, RESOURCES_FILE) # [جديد]

# دوال البحث والمساعدة
def find_user_by_email(email: str) -> Optional[User]:
    return next((u for u in users_db if u.email == email), None)

def find_project_by_id(project_id: str) -> Optional[Project]: 
    return next((p for p in projects_db if p.id == project_id), None)

def get_project_tasks_file(project_id: str) -> str:
    safe_project_id = "".join(c for c in project_id if c.isalnum() or c in ('-', '_'))
    if not safe_project_id:
        raise ValueError("Invalid project_id")
    return os.path.join(DATA_FOLDER, f"tasks_{safe_project_id}.json")

def get_project_chat_file(project_id: str) -> str:
    safe_id = "".join(c for c in project_id if c.isalnum() or c in ('-', '_'))
    return os.path.join(DATA_FOLDER, f"chat_{safe_id}.json")

def get_project_polls_file(project_id: str) -> str:
    safe_id = "".join(c for c in project_id if c.isalnum() or c in ('-', '_'))
    return os.path.join(DATA_FOLDER, f"polls_{safe_id}.json")

# [جديد] دالة لإنشاء/جلب مسار مجلد الفريق (Isolated Storage)
def get_project_upload_dir(project_id: str) -> str:
    safe_id = "".join(c for c in project_id if c.isalnum() or c in ('-', '_'))
    path = os.path.join(UPLOADS_FOLDER, safe_id)
    os.makedirs(path, exist_ok=True) 
    return path