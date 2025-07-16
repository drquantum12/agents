from db_utility.mongo_db import UserSchema
from firebase_admin import  auth
from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from db_utility.mongo_db import mongo_db
class UserLoginPayload(BaseModel):
    userId: str

class UserProfileCreate(BaseModel):
    userId: str
    name: str
    email: str
    photo_url: Optional[str] = None

mongodb_user_collection = mongo_db["users"]

auth_router = APIRouter(
    responses={404: {"description": "Not found"}},
)

async def get_current_user_from_firebase_token(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) 
    
@auth_router.post("/create-user", response_model=dict)
async def create_user(user: UserProfileCreate,
                      current_firebase_user: dict=Depends(get_current_user_from_firebase_token)):

    """
    payload: {
        "userId": "user id",
        "name": "User Name",
        "email": "user@example.com",
        "photo_url": "https://example.com/photo.jpg" # Optional
    }
    This endpoint creates a new user profile in Firestore.
    It requires a valid Firebase ID token in the Authorization header.
    """

    if current_firebase_user["uid"] != user.userId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User ID does not match the authenticated user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_data = UserSchema(
        _id=user.userId,
        name=user.name,
        email=user.email,
        created_at=datetime.now(),
        photo_url=user.photo_url if user.photo_url else "",
        conversation_ids=[],
        quiz_ids=[]
    )

    try:
        mongodb_user_collection.insert_one(user_data)
        return {"message": "User registered successfully", "user_id": user_data}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )
    
@auth_router.post("/login-email-password")
async def login_email_password(
    payload: UserLoginPayload,
    current_firebase_user: dict = Depends(get_current_user_from_firebase_token)):
    firebase_uid = current_firebase_user.get("uid")
    if payload.userId and payload.userId != firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User ID does not match the authenticated user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_doc = mongodb_user_collection.find_one({"_id": payload.userId})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User profile not found, Please complete registration",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"message": "Login successful", "user": user_doc}



@auth_router.post("/continue-with-google")
async def google_sign_in(
    payload: UserLoginPayload,
    current_firebase_user: dict = Depends(get_current_user_from_firebase_token)):
    """
    This endpoint is used to log in a user.
    It requires a valid Firebase ID token in the Authorization header.
    """
    if payload.userId and payload.userId != current_firebase_user.get("uid"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User ID does not match the authenticated user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = current_firebase_user.get("uid")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="User ID not found in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user exists in Firestore else create a new user profile
    user_doc = mongodb_user_collection.find_one({"_id": user_id})

    if not user_doc:
        user_data = UserSchema(
        _id=current_firebase_user.get("uid"),
        name=current_firebase_user.get("name"),
        email=current_firebase_user.get("email"),
        created_at=datetime.now(),
        photo_url=current_firebase_user.get("picture") if current_firebase_user.get("picture") else None,
        conversation_ids=[],
        quiz_ids=[]
    )
        mongodb_user_collection.insert_one(user_data)
    return {"message": "Sign-in successful", "user": user_doc}




