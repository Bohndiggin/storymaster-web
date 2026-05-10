"""Litography DTOs: nodes, connections, plots, plot sections."""

from __future__ import annotations

from pydantic import BaseModel, Field

from storymaster.api.schemas.common import TimestampedDTO


# --- Nodes ----------------------------------------------------------------


class NodeCreate(BaseModel):
    name: str = "Untitled Node"
    description: str | None = None
    node_type: str  # NodeType enum value: exposition/action/reaction/twist/development/other
    x_position: float = 0.0
    y_position: float = 0.0


class NodeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    node_type: str | None = None
    x_position: float | None = None
    y_position: float | None = None


class NodeOut(TimestampedDTO):
    id: int
    name: str
    description: str | None
    node_type: str
    x_position: float
    y_position: float
    storyline_id: int


class NodePosition(BaseModel):
    """Single position update for the bulk-position PATCH endpoint."""

    id: int
    x: float
    y: float


class NodePositionsUpdate(BaseModel):
    positions: list[NodePosition] = Field(default_factory=list)


# --- Connections ----------------------------------------------------------


class ConnectionCreate(BaseModel):
    output_node_id: int
    input_node_id: int


class ConnectionOut(TimestampedDTO):
    id: int
    output_node_id: int
    input_node_id: int


# --- Plots & Sections -----------------------------------------------------


class PlotCreate(BaseModel):
    title: str
    description: str | None = None


class PlotUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class PlotOut(TimestampedDTO):
    id: int
    title: str
    description: str | None
    storyline_id: int


class PlotSectionCreate(BaseModel):
    plot_section_type: str  # PlotSectionType enum value


class PlotSectionUpdate(BaseModel):
    plot_section_type: str | None = None


class PlotSectionOut(TimestampedDTO):
    id: int
    plot_section_type: str
    plot_id: int


class NodeSectionLink(BaseModel):
    node_id: int
    plot_section_id: int


class NodeSectionLinkOut(TimestampedDTO):
    id: int
    node_id: int | None
    litography_plot_section_id: int | None
