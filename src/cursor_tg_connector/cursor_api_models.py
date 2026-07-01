from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PromptImage(BaseModel):
    data: str
    dimension: dict[str, int] | None = None


class AgentSource(BaseModel):
    repository: str
    ref: str | None = None


class AgentTarget(BaseModel):
    url: str
    branch_name: str | None = Field(default=None, alias="branchName")
    pr_url: str | None = Field(default=None, alias="prUrl")


class Agent(BaseModel):
    id: str
    name: str
    status: str
    source: AgentSource
    target: AgentTarget
    summary: str | None = None
    created_at: str = Field(alias="createdAt")


class ListAgentsResponse(BaseModel):
    agents: list[Agent]
    next_cursor: str | None = Field(default=None, alias="nextCursor")


class ConversationMessage(BaseModel):
    id: str
    type: Literal["user_message", "assistant_message"]
    text: str


class AgentConversation(BaseModel):
    id: str
    messages: list[ConversationMessage]


class Repository(BaseModel):
    owner: str
    name: str
    repository: str


class ListRepositoriesResponse(BaseModel):
    repositories: list[Repository]


class ListModelsResponse(BaseModel):
    models: list[str]


class ApiKeyInfo(BaseModel):
    api_key_name: str = Field(alias="apiKeyName")
    created_at: str = Field(alias="createdAt")
    user_email: str | None = Field(default=None, alias="userEmail")


class PrivateWorker(BaseModel):
    name: str
    repo_url: str = Field(alias="repoUrl")
    repo_owner: str = Field(alias="repoOwner")
    repo_name: str = Field(alias="repoName")
    is_in_use: bool = Field(alias="isInUse")
    workspace_root_path: str | None = Field(default=None, alias="workspaceRootPath")
    worker_id: str | None = Field(default=None, alias="workerId")


class ListPrivateWorkersResponse(BaseModel):
    workers: list[PrivateWorker]


class ErrorBody(BaseModel):
    message: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody | None = None
    code: str | None = None
    message: str | None = None
