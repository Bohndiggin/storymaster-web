"""Litographer endpoints: nodes, connections, plots, plot sections.

The bulk position endpoint
    PATCH /api/v1/storylines/{id}/nodes/positions
exists so the React Flow canvas can flush a multi-node drag in one round trip
instead of N concurrent PATCHes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.authz import (
    get_storyline_owned_node,
    require_node,
    require_plot,
    require_storyline,
)
from storymaster.api.deps import get_current_user
from storymaster.api.schemas.litography import (
    ConnectionCreate,
    ConnectionOut,
    NodeCreate,
    NodeOut,
    NodePositionsUpdate,
    NodeSectionLink,
    NodeSectionLinkOut,
    NodeUpdate,
    PlotCreate,
    PlotOut,
    PlotSectionCreate,
    PlotSectionOut,
    PlotSectionUpdate,
    PlotUpdate,
)
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["litography"])


def _coerce_node_type(value: str) -> schema.NodeType:
    try:
        return schema.NodeType(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid node_type: {value!r}",
        ) from exc


def _coerce_section_type(value: str) -> schema.PlotSectionType:
    try:
        return schema.PlotSectionType(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid plot_section_type: {value!r}",
        ) from exc


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


@router.get("/storylines/{storyline_id}/nodes", response_model=list[NodeOut])
def list_nodes(
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> list[schema.LitographyNode]:
    stmt = (
        select(schema.LitographyNode)
        .where(schema.LitographyNode.storyline_id == storyline.id)
        .order_by(schema.LitographyNode.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/storylines/{storyline_id}/nodes",
    response_model=NodeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_node(
    payload: NodeCreate,
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> schema.LitographyNode:
    node = schema.LitographyNode(
        name=payload.name,
        description=payload.description,
        node_type=_coerce_node_type(payload.node_type),
        x_position=payload.x_position,
        y_position=payload.y_position,
        storyline_id=storyline.id,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


@router.get("/nodes/{node_id}", response_model=NodeOut)
def get_node(node: schema.LitographyNode = Depends(require_node)) -> schema.LitographyNode:
    return node


@router.patch("/nodes/{node_id}", response_model=NodeOut)
def update_node(
    payload: NodeUpdate,
    node: schema.LitographyNode = Depends(require_node),
    db: Session = Depends(get_db),
) -> schema.LitographyNode:
    data = payload.model_dump(exclude_unset=True)
    if "node_type" in data and data["node_type"] is not None:
        data["node_type"] = _coerce_node_type(data["node_type"])
    for k, v in data.items():
        if v is None and k in {"node_type", "x_position", "y_position", "name"}:
            # These columns are NOT NULL; refuse to clobber them with explicit None.
            continue
        setattr(node, k, v)
    db.commit()
    db.refresh(node)
    return node


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(
    node: schema.LitographyNode = Depends(require_node),
    db: Session = Depends(get_db),
):
    # Cascade: connections involving this node, then notes pinned to it,
    # then any plot-section links, then the node itself. The relationships
    # on LitographyNode aren't configured with ORM cascade rules, so we do
    # this explicitly. Mirrors `BaseModel.delete_node_with_associations`.
    db.query(schema.NodeConnection).filter(
        (schema.NodeConnection.output_node_id == node.id)
        | (schema.NodeConnection.input_node_id == node.id)
    ).delete(synchronize_session=False)
    db.query(schema.LitographyNotes).filter_by(linked_node_id=node.id).delete(
        synchronize_session=False
    )
    db.query(schema.LitographyNodeToPlotSection).filter_by(node_id=node.id).delete(
        synchronize_session=False
    )
    db.delete(node)
    db.commit()


@router.patch(
    "/storylines/{storyline_id}/nodes/positions", status_code=status.HTTP_204_NO_CONTENT
)
def update_node_positions(
    payload: NodePositionsUpdate,
    storyline: schema.Storyline = Depends(require_storyline),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-update positions for nodes in this storyline. Cross-storyline IDs
    in the body are rejected with 404 — callers must batch by storyline."""
    if not payload.positions:
        return
    ids = [p.id for p in payload.positions]
    stmt = select(schema.LitographyNode).where(schema.LitographyNode.id.in_(ids))
    nodes = {n.id: n for n in db.execute(stmt).scalars().all()}
    for pos in payload.positions:
        node = nodes.get(pos.id)
        if node is None or node.storyline_id != storyline.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
        node.x_position = pos.x
        node.y_position = pos.y
    db.commit()


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


@router.get(
    "/storylines/{storyline_id}/connections", response_model=list[ConnectionOut]
)
def list_connections(
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> list[schema.NodeConnection]:
    stmt = (
        select(schema.NodeConnection)
        .join(
            schema.LitographyNode,
            schema.LitographyNode.id == schema.NodeConnection.output_node_id,
        )
        .where(schema.LitographyNode.storyline_id == storyline.id)
        .order_by(schema.NodeConnection.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/storylines/{storyline_id}/connections",
    response_model=ConnectionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    payload: ConnectionCreate,
    storyline: schema.Storyline = Depends(require_storyline),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.NodeConnection:
    if payload.output_node_id == payload.input_node_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A node cannot connect to itself",
        )
    output = get_storyline_owned_node(db, user, payload.output_node_id)
    input_ = get_storyline_owned_node(db, user, payload.input_node_id)
    if output.storyline_id != storyline.id or input_.storyline_id != storyline.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Both nodes must belong to this storyline",
        )

    # Idempotent: a (output→input) pair returns the existing row instead of
    # creating a duplicate. Matches BaseModel.create_node_connection.
    existing = db.execute(
        select(schema.NodeConnection).where(
            schema.NodeConnection.output_node_id == output.id,
            schema.NodeConnection.input_node_id == input_.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    connection = schema.NodeConnection(
        output_node_id=output.id, input_node_id=input_.id
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = db.get(schema.NodeConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    output = db.get(schema.LitographyNode, connection.output_node_id)
    if output is None or output.storyline is None or output.storyline.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    db.delete(connection)
    db.commit()


# ---------------------------------------------------------------------------
# Plots & Plot Sections
# ---------------------------------------------------------------------------


@router.get("/storylines/{storyline_id}/plots", response_model=list[PlotOut])
def list_plots(
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> list[schema.LitographyPlot]:
    stmt = (
        select(schema.LitographyPlot)
        .where(schema.LitographyPlot.storyline_id == storyline.id)
        .order_by(schema.LitographyPlot.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/storylines/{storyline_id}/plots",
    response_model=PlotOut,
    status_code=status.HTTP_201_CREATED,
)
def create_plot(
    payload: PlotCreate,
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> schema.LitographyPlot:
    plot = schema.LitographyPlot(
        title=payload.title, description=payload.description, storyline_id=storyline.id
    )
    db.add(plot)
    db.commit()
    db.refresh(plot)
    return plot


@router.get("/plots/{plot_id}", response_model=PlotOut)
def get_plot(plot: schema.LitographyPlot = Depends(require_plot)) -> schema.LitographyPlot:
    return plot


@router.patch("/plots/{plot_id}", response_model=PlotOut)
def update_plot(
    payload: PlotUpdate,
    plot: schema.LitographyPlot = Depends(require_plot),
    db: Session = Depends(get_db),
) -> schema.LitographyPlot:
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(plot, k, v)
    db.commit()
    db.refresh(plot)
    return plot


@router.delete("/plots/{plot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plot(
    plot: schema.LitographyPlot = Depends(require_plot),
    db: Session = Depends(get_db),
):
    db.delete(plot)
    db.commit()


@router.get("/plots/{plot_id}/sections", response_model=list[PlotSectionOut])
def list_plot_sections(
    plot: schema.LitographyPlot = Depends(require_plot),
    db: Session = Depends(get_db),
) -> list[schema.LitographyPlotSection]:
    stmt = (
        select(schema.LitographyPlotSection)
        .where(schema.LitographyPlotSection.plot_id == plot.id)
        .order_by(schema.LitographyPlotSection.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/plots/{plot_id}/sections",
    response_model=PlotSectionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_plot_section(
    payload: PlotSectionCreate,
    plot: schema.LitographyPlot = Depends(require_plot),
    db: Session = Depends(get_db),
) -> schema.LitographyPlotSection:
    section = schema.LitographyPlotSection(
        plot_section_type=_coerce_section_type(payload.plot_section_type),
        plot_id=plot.id,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.get("/plot-sections/{section_id}", response_model=PlotSectionOut)
def get_plot_section(
    section_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyPlotSection:
    return _require_section(db, user, section_id)


@router.get("/plot-sections/{section_id}/nodes", response_model=list[NodeOut])
def list_nodes_in_plot_section(
    section_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schema.LitographyNode]:
    section = _require_section(db, user, section_id)
    plot = db.get(schema.LitographyPlot, section.plot_id)
    storyline_id = plot.storyline_id if plot else None
    stmt = (
        select(schema.LitographyNode)
        .join(
            schema.LitographyNodeToPlotSection,
            schema.LitographyNode.id == schema.LitographyNodeToPlotSection.node_id,
        )
        .where(
            schema.LitographyNodeToPlotSection.litography_plot_section_id == section_id,
            schema.LitographyNode.storyline_id == storyline_id,
        )
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/nodes/{node_id}/connections")
def list_node_connections(
    node: schema.LitographyNode = Depends(require_node),
    db: Session = Depends(get_db),
) -> dict[str, list]:
    """Connections grouped by direction.

    `input`: rows where this node is the input (i.e. arrows pointing in).
    `output`: rows where this node is the output (i.e. arrows pointing out).
    The desktop's side panel shows both."""
    inputs = db.execute(
        select(schema.NodeConnection).where(
            schema.NodeConnection.input_node_id == node.id
        )
    ).scalars().all()
    outputs = db.execute(
        select(schema.NodeConnection).where(
            schema.NodeConnection.output_node_id == node.id
        )
    ).scalars().all()

    def _dump(c: schema.NodeConnection) -> dict:
        return {
            "id": c.id,
            "output_node_id": c.output_node_id,
            "input_node_id": c.input_node_id,
            "sync_uuid": c.sync_uuid,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "deleted_at": c.deleted_at.isoformat() if c.deleted_at else None,
            "version": c.version,
        }

    return {"input": [_dump(c) for c in inputs], "output": [_dump(c) for c in outputs]}


@router.get("/nodes/{node_id}/sections", response_model=list[NodeSectionLinkOut])
def list_sections_for_node(
    node: schema.LitographyNode = Depends(require_node),
    db: Session = Depends(get_db),
) -> list[schema.LitographyNodeToPlotSection]:
    stmt = select(schema.LitographyNodeToPlotSection).where(
        schema.LitographyNodeToPlotSection.node_id == node.id
    )
    return list(db.execute(stmt).scalars().all())


@router.put("/nodes/{node_id}/section", response_model=NodeSectionLinkOut)
def set_node_section(
    payload: NodeSectionLink,
    node: schema.LitographyNode = Depends(require_node),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyNodeToPlotSection:
    """Idempotently move the node to exactly one section. Existing links for
    this node are dropped first; the chosen section must belong to a plot in
    the same storyline as the node."""
    section = _require_section(db, user, payload.plot_section_id)
    plot = db.get(schema.LitographyPlot, section.plot_id)
    if plot is None or plot.storyline_id != node.storyline_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Node and plot section must share a storyline",
        )

    db.query(schema.LitographyNodeToPlotSection).filter_by(node_id=node.id).delete(
        synchronize_session=False
    )
    link = schema.LitographyNodeToPlotSection(
        node_id=node.id, litography_plot_section_id=section.id
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.patch("/plot-sections/{section_id}", response_model=PlotSectionOut)
def update_plot_section(
    section_id: int,
    payload: PlotSectionUpdate,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyPlotSection:
    section = _require_section(db, user, section_id)
    data = payload.model_dump(exclude_unset=True)
    if "plot_section_type" in data and data["plot_section_type"] is not None:
        data["plot_section_type"] = _coerce_section_type(data["plot_section_type"])
    for k, v in data.items():
        if v is None:
            continue
        setattr(section, k, v)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/plot-sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plot_section(
    section_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    section = _require_section(db, user, section_id)
    db.delete(section)
    db.commit()


# ---------------------------------------------------------------------------
# Node ↔ Plot Section linkage
# ---------------------------------------------------------------------------


@router.post(
    "/plot-sections/{section_id}/nodes",
    response_model=NodeSectionLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def link_node_to_section(
    section_id: int,
    payload: NodeSectionLink,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyNodeToPlotSection:
    section = _require_section(db, user, section_id)
    node = get_storyline_owned_node(db, user, payload.node_id)
    plot = db.get(schema.LitographyPlot, section.plot_id)
    if plot is None or plot.storyline_id != node.storyline_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Node and plot section must share a storyline",
        )

    link = schema.LitographyNodeToPlotSection(
        node_id=node.id, litography_plot_section_id=section.id
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/node-section-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT
)
def unlink_node_from_section(
    link_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    link = db.get(schema.LitographyNodeToPlotSection, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    # Authorize via owning node OR owning section.
    if link.node_id is not None:
        node = db.get(schema.LitographyNode, link.node_id)
        if node is None or node.storyline is None or node.storyline.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Link not found"
            )
    elif link.litography_plot_section_id is not None:
        _require_section(db, user, link.litography_plot_section_id)
    db.delete(link)
    db.commit()


def _require_section(
    db: Session, user: schema.User, section_id: int
) -> schema.LitographyPlotSection:
    section = db.get(schema.LitographyPlotSection, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot section not found")
    plot = db.get(schema.LitographyPlot, section.plot_id)
    if plot is None or plot.storyline is None or plot.storyline.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot section not found")
    return section
