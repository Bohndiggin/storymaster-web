import { type FormEvent, useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  useArcTypes,
  useCreateArcType,
  useDeleteArcType,
  useUpdateArcType,
} from "@/api/arcs";
import type { ArcType } from "@/api/types";
import { Button } from "@/components/Button";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { Field } from "@/components/Field";
import { Input } from "@/components/Input";
import { Textarea } from "@/components/Textarea";

import type { ArcOutletContext } from "./Index";

export function ArcTypeManagerPage() {
  const { settingId } = useOutletContext<ArcOutletContext>();

  if (settingId == null) {
    return (
      <Card>
        <p className="text-sm text-slate-400">
          Pick a setting in the top bar to manage its arc types.
        </p>
      </Card>
    );
  }

  return <Inner settingId={settingId} />;
}

function Inner({ settingId }: { settingId: number }) {
  const types = useArcTypes(settingId);
  const create = useCreateArcType(settingId);

  const [draftName, setDraftName] = useState("");
  const [draftDesc, setDraftDesc] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!draftName.trim()) {
      setError("Name is required.");
      return;
    }
    try {
      await create.mutateAsync({
        name: draftName.trim(),
        description: draftDesc.trim() || null,
      });
      setDraftName("");
      setDraftDesc("");
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Save failed.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>New arc type</CardTitle>
        </CardHeader>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <Field label="Name" htmlFor="type-name">
            <Input
              id="type-name"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              placeholder="e.g. Growth, Fall, Flat"
            />
          </Field>
          <Field label="Description" htmlFor="type-desc">
            <Textarea
              id="type-desc"
              rows={2}
              value={draftDesc}
              onChange={(e) => setDraftDesc(e.target.value)}
            />
          </Field>
          <div className="flex items-center justify-between">
            {error ? <span className="text-xs text-red-400">{error}</span> : <span />}
            <Button type="submit" disabled={create.isPending}>
              Create type
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Existing types</CardTitle>
        </CardHeader>
        {types.isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : types.error ? (
          <p className="text-sm text-red-400">Failed to load arc types.</p>
        ) : types.data && types.data.length > 0 ? (
          <ul className="flex flex-col divide-y divide-slate-800">
            {types.data.map((t) => (
              <ArcTypeRow key={t.id} settingId={settingId} arcType={t} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">No arc types defined yet.</p>
        )}
      </Card>
    </div>
  );
}

function ArcTypeRow({
  settingId,
  arcType,
}: {
  settingId: number;
  arcType: ArcType;
}) {
  const update = useUpdateArcType(settingId);
  const remove = useDeleteArcType(settingId);

  const [name, setName] = useState(arcType.name);
  const [desc, setDesc] = useState(arcType.description ?? "");
  const [error, setError] = useState<string | null>(null);

  // Re-hydrate if the canonical row updates from elsewhere.
  useEffect(() => {
    setName(arcType.name);
    setDesc(arcType.description ?? "");
  }, [arcType]);

  const persistIfChanged = async () => {
    setError(null);
    const patch: { name?: string; description?: string | null } = {};
    if (name !== arcType.name) patch.name = name;
    if (desc !== (arcType.description ?? "")) patch.description = desc || null;
    if (Object.keys(patch).length === 0) return;
    try {
      await update.mutateAsync({ id: arcType.id, ...patch });
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Save failed.");
    }
  };

  const onDelete = async () => {
    if (
      !window.confirm(
        `Delete arc type "${arcType.name}"? This will also delete every arc that uses it.`,
      )
    ) {
      return;
    }
    await remove.mutateAsync(arcType.id);
  };

  return (
    <li className="grid grid-cols-12 items-start gap-2 py-3">
      <div className="col-span-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={persistIfChanged}
          className="w-full bg-transparent text-sm font-medium text-slate-100 focus:outline-none"
        />
      </div>
      <div className="col-span-7">
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          onBlur={persistIfChanged}
          rows={1}
          className="w-full resize-none bg-transparent text-sm text-slate-300 focus:outline-none"
          placeholder="Optional description"
        />
        {error ? <p className="text-xs text-red-400">{error}</p> : null}
      </div>
      <div className="col-span-2 flex justify-end">
        <Button
          variant="danger"
          size="sm"
          onClick={onDelete}
          disabled={remove.isPending}
        >
          Delete
        </Button>
      </div>
    </li>
  );
}

function formatApiError(err: ApiError): string {
  const detail = err.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) =>
        typeof d === "object" && d && "msg" in d
          ? (d as { msg: string }).msg
          : String(d),
      )
      .join("; ");
  }
  return `Error ${err.status}`;
}
