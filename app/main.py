import requests, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials
from utility.auth import auth_router
from utility.chat import chat_router
from utility.quizzes import quiz_router
from analytics.user_performance_metrics import analytics_router


app = FastAPI()

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], # Allow all origins for simplicity; adjust as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not firebase_admin._apps:
    cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
    firebase_admin.initialize_app(cred)

# Register the auth router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(quiz_router, prefix="/api/v1/quiz", tags=["quiz"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["analytics"])


@app.get("/")
async def root():
    return {"message": "Welcome to the Teacher Agent API"}
