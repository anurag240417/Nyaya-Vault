import { Link } from "react-router-dom";
export default function NotFoundPage() {
  return (
    <div className="not-found">
      <strong>404</strong>
      <h1>Page not found</h1>
      <p>The requested Nyaya Vault page does not exist.</p>
      <Link className="button button-primary" to="/dashboard">
        Return to case desk
      </Link>
    </div>
  );
}
