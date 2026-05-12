import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type OnConnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  useAddNodeToSection,
  useConnections,
  useCreateConnection,
  useCreateNode,
  useDeleteConnection,
  useDeleteNode,
  useNodes,
  useNodesInSection,
} from "@/api/litographer";
import type { LitographyNode, NodeType } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { useWorkspace } from "@/lib/workspace";

import { NodeEditPanel } from "./NodeEditPanel";
import { PlotSectionTabs } from "./PlotSectionTabs";
import { StoryNode, type StoryNodeData } from "./nodes/StoryNode";
import { usePositionFlush } from "./state";

const NODE_TYPES = { story: StoryNode } as const;

export function LitographerPage() {
  const { storylineId } = useWorkspace();

  if (storylineId == null) {
    return (
      <Card>
        <p className="text-sm text-slate-400">
          Pick or create a storyline in the top bar to start drafting.
        </p>
      </Card>
    );
  }

  return (
    <ReactFlowProvider>
      <Inner storylineId={storylineId} />
    </ReactFlowProvider>
  );
}

function Inner({ storylineId }: { storylineId: number }) {
  const nodesQ = useNodes(storylineId);
  const connectionsQ = useConnections(storylineId);

  const [activeSectionId, setActiveSectionId] = useState<number | null>(null);
  const sectionNodesQ = useNodesInSection(activeSectionId);

  const createNode = useCreateNode(storylineId);
  const deleteNode = useDeleteNode(storylineId);
  const createConnection = useCreateConnection(storylineId);
  const deleteConnection = useDeleteConnection(storylineId);
  const addNodeToSection = useAddNodeToSection(storylineId);
  const positionFlush = usePositionFlush(storylineId);

  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  // Visible-node set: when a section is selected, show only nodes in that
  // section. Falling back to all-storyline nodes happens during the brief
  // window before the default section auto-creates on first load.
  const visibleNodes = useMemo(() => {
    if (activeSectionId != null && sectionNodesQ.data) return sectionNodesQ.data;
    return nodesQ.data ?? [];
  }, [activeSectionId, sectionNodesQ.data, nodesQ.data]);

  // React Flow holds its own copy of nodes/edges so it can drag without
  // round-tripping the server on every frame. We rebuild that local copy
  // whenever the server data changes (ids stay stable, so React Flow's
  // diffing remains cheap).
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);

  useEffect(() => {
    setRfNodes(visibleNodes.map(toReactFlowNode));
  }, [visibleNodes]);

  // Filter edges to only those whose endpoints are both in the visible set.
  // Otherwise dragging a connection between sections would render dangling
  // edges anchored to nothing.
  useEffect(() => {
    if (!connectionsQ.data) return;
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    setRfEdges(
      connectionsQ.data
        .filter(
          (c) =>
            visibleIds.has(c.output_node_id) && visibleIds.has(c.input_node_id),
        )
        .map(toReactFlowEdge),
    );
  }, [connectionsQ.data, visibleNodes]);

  // Keep the selected-node ring in sync with selection state so React Flow
  // re-renders the node component with the right `selected` flag.
  useEffect(() => {
    setRfNodes((nodes) =>
      nodes.map((n) => ({ ...n, selected: Number(n.id) === selectedNodeId })),
    );
  }, [selectedNodeId]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // Apply locally first so React Flow renders smoothly.
      setRfNodes((current) => applyNodeChanges(changes, current));
      for (const change of changes) {
        if (change.type === "position" && change.position && !change.dragging) {
          positionFlush.enqueue(
            Number(change.id),
            change.position.x,
            change.position.y,
          );
        }
        if (change.type === "select") {
          setSelectedNodeId(change.selected ? Number(change.id) : null);
        }
        if (change.type === "remove") {
          deleteNode.mutate(Number(change.id));
        }
      }
    },
    [positionFlush, deleteNode],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setRfEdges((current) => applyEdgeChanges(changes, current));
      for (const change of changes) {
        if (change.type === "remove") {
          deleteConnection.mutate(Number(change.id));
        }
      }
    },
    [deleteConnection],
  );

  const onConnect: OnConnect = useCallback(
    (conn: Connection) => {
      if (!conn.source || !conn.target) return;
      if (conn.source === conn.target) return; // server rejects self-loops too
      createConnection.mutate({
        output_node_id: Number(conn.source),
        input_node_id: Number(conn.target),
      });
    },
    [createConnection],
  );

  const onAddNode = useCallback(
    async (nodeType: NodeType) => {
      // Drop the new node near the visible center. With pan/zoom this
      // approximation is fine for the "+" button affordance; right-click in
      // the canvas would let us use the click position, deferred to a later
      // pass.
      const created = await createNode.mutateAsync({
        node_type: nodeType,
        name: titleFor(nodeType),
        x_position: 100 + Math.random() * 200,
        y_position: 100 + Math.random() * 200,
      });
      // If a section is active, link the new node into it so the section
      // tabs actually filter what you just added. Without this, new nodes
      // would land in "all" but never show up under any section tab.
      if (activeSectionId != null) {
        try {
          await addNodeToSection.mutateAsync({
            sectionId: activeSectionId,
            nodeId: created.id,
          });
        } catch {
          // Server already returns 201 if the link existed; we treat any
          // failure as benign and let the next refresh sort it out.
        }
      }
    },
    [createNode, addNodeToSection, activeSectionId],
  );

  const selectedNode = useMemo(() => {
    if (selectedNodeId == null) return null;
    // Look in the visible set first so the side panel only opens for nodes
    // that the user can actually see. Switching sections clears stale
    // selections without an explicit reset.
    return visibleNodes.find((n) => n.id === selectedNodeId) ?? null;
  }, [selectedNodeId, visibleNodes]);

  // If the user switches sections, drop a selection that's no longer visible.
  useEffect(() => {
    if (selectedNodeId == null) return;
    const stillVisible = visibleNodes.some((n) => n.id === selectedNodeId);
    if (!stillVisible) setSelectedNodeId(null);
  }, [visibleNodes, selectedNodeId]);

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      <div className="mb-2 rounded-md border border-amber-700/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200 md:hidden">
        Litographer is designed for a mouse and a larger screen. Open this view
        on a desktop for the best experience.
      </div>
      <PlotSectionTabs
        storylineId={storylineId}
        selectedSectionId={activeSectionId}
        onSelect={setActiveSectionId}
      />

      <div className="flex flex-1 min-h-0">
        <div className="relative flex-1">
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={() => positionFlush.flushNow()}
            nodeTypes={NODE_TYPES}
            fitView
            colorMode="dark"
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={24} size={1} />
            <Controls className="!bg-canvas-panel !border-slate-800" />
            <MiniMap
              pannable
              zoomable
              maskColor="rgba(8, 16, 32, 0.6)"
              className="!bg-canvas-panel !border-slate-800"
            />
          </ReactFlow>

          <NodePalette onAdd={onAddNode} disabled={createNode.isPending} />
        </div>

        {selectedNode ? (
          <NodeEditPanel
            node={selectedNode}
            storylineId={storylineId}
            onClose={() => setSelectedNodeId(null)}
          />
        ) : null}
      </div>
    </div>
  );
}

function NodePalette({
  onAdd,
  disabled,
}: {
  onAdd: (type: NodeType) => void;
  disabled: boolean;
}) {
  const types: NodeType[] = [
    "exposition",
    "action",
    "reaction",
    "twist",
    "development",
    "other",
  ];
  return (
    <div className="absolute left-3 top-3 z-10 flex flex-col gap-1 rounded-md border border-slate-800 bg-canvas-panel p-2 shadow-lg">
      <span className="px-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Add node
      </span>
      {types.map((t) => (
        <Button
          key={t}
          size="sm"
          variant="ghost"
          onClick={() => onAdd(t)}
          disabled={disabled}
          className="!justify-start text-xs"
        >
          {titleFor(t)}
        </Button>
      ))}
    </div>
  );
}

function toReactFlowNode(node: LitographyNode): Node<StoryNodeData> {
  return {
    id: String(node.id),
    type: "story",
    position: { x: node.x_position, y: node.y_position },
    data: {
      label: node.name,
      nodeType: node.node_type,
      description: node.description,
      selected: false,
    },
  };
}

function toReactFlowEdge(c: { id: number; output_node_id: number; input_node_id: number }): Edge {
  return {
    id: String(c.id),
    source: String(c.output_node_id),
    target: String(c.input_node_id),
    animated: false,
    style: { stroke: "#94a3b8", strokeWidth: 1.5 },
  };
}

function titleFor(nodeType: NodeType): string {
  return nodeType.charAt(0).toUpperCase() + nodeType.slice(1);
}
