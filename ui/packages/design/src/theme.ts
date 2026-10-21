// Theme: light, dark or follow the system (D-038). Touch starts dark; tech follows the system.
// The choice is a per-screen convenience in browser storage, so it is wrapped in try/catch
// and the page works without it (docs/design/gui-konsept.md).

export type Theme = "system" | "light" | "dark";

const key = (screen: string) => `cutcut.theme.${screen}`;

export function loadTheme(screen: string, fallback: Theme): Theme {
  try {
    const v = window.localStorage.getItem(key(screen));
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* storage blocked: use the default */
  }
  return fallback;
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

export function saveTheme(screen: string, theme: Theme): void {
  try {
    window.localStorage.setItem(key(screen), theme);
  } catch {
    /* not important enough to fail over */
  }
}

export function isDark(): boolean {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr) return attr === "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}
