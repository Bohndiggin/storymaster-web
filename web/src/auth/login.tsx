import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Button } from "@/components/Button";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { Field } from "@/components/Field";
import { Input } from "@/components/Input";

import { useLogin } from "./auth";

interface LocationState {
  from?: { pathname?: string };
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    try {
      await login.mutateAsync({ username, password });
      const from = (location.state as LocationState | null)?.from?.pathname ?? "/";
      navigate(from, { replace: true });
    } catch {
      // useMutation's `error` is rendered below; nothing to do here.
    }
  };

  const error =
    login.error instanceof ApiError
      ? typeof login.error.detail === "string"
        ? login.error.detail
        : "Invalid username or password"
      : login.error
        ? "Could not reach the server"
        : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="flex-col items-center gap-2 text-center">
          <img
            src="/storymaster_icon_256.png"
            alt=""
            aria-hidden
            className="h-16 w-16 rounded-md"
          />
          <CardTitle>Sign in to Storymaster</CardTitle>
        </CardHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Username" htmlFor="username">
            <Input
              id="username"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={login.isPending}
            />
          </Field>
          <Field label="Password" htmlFor="password" error={error}>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={login.isPending}
            />
          </Field>
          <Button
            type="submit"
            disabled={login.isPending || !username || !password}
            className="w-full"
          >
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
          <p className="text-center text-xs text-slate-500">
            No public sign-up. Ask an admin to create an account.
          </p>
        </form>
      </Card>
    </div>
  );
}
