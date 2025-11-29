# routes/chat.py
from fastapi import APIRouter, Depends
from typing import List
from datetime import datetime
import uuid
from models import DiscussionMessage, DiscussionMessageCreate, User, IdeaStatus
# [تعديل] أضفنا users_db, find_project_by_id, projects_db لضمان جلب كل أعضاء الفريق
from database import load_db, save_db, ideas_db, get_project_chat_file, users_db, find_project_by_id, projects_db
from utils import check_chat_permissions
from dependencies import get_current_user
from routes.realtime import manager # استيراد المانجر

router = APIRouter()

@router.get("/ideas/{project_id}/discussion", response_model=List[dict])
async def get_project_discussion(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    check_chat_permissions(current_user, project_id)
        
    chat_file = get_project_chat_file(project_id)
    discussion_messages = load_db(DiscussionMessage, chat_file)
    
    response_messages = []
    for msg in discussion_messages:
        msg_dict = msg.model_dump()
        msg_dict["is_me"] = (msg.sender_email == current_user.email)
        response_messages.append(msg_dict)
        
    response_messages.sort(key=lambda x: x['timestamp'])
    return response_messages


@router.post("/ideas/{project_id}/discussion", response_model=DiscussionMessage)
async def post_project_discussion_message(
    project_id: str,
    message: DiscussionMessageCreate,
    current_user: User = Depends(get_current_user)
):
    check_chat_permissions(current_user, project_id)

    linked_idea = next((
        i for i in ideas_db 
        if i.linked_project_id == project_id and i.idea_status != IdeaStatus.available
    ), None)

    new_message = DiscussionMessage(
        id=str(uuid.uuid4()),
        idea_id=linked_idea.id if linked_idea else None, 
        project_id=project_id,
        sender_email=current_user.email,
        sender_name=current_user.name,
        content=message.content,
        timestamp=datetime.utcnow().isoformat()
    )
    
    chat_file = get_project_chat_file(project_id)
    team_messages = load_db(DiscussionMessage, chat_file)
    
    team_messages.append(new_message)
    save_db(team_messages, chat_file)
    
    # ---------------------------------------------------------
    # إرسال إشعار Realtime (WebSocket) للفريق بالكامل
    # ---------------------------------------------------------
    try:
        project = find_project_by_id(project_id)
        if not project:
            # لو لم يتم العثور على المشروع (لا ينبغي أن يحدث)
            raise Exception("Project data not found, cannot notify team.")

        # 1. تحديد أعضاء الفريق (الطلاب فقط - بناءً على project_id)
        student_recipients = [
            u for u in users_db 
            if u.project_id == project_id
        ]
        
        # 2. تحديد طاقم الإشراف (المعيد/الدكتور - بناءً على email المشروع)
        staff_emails = {project.assistant_email, project.doctor_email}
        staff_recipients = [
            u for u in users_db
            if u.email in staff_emails and u.user_type in ["Assistant", "Doctor"]
        ]
        
        # دمج القائمتين وتجنب التكرار (واستخدام الـ email كـ مفتاح للفرز)
        all_recipients = list({u.email: u for u in student_recipients + staff_recipients}.values())
        
        # إعداد نص الإشعار
        notification_text = f"New message from {current_user.name}: {new_message.content[:30]}..."
        if len(new_message.content) > 30:
             notification_text += "..."

        # 3. إرسال الإشعار لكل عضو متصل (ما عدا المرسل)
        for member in all_recipients:
            if member.email != current_user.email: 
                await manager.send_personal_message(notification_text, member.email)
            
    except Exception as e:
        # لو فشل الاتصال، نطبع تحذير في السيرفر بس مانوقفش الشات
        print(f"⚠️ Chat Notification Warning/Failure: {e}")
    # ---------------------------------------------------------

    return new_message