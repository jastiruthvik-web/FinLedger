const KEY = "finledger-theme";

export type Theme = "light" | "night";

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "night" ? "night" : "light";
}

export function toggleTheme(): Theme {
  const next: Theme = currentTheme() === "night" ? "light" : "night";
  if (next === "night") document.documentElement.dataset.theme = "night";
  else delete document.documentElement.dataset.theme;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    /* private mode */
  }
  return next;
}
