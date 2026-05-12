import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
} from "react";

import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Textarea } from "@/components/Textarea";
import { cn } from "@/lib/cn";

interface WorkspaceItem {
  id: number;
  name: string | null;
}

interface WorkspacePickerProps<T extends WorkspaceItem> {
  label: string;
  items: T[] | undefined;
  isLoading: boolean;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  fallbackPrefix: string;
  onCreate: (payload: { name: string; description?: string }) => Promise<T>;
  isCreating: boolean;
  onRename: (id: number, name: string) => Promise<unknown>;
  onDelete: (id: number) => Promise<unknown>;
  isMutating: boolean;
}

export function WorkspacePicker<T extends WorkspaceItem>({
  label,
  items,
  isLoading,
  selectedId,
  onSelect,
  fallbackPrefix,
  onCreate,
  isCreating,
  onRename,
  onDelete,
  isMutating,
}: WorkspacePickerProps<T>) {
  const [open, setOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (isLoading) return null;

  const hasItems = !!items && items.length > 0;

  function labelFor(item: WorkspaceItem): string {
    return item.name ?? `${fallbackPrefix} #${item.id}`;
  }

  async function handleCreate(payload: { name: string; description?: string }) {
    const created = await onCreate(payload);
    onSelect(created.id);
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative flex items-center gap-1">
      {hasItems ? (
        <Select
          className="h-8 w-44 text-xs"
          value={selectedId ?? ""}
          onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
          aria-label={`Active ${label.toLowerCase()}`}
        >
          {items!.map((item) => (
            <option key={item.id} value={item.id}>
              {labelFor(item)}
            </option>
          ))}
        </Select>
      ) : (
        <span className="text-xs text-slate-500">No {label.toLowerCase()}s</span>
      )}
      <Button
        size="sm"
        variant={hasItems ? "ghost" : "secondary"}
        className="h-8 px-2"
        onClick={() => setOpen((v) => !v)}
        aria-label={`New ${label.toLowerCase()}`}
        aria-expanded={open}
      >
        {hasItems ? "+" : `+ New ${label.toLowerCase()}`}
      </Button>
      {hasItems ? (
        <Button
          size="sm"
          variant="ghost"
          className="h-8 px-2"
          onClick={() => setManageOpen(true)}
          aria-label={`Manage ${label.toLowerCase()}s`}
          title={`Manage ${label.toLowerCase()}s`}
        >
          <GearIcon />
        </Button>
      ) : null}
      {open ? (
        <CreatePopover
          label={label}
          isCreating={isCreating}
          onCancel={() => setOpen(false)}
          onSubmit={handleCreate}
        />
      ) : null}
      {manageOpen && items ? (
        <ManageDialog
          label={label}
          items={items}
          labelFor={labelFor}
          selectedId={selectedId}
          isMutating={isMutating}
          onRename={onRename}
          onDelete={async (id) => {
            await onDelete(id);
            if (id === selectedId) {
              // The active item is gone; fall back to whatever's left.
              const remaining = items.filter((i) => i.id !== id);
              onSelect(remaining[0]?.id ?? null);
            }
          }}
          onClose={() => setManageOpen(false)}
        />
      ) : null}
    </div>
  );
}

function GearIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M8 5.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5zM8 7a1 1 0 110 2 1 1 0 010-2z" />
      <path d="M6.94 1.5a1 1 0 011.06 0l.74.43a1 1 0 01.32.31l.46.74a1 1 0 00.86.5l.87-.01a1 1 0 01.93.55l.42.79a1 1 0 01.1.44l-.04.86a1 1 0 00.43.86l.7.5a1 1 0 01.39 1.02l-.2.85a1 1 0 01-.2.4l-.57.65a1 1 0 000 1.31l.57.65a1 1 0 01.2.4l.2.85a1 1 0 01-.4 1.03l-.69.5a1 1 0 00-.43.85l.04.86a1 1 0 01-.1.44l-.42.79a1 1 0 01-.93.55l-.87-.01a1 1 0 00-.86.5l-.46.73a1 1 0 01-.32.32l-.74.43a1 1 0 01-1.06 0l-.74-.43a1 1 0 01-.32-.32l-.46-.73a1 1 0 00-.86-.5l-.87.01a1 1 0 01-.93-.55l-.42-.79a1 1 0 01-.1-.44l.04-.86a1 1 0 00-.43-.85l-.7-.5a1 1 0 01-.39-1.03l.2-.85a1 1 0 01.2-.4l.57-.65a1 1 0 000-1.31l-.57-.65a1 1 0 01-.2-.4l-.2-.85a1 1 0 01.4-1.02l.69-.5a1 1 0 00.43-.86l-.04-.86a1 1 0 01.1-.44l.42-.79a1 1 0 01.93-.55l.87.01a1 1 0 00.86-.5l.46-.74a1 1 0 01.32-.31l.74-.43z" opacity="0.35" />
    </svg>
  );
}

interface CreatePopoverProps {
  label: string;
  isCreating: boolean;
  onCancel: () => void;
  onSubmit: (payload: { name: string; description?: string }) => Promise<void>;
}

function CreatePopover({ label, isCreating, onCancel, onSubmit }: CreatePopoverProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  const descriptionId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Name is required");
      return;
    }
    setError(null);
    try {
      await onSubmit({
        name: trimmed,
        description: description.trim() || undefined,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        "absolute right-0 top-9 z-20 w-72 rounded-md border border-slate-700 bg-canvas-panel p-3 shadow-lg",
        "flex flex-col gap-2",
      )}
    >
      <label htmlFor={nameId} className="text-xs font-medium uppercase tracking-wide text-slate-400">
        New {label.toLowerCase()}
      </label>
      <Input
        ref={inputRef}
        id={nameId}
        className="h-8 text-sm"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name"
        disabled={isCreating}
      />
      <Textarea
        id={descriptionId}
        rows={2}
        className="p-2 text-xs"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        disabled={isCreating}
      />
      {error ? <p className="text-xs text-red-400">{error}</p> : null}
      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={isCreating}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={isCreating || !name.trim()}>
          {isCreating ? "Creating…" : "Create"}
        </Button>
      </div>
    </form>
  );
}

interface ManageDialogProps<T extends WorkspaceItem> {
  label: string;
  items: T[];
  labelFor: (item: WorkspaceItem) => string;
  selectedId: number | null;
  isMutating: boolean;
  onRename: (id: number, name: string) => Promise<unknown>;
  onDelete: (id: number) => Promise<unknown>;
  onClose: () => void;
}

function ManageDialog<T extends WorkspaceItem>({
  label,
  items,
  labelFor,
  selectedId,
  isMutating,
  onRename,
  onDelete,
  onClose,
}: ManageDialogProps<T>) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleRename(id: number, name: string) {
    setError(null);
    try {
      await onRename(id, name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rename failed");
    }
  }

  async function handleDelete(item: WorkspaceItem) {
    setError(null);
    const noun = label.toLowerCase();
    const warning =
      noun === "storyline"
        ? "This permanently deletes the storyline and everything in it (plot nodes, arcs, notes)."
        : "This permanently deletes the setting and all of its Lorekeeper entries (characters, places, factions, lore).";
    if (
      !window.confirm(
        `Delete ${noun} "${labelFor(item)}"?\n\n${warning}\n\nThis cannot be undone.`,
      )
    ) {
      return;
    }
    try {
      await onDelete(item.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="manage-workspace-title"
        className="flex max-h-[80vh] w-full max-w-md flex-col overflow-hidden rounded-md border border-slate-700 bg-canvas-panel shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <h2 id="manage-workspace-title" className="text-base font-semibold">
            Manage {label.toLowerCase()}s
          </h2>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {error ? <p className="mb-2 text-xs text-red-400">{error}</p> : null}
          <ul className="flex flex-col divide-y divide-slate-800">
            {items.map((item) => (
              <ManageRow
                key={item.id}
                item={item}
                initialName={labelFor(item)}
                isActive={item.id === selectedId}
                disabled={isMutating}
                onRename={(name) => handleRename(item.id, name)}
                onDelete={() => handleDelete(item)}
              />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

interface ManageRowProps {
  item: WorkspaceItem;
  initialName: string;
  isActive: boolean;
  disabled: boolean;
  onRename: (name: string) => Promise<void>;
  onDelete: () => Promise<void>;
}

function ManageRow({
  item,
  initialName,
  isActive,
  disabled,
  onRename,
  onDelete,
}: ManageRowProps) {
  const [name, setName] = useState(item.name ?? "");

  function commitRename() {
    const trimmed = name.trim();
    if (!trimmed || trimmed === (item.name ?? "")) {
      // Nothing meaningful changed; snap back to whatever the canonical
      // display name is so the field isn't left blank.
      setName(item.name ?? "");
      return;
    }
    onRename(trimmed);
  }

  return (
    <li className="flex items-center gap-2 py-2">
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={commitRename}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            (e.target as HTMLInputElement).blur();
          }
        }}
        placeholder={initialName}
        disabled={disabled}
        className="h-8 flex-1 text-sm"
        aria-label={`Rename ${initialName}`}
      />
      {isActive ? (
        <span className="rounded bg-canvas-raised px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
          active
        </span>
      ) : null}
      <Button
        size="sm"
        variant="danger"
        className="h-8 px-2"
        onClick={onDelete}
        disabled={disabled}
        aria-label={`Delete ${initialName}`}
      >
        Delete
      </Button>
    </li>
  );
}
