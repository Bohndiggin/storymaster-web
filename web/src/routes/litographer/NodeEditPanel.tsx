import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { useDeleteNode, useUpdateNode } from "@/api/litographer";
import type { LitographyNode, NodeType } from "@/api/types";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Textarea } from "@/components/Textarea";

const NODE_TYPES: NodeType[] = [
  "exposition",
  "action",
  "reaction",
  "twist",
  "development",
  "other",
];

interface Props {
  node: LitographyNode;
  storylineId: number;
  onClose: () => void;
}

export function NodeEditPanel({ node, storylineId, onClose }: Props) {
  const update = useUpdateNode(storylineId);
  const remove = useDeleteNode(storylineId);

  const [name, setName] = useState(node.name);
  const [description, setDescription] = useState(node.description ?? "");
  const [nodeType, setNodeType] = useState<NodeType>(node.node_type);
  const [error, setError] = useState<string | null>(null);

  // Re-hydrate when the selected node changes (clicking a different node
  // shouldn't carry the prior node's pending edits).
  useEffect(() => {
    setName(node.name);
    setDescription(node.description ?? "");
    setNodeType(node.node_type);
    setError(null);
  }, [node.id, node.name, node.description, node.node_type]);

  const persist = async (patch: Partial<{ name: string; description: string | null; node_type: NodeType }>) => {
    setError(null);
    try {
      await update.mutateAsync({ id: node.id, ...patch });
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Save failed.");
    }
  };

  const onDelete = async () => {
    if (!window.confirm(`Delete node "${node.name}" and its connections?`)) return;
    await remove.mutateAsync(node.id);
    onClose();
  };

  return (
    <aside className="flex h-full w-80 flex-shrink-0 flex-col gap-4 border-l border-slate-800 bg-canvas-panel p-4">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Node
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-slate-400 hover:text-slate-100"
        >
          Close ✕
        </button>
      </header>

      <Field label="Name" htmlFor="np-name">
        <Input
          id="np-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => {
            if (name !== node.name) persist({ name });
          }}
        />
      </Field>

      <Field label="Type" htmlFor="np-type">
        <Select
          id="np-type"
          value={nodeType}
          onChange={(e) => {
            const next = e.target.value as NodeType;
            setNodeType(next);
            persist({ node_type: next });
          }}
        >
          {NODE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
      </Field>

      <Field label="Description" htmlFor="np-desc">
        <Textarea
          id="np-desc"
          rows={6}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() => {
            if (description !== (node.description ?? "")) {
              persist({ description: description || null });
            }
          }}
        />
      </Field>

      <div className="text-xs text-slate-500">
        Position: {node.x_position.toFixed(0)}, {node.y_position.toFixed(0)}
      </div>

      {error ? <p className="text-xs text-red-400">{error}</p> : null}

      <div className="mt-auto flex justify-between">
        <Button
          type="button"
          variant="danger"
          size="sm"
          onClick={onDelete}
          disabled={remove.isPending}
        >
          Delete
        </Button>
      </div>
    </aside>
  );
}
