import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
      <h1 className="text-lg font-semibold">Nothing here</h1>
      <p className="text-sm text-muted">That page is not part of the TRACE prototype.</p>
      <Link className="link text-sm" to="/">
        Back to Explore
      </Link>
    </div>
  );
}
