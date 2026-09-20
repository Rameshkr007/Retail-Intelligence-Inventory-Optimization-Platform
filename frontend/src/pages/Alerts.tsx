import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

const SEVERITY_COLOR: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-600",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

export default function Alerts() {
  const { datasetId } = useApp();
  const [alerts, setAlerts] = useState<any[]>([]);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [note, setNote] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!datasetId) return;
    setError(null);
    try {
      const res = await api.getAlerts(datasetId);
      setAlerts(res.alerts);
      setNote(res.note);
      const anomRes = await api.getAnomalies(datasetId, 3.0);
      setAnomalies(anomRes.anomalies);
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, [datasetId]);

  if (!datasetId) return <div className="card max-w-lg"><p className="text-slate-500 text-sm">Select a dataset in the Data Hub first.</p></div>;

  const types = ["ALL", ...Array.from(new Set(alerts.map((a) => a.type)))];
  const filtered = filter === "ALL" ? alerts : alerts.filter((a) => a.type === filter);

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Alert Center</h1>
          <p className="text-slate-500 text-sm">Demand spikes and high-volatility SKUs, detected from real history.</p>
        </div>
        <button className="btn-secondary" onClick={load}>Rescan</button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-2">
        {types.map((t) => (
          <button key={t} onClick={() => setFilter(t)} className={`btn-secondary ${filter === t ? "ring-2 ring-brand-500" : ""}`}>
            {t.replaceAll("_", " ")}
          </button>
        ))}
      </div>

      <div className="card divide-y divide-slate-100 dark:divide-slate-800/50">
        {filtered.map((a, i) => (
          <div key={i} className="py-3 flex items-start gap-3">
            <span className={`badge ${SEVERITY_COLOR[a.severity]}`}>{a.severity}</span>
            <div>
              <div className="font-medium text-sm">{a.type.replaceAll("_", " ")} — Store {a.store_id}, Item {a.item_id}</div>
              <div className="text-sm text-slate-500">{a.message}</div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <p className="text-slate-400 py-4 text-sm">No alerts for this filter.</p>}
      </div>

      {note && <p className="text-xs text-slate-400">{note}</p>}

      <div>
        <h2 className="text-lg font-semibold mb-2">Anomaly Detection (statistical, z-score ≥ 3)</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <th className="py-2">Date</th><th>Store</th><th>Item</th><th>Sales</th><th>Expected</th><th>Score</th><th>Type</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((a, i) => (
                <tr key={i} className="border-b border-slate-100 dark:border-slate-800/50">
                  <td className="py-2">{a.date}</td>
                  <td>{a.store_id}</td>
                  <td>{a.item_id}</td>
                  <td>{a.sales}</td>
                  <td>{a.expected_sales}</td>
                  <td>{a.anomaly_score}</td>
                  <td><span className={`badge ${a.anomaly_type === "SPIKE" ? "bg-orange-100 text-orange-700" : "bg-blue-100 text-blue-700"}`}>{a.anomaly_type}</span></td>
                </tr>
              ))}
              {anomalies.length === 0 && <tr><td colSpan={7} className="py-4 text-slate-400">No statistical anomalies detected.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
