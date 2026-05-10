/// <reference types="vitest/globals" />
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceProvider } from "@/lib/workspace";

import { ArcsHome, ArcsLayout } from "./Index";

// Stub fetch for the queries the layout fires; we don't need real data,
// just a non-error response so the components don't show error states.
function stubFetch() {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    const body =
      url.includes("/api/auth/me") ? JSON.stringify({ id: 1, username: "alice", is_active: true })
      : "[]";
    return new Response(body, {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
}

function renderArcs(initialPath = "/arcs") {
  stubFetch();
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <WorkspaceProvider>
          <Routes>
            <Route path="/arcs" element={<ArcsLayout />}>
              <Route index element={<ArcsHome />} />
            </Route>
          </Routes>
        </WorkspaceProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<ArcsLayout />", () => {
  it("prompts for a storyline when none is selected", () => {
    renderArcs();
    expect(
      screen.getByText(/pick or create a storyline/i),
    ).toBeInTheDocument();
  });
});
