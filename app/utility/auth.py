from db_utility.mongo_db import UserSchema
from firebase_admin import  auth
from fastapi import APIRouter, HTTPException, Header, Depends, status, Body
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
    grade: Optional[str] = "10th"  # Default to 10th grade if not specified
    board: Optional[str] = None  # Optional field for user boards

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    personalized_response: Optional[bool] = None
    photo_url: Optional[str] = None
    grade: Optional[str] = "10th"  # Default to 10th grade if not specified
    board: Optional[str] = None  # Optional field for user boards

mongodb_user_collection = mongo_db["users"]

auth_router = APIRouter(
    responses={404: {"description": "Not found"}},
)

async def get_current_user_from_firebase_token(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid authorization header format",
        )
    
    token = authorization.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except (auth.RevokedIdTokenError, auth.InvalidIdTokenError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or revoked token",
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
        return {
            "message": "User created successfully",
            "userId" : user.userId
        }

    except Exception as e:
        print(f"Error during user creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )
    
@auth_router.post("/login")
async def login(
    payload: UserLoginPayload,
    current_firebase_user: dict = Depends(get_current_user_from_firebase_token)
    ):
    firebase_uid = current_firebase_user.get("uid")
    if payload.userId and payload.userId != firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User ID does not match the authenticated user",
        )
    user_doc = mongodb_user_collection.find_one(
        {"_id": payload.userId},
        {"quiz_ids": 0}  # Exclude quiz_ids from response
        )
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User profile not found, Please complete registration",
        )
    return {
        "message" : "Login successful",
        "userId": user_doc["_id"]
    }



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
        )
    
    user_id = current_firebase_user.get("uid")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="User ID not found in token",
        )
    
    # Check if user exists in Firestore else create a new user profile
    user_doc = mongodb_user_collection.find_one({"_id": user_id})

    if not user_doc:
        user_doc = UserSchema(
        _id=current_firebase_user.get("uid"),
        name=current_firebase_user.get("name"),
        email=current_firebase_user.get("email"),
        created_at=datetime.now(),
        photo_url=current_firebase_user.get("picture") if current_firebase_user.get("picture") else None,
        conversation_ids=[],
        quiz_ids=[]
    )
        mongodb_user_collection.insert_one(user_doc)
    return {
        "message": "User logged in successfully",
        "userId": user_id
    }

@auth_router.post("/logout")
async def logout(
    decoded_token: dict = Depends(get_current_user_from_firebase_token)):
    """
    This endpoint is used to log out a user.
    It requires a valid Firebase ID token in the Authorization header.
    """
    try:
        auth.revoke_refresh_tokens(decoded_token["uid"])
        return {"message": "User logged out successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to revoke refresh tokens",
        )


# Get user profile
@auth_router.get("/user/{userId}")
async def get_user_profile(
    userId: str,
    current_firebase_user: dict = Depends(get_current_user_from_firebase_token)):
    """
    This endpoint retrieves the user profile.
    It requires a valid Firebase ID token in the Authorization header.
    """
    if current_firebase_user["uid"] != userId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User ID does not match the authenticated user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_doc = mongodb_user_collection.find_one(
        {"_id": userId},
        {"quiz_ids": 0, "conversation_ids": 0}  # Exclude quiz_ids and conversation_ids from response
    )

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User profile not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    resp = {
        "message": "User profile retrieved successfully",
        "user": user_doc
    }
    return resp



@auth_router.patch("/user/{userId}")
async def update_user_profile(
    userId: str,
    user: UserProfileUpdate = Body(...),
    current_firebase_user: dict = Depends(get_current_user_from_firebase_token)
):
    """
    This endpoint updates the user profile.
    Requires valid Firebase ID token in Authorization header.
    """
    if current_firebase_user["uid"] != userId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User ID does not match the authenticated user",
        )
    
    update_data = user.model_dump(exclude_none=True)
    
    result = mongodb_user_collection.update_one(
        {"_id": userId},
        {"$set": update_data}
    )
    user_doc = mongodb_user_collection.find_one({"_id": userId}, {"quiz_ids": 0, "conversation_ids": 0})  # Exclude quiz_ids and conversation_ids from response

    response = {
        "message": "User profile updated successfully",
        "user": user_doc
    }
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found",
        )

    return response




