import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Locale = "zh" | "en";

const STORAGE_KEY = "mathclaw.console.locale";

const EN_DICT: Record<string, string> = {};

function normalizeLocale(input: string | null | undefined): Locale {
  if (!input) return "zh";
  const v = input.toLowerCase();
  if (v.startsWith("en")) return "en";
  return "zh";
}

function formatTemplate(template: string, vars?: Record<string, unknown>): string {
  if (!vars) return template;
  let out = template;
  for (const [k, v] of Object.entries(vars)) {
    out = out.replace(new RegExp(`\\{${k}\\}`, "g"), String(v ?? ""));
  }
  return out;
}

export function translateText(
  locale: Locale,
  text: string,
  vars?: Record<string, unknown>,
): string {
  const source = String(text ?? "");
  if (!source) return source;
  if (locale === "zh") return formatTemplate(source, vars);

  if (EN_DICT[source]) return formatTemplate(EN_DICT[source], vars);

  const leading = source.match(/^\s*/)?.[0] ?? "";
  const trailing = source.match(/\s*$/)?.[0] ?? "";
  const core = source.slice(leading.length, source.length - trailing.length);
  if (EN_DICT[core]) {
    return `${leading}${formatTemplate(EN_DICT[core], vars)}${trailing}`;
  }
  return formatTemplate(source, vars);
}

export function getStoredLocale(): Locale {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return normalizeLocale(raw);
  } catch {
    // ignore
  }
  if (typeof navigator !== "undefined") {
    return normalizeLocale(navigator.language);
  }
  return "zh";
}

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (text: string, vars?: Record<string, unknown>) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => getStoredLocale());

  useEffect(() => {
    let cancelled = false;
    let shouldFetch = true;
    try {
      shouldFetch = !localStorage.getItem(STORAGE_KEY);
    } catch {
      shouldFetch = true;
    }
    if (!shouldFetch) return () => {};

    void fetch("/api/config")
      .then(async (res) => (res.ok ? res.json() : {}))
      .then((cfg) => {
        if (cancelled) return;
        const lang = typeof cfg?.language === "string" ? cfg.language : "";
        if (lang) {
          setLocaleState(normalizeLocale(lang));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setLocale = useCallback((next: Locale) => {
    const normalized = normalizeLocale(next);
    setLocaleState(normalized);
    try {
      localStorage.setItem(STORAGE_KEY, normalized);
    } catch {
      // ignore
    }
    const payload = { language: normalized === "zh" ? "zh" : "en" };
    void fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});
  }, []);

  const t = useCallback(
    (text: string, vars?: Record<string, unknown>) =>
      translateText(locale, text, vars),
    [locale],
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
    }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return ctx;
}

const TRANSLATABLE_ATTRS = [
  "placeholder",
  "title",
  "aria-label",
  "alt",
  "data-tooltip",
] as const;
const ORIGINAL_TEXT_NODES = new WeakMap<Text, string>();
const ORIGINAL_ATTRS = new WeakMap<Element, Record<string, string>>();

function _is_skippable_text_node(node: Text): boolean {
  const parent = node.parentElement;
  if (!parent) return true;

  const tag = parent.tagName.toLowerCase();
  if (tag === "script" || tag === "style" || tag === "noscript") return true;
  if (parent.closest("textarea, input, code, pre")) return true;
  if (parent.isContentEditable) return true;
  return false;
}

function _apply_text_translations(root: HTMLElement, locale: Locale): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let cur = walker.nextNode();
  while (cur) {
    const node = cur as Text;
    const raw = node.nodeValue ?? "";
    if (raw.trim() && !_is_skippable_text_node(node)) {
      if (!ORIGINAL_TEXT_NODES.has(node)) {
        ORIGINAL_TEXT_NODES.set(node, raw);
      }
      const original = ORIGINAL_TEXT_NODES.get(node) ?? raw;
      const next =
        locale === "en" ? translateText("en", original) : original;
      if (node.nodeValue !== next) {
        node.nodeValue = next;
      }
    }
    cur = walker.nextNode();
  }
}

function _apply_attr_translations(root: HTMLElement, locale: Locale): void {
  const selector = TRANSLATABLE_ATTRS.map((x) => `[${x}]`).join(",");
  if (!selector) return;

  root.querySelectorAll(selector).forEach((el) => {
    let record = ORIGINAL_ATTRS.get(el);
    if (!record) {
      record = {};
      ORIGINAL_ATTRS.set(el, record);
    }

    for (const attr of TRANSLATABLE_ATTRS) {
      const value = el.getAttribute(attr);
      if (value == null) continue;
      if (!(attr in record)) {
        record[attr] = value;
      }
      const original = record[attr] ?? value;
      const next =
        locale === "en" ? translateText("en", original) : original;
      if (value !== next) {
        el.setAttribute(attr, next);
      }
    }
  });
}

function _apply_dom_translations(root: HTMLElement, locale: Locale): void {
  _apply_text_translations(root, locale);
  _apply_attr_translations(root, locale);
}

export function AutoTranslate({ children }: { children: React.ReactNode }) {
  const { locale } = useI18n();

  useEffect(() => {
    const root = document.getElementById("root");
    if (!root) return () => {};

    let rafId: number | null = null;
    const run = () => {
      rafId = null;
      _apply_dom_translations(root, locale);
    };

    run();

    const observer = new MutationObserver(() => {
      if (rafId != null) {
        cancelAnimationFrame(rafId);
      }
      rafId = requestAnimationFrame(run);
    });

    observer.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: [...TRANSLATABLE_ATTRS],
    });

    return () => {
      observer.disconnect();
      if (rafId != null) {
        cancelAnimationFrame(rafId);
      }
    };
  }, [locale]);

  return <>{children}</>;
}
