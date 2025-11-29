# models.py
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional

# --- Tasks ---
class TaskStatus(str, Enum):
    todo = "todo"
    inProgress = "inProgress"
    done = "done"

class Task(BaseModel):
    id: str
    title: str
    description: str
    assignee: str
    status: TaskStatus = TaskStatus.todo
    due_date: Optional[str] = None 

# --- Projects ---
class Project(BaseModel): 
    id: str
    name: str
    assistant_email: str
    doctor_email: Optional[str] = None
    idea_id: Optional[str] = None 

# --- Users ---
class User(BaseModel):
    name: str
    email: str
    password: str
    user_type: str
    project_id: Optional[str] = None
    tracks: List[str] = []
    skills: List[str] = []
    github_link: Optional[str] = None
    meeting_preference: str = "Any"
    daily_hours: float = 0.0
    readiness_status: str = "Learning"

class UserProfileUpdate(BaseModel):
    tracks: List[str]
    skills: List[str]
    github_link: Optional[str] = None
    meeting_preference: str
    daily_hours: float
    readiness_status: str

class UserPublic(BaseModel): 
    name: str
    email: str
    user_type: str
    project_id: Optional[str] = None
    tracks: List[str] = []
    skills: List[str] = []
    meeting_preference: str = "Any"
    readiness_status: str = "Learning"

class TokenData(BaseModel):
    email: Optional[str] = None
    user_type: Optional[str] = None
    project_id: Optional[str] = None

class TeamMember(BaseModel):
    name: str
    email: str
    tracks: List[str] = []
    role_in_team: str = "Member"

# --- Activity & Logs ---
class ActivityLog(BaseModel):
    id: str
    user: str
    action: str
    timestamp: str

# --- Ideas ---
class IdeaStatus(str, Enum):
    available = "available"
    pending_approval = "pending_approval"
    assigned = "assigned"
    in_discussion = "in_discussion" 

class IdeaSubmission(BaseModel):
    name: str
    description: str
    idea_type: str

class Idea(BaseModel):
    id: str
    name: str
    description: str
    idea_type: str
    staff_name: str
    staff_email: str
    timestamp: str
    idea_status: IdeaStatus = IdeaStatus.available
    linked_project_id: Optional[str] = None

class IdeaAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    UNASSIGN = "unassign"
    DISCUSS = "discuss" 

class ManageIdeaAction(BaseModel):
    action: IdeaAction

# --- Chat ---
class DiscussionMessage(BaseModel):
    id: str
    idea_id: Optional[str] = None 
    project_id: str
    sender_email: str
    sender_name: str
    content: str
    timestamp: str

class DiscussionMessageCreate(BaseModel):
    content: str

# --- Polls & Time Coordination ---
class TimeSlot(BaseModel):
    start: int
    end: int

class Availability(BaseModel):
    user_email: str
    user_name: str
    slots: List[TimeSlot] = [] 

class PollOption(BaseModel):
    id: str
    text: str
    voter_emails: List[str] = [] 

class Poll(BaseModel):
    id: str
    project_id: str
    question: str
    creator_name: str
    creator_email: str
    options: List[PollOption] = []
    poll_type: str = "standard"
    availabilities: List[Availability] = [] 
    allow_multiple_votes: bool = False
    target_date: Optional[str] = None 
    timestamp: str
    status: str = "open"
    result: Optional[str] = None 
    conflict_note: Optional[str] = None

class VoteRequest(BaseModel):
    option_id: str

class CreatePollRequest(BaseModel):
    question: str
    options: List[str] = []
    target_date: Optional[str] = None 

# --- Resources / Files [NEW] ---
class ResourceType(str, Enum):
    pdf = "pdf"
    image = "image"
    code = "code"
    link = "link"
    other = "other"

class Resource(BaseModel):
    id: str
    project_id: str
    title: str
    type: ResourceType
    url: str          # مسار الملف الفعلي أو الرابط الخارجي
    uploaded_by_name: str
    uploaded_by_email: str
    uploaded_at: str  # Timestamp ISO
    size: str         # e.g., "2.5 MB"
    is_external_link: bool = False

class Feedback(BaseModel):
    id: str
    user_email: str
    user_name: str
    description: str
    screenshot_url: Optional[str] = None
    timestamp: str
    device_info: Optional[str] = None # لتسجيل نوع الجهاز إذا أمكن    