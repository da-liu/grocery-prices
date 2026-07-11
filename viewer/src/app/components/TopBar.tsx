import { useEffect, useRef, useState, type RefObject } from "react";
import { Camera, Home, ListFilter, Menu } from "lucide-react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { useCatalog } from "@/features/browse/CatalogContext";
import type { BrowseStats } from "@/shared/types/types";
import "./TopBar.css";

interface TopBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder: string;
  user: { username: string };
  onLogout: () => void;
  photoInputRef: RefObject<HTMLInputElement | null>;
  onPhotosSelected: (files: File[]) => void;
  showSortFilter?: boolean;
  sortFilterOpen?: boolean;
  activeChipCount?: number;
  onToggleSortFilter?: () => void;
  browseStats?: BrowseStats;
  onShowOnboarding?: () => void;
  showSettings?: boolean;
}

export function TopBar({
  search,
  onSearchChange,
  searchPlaceholder,
  user,
  onLogout,
  photoInputRef,
  onPhotosSelected,
  showSortFilter = false,
  sortFilterOpen = false,
  activeChipCount = 0,
  onToggleSortFilter,
  browseStats,
  onShowOnboarding,
  showSettings = false,
}: TopBarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const catalog = useCatalog();
  const isSettings = location.pathname === "/settings";
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
  }, [location.pathname]);

  function goToCatalog() {
    setMenuOpen(false);
    navigate("/");
  }

  return (
    <header className="top-bar">
      {isSettings ? (
        <p className="top-bar-title">Settings</p>
      ) : (
        <input
          type="search"
          id="catalog-search"
          name="catalog-search"
          className="top-bar-search"
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          aria-label={searchPlaceholder}
          autoComplete="off"
        />
      )}

      <div className="top-bar-actions">
        <input
          ref={photoInputRef}
          id="catalog-photo-upload"
          name="catalog-photo-upload"
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          onChange={(e) => {
            const files = e.target.files;
            if (files?.length) onPhotosSelected(Array.from(files));
            e.target.value = "";
          }}
        />
        {isSettings ? (
          <button
            type="button"
            className="top-bar-icon-btn top-bar-icon-btn--primary"
            aria-label="Back to catalog"
            onClick={goToCatalog}
          >
            <Home size={20} aria-hidden />
          </button>
        ) : (
          <button
            type="button"
            className="top-bar-icon-btn top-bar-icon-btn--primary"
            aria-label="Take or upload photo"
            onClick={() => photoInputRef.current?.click()}
          >
            <Camera size={20} aria-hidden />
          </button>
        )}

        {showSortFilter && (
          <button
            type="button"
            className={`top-bar-icon-btn top-bar-icon-btn--filter${sortFilterOpen || activeChipCount > 0 ? " active" : ""}`}
            aria-label="Sort and filter"
            aria-expanded={sortFilterOpen}
            data-onboarding-target="sort-filter"
            onClick={() => {
              onToggleSortFilter?.();
              setMenuOpen(false);
            }}
          >
            <ListFilter size={20} aria-hidden />
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
            <Menu size={20} aria-hidden />
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
              <NavLink
                to="/"
                role="menuitem"
                className={({ isActive }) => (isActive ? "active" : undefined)}
                onClick={(e) => {
                  if (location.pathname === "/") {
                    e.preventDefault();
                    setMenuOpen(false);
                    catalog.setSortFilterOpen(false);
                  }
                }}
              >
                Catalog
              </NavLink>
              {showSettings && (
                <NavLink
                  to="/settings"
                  role="menuitem"
                  className={({ isActive }) => (isActive ? "active" : undefined)}
                  onClick={() => setMenuOpen(false)}
                >
                  Settings
                </NavLink>
              )}

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
