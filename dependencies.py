# dependencies.py
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from models import TokenData, User
from database import find_user_by_email
from utils import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login") # لاحظ تم تعديل المسار ليناسب الراوتر

def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_type: str = payload.get("user_type")
        project_id: Optional[str] = payload.get("project_id")
        if email is None or user_type is None:
            raise JWTError("Missing token claims")
        return TokenData(email=email, user_type=user_type, project_id=project_id)
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

async def get_current_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    return decode_token(token)

async def get_current_user(token: TokenData = Depends(get_current_token_data)) -> User:
    user = find_user_by_email(token.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return user

async def get_current_staff_user(token: TokenData = Depends(get_current_token_data)) -> User:
    allowed_roles = ["Staff", "Doctor", "Assistant", "System User"]
    if token.user_type not in allowed_roles:
        raise HTTPException(status_code=403, detail="Operation not permitted. Privileged access required.")
    user = find_user_by_email(token.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return user