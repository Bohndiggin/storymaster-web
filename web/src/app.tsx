import { Navigate, Route, Routes } from "react-router-dom";

import { LoginPage } from "@/auth/login";
import { RequireAuth } from "@/auth/RequireAuth";
import { Shell } from "@/layout/Shell";
import { ArcEditPage } from "@/routes/arcs/ArcEdit";
import { ArcTypeManagerPage } from "@/routes/arcs/ArcTypes";
import { ArcsHome, ArcsLayout } from "@/routes/arcs/Index";
import { LitographerPage } from "@/routes/litographer/Canvas";
import {
  EntityListPage,
  LorekeeperHome,
  LorekeeperLayout,
} from "@/routes/lorekeeper/Index";
import { EntityFormPage } from "@/routes/lorekeeper/EntityForm";
import { StoryweaverEditor } from "@/routes/storyweaver/Editor";
import { StoryweaverHome, StoryweaverLayout } from "@/routes/storyweaver/Index";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/lorekeeper" replace />} />
        <Route path="lorekeeper" element={<LorekeeperLayout />}>
          <Route index element={<LorekeeperHome />} />
          <Route path=":table" element={<EntityListPage />} />
          <Route path=":table/:id" element={<EntityFormPage />} />
        </Route>
        <Route path="litographer" element={<LitographerPage />} />
        <Route path="storyweaver" element={<StoryweaverLayout />}>
          <Route index element={<StoryweaverHome />} />
          <Route path=":id" element={<StoryweaverEditor />} />
        </Route>
        <Route path="arcs" element={<ArcsLayout />}>
          <Route index element={<ArcsHome />} />
          <Route path="types" element={<ArcTypeManagerPage />} />
          <Route path="new" element={<ArcEditPage />} />
          <Route path=":id" element={<ArcEditPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
