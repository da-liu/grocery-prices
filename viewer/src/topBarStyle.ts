export type TopBarStyle = "border" | "shadow" | "clean" | "shadow-scroll";

export interface TopBarStyleOption {
  id: TopBarStyle;
  label: string;
  description: string;
}

export const DEFAULT_TOP_BAR_STYLE: TopBarStyle = "border";
const STORAGE_KEY = "grocery-top-bar-style";

export const TOP_BAR_STYLE_OPTIONS: TopBarStyleOption[] = [
  {
    id: "border",
    label: "Border line",
    description: "Keeps the current crisp divider under the sticky bar.",
  },
  {
    id: "shadow",
    label: "Soft shadow",
    description: "Uses depth instead of a hard line for separation.",
  },
  {
    id: "clean",
    label: "Clean",
    description: "Removes the separator entirely for a lighter feel.",
  },
  {
    id: "shadow-scroll",
    label: "Shadow on scroll",
    description: "Stays clean at the top and adds depth once you scroll.",
  },
];

export function isTopBarStyle(value: string | null | undefined): value is TopBarStyle {
  return TOP_BAR_STYLE_OPTIONS.some((option) => option.id === value);
}

export function loadTopBarStyle(): TopBarStyle {
  if (typeof window === "undefined") return DEFAULT_TOP_BAR_STYLE;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return isTopBarStyle(stored) ? stored : DEFAULT_TOP_BAR_STYLE;
}

export function saveTopBarStyle(style: TopBarStyle): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, style);
}
