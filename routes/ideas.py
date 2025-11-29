# routes/ideas.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
import uuid
from datetime import datetime
from models import Idea, IdeaSubmission, IdeaStatus, User, IdeaAction, ManageIdeaAction, TokenData
from database import ideas_db, IDEAS_FILE, projects_db, PROJECTS_FILE, save_db, find_project_by_id
from utils import add_activity_log
from dependencies import get_current_user, get_current_staff_user, get_current_token_data

router = APIRouter()

@router.post("/ideas", response_model=Idea)
async def create_idea(
    idea: IdeaSubmission,
    current_user: User = Depends(get_current_staff_user)
):
    if current_user.user_type != "Doctor":
         raise HTTPException(status_code=403, detail="Only Doctors can add project ideas.")

    new_idea = Idea(
        id=str(uuid.uuid4()),
        name=idea.name,
        description=idea.description,
        idea_type=idea.idea_type,
        staff_name=current_user.name, 
        staff_email=current_user.email, 
        timestamp=datetime.utcnow().isoformat()
    )
    
    ideas_db.append(new_idea)
    save_db(ideas_db, IDEAS_FILE) 
    
    add_activity_log(current_user.email, f"Added new project idea: '{new_idea.name}'")
    return new_idea

@router.get("/ideas", response_model=List[Idea])
async def get_ideas(current_user: User = Depends(get_current_staff_user)):
    my_ideas = [idea for idea in ideas_db if idea.staff_email == current_user.email]
    return my_ideas

@router.get("/ideas/available", response_model=List[Idea])
async def get_available_ideas(token_data: TokenData = Depends(get_current_token_data)):
    if token_data.user_type != "Student":
        raise HTTPException(status_code=403, detail="Only students can view available ideas")
    
    available = [idea for idea in ideas_db if idea.idea_status == IdeaStatus.available]
    return available

@router.post("/ideas/{idea_id}/request", response_model=Idea)
async def request_idea(
    idea_id: str,
    current_user: User = Depends(get_current_user)
):
    if current_user.user_type != "Student":
        raise HTTPException(status_code=403, detail="Only students can request ideas")
    
    project_id = current_user.project_id
    if not project_id:
        raise HTTPException(status_code=400, detail="You must be assigned to a team to request an idea.")
    
    idea = next((i for i in ideas_db if i.id == idea_id), None)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    if idea.idea_status != IdeaStatus.available:
        raise HTTPException(status_code=400, detail="This idea is not available for request.")
    
    existing_request = next((
        i for i in ideas_db 
        if i.linked_project_id == project_id and i.idea_status != IdeaStatus.available
    ), None)
    if existing_request:
        raise HTTPException(status_code=400, detail=f"Your team already has a request pending or assigned ('{existing_request.name}').")

    idea.idea_status = IdeaStatus.pending_approval
    idea.linked_project_id = project_id
    save_db(ideas_db, IDEAS_FILE)
    
    add_activity_log(current_user.email, f"Team (ID: {project_id}) requested idea: '{idea.name}'")
    return idea

@router.post("/ideas/{idea_id}/manage", response_model=Idea)
async def manage_idea_request(
    idea_id: str,
    management: ManageIdeaAction,
    current_user: User = Depends(get_current_staff_user)
):
    idea = next((i for i in ideas_db if i.id == idea_id), None)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    if idea.staff_email != current_user.email:
        raise HTTPException(status_code=403, detail="You are not authorized to manage this idea.")
    
    action = management.action

    if action == IdeaAction.ACCEPT or action == IdeaAction.REJECT:
        if idea.idea_status not in [IdeaStatus.pending_approval, IdeaStatus.in_discussion]:
            raise HTTPException(status_code=400, detail=f"This action is only valid for 'pending' or 'discussion' states.")

        project = find_project_by_id(idea.linked_project_id)
        if not project:
            idea.idea_status = IdeaStatus.available
            idea.linked_project_id = None
            save_db(ideas_db, IDEAS_FILE)
            raise HTTPException(status_code=404, detail=f"The requesting project was not found.")

        if action == IdeaAction.ACCEPT:
            idea.idea_status = IdeaStatus.assigned
            project.name = idea.name 
            project.doctor_email = current_user.email
            save_db(projects_db, PROJECTS_FILE)
            save_db(ideas_db, IDEAS_FILE)
            
            add_activity_log(
                current_user.email, 
                f"Accepted idea '{idea.name}' for project '{project.name}'. Assigned Dr. {current_user.name} as supervisor."
            )
        
        else: # REJECT
            idea.idea_status = IdeaStatus.available
            idea.linked_project_id = None
            save_db(ideas_db, IDEAS_FILE)
            add_activity_log(current_user.email, f"Rejected idea '{idea.name}' for project (ID: {project.id})")

    elif action == IdeaAction.UNASSIGN:
        if idea.idea_status != IdeaStatus.assigned:
            raise HTTPException(status_code=400, detail=f"This idea is not in an 'assigned' state.")

        project = find_project_by_id(idea.linked_project_id)
        if project:
             project.doctor_email = None
             save_db(projects_db, PROJECTS_FILE)

        add_activity_log(current_user.email, f"Unassigned idea '{idea.name}' from project (ID: {idea.linked_project_id})")
        idea.idea_status = IdeaStatus.available
        idea.linked_project_id = None
        save_db(ideas_db, IDEAS_FILE)
    
    elif action == IdeaAction.DISCUSS:
        if idea.idea_status != IdeaStatus.pending_approval:
            raise HTTPException(status_code=400, detail=f"This idea is not in a 'pending_approval' state.")
        
        idea.idea_status = IdeaStatus.in_discussion
        save_db(ideas_db, IDEAS_FILE)
        add_activity_log(current_user.email, f"Started discussion for idea '{idea.name}' (ID: {idea.id})")

    return idea

@router.delete("/ideas/{idea_id}", status_code=200)
async def delete_idea(
    idea_id: str,
    current_user: User = Depends(get_current_staff_user)
):
    idea = next((i for i in ideas_db if i.id == idea_id), None)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    if idea.staff_email != current_user.email:
        raise HTTPException(
            status_code=403, 
            detail="You are not authorized to delete this idea. Only the creator can."
        )

    if idea.idea_status != IdeaStatus.available:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete idea. It is currently '{idea.idea_status.value}'. Only 'available' ideas can be deleted."
        )

    ideas_db.remove(idea)
    save_db(ideas_db, IDEAS_FILE)
    add_activity_log(current_user.email, f"Deleted idea: '{idea.name}' (ID: {idea_id})")
    return {"message": "Idea deleted successfully"}

@router.get("/ideas/my-status", response_model=Optional[Idea])
async def get_my_idea_status(token_data: TokenData = Depends(get_current_token_data)):
    if token_data.user_type != "Student":
        raise HTTPException(status_code=403, detail="Only students can check their idea status")
    
    project_id = token_data.project_id
    if not project_id:
        return None 

    my_idea = next((
        idea for idea in ideas_db 
        if idea.linked_project_id == project_id and idea.idea_status != IdeaStatus.available
    ), None)
    
    return my_idea