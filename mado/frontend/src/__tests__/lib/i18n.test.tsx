import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { I18nProvider, useI18n } from "@/lib/i18n";

function TestConsumer() {
  const { locale, setLocale, t } = useI18n();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="translated">{t("start")}</span>
      <button onClick={() => setLocale("en")}>Switch to EN</button>
      <button onClick={() => setLocale("ja")}>Switch to JA</button>
    </div>
  );
}

describe("I18nProvider + useI18n", () => {
  it("defaults to Japanese locale", () => {
    render(
      <I18nProvider>
        <TestConsumer />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale").textContent).toBe("ja");
    expect(screen.getByTestId("translated").textContent).toBe("開始");
  });

  it("switches to English when setLocale('en') is called", () => {
    render(
      <I18nProvider>
        <TestConsumer />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByText("Switch to EN"));
    expect(screen.getByTestId("locale").textContent).toBe("en");
    expect(screen.getByTestId("translated").textContent).toBe("Start");
  });

  it("switches back to Japanese", () => {
    render(
      <I18nProvider>
        <TestConsumer />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByText("Switch to EN"));
    fireEvent.click(screen.getByText("Switch to JA"));
    expect(screen.getByTestId("translated").textContent).toBe("開始");
  });

  it("persists locale to localStorage", () => {
    render(
      <I18nProvider>
        <TestConsumer />
      </I18nProvider>,
    );
    fireEvent.click(screen.getByText("Switch to EN"));
    expect(localStorage.getItem("mado_locale")).toBe("en");
  });
});
