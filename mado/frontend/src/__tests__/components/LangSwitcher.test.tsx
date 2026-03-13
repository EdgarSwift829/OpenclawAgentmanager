import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LangSwitcher } from "@/components/LangSwitcher";
import { I18nProvider } from "@/lib/i18n";

function renderWithI18n() {
  return render(
    <I18nProvider>
      <LangSwitcher />
    </I18nProvider>,
  );
}

describe("LangSwitcher", () => {
  it("renders JA and EN buttons", () => {
    renderWithI18n();
    expect(screen.getByText("JA")).toBeInTheDocument();
    expect(screen.getByText("EN")).toBeInTheDocument();
  });

  it("JA is active by default", () => {
    renderWithI18n();
    const jaBtn = screen.getByText("JA");
    expect(jaBtn.className).toContain("lang-btn-active");
  });

  it("clicking EN switches active button", () => {
    renderWithI18n();
    const enBtn = screen.getByText("EN");
    fireEvent.click(enBtn);
    expect(enBtn.className).toContain("lang-btn-active");
    const jaBtn = screen.getByText("JA");
    expect(jaBtn.className).not.toContain("lang-btn-active");
  });

  it("clicking JA after EN switches back", () => {
    renderWithI18n();
    fireEvent.click(screen.getByText("EN"));
    fireEvent.click(screen.getByText("JA"));
    expect(screen.getByText("JA").className).toContain("lang-btn-active");
  });
});
