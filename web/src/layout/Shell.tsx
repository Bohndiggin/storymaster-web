import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import {
  useCreateSetting,
  useCreateStoryline,
  useDeleteSetting,
  useDeleteStoryline,
  useSettings,
  useStorylines,
  useUpdateSetting,
  useUpdateStoryline,
} from "@/api/storylines";
import { useCurrentUser, useLogout } from "@/auth/auth";
import { ChangePasswordDialog } from "@/auth/ChangePasswordDialog";
import { Button } from "@/components/Button";
import { useWorkspace, WorkspaceProvider } from "@/lib/workspace";
import { cn } from "@/lib/cn";

import { WorkspacePicker } from "./WorkspacePicker";

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
        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
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
  const location = useLocation();
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Auto-close the mobile menu on route change so a NavLink tap collapses it.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  async function handleSignOut() {
    await logout.mutateAsync();
    navigate("/login", { replace: true });
  }

  return (
    <header className="border-b border-slate-800 bg-canvas-panel">
      {/* Desktop bar — single inline row from `md` and up. */}
      <div className="hidden items-center gap-6 px-6 py-3 md:flex">
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
              <span className="hidden lg:inline">{user.username}</span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setChangePasswordOpen(true)}
              >
                Change password
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleSignOut}
                disabled={logout.isPending}
              >
                Sign out
              </Button>
            </div>
          ) : null}
        </div>
      </div>

      {/* Mobile bar — brand + hamburger; everything else lives in the drawer. */}
      <div className="flex items-center justify-between px-4 py-3 md:hidden">
        <Brand />
        <button
          type="button"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md text-slate-200 hover:bg-canvas-raised"
        >
          <HamburgerIcon open={menuOpen} />
        </button>
      </div>
      {menuOpen ? (
        <div className="border-t border-slate-800 bg-canvas-panel px-4 py-3 md:hidden">
          <nav className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavTab key={item.to} to={item.to} block>
                {item.label}
              </NavTab>
            ))}
          </nav>
          <div className="mt-3 flex flex-col gap-2 border-t border-slate-800 pt-3">
            <StorylineSwitcher />
            <SettingSwitcher />
          </div>
          {user ? (
            <div className="mt-3 flex flex-col gap-2 border-t border-slate-800 pt-3">
              <span className="text-xs text-slate-500">Signed in as {user.username}</span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="flex-1"
                  onClick={() => {
                    setChangePasswordOpen(true);
                    setMenuOpen(false);
                  }}
                >
                  Change password
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="flex-1"
                  onClick={handleSignOut}
                  disabled={logout.isPending}
                >
                  Sign out
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {changePasswordOpen ? (
        <ChangePasswordDialog onClose={() => setChangePasswordOpen(false)} />
      ) : null}
    </header>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2 font-semibold tracking-tight">
      <img
        src="/storymaster_icon_64.png"
        alt=""
        aria-hidden
        className="h-6 w-6 rounded-sm"
      />
      Storymaster
    </div>
  );
}

function NavTab({
  to,
  children,
  block = false,
}: {
  to: string;
  children: ReactNode;
  block?: boolean;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm transition-colors",
          block ? "block" : "",
          isActive ? "bg-canvas-raised text-slate-100" : "text-slate-400 hover:text-slate-100",
        )
      }
    >
      {children}
    </NavLink>
  );
}

function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden
    >
      {open ? (
        <>
          <line x1="5" y1="5" x2="15" y2="15" />
          <line x1="15" y1="5" x2="5" y2="15" />
        </>
      ) : (
        <>
          <line x1="4" y1="6" x2="16" y2="6" />
          <line x1="4" y1="10" x2="16" y2="10" />
          <line x1="4" y1="14" x2="16" y2="14" />
        </>
      )}
    </svg>
  );
}

function StorylineSwitcher() {
  const { storylineId, setStorylineId } = useWorkspace();
  const { data: storylines, isLoading } = useStorylines();
  const create = useCreateStoryline();
  const updateMut = useUpdateStoryline();
  const deleteMut = useDeleteStoryline();
  return (
    <WorkspacePicker
      label="Storyline"
      items={storylines}
      isLoading={isLoading}
      selectedId={storylineId}
      onSelect={setStorylineId}
      fallbackPrefix="Storyline"
      onCreate={(payload) => create.mutateAsync(payload)}
      isCreating={create.isPending}
      onRename={(id, name) => updateMut.mutateAsync({ id, name })}
      onDelete={(id) => deleteMut.mutateAsync(id)}
      isMutating={updateMut.isPending || deleteMut.isPending}
    />
  );
}

function SettingSwitcher() {
  const { settingId, setSettingId } = useWorkspace();
  const { data: settings, isLoading } = useSettings();
  const create = useCreateSetting();
  const updateMut = useUpdateSetting();
  const deleteMut = useDeleteSetting();
  return (
    <WorkspacePicker
      label="Setting"
      items={settings}
      isLoading={isLoading}
      selectedId={settingId}
      onSelect={setSettingId}
      fallbackPrefix="Setting"
      onCreate={(payload) => create.mutateAsync(payload)}
      isCreating={create.isPending}
      onRename={(id, name) => updateMut.mutateAsync({ id, name })}
      onDelete={(id) => deleteMut.mutateAsync(id)}
      isMutating={updateMut.isPending || deleteMut.isPending}
    />
  );
}
