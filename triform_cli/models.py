"""Pydantic models matching Triform API schemas."""

from typing import Optional, Literal, Any
from pydantic import BaseModel, Field


# ----- Common Models -----

class ComponentMeta(BaseModel):
    name: str
    intention: str = ""
    starred: bool = False


class IOPort(BaseModel):
    description: str = ""
    schema_: dict = Field(default_factory=dict, alias="schema")
    
    class Config:
        populate_by_name = True


# ----- Action Models -----

class ActionSpec(BaseModel):
    source: str
    requirements: str = ""
    checksum: str = ""
    readme: str = ""
    runtime: Literal["python-3.13"] = "python-3.13"
    inputs: dict[str, IOPort] = Field(default_factory=dict)
    outputs: dict[str, IOPort] = Field(default_factory=dict)


class Action(BaseModel):
    id: str
    resource: Literal["action/v1"]
    meta: ComponentMeta
    spec: ActionSpec


# ----- Flow Models -----

class Position(BaseModel):
    x: float = 0
    y: float = 0


class NodePort(BaseModel):
    source: str  # node_id or "parent"
    target: Optional[str] = None  # output port name


class FlowNode(BaseModel):
    component_id: str
    inputs: dict[str, NodePort] = Field(default_factory=dict)
    position: Position = Field(default_factory=Position)
    loop: dict = Field(default_factory=lambda: {"enabled": False})
    spec: Optional[Any] = None  # Resolved component


class FlowOutput(BaseModel):
    description: str = ""
    schema_: dict = Field(default_factory=dict, alias="schema")
    source: Optional[str] = None
    target: Optional[str] = None
    
    class Config:
        populate_by_name = True


class IONodes(BaseModel):
    input: Position = Field(default_factory=Position)
    output: Position = Field(default_factory=Position)


class FlowSpec(BaseModel):
    readme: str = ""
    nodes: dict[str, FlowNode] = Field(default_factory=dict)
    outputs: dict[str, FlowOutput] = Field(default_factory=dict)
    inputs: dict[str, IOPort] = Field(default_factory=dict)
    io_nodes: IONodes = Field(default_factory=IONodes)


class Flow(BaseModel):
    id: str
    resource: Literal["flow/v1"]
    meta: ComponentMeta
    spec: FlowSpec


# ----- Agent Models -----

class PromptTemplate(BaseModel):
    type: Literal["template"] = "template"
    enabled: bool = True
    value: str


class AgentNode(BaseModel):
    component_id: str
    inputs: dict[str, NodePort] = Field(default_factory=dict)
    order: int = 0
    spec: Optional[Any] = None  # Resolved component


class AgentSettings(BaseModel):
    temperature: Optional[float] = None
    topP: Optional[float] = None
    maxTokens: Optional[int] = 32768


class AgentSpec(BaseModel):
    model: str = "gemma-3-27b-it"
    readme: str = ""
    prompts: dict[str, list[PromptTemplate]] = Field(default_factory=lambda: {"system": [], "user": []})
    settings: AgentSettings = Field(default_factory=AgentSettings)
    nodes: dict[str, AgentNode] = Field(default_factory=dict)
    inputs: dict[str, IOPort] = Field(default_factory=dict)
    outputs: dict[str, IOPort] = Field(default_factory=dict)


class Agent(BaseModel):
    id: str
    resource: Literal["agent/v1"]
    meta: ComponentMeta
    spec: AgentSpec


# ----- Project Models -----

class ProjectVariable(BaseModel):
    key: str
    value: str
    secret: bool = False


class ProjectEnvironment(BaseModel):
    variables: list[ProjectVariable] = Field(default_factory=list)


class ProjectNode(BaseModel):
    component_id: str
    order: int = 0


class ProjectTriggers(BaseModel):
    endpoints: dict = Field(default_factory=dict)
    scheduled: dict = Field(default_factory=dict)


class ProjectSpec(BaseModel):
    readme: str = ""
    nodes: dict[str, ProjectNode] = Field(default_factory=dict)
    modifiers: dict = Field(default_factory=dict)
    environment: ProjectEnvironment = Field(default_factory=ProjectEnvironment)
    triggers: ProjectTriggers = Field(default_factory=ProjectTriggers)


class ProjectMeta(BaseModel):
    name: str
    intention: str = ""
    starred: bool = False


class Project(BaseModel):
    id: str
    resource: Literal["project/v1"]
    meta: ProjectMeta
    spec: ProjectSpec


# ----- Requirements Model -----

class TextItem(BaseModel):
    id: str
    text: str


class DependencyItem(BaseModel):
    id: str
    name: str
    description: str = ""
    type: str = ""


class Requirements(BaseModel):
    context: list[TextItem] = Field(default_factory=list)
    userStories: list[TextItem] = Field(default_factory=list)
    outcomes: list[TextItem] = Field(default_factory=list)
    guidelines: list[TextItem] = Field(default_factory=list)
    dependencies: list[DependencyItem] = Field(default_factory=list)
    boundaries: list[TextItem] = Field(default_factory=list)
    safety: list[TextItem] = Field(default_factory=list)


# ----- Execution Models -----

class ExecutionSpec(BaseModel):
    component: dict  # Resolved component
    payload: dict = Field(default_factory=dict)
    modifiers: dict = Field(default_factory=dict)
    environment: ProjectEnvironment = Field(default_factory=ProjectEnvironment)


class Execution(BaseModel):
    resource: Literal["execution/v1"] = "execution/v1"
    meta: dict = Field(default_factory=lambda: {"name": ""})
    spec: ExecutionSpec


# ----- Component Union -----

Component = Action | Flow | Agent

