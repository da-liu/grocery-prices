import { useEffect, useRef, useState, type RefObject } from "react";

type Page = "browse" | "compare" | "settings" | "metadata" | "compress";

interface BrowseStats {
  shown: number;
  total: number;
  photoCount: number;
  storeCount: number;
  avgPriceLabel: string;
}

interface TopBarProps {
  page: Page;
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder: string;
  user: { username: string };
  onLogout: () => void;
  onNavigate: (page: Page) => void;
  photoInputRef: RefObject<HTMLInputElement | null>;
  onPhotosSelected: (files: File[]) => void;
  showSortFilter?: boolean;
  sortFilterOpen?: boolean;
  activeChipCount?: number;
  onToggleSortFilter?: () => void;
  browseStats?: BrowseStats;
  showCompareNav?: boolean;
  onShowOnboarding?: () => void;
}

function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 8.5h2.2L7.5 6.5h9l1.3 2h2.2a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1Z"
      />
      <circle cx="12" cy="13" r="3.25" fill="none" stroke="currentColor" strokeWidth="1.75" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        d="M5 7h14M5 12h14M5 17h14"
      />
    </svg>
  );
}

function FilterIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 6h16M7 12h10M10 18h4"
      />
    </svg>
  );
}

export function TopBar({
  page,
  search,
  onSearchChange,
  searchPlaceholder,
  user,
  onLogout,
  onNavigate,
  photoInputRef,
  onPhotosSelected,
  showSortFilter = false,
  sortFilterOpen = false,
  activeChipCount = 0,
  onToggleSortFilter,
  browseStats,
  showCompareNav = true,
  onShowOnboarding,
}: TopBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      const target = e.target as Node;
      if (menuOpen && menuRef.current && !menuRef.current.contains(target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [menuOpen]);

  useEffect(() => {
    setMenuOpen(false);
  }, [page]);

  function handlePhotos(files: FileList | null | undefined) {
    if (!files?.length) return;
    onPhotosSelected(Array.from(files));
  }

  function pickNav(pageName: Page) {
    setMenuOpen(false);
    onNavigate(pageName);
  }

  return (
    <header className="top-bar">
      {page === "settings" ? (
        <p className="top-bar-title">Settings</p>
      ) : page === "metadata" ? (
        <p className="top-bar-title">Metadata</p>
      ) : page === "compress" ? (
        <p className="top-bar-title">Compress</p>
      ) : (
        <input
          type="search"
          className="top-bar-search"
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          aria-label={searchPlaceholder}
        />
      )}

      <div className="top-bar-actions">
        <input
          ref={photoInputRef}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          onChange={(e) => {
            handlePhotos(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="top-bar-icon-btn top-bar-icon-btn--primary"
          aria-label="Take or upload photo"
          onClick={() => photoInputRef.current?.click()}
        >
          <CameraIcon />
        </button>

        {showSortFilter && (
          <button
            type="button"
            className={`top-bar-icon-btn top-bar-icon-btn--filter${sortFilterOpen || activeChipCount > 0 ? " active" : ""}`}
            aria-label="Sort and filter"
            aria-expanded={sortFilterOpen}
            onClick={() => {
              onToggleSortFilter?.();
              setMenuOpen(false);
            }}
          >
            <FilterIcon />
            {activeChipCount > 0 && (
              <span className="top-bar-filter-badge" aria-hidden="true">
                {activeChipCount}
              </span>
            )}
          </button>
        )}

        <div className="top-bar-menu-wrap" ref={menuRef}>
          <button
            type="button"
            className="top-bar-icon-btn"
            aria-label="Menu"
            aria-expanded={menuOpen}
            onClick={() => {
              setMenuOpen((open) => !open);
            }}
          >
            <MenuIcon />
          </button>
          {menuOpen && (
            <div className="top-bar-dropdown top-bar-dropdown--wide" role="menu">
              {browseStats && (
                <>
                  <p className="top-bar-dropdown-label">Catalog</p>
                  <p className="top-bar-dropdown-meta">
                    {browseStats.shown} shown · {browseStats.total} products ·{" "}
                    {browseStats.photoCount} photos · {browseStats.storeCount} stores · avg{" "}
                    {browseStats.avgPriceLabel}
                  </p>
                </>
              )}

              <p className="top-bar-dropdown-label">Go to</p>
              <button
                type="button"
                role="menuitem"
                className={page === "browse" ? "active" : undefined}
                onClick={() => pickNav("browse")}
              >
                Browse
              </button>
              {showCompareNav && (
                <button
                  type="button"
                  role="menuitem"
                  className={page === "compare" ? "active" : undefined}
                  onClick={() => pickNav("compare")}
                >
                  Compare
                </button>
              )}
              <button
                type="button"
                role="menuitem"
                className={page === "settings" ? "active" : undefined}
                onClick={() => pickNav("settings")}
              >
                Settings
              </button>
              <button
                type="button"
                role="menuitem"
                className={page === "metadata" ? "active" : undefined}
                onClick={() => pickNav("metadata")}
              >
                Metadata
              </button>
              <button
                type="button"
                role="menuitem"
                className={page === "compress" ? "active" : undefined}
                onClick={() => pickNav("compress")}
              >
                Compress
              </button>

              <p className="top-bar-dropdown-label">Help</p>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  onShowOnboarding?.();
                }}
              >
                Getting started guide
              </button>

              <p className="top-bar-dropdown-label">Account</p>
              <p className="top-bar-dropdown-meta">{user.username}</p>
              <button
                type="button"
                role="menuitem"
                className="top-bar-menu-danger"
                onClick={() => {
                  setMenuOpen(false);
                  onLogout();
                }}
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
