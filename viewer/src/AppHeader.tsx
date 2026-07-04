import { useEffect, useRef, type ReactNode } from "react";

interface AppHeaderProps {
  children: ReactNode;
}

export function AppHeader({ children }: AppHeaderProps) {
  const headerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;

    const syncHeight = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        if (!header) return;
        document.documentElement.style.setProperty(
          "--app-header-height",
          `${header.offsetHeight}px`,
        );
      });
    };

    let rafId = 0;
    syncHeight();
    const observer = new ResizeObserver(syncHeight);
    observer.observe(header);
    return () => {
      cancelAnimationFrame(rafId);
      observer.disconnect();
    };
  }, []);

  return (
    <>
      <div ref={headerRef} className="app-header">
        <div className="app-header-inner">{children}</div>
      </div>
      <div className="app-header-spacer" aria-hidden="true" />
    </>
  );
}
