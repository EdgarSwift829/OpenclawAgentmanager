"use client";

import { useI18n, Locale } from "@/lib/i18n";

export function LangSwitcher() {
  const { locale, setLocale } = useI18n();

  return (
    <div className="lang-switcher">
      {(["ja", "en"] as Locale[]).map((l) => (
        <button
          key={l}
          className={`lang-btn ${locale === l ? "lang-btn-active" : ""}`}
          onClick={() => setLocale(l)}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
