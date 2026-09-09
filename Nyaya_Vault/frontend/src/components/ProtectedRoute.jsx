import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import LoadingState from "./LoadingState";
export default function ProtectedRoute() {
  const { user, profile, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return <LoadingState fullPage label="Loading secure workspace…" />;
  if (!user)
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (profile && !profile.is_active)
    return (
      <div className="center-message">
        <h2>Account disabled</h2>
        <p>Contact a CaseVault administrator.</p>
      </div>
    );
  return <Outlet />;
}
