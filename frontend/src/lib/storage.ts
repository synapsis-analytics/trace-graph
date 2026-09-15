const KEY_ACCESS = "trace.accessKey";
const KEY_THEME = "trace.theme";
const KEY_ATTESTOR = "trace.attestedBy";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* private mode — ignore */
  }
}

export const accessKeyStore = {
  get: () => read(KEY_ACCESS),
  set: (v: string | null) => write(KEY_ACCESS, v),
};

export const attestorStore = {
  get: () => read(KEY_ATTESTOR) ?? "person:anonymous",
  set: (v: string | null) => write(KEY_ATTESTOR, v),
};

export type ThemeMode = "light" | "dark";

export const themeStore = {
  get(): ThemeMode {
    const v = read(KEY_THEME);
    if (v === "dark" || v === "light") return v;
    return typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  },
  set(v: ThemeMode) {
    write(KEY_THEME, v);
  },
  apply(v: ThemeMode) {
    const root = document.documentElement;
    root.classList.toggle("dark", v === "dark");
    root.classList.toggle("light", v === "light");
  },
};
