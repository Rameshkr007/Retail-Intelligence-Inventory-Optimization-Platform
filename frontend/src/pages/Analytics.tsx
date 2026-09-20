import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

const QUADRANT_COLOR: Record<string, string> = {
  "High Value + High Risk": "bg-red-100 text-red-700",
  "High Value + Low Risk": "bg-emerald-100 text-emerald-700",
  "Low Value + High Risk": "bg-amber-100 text-amber-700",
  "Low Value + Low Risk": "bg-slate-100 text-slate-600",
};

export default function Analytics() {
  const { datasetId } = useApp();
  const [segments, setSegments] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getAbcXyz(datasetId);
      setSegments(res.segments);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [datasetId]);

  if (!datasetId) return <div className="card max-w-lg"><p className="text-slate-500 text-sm">Select a dataset in the Data Hub first.</p></div>;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">ABC-XYZ Segmentation</h1>
          <p className="text-slate-500 text-sm">Value contribution (A/B/C) × demand variability (X/Y/Z) across every store/item.</p>
        </div>
        <button className="btn-secondary" onClick={load} disabled={loading}>{loading ? "Loading…" : "Refresh"}</button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
              <th className="py-2">Store</th><th>Item</th><th>Annual Value</th><th>Contribution %</th><th>Segment</th><th>Priority</th>
            </tr>
          </thead>
          <tbody>
            {segments.map((s, i) => (
              <tr key={i} className="border-b border-slate-100 dark:border-slate-800/50">
                <td className="py-2">{s.store_id}</td>
                <td>{s.item_id}</td>
                <td>{s.annual_value?.toLocaleString()}</td>
                <td>{s.contribution_pct}%</td>
                <td><span className="badge bg-slate-100 dark:bg-slate-800">{s.segment}</span></td>
                <td><span className={`badge ${QUADRANT_COLOR[s.priority_quadrant]}`}>{s.priority_quadrant}</span></td>
              </tr>
            ))}
            {segments.length === 0 && !loading && <tr><td colSpan={6} className="py-4 text-slate-400">No segmentation data. Train a model first (Forecasting page).</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
