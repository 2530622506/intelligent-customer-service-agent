from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    channel: str = Field(default="web", max_length=32)


class CreateRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    turn_id: str | None = None


class ConversationView(BaseModel):
    id: str
    title: str | None
    channel: str
    status: str


class MessageView(BaseModel):
    id: str
    turn_id: str
    author_type: str
    content: str
    status: str


class RunView(BaseModel):
    id: str
    turn_id: str
    status: str
