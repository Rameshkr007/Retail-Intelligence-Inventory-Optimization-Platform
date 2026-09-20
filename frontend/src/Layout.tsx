import React, { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useApp } from "./state";
import { api } from "./api";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/data-hub", label: "Data Hub" },
  { to: "/forecasting", label: "Forecasting" },
  { to: "/inventory", label: "Inventory" },
  { to: "/simulation", label: "What-If Simulator" },
  { to: "/analytics", label: "ABC-XYZ Analytics" },
  { to: "/alerts", label: "Alert Center" },
  { to: "/insights", label: "AI Insights" },
  { to: "/models", label: "Model Registry" },
  { to: "/reports", label: "Reports" },
  { to: "/interview-mode", label: "Interview Mode" },
  { to: "/architecture", label: "Architecture" },
  { to: "/audit-log", label: "Audit Log" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { role, logout, datasetId, setDatasetId } = useApp();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const searchRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    try {
      const res = await api.search(q);
      setResults(res.results);
    } catch {
      setResults([]);
    }
  }

  return (
    <div className="min-h-screen flex app-shell">
      <aside className="w-64 shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 flex flex-col">
        <div className="text-lg font-bold text-brand-700 dark:text-brand-500 mb-1"><span className="brand-mark">RI</span> Retail Intelligence</div>
        <div className="text-xs text-slate-400 mb-6">Explainable ML Decision Platform</div>
        <nav className="flex-1 space-y-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive
                    ? "bg-brand-50 dark:bg-brand-900/40 text-brand-700 dark:text-brand-400"
                    : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 dark:border-slate-800 pt-3 mt-3 text-xs">
          <div className="mb-1">Role: <span className="font-semibold">{role}</span></div>
          <div className="mb-2">Active dataset: <span className="font-semibold">{datasetId ?? "none"}</span></div>
          <button
            className="btn-secondary w-full"
            onClick={() => { logout(); navigate("/login"); }}
          >
            Log out
          </button>
        </div>
      </aside>
      <main className="flex-1 p-8 overflow-y-auto">
        <form onSubmit={runSearch} className="mb-6 max-w-md flex gap-2">
          <input ref={searchRef} className="input" placeholder="Search datasets, models… (Ctrl/Cmd+K)" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn-secondary" type="submit">Search</button>
        </form>
        {results.length > 0 && (
          <div className="card mb-6 max-w-md">
            {results.map((r, i) => (
              <div key={i} className="flex justify-between text-sm py-1 border-b border-slate-100 dark:border-slate-800/50 last:border-0">
                <span>{r.label} <span className="text-slate-400 text-xs">({r.type})</span></span>
                <span className="text-slate-500">{r.detail}</span>
              </div>
            ))}
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
