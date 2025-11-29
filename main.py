# main.py
# © 2025 Mohamed Ali. All Rights Reserved.

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# استيراد الـ routers من الباكيج
from routes import (
    auth_router,
    projects_router,
    ideas_router,
    tasks_router,
    chat_router,
    users_router,
    activity_router,
    polls_router,
    realtime_router,
    resources_router,
    feedback_router # [جديد] إضافة راوتر الفيدباك هنا
)

# 1. إنشاء التطبيق
app = FastAPI()

# 2. إعدادات CORS
origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. ربط المسارات (Routers)
app.include_router(auth_router, tags=["Authentication"])
app.include_router(projects_router, tags=["Projects"])
app.include_router(ideas_router, tags=["Ideas"])
app.include_router(tasks_router, tags=["Tasks"])
app.include_router(chat_router, tags=["Chat"])
app.include_router(users_router, tags=["Users"])
app.include_router(activity_router, tags=["Activity & System"])
app.include_router(polls_router, tags=["Polls"])
app.include_router(realtime_router, tags=["Realtime Notification"])
app.include_router(resources_router, tags=["Project Resources"])

# [جديد] ربط راوتر الفيدباك بالتطبيق
app.include_router(feedback_router, tags=["Feedback"])

# 4. نقطة الانطلاق (Entry Point)
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)