/**
 * Route map. Unauthenticated users only ever see the login screen; once a
 * coordinator session exists, the console routes are available and any unknown
 * path bounces home.
 */
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./hooks/useAuth";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { SwimDetailPage } from "./pages/SwimDetailPage";
import { AccountsPage } from "./pages/AccountsPage";

export function App() {
  const { user } = useAuth();

  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/swims/:swimId" element={<SwimDetailPage />} />
      <Route path="/accounts" element={<AccountsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
