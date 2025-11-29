from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Set, Optional
import uuid
from datetime import datetime
from models import Poll, PollOption, CreatePollRequest, VoteRequest, User, Availability, TimeSlot
from database import load_db, save_db, get_project_polls_file
from dependencies import get_current_user
from utils import add_activity_log

router = APIRouter()

# --- Helpers ---

def minutes_to_time(minutes: int) -> str:
    """Converts minutes to 12-hour AM/PM format compactly."""
    m = max(0, min(minutes, 1440))
    h, mn = divmod(m, 60)
    
    period = "PM" if h >= 12 else "AM"
    h = h % 12
    if h == 0: h = 12
        
    return f"{h:02}:{mn:02} {period}"

def format_ranges(indices_list: List[int]) -> str:
    """Formats a list of minute indices into time ranges string."""
    if not indices_list: return ""
    indices_list.sort()
    
    ranges = []
    start_m = curr_m = indices_list[0]
    
    for i in range(1, len(indices_list)):
        if indices_list[i] == curr_m + 1:
            curr_m = indices_list[i]
        else:
            ranges.append(f"{minutes_to_time(start_m)}-{minutes_to_time(curr_m + 1)}")
            start_m = curr_m = indices_list[i]
    
    ranges.append(f"{minutes_to_time(start_m)}-{minutes_to_time(curr_m + 1)}")
    return " & ".join(ranges)

def calculate_best_time(availabilities: List[Availability]):
    if not availabilities:
        return None, None

    total_users = len(availabilities)
    timeline: List[Set[str]] = [set() for _ in range(1440)]

    # Fill Timeline
    for avail in availabilities:
        for slot in avail.slots:
            start_m = max(0, min(slot.start, 1439))
            end_m = max(0, min(slot.end, 1440)) 
            for m in range(start_m, end_m):
                timeline[m].add(avail.user_name)

    # 1. Find Perfect Match
    perfect_minutes = [m for m in range(1440) if len(timeline[m]) == total_users]
    if perfect_minutes:
        return format_ranges(perfect_minutes), None

    # 2. Find Majority (Total - 1)
    majority_minutes = []
    missing_counter = {}
    
    for m in range(1440):
        if len(timeline[m]) == total_users - 1 and total_users > 1:
            majority_minutes.append(m)
            # Find the missing person
            all_names = {a.user_name for a in availabilities}
            missing = list(all_names - timeline[m])
            if missing: 
                name = missing[0]
                missing_counter[name] = missing_counter.get(name, 0) + 1

    if majority_minutes:
        most_missing = max(missing_counter, key=missing_counter.get) if missing_counter else "Someone"
        return f"{format_ranges(majority_minutes)} (Majority)", f"{most_missing} is not available."

    return "No common time found", "Complex conflict."

def get_poll_or_404(polls: List[Poll], poll_id: str) -> Poll:
    """Helper to find a poll or raise 404."""
    poll = next((p for p in polls if p.id == poll_id), None)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    return poll

# --- Endpoints ---

@router.get("/polls", response_model=List[Poll])
async def get_project_polls(
    project_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    if current_user.user_type == "Student" and current_user.project_id != project_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    polls = load_db(Poll, get_project_polls_file(project_id))
    polls.sort(key=lambda x: x.timestamp, reverse=True)
    return polls

@router.post("/polls", response_model=Poll)
async def create_poll(
    request: CreatePollRequest,
    allow_multiple: bool = Query(False),
    poll_type: str = Query("standard"),
    project_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    poll_options = []
    if poll_type == "standard":
        poll_options = [
            PollOption(id=str(uuid.uuid4()), text=opt, voter_emails=[]) 
            for opt in request.options
        ]

    new_poll = Poll(
        id=str(uuid.uuid4()),
        project_id=project_id,
        question=request.question,
        creator_name=current_user.name,
        creator_email=current_user.email,
        poll_type=poll_type,
        options=poll_options,
        allow_multiple_votes=allow_multiple,
        timestamp=datetime.utcnow().isoformat(),
        target_date=request.target_date
    )

    polls_file = get_project_polls_file(project_id)
    polls = load_db(Poll, polls_file)
    polls.append(new_poll)
    save_db(polls, polls_file)

    add_activity_log(current_user.email, f"Created poll: '{request.question}'")
    return new_poll

@router.post("/polls/{poll_id}/vote")
async def vote_poll(
    poll_id: str,
    vote_req: VoteRequest,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    polls_file = get_project_polls_file(project_id)
    polls = load_db(Poll, polls_file)
    
    poll = get_poll_or_404(polls, poll_id) # Reuse helper

    if poll.status == "closed":
        raise HTTPException(status_code=400, detail="Voting is closed")

    target_option = next((o for o in poll.options if o.id == vote_req.option_id), None)
    if not target_option:
        raise HTTPException(status_code=404, detail="Option not found")

    email = current_user.email
    msg = ""

    if poll.allow_multiple_votes:
        if email in target_option.voter_emails:
            target_option.voter_emails.remove(email)
            msg = "Vote removed"
        else:
            target_option.voter_emails.append(email)
            msg = "Vote added"
    else:
        # Remove previous vote if exists
        for opt in poll.options:
            if email in opt.voter_emails:
                opt.voter_emails.remove(email)
        
        target_option.voter_emails.append(email)
        msg = "Vote recorded"
    
    save_db(polls, polls_file)
    return {"message": msg}

@router.post("/polls/{poll_id}/availability")
async def submit_availability(
    poll_id: str,
    slots: List[TimeSlot], 
    project_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    polls_file = get_project_polls_file(project_id)
    polls = load_db(Poll, polls_file)
    
    poll = get_poll_or_404(polls, poll_id) # Reuse helper
    
    if poll.status == "closed":
        raise HTTPException(status_code=400, detail="Poll closed")

    # Update availability
    poll.availabilities = [a for a in poll.availabilities if a.user_email != current_user.email]
    poll.availabilities.append(Availability(
        user_email=current_user.email,
        user_name=current_user.name,
        slots=slots
    ))
    
    save_db(polls, polls_file)
    return {"message": "Availability saved"}

@router.post("/polls/{poll_id}/close", response_model=Poll)
async def close_poll(
    poll_id: str,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    polls_file = get_project_polls_file(project_id)
    polls = load_db(Poll, polls_file)
    
    poll = get_poll_or_404(polls, poll_id) # Reuse helper

    if poll.creator_email != current_user.email:
        raise HTTPException(status_code=403, detail="Only the creator can close this poll")

    if poll.poll_type == "time_range":
        result_text, conflict = calculate_best_time(poll.availabilities)
        poll.result = result_text
        poll.conflict_note = conflict
    else:
        # Calculate winner for standard polls
        max_votes = 0
        winners = []
        for opt in poll.options:
            count = len(opt.voter_emails)
            if count > max_votes:
                max_votes = count
                winners = [opt.text]
            elif count == max_votes and count > 0:
                winners.append(opt.text)

        poll.result = " & ".join(winners) if winners else "No votes"

    poll.status = "closed"
    save_db(polls, polls_file)
    add_activity_log(current_user.email, f"Closed poll '{poll.question}'")
    
    return poll

@router.delete("/polls/{poll_id}")
async def delete_poll(
    poll_id: str,
    project_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    polls_file = get_project_polls_file(project_id)
    polls = load_db(Poll, polls_file)
    
    poll = get_poll_or_404(polls, poll_id) # Reuse helper

    if poll.creator_email != current_user.email:
        raise HTTPException(status_code=403, detail="You can only delete polls you created")

    polls.remove(poll)
    save_db(polls, polls_file)
    add_activity_log(current_user.email, f"Deleted poll: '{poll.question}'")
    
    return {"message": "Poll deleted successfully"}