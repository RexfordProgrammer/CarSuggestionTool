from typing import Any, Dict, List
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class MessageRecord(BaseModel):
    connectionId: str
    messages: List[ChatMessage] = Field(default_factory=list)

class PreferenceRecord(BaseModel):
    preferenceKey: str
    vehicle_type: Dict[str, Any] = Field(default_factory=dict)
    drive_train: Dict[str, Any] = Field(default_factory=dict)
    num_of_seating: Dict[str, Any] = Field(default_factory=dict)
    overall_stars: Dict[str, Any] = Field(default_factory=dict)

class MemoryRecord(BaseModel):
    connectionId: str
    working_state: Dict[str, Any] = Field(default_factory=dict)

class WorkingState(BaseModel):
    preferences: Dict[str, Any] = Field(default_factory=dict)
    cars: List[Any] = Field(default_factory=list)
    ratings: List[Any] = Field(default_factory=list)
    gas_data: List[Any] = Field(default_factory=list)
