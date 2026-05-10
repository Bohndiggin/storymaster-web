import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  Navigate,
  useNavigate,
  useOutletContext,
  useParams,
} from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  useActorsForSetting,
  useArc,
  useArcTypes,
  useArcs,
  useCreateArc,
  useDeleteArc,
  useUpdateArc,
  type ArcWritePayload,
} from "@/api/arcs";
import { Button } from "@/components/Button";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { Field } from "@/components/Field";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Textarea } from "@/components/Textarea";
import { actorDisplayName } from "@/lib/names";
import { cn } from "@/lib/cn";

import type { ArcOutletContext } from "./Index";
import { ArcPointsList } from "./ArcPoints";

interface FormState {
  title: string;
  description: string;
  arc_type_id: string; // string while in the form, coerced on submit
  actor_ids: number[];
}

const EMPTY: FormState = {
  title: "",
  description: "",
  arc_type_id: "",
  actor_ids: [],
};

export function ArcEditPage() {
  const { id } = useParams<{ id: string }>();
  const isNew = id === "new";
  const arcId = !isNew && id ? Number(id) : null;
  const { storylineId, settingId } = useOutletContext<ArcOutletContext>();
  const navigate = useNavigate();

  const arc = useArc(arcId);
  const arcTypes = useArcTypes(settingId);
  const actors = useActorsForSetting(settingId);

  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  // Hydrate from server when an existing arc loads. Note: the API doesn't
  // return actor_ids today (the join table sits on the server side); we
  // start the picker empty when editing, and "Save" will replace links if
  // the user touches it. Surface this in the UI (see hint below) so it
  // doesn't surprise editors.
  useEffect(() => {
    if (isNew) {
      setForm({
        ...EMPTY,
        arc_type_id: arcTypes.data?.[0]?.id ? String(arcTypes.data[0].id) : "",
      });
    } else if (arc.data) {
      setForm({
        title: arc.data.title ?? "",
        description: arc.data.description ?? "",
        arc_type_id: String(arc.data.arc_type_id),
        actor_ids: [],
      });
    }
  }, [arc.data, arcTypes.data, isNew]);

  const create = useCreateArc(storylineId);
  const update = useUpdateArc(storylineId);
  const remove = useDeleteArc(storylineId);

  const arcs = useArcs(storylineId);

  if (!isNew && arcId == null) return <Navigate to="/arcs" replace />;

  if (settingId == null && isNew) {
    return (
      <Card>
        <p className="text-sm text-slate-400">
          New arcs need an arc type, which lives under a setting. Pick or
          create a setting in the top bar.
        </p>
      </Card>
    );
  }

  if (arcTypes.isLoading || (!isNew && arc.isLoading)) {
    return <p className="text-sm text-slate-400">Loading…</p>;
  }
  if (arcTypes.error) {
    return <p className="text-sm text-red-400">Failed to load arc types.</p>;
  }
  if (!isNew && arc.error) {
    return <p className="text-sm text-red-400">Could not load this arc.</p>;
  }

  if ((arcTypes.data?.length ?? 0) === 0) {
    return (
      <Card>
        <p className="text-sm text-slate-400">
          No arc types defined for this setting yet.{" "}
          <button
            className="text-accent hover:underline"
            onClick={() => navigate("/arcs/types")}
            type="button"
          >
            Create one →
          </button>
        </p>
      </Card>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.title.trim() || !form.arc_type_id) {
      setError("Title and type are required.");
      return;
    }
    const payload: ArcWritePayload = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      arc_type_id: Number(form.arc_type_id),
      actor_ids: form.actor_ids,
    };
    try {
      if (isNew) {
        const created = await create.mutateAsync(payload);
        navigate(`/arcs/${created.id}`, { replace: true });
      } else if (arcId != null) {
        await update.mutateAsync({ id: arcId, ...payload });
      }
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Save failed.");
    }
  };

  const onDelete = async () => {
    if (arcId == null) return;
    if (!window.confirm("Delete this arc and all its points?")) return;
    await remove.mutateAsync(arcId);
    // Navigate to the next remaining arc, or the home view.
    const remaining = (arcs.data ?? []).filter((a) => a.id !== arcId);
    navigate(remaining.length ? `/arcs/${remaining[0].id}` : "/arcs", {
      replace: true,
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{isNew ? "New arc" : arc.data?.title || "Arc"}</CardTitle>
        </CardHeader>
        <form onSubmit={submit} className="grid grid-cols-2 gap-4">
          <Field label="Title" htmlFor="title" className="col-span-2">
            <Input
              id="title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              autoFocus={isNew}
            />
          </Field>
          <Field label="Type" htmlFor="arc_type_id">
            <Select
              id="arc_type_id"
              value={form.arc_type_id}
              onChange={(e) => setForm({ ...form, arc_type_id: e.target.value })}
            >
              {arcTypes.data!.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Description" htmlFor="description" className="col-span-2">
            <Textarea
              id="description"
              rows={4}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <Field
            label="Linked actors"
            className="col-span-2"
            hint={
              isNew
                ? "Select one or more actors this arc follows."
                : "Editing actor links replaces all current links on save. Leave empty to keep existing links untouched server-side — the API ignores omitted fields."
            }
          >
            <ActorMultiPicker
              actors={actors.data ?? []}
              loading={actors.isLoading}
              selected={form.actor_ids}
              onChange={(ids) => setForm({ ...form, actor_ids: ids })}
            />
          </Field>
          <div className="col-span-2 flex items-center justify-between pt-2">
            <div>
              {!isNew ? (
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  onClick={onDelete}
                  disabled={remove.isPending}
                >
                  Delete arc
                </Button>
              ) : null}
            </div>
            <div className="flex items-center gap-3">
              {error ? (
                <span className="text-xs text-red-400">{error}</span>
              ) : null}
              <Button type="submit" disabled={create.isPending || update.isPending}>
                {isNew ? "Create" : "Save"}
              </Button>
            </div>
          </div>
        </form>
      </Card>

      {!isNew && arcId != null ? (
        <ArcPointsList arcId={arcId} storylineId={storylineId} />
      ) : null}
    </div>
  );
}

interface ActorMultiPickerProps {
  actors: { id: number; [k: string]: unknown }[];
  loading: boolean;
  selected: number[];
  onChange: (ids: number[]) => void;
}

function ActorMultiPicker({
  actors,
  loading,
  selected,
  onChange,
}: ActorMultiPickerProps) {
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  if (loading) {
    return <p className="text-xs text-slate-500">Loading actors…</p>;
  }
  if (actors.length === 0) {
    return (
      <p className="text-xs text-slate-500">
        No actors in this setting yet — create one in Lorekeeper first.
      </p>
    );
  }

  const toggle = (id: number) => {
    if (selectedSet.has(id)) {
      onChange(selected.filter((x) => x !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  return (
    <div className="flex flex-wrap gap-2 rounded-md border border-slate-700 bg-canvas p-2">
      {actors.map((actor) => {
        const active = selectedSet.has(actor.id);
        return (
          <button
            key={actor.id}
            type="button"
            onClick={() => toggle(actor.id)}
            className={cn(
              "rounded-full px-3 py-1 text-xs transition-colors",
              active
                ? "bg-accent text-slate-950"
                : "bg-canvas-raised text-slate-300 hover:bg-slate-800",
            )}
          >
            {actorDisplayName(actor as never)}
          </button>
        );
      })}
    </div>
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
