import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useSettings, useStorylines } from "@/api/storylines";

interface WorkspaceContextValue {
  storylineId: number | null;
  settingId: number | null;
  setStorylineId: (id: number | null) => void;
  setSettingId: (id: number | null) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

const STORAGE_KEY = "storymaster.workspace";

interface PersistedWorkspace {
  storylineId: number | null;
  settingId: number | null;
}

function readPersisted(): PersistedWorkspace {
  if (typeof window === "undefined") return { storylineId: null, settingId: null };
  try {
    const raw = window.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return { storylineId: null, settingId: null };
    const parsed = JSON.parse(raw) as PersistedWorkspace;
    return {
      storylineId: typeof parsed.storylineId === "number" ? parsed.storylineId : null,
      settingId: typeof parsed.settingId === "number" ? parsed.settingId : null,
    };
  } catch {
    return { storylineId: null, settingId: null };
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const persisted = readPersisted();
  const [storylineId, setStorylineId] = useState<number | null>(persisted.storylineId);
  const [settingId, setSettingId] = useState<number | null>(persisted.settingId);

  const storylines = useStorylines();
  const settings = useSettings();

  // Auto-pick the first option on initial load if none persisted, and drop
  // ids that no longer exist (deleted by another session, etc.).
  useEffect(() => {
    if (!storylines.data) return;
    if (storylineId == null && storylines.data.length > 0) {
      setStorylineId(storylines.data[0].id);
    } else if (
      storylineId != null &&
      !storylines.data.some((s) => s.id === storylineId)
    ) {
      setStorylineId(storylines.data[0]?.id ?? null);
    }
  }, [storylines.data, storylineId]);

  useEffect(() => {
    if (!settings.data) return;
    if (settingId == null && settings.data.length > 0) {
      setSettingId(settings.data[0].id);
    } else if (settingId != null && !settings.data.some((s) => s.id === settingId)) {
      setSettingId(settings.data[0]?.id ?? null);
    }
  }, [settings.data, settingId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage?.setItem(
        STORAGE_KEY,
        JSON.stringify({ storylineId, settingId } satisfies PersistedWorkspace),
      );
    } catch {
      // localStorage may be missing/restricted (private mode, jsdom without
      // the right env). Worst case we lose the persisted selection.
    }
  }, [storylineId, settingId]);

  const value = useMemo(
    () => ({ storylineId, settingId, setStorylineId, setSettingId }),
    [storylineId, settingId],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return ctx;
}
