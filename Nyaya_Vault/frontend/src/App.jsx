import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import AppShell from "./components/AppShell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import CasesPage from "./pages/CasesPage";
import CasePage from "./pages/CasePage";
import DocumentPage from "./pages/DocumentPage";
import SearchPage from "./pages/SearchPage";
import IntegrityPage from "./pages/IntegrityPage";
import AdminPage from "./pages/AdminPage";
import ProfilePage from "./pages/ProfilePage";
import NotFoundPage from "./pages/NotFoundPage";
import GuideProvider from "./guide/GuideProvider";
import GuideAssistant from "./guide/GuideAssistant";
export default function App() {
  return (
    <GuideProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/cases" element={<CasesPage />} />
            <Route path="/cases/:caseId/*" element={<CasePage />} />
            <Route path="/documents/:documentId" element={<DocumentPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/integrity" element={<IntegrityPage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <GuideAssistant />
    </GuideProvider>
  );
}
