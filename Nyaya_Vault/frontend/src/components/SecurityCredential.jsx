import { ShieldCheck } from "lucide-react";
import Badge, { clearanceTone, departmentTone } from "./Badge";

export default function SecurityCredential({ profile }) {
  return (
    <section className="security-credential" aria-label="Authorization credential">
      <div className="eyebrow"><ShieldCheck size={15} /> Authorization credential</div>
      <strong>{profile?.role?.replaceAll("_", " ") || "USER"}</strong>
      <div className="credential-labels">
        <Badge tone={clearanceTone(profile?.clearance_level)}>{profile?.clearance_level || "PUBLIC"}</Badge>
        {profile?.department ? <Badge tone={departmentTone(profile.department)}>{profile.department}</Badge> : null}
      </div>
      <span className="small muted">Access follows case assignment and clearance.</span>
    </section>
  );
}
