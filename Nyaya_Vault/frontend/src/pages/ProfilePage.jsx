import { Shield, UserRound } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import Avatar from "../components/Avatar";
import Badge, { clearanceTone } from "../components/Badge";
import { formatDate } from "../lib/format";
export default function ProfilePage() {
  const { user, profile } = useAuth();
  return (
    <div className="page">
      <div className="page-title-row">
        <div>
          <h1>Profile</h1>
          <p>Your identity and authorization attributes.</p>
        </div>
      </div>
      <section className="panel profile-panel">
        <div className="profile-hero">
          <Avatar name={profile?.username} size="lg" />
          <div>
            <h2>{profile?.username}</h2>
            <p>{user?.email}</p>
            <div className="button-row">
              <Badge tone="info">{profile?.role?.replaceAll("_", " ")}</Badge>
              <Badge tone={clearanceTone(profile?.clearance_level)}>
                {profile?.clearance_level}
              </Badge>
            </div>
          </div>
        </div>
        <dl className="definition-grid">
          <dt>
            <UserRound size={15} /> User ID
          </dt>
          <dd>
            <code>{user?.id}</code>
          </dd>
          <dt>
            <Shield size={15} /> Account state
          </dt>
          <dd>{profile?.is_active ? "Active" : "Disabled"}</dd>
          <dt>Created</dt>
          <dd>{formatDate(profile?.created_at)}</dd>
        </dl>
      </section>
    </div>
  );
}
