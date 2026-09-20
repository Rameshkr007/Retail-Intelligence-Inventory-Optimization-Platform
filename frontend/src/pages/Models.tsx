import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

const STATUS_COLOR: Record<string, string> = {
  Development: "bg-slate-100 text-slate-600",
  Validated: "bg-blue-100 text-blue-700",
  Production: "bg-emerald-100 text-emerald-700",
  Archived: "bg-slate-100 text-slate-400",
};

export default function Models() {
  const { datasetId, role } = useApp();
  const [versions, setVersions] = useState<any[]>([]);
  const [monitoring, setMonitoring] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setVersions(await api.getRegistry());
      if (datasetId) setMonitoring(await api.getMonitoring(datasetId));
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, [datasetId]);

  async function promote(id: number) {
    try {
      await api.updateModelStatus(id, "Production");
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Model Registry & Monitoring</h1>
        <p className="text-slate-500 text-sm">Every training run is versioned with its metrics and status.</p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {monitoring && (
        <div className={`card ${monitoring.retraining_recommended ? "border-amber-400" : ""}`}>
          <h2 className="font-semibold mb-2">Monitoring — dataset #{datasetId}</h2>
          <div className="flex gap-8 text-sm">
            <div><div className="text-slate-400 text-xs">Latest Test MAE</div><div className="font-bold text-lg">{monitoring.latest_test_mae?.toFixed(2)}</div></div>
            <div><div className="text-slate-400 text-xs">Latest Test WAPE</div><div className="font-bold text-lg">{monitoring.latest_test_wape?.toFixed(1)}%</div></div>
            <div><div className="text-slate-400 text-xs">Versions Trained</div><div className="font-bold text-lg">{monitoring.model_version_count}</div></div>
          </div>
          {monitoring.retraining_recommended && (
            <p className="text-sm text-amber-600 mt-2 font-medium">⚠ Retraining Recommended — test MAE exceeds threshold ({monitoring.retraining_threshold_mae}).</p>
          )}
        </div>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
              <th className="py-2">Version</th><th>Dataset</th><th>Algorithm</th><th>Status</th><th>Val MAE</th><th>Test MAE</th><th>Trained At</th><th></th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.model_version_id} className="border-b border-slate-100 dark:border-slate-800/50">
                <td className="py-2">#{v.model_version_id}</td>
                <td>{v.dataset_version_id}</td>
                <td>{v.algorithm}</td>
                <td><span className={`badge ${STATUS_COLOR[v.status]}`}>{v.status}</span></td>
                <td>{v.val_mae?.toFixed(2)}</td>
                <td>{v.test_mae?.toFixed(2)}</td>
                <td className="text-xs text-slate-400">{new Date(v.trained_at).toLocaleString()}</td>
                <td>
                  {role === "admin" && v.status !== "Production" && (
                    <button className="btn-secondary" onClick={() => promote(v.model_version_id)}>Promote</button>
                  )}
                </td>
              </tr>
            ))}
            {versions.length === 0 && <tr><td colSpan={8} className="py-4 text-slate-400">No models trained yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
