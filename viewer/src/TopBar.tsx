import { useEffect, useId, useRef, useState } from "react";

type Page = "browse" | "upload" | "compare" | "settings";

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
  onPhotoSelected: (file: File) => void;
  stores?: string[];
  store?: string;
  onStoreChange?: (store: string) => void;
  browseStats?: BrowseStats;
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
  onPhotoSelected,
  stores = [],
  store = "all",
  onStoreChange,
  browseStats,
  onShowOnboarding,
}: TopBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const photoRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const filterRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const filterId = useId();

  const showStoreFilter = page === "browse" && stores.length > 0;
  const storeFiltered = store !== "all";

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      const target = e.target as Node;
      if (menuOpen && menuRef.current && !menuRef.current.contains(target)) {
        setMenuOpen(false);
      }
      if (filterOpen && filterRef.current && !filterRef.current.contains(target)) {
        setFilterOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [menuOpen, filterOpen]);

  useEffect(() => {
    setMenuOpen(false);
    setFilterOpen(false);
  }, [page]);

  function handlePhoto(file: File | undefined) {
    if (file) onPhotoSelected(file);
  }

  function pickNav(pageName: Page) {
    setMenuOpen(false);
    onNavigate(pageName);
  }

  function pickStore(next: string) {
    onStoreChange?.(next);
    setFilterOpen(false);
  }

  return (
    <header className="top-bar">
      {page === "upload" ? (
        <p className="top-bar-title">Upload</p>
      ) : page === "settings" ? (
        <p className="top-bar-title">Settings</p>
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
          ref={photoRef}
          type="file"
          accept="image/*,.heic"
          className="sr-only"
          onChange={(e) => {
            handlePhoto(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="top-bar-icon-btn top-bar-icon-btn--primary"
          aria-label="Take or upload photo"
          onClick={() => photoRef.current?.click()}
        >
          <CameraIcon />
        </button>

        {showStoreFilter && (
          <div className="top-bar-menu-wrap" ref={filterRef}>
            <button
              type="button"
              className={`top-bar-icon-btn${storeFiltered ? " active" : ""}`}
              aria-label="Filter by store"
              aria-expanded={filterOpen}
              aria-controls={filterId}
              onClick={() => {
                setFilterOpen((open) => !open);
                setMenuOpen(false);
              }}
            >
              <FilterIcon />
            </button>
            {filterOpen && (
              <div id={filterId} className="top-bar-dropdown" role="menu">
                <p className="top-bar-dropdown-label">Store</p>
                <button
                  type="button"
                  role="menuitem"
                  className={store === "all" ? "active" : undefined}
                  onClick={() => pickStore("all")}
                >
                  All stores
                </button>
                {stores.map((name) => (
                  <button
                    key={name}
                    type="button"
                    role="menuitem"
                    className={store === name ? "active" : undefined}
                    onClick={() => pickStore(name)}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="top-bar-menu-wrap" ref={menuRef}>
          <button
            type="button"
            className="top-bar-icon-btn"
            aria-label="Menu"
            aria-expanded={menuOpen}
            aria-controls={menuId}
            onClick={() => {
              setMenuOpen((open) => !open);
              setFilterOpen(false);
            }}
          >
            <MenuIcon />
          </button>
          {menuOpen && (
            <div id={menuId} className="top-bar-dropdown top-bar-dropdown--wide" role="menu">
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
              <button
                type="button"
                role="menuitem"
                className={page === "compare" ? "active" : undefined}
                onClick={() => pickNav("compare")}
              >
                Compare
              </button>
              <button
                type="button"
                role="menuitem"
                className={page === "upload" ? "active" : undefined}
                onClick={() => pickNav("upload")}
              >
                Upload & import
              </button>
              <button
                type="button"
                role="menuitem"
                className={page === "settings" ? "active" : undefined}
                onClick={() => pickNav("settings")}
              >
                Store locations
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
