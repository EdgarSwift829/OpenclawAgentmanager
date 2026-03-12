"use client";

import { I18nProvider } from "@/lib/i18n";
import { ToastProvider } from "@/components/Toast";
import { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <ToastProvider>{children}</ToastProvider>
    </I18nProvider>
  );
}
