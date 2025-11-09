from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    user_id: int
    username: Optional[str]
    full_name: Optional[str]

class UserResponse(UserBase):
    subscription: bool
    subscription_start: Optional[datetime]
    subscription_end: Optional[datetime]
    created_at: datetime
    last_active: datetime
    
    class Config:
        from_attributes = True

class PhotoBase(BaseModel):
    user_id: int
    file_id: str
    original_filename: Optional[str]

class PhotoResponse(PhotoBase):
    id: int
    status: str
    result_text: Optional[str]
    processing_time: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserStatsResponse(BaseModel):
    user: Optional[UserResponse]
    photos_count: int

class UserActionBase(BaseModel):
    user_id: int
    action_type: str
    details: Optional[str]

class UserActionResponse(UserActionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True