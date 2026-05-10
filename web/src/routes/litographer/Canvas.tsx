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
  useConnections,
  useCreateConnection,
  useCreateNode,
  useDeleteConnection,
  useDeleteNode,
  useNodes,
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

  const createNode = useCreateNode(storylineId);
  const deleteNode = useDeleteNode(storylineId);
  const createConnection = useCreateConnection(storylineId);
  const deleteConnection = useDeleteConnection(storylineId);
  const positionFlush = usePositionFlush(storylineId);

  const [activeSectionId, setActiveSectionId] = useState<number | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  // React Flow holds its own copy of nodes/edges so it can drag without
  // round-tripping the server on every frame. We rebuild that local copy
  // whenever the server data changes (ids stay stable, so React Flow's
  // diffing remains cheap).
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);

  useEffect(() => {
    if (!nodesQ.data) return;
    setRfNodes(nodesQ.data.map(toReactFlowNode));
  }, [nodesQ.data]);

  useEffect(() => {
    if (!connectionsQ.data) return;
    setRfEdges(connectionsQ.data.map(toReactFlowEdge));
  }, [connectionsQ.data]);

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
    (nodeType: NodeType) => {
      // Drop the new node near the visible center. With pan/zoom this
      // approximation is fine for the "+" button affordance; right-click in
      // the canvas would let us use the click position, deferred to a later
      // pass.
      createNode.mutate({
        node_type: nodeType,
        name: titleFor(nodeType),
        x_position: 100 + Math.random() * 200,
        y_position: 100 + Math.random() * 200,
      });
    },
    [createNode],
  );

  const selectedNode = useMemo(() => {
    if (selectedNodeId == null || !nodesQ.data) return null;
    return nodesQ.data.find((n) => n.id === selectedNodeId) ?? null;
  }, [selectedNodeId, nodesQ.data]);

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
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
