import { type ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useSettings, useStorylines } from "@/api/storylines";
import { useCurrentUser, useLogout } from "@/auth/auth";
import { Button } from "@/components/Button";
import { Select } from "@/components/Select";
import { useWorkspace, WorkspaceProvider } from "@/lib/workspace";
import { cn } from "@/lib/cn";

const NAV: Array<{ to: string; label: string }> = [
  { to: "/lorekeeper", label: "Lorekeeper" },
  // Litographer + Storyweaver land in later phases. Keep the slots reserved
  // so the nav doesn't shift when they arrive.
  { to: "/litographer", label: "Litographer" },
  { to: "/storyweaver", label: "Storyweaver" },
  { to: "/arcs", label: "Arcs" },
];

export function Shell() {
  return (
    <WorkspaceProvider>
      <div className="flex min-h-screen flex-col">
        <TopBar />
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <Outlet />
        </main>
      </div>
    </WorkspaceProvider>
  );
}

function TopBar() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <header className="border-b border-slate-800 bg-canvas-panel">
      <div className="flex items-center gap-6 px-6 py-3">
        <Brand />
        <nav className="flex items-center gap-1">
          {NAV.map((item) => (
            <NavTab key={item.to} to={item.to}>
              {item.label}
            </NavTab>
          ))}
        </nav>
        <div className="flex flex-1 items-center justify-end gap-3">
          <StorylineSwitcher />
          <SettingSwitcher />
          {user ? (
            <div className="flex items-center gap-2 text-sm text-slate-300">
              <span className="hidden md:inline">{user.username}</span>
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  await logout.mutateAsync();
                  navigate("/login", { replace: true });
                }}
                disabled={logout.isPending}
              >
                Sign out
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="inline-block h-2 w-2 rounded-full bg-accent" aria-hidden />
      Storymaster
    </div>
  );
}

function NavTab({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm transition-colors",
          isActive ? "bg-canvas-raised text-slate-100" : "text-slate-400 hover:text-slate-100",
        )
      }
    >
      {children}
    </NavLink>
  );
}

function StorylineSwitcher() {
  const { storylineId, setStorylineId } = useWorkspace();
  const { data: storylines, isLoading } = useStorylines();
  if (isLoading) return null;
  if (!storylines || storylines.length === 0) return null;
  return (
    <Select
      className="h-8 w-44 text-xs"
      value={storylineId ?? ""}
      onChange={(e) => setStorylineId(e.target.value ? Number(e.target.value) : null)}
      aria-label="Active storyline"
    >
      {storylines.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name ?? `Storyline #${s.id}`}
        </option>
      ))}
    </Select>
  );
}

function SettingSwitcher() {
  const { settingId, setSettingId } = useWorkspace();
  const { data: settings, isLoading } = useSettings();
  if (isLoading) return null;
  if (!settings || settings.length === 0) return null;
  return (
    <Select
      className="h-8 w-44 text-xs"
      value={settingId ?? ""}
      onChange={(e) => setSettingId(e.target.value ? Number(e.target.value) : null)}
      aria-label="Active setting"
    >
      {settings.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name ?? `Setting #${s.id}`}
        </option>
      ))}
    </Select>
  );
}
