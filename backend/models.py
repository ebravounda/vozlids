from datetime import datetime, timezone
from typing import Annotated, Any, List, Optional
from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        return cls.model_validate(doc) if doc else None

    def to_mongo(self) -> dict:
        d = self.model_dump(by_alias=True)
        if d.get("_id") is None:
            d.pop("_id", None)
        return d

    def out(self) -> dict:
        return self.model_dump()


class Agent(BaseDocument):
    tenant_id: str
    name: str
    business_name: str
    product: str
    objective: str
    questions: List[str] = []
    voice: str
    ambience: str
    ambience_volume: int = 35
    greeting: str
    extra_instructions: str = ""
    active: bool = True
    is_sample: bool = False
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Lead(BaseDocument):
    tenant_id: str
    agent_id: str
    agent_name: str = ""
    name: str
    phone: str
    email: str = ""
    consent: bool = True
    is_test: bool = False
    is_sample: bool = False
    status: str = "llamando"
    call_phase: str = ""
    vapi_call_id: Optional[str] = None
    error: str = ""
    transcript: str = ""
    messages: List[dict] = []
    recording_url: str = ""
    summary: str = ""
    interest_score: Optional[int] = None
    answers: str = ""
    ended_reason: str = ""
    duration_seconds: Optional[float] = None
    appointment_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Appointment(BaseDocument):
    tenant_id: str
    lead_id: Optional[str] = None
    lead_name: str = ""
    lead_phone: str = ""
    agent_id: Optional[str] = None
    start: str
    notes: str = ""
    is_sample: bool = False
    created_at: str = Field(default_factory=now_iso)


class DncEntry(BaseDocument):
    tenant_id: str
    phone: str
    reason: str = ""
    created_at: str = Field(default_factory=now_iso)


class Availability(BaseDocument):
    tenant_id: str
    slot_minutes: int = 30
    days: List[Any] = []
