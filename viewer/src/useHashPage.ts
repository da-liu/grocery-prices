import { useCallback, useEffect, useState } from "react";
import type { AppPage } from "./types";

function pageFromHash(): AppPage {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return hash === "settings" ? "settings" : "browse";
}

export function useHashPage() {
  const [page, setPage] = useState<AppPage>(pageFromHash);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = useCallback((next: AppPage) => {
    window.location.hash = next === "browse" ? "" : `#/${next}`;
    setPage(next);
  }, []);

  return { page, navigate };
}
