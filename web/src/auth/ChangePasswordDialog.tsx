import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { Input } from "@/components/Input";

import { useChangePassword } from "./auth";

const MIN_LENGTH = 8;

interface ChangePasswordDialogProps {
  onClose: () => void;
}

export function ChangePasswordDialog({ onClose }: ChangePasswordDialogProps) {
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const serverError =
    change.error instanceof ApiError
      ? typeof change.error.detail === "string"
        ? change.error.detail
        : "Could not change password"
      : change.error
        ? "Could not reach the server"
        : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLocalError(null);
    if (next.length < MIN_LENGTH) {
      setLocalError(`New password must be at least ${MIN_LENGTH} characters`);
      return;
    }
    if (next !== confirm) {
      setLocalError("New passwords do not match");
      return;
    }
    if (next === current) {
      setLocalError("New password must be different from the current one");
      return;
    }
    try {
      await change.mutateAsync({ current_password: current, new_password: next });
      setDone(true);
    } catch {
      // useMutation's `error` surfaces via `serverError`.
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
        aria-labelledby="change-password-title"
        className="w-full max-w-sm rounded-md border border-slate-700 bg-canvas-panel p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="change-password-title" className="mb-3 text-base font-semibold">
          Change password
        </h2>

        {done ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-slate-300">
              Password updated. Other sessions for your account have been signed out.
            </p>
            <div className="flex justify-end">
              <Button size="sm" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-3">
            <Field label="Current password" htmlFor="current-password">
              <Input
                id="current-password"
                type="password"
                autoComplete="current-password"
                autoFocus
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                disabled={change.isPending}
              />
            </Field>
            <Field
              label="New password"
              htmlFor="new-password"
              hint={`At least ${MIN_LENGTH} characters`}
            >
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                disabled={change.isPending}
              />
            </Field>
            <Field
              label="Confirm new password"
              htmlFor="confirm-password"
              error={localError ?? serverError}
            >
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                disabled={change.isPending}
              />
            </Field>
            <div className="flex justify-end gap-2 pt-1">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={onClose}
                disabled={change.isPending}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={change.isPending || !current || !next || !confirm}
              >
                {change.isPending ? "Updating…" : "Update password"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
