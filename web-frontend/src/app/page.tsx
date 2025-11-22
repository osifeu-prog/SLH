"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

// Simple landing page + check your wallet by Telegram ID
export default function HomePage() {
  const [telegramId, setTelegramId] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function fetchWallet() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/wallet/by-telegram/${telegramId}`);
      if (!res.ok) {
        throw new Error("Wallet not found");
      }
      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ maxWidth: 600, width: "100%", padding: 24, borderRadius: 16, background: "#020617", border: "1px solid #1f2937" }}>
        <h1 style={{ fontSize: 28, marginBottom: 12 }}>SLH Community Wallet Hub</h1>
        <p style={{ marginBottom: 16, color: "#9ca3af" }}>
          בדוק את פרטי הארנק שלך לפי Telegram ID. כרגע התצוגה בסיסית – בהמשך נוסיף סטייקינג, מסחר ועוד.
        </p>

        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <input
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: 999,
              border: "1px solid #4b5563",
              background: "#020617",
              color: "#e5e7eb"
            }}
            value={telegramId}
            onChange={(e) => setTelegramId(e.target.value)}
            placeholder="לדוגמה: 224223270"
          />
          <button
            onClick={fetchWallet}
            disabled={loading || !telegramId}
            style={{
              padding: "8px 16px",
              borderRadius: 999,
              border: "none",
              background: "#22c55e",
              color: "#022c22",
              fontWeight: 600,
              cursor: "pointer",
              opacity: loading || !telegramId ? 0.6 : 1
            }}
          >
            {loading ? "טוען..." : "בדוק"}
          </button>
        </div>

        {error && <p style={{ color: "#f97373" }}>{error}</p>}

        {result && (
          <div style={{ marginTop: 16, padding: 16, borderRadius: 12, background: "#020617", border: "1px solid #374151" }}>
            <h2 style={{ fontSize: 20, marginBottom: 8 }}>ארנק</h2>
            <p>Telegram ID: {result.telegram_id}</p>
            {result.username && <p>Username: @{result.username}</p>}
            {result.bnb_address && <p>BNB: {result.bnb_address}</p>}
            {result.slh_address && <p>SLH: {result.slh_address}</p>}
            {result.slh_ton_address && <p>TON: {result.slh_ton_address}</p>}
          </div>
        )}
      </div>
    </main>
  );
}
