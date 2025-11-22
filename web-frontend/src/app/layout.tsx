import type { ReactNode } from "react";

export const metadata = {
  title: "SLH Wallet Hub",
  description: "Community wallet hub for SLH on BNB + internal ledger."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#020617", color: "#e5e7eb" }}>
        {children}
      </body>
    </html>
  );
}
