import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "@/App";
import { LightboxProvider } from "@/components/LightboxContext";
import type { Manifest } from "@/lib/types";
import "@/styles/index.css";

function Root() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/manifest.json")
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load manifest (${res.status})`);
        return res.json();
      })
      .then(setManifest)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="boot-error">
        <h1>Match Explorer</h1>
        <p>{error}</p>
        <p>
          Run <code>python3 scripts/build_data.py</code> from <code>experiments/match-explorer</code>.
        </p>
      </div>
    );
  }

  if (!manifest) {
    return <div className="boot-loading">Loading manifest…</div>;
  }

  return (
    <LightboxProvider>
      <App manifest={manifest} />
    </LightboxProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
