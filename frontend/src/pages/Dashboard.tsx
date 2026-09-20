import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../state";

export default function Dashboard() {
  const { datasetId, setDatasetId } = useApp();
  const [dataset, setDataset] = useState<any>(null);
  const [monitoring, setMonitoring] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);

  useEffect(() => {
    api.listDatasets().then((list) => {
      setDatasets(list);
      if (!datasetId && list.length) setDatasetId(list[0].dataset_id);
    });
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    api.getDataset(datasetId).then(setDataset).catch(() => {});
    api.getMonitoring(datasetId).then(setMonitoring).catch(() => setMonitoring(null));
    api.getAlerts(datasetId).then((r) => setAlerts(r.alerts)).catch(() => setAlerts([]));
    api.getRecommendations(datasetId).then((r) => setRecommendations(r.recommendations)).catch(() => setRecommendations([]));
  }, [datasetId]);

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Executive Dashboard</h1>
        <p className="text-slate-500 text-sm">An explainable ML-based retail decision intelligence platform.</p>
      </div>

      {!datasetId && (
        <div className="card">
          <p className="text-sm text-slate-500 mb-3">No dataset selected yet.</p>
          <Link to="/data-hub" className="btn">Go to Data Hub</Link>
        </div>
      )}

      {dataset && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Kpi label="Total Records" value={dataset.record_count?.toLocaleString()} />
          <Kpi label="Data Quality Score" value={`${dataset.profiling_report?.data_quality_score}/100`} />
          <Kpi label="Stores" value={dataset.profiling_report?.unique_stores} />
          <Kpi label="Products" value={dataset.profiling_report?.unique_products} />
        </div>
      )}

      {monitoring && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <Kpi label="Latest Test MAE" value={monitoring.latest_test_mae?.toFixed(2)} />
          <Kpi label="Latest Test WAPE" value={`${monitoring.latest_test_wape?.toFixed(1)}%`} />
          <Kpi label="Active Alerts" value={alerts.length} accent={alerts.length > 0} />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <QuickLink to="/data-hub" title="Data Hub" desc="Upload a dataset and review its quality profile." />
        <QuickLink to="/forecasting" title="Forecasting" desc="Train LightGBM and view explainable forecasts." />
        <QuickLink to="/inventory" title="Inventory" desc="Safety Stock, ROP, EOQ and reorder recommendations." />
        <QuickLink to="/simulation" title="What-If Simulator" desc="Test demand-growth and lead-time scenarios." />
      </div>

      {recommendations.length > 0 && (
        <div className="card">
          <h2 className="font-semibold mb-3">Smart Recommendations</h2>
          <div className="space-y-2">
            {recommendations.slice(0, 5).map((r, i) => (
              <div key={i} className="flex items-start gap-3 text-sm border-b border-slate-100 dark:border-slate-800/50 pb-2 last:border-0">
                <span className={`badge shrink-0 ${r.priority === "HIGH" ? "bg-red-100 text-red-700" : r.priority === "MEDIUM" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>{r.priority}</span>
                <div>
                  <span className="font-medium">{r.action}</span> — <span className="text-slate-500">{r.reason}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {datasets.length > 1 && (
        <div className="card">
          <label className="label">Switch active dataset</label>
          <select className="input max-w-xs" value={datasetId ?? ""} onChange={(e) => setDatasetId(Number(e.target.value))}>
            {datasets.map((d) => <option key={d.dataset_id} value={d.dataset_id}>#{d.dataset_id} — {d.filename}</option>)}
          </select>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
  return (
    <div className="card">
      <div className="text-slate-400 text-xs">{label}</div>
      <div className={`text-2xl font-bold ${accent ? "text-amber-600" : ""}`}>{value ?? "—"}</div>
    </div>
  );
}

function QuickLink({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link to={to} className="card hover:shadow-md transition-shadow block">
      <div className="font-semibold">{title}</div>
      <div className="text-sm text-slate-500">{desc}</div>
    </Link>
  );
}
