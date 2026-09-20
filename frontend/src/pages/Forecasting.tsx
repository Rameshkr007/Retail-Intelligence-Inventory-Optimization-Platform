import React, { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

export default function Forecasting() {
  const { datasetId, storeId, setStoreId, itemId, setItemId } = useApp();
  const [horizon, setHorizon] = useState(14);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleTrain() {
    if (!datasetId) return;
    setTraining(true);
    setError(null);
    try {
      const res = await api.trainModel(datasetId, horizon);
      setTrainResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setTraining(false);
    }
  }

  async function handleForecast() {
    if (!datasetId) return;
    setError(null);
    try {
      setForecast(await api.getForecast(datasetId, storeId, itemId));
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!datasetId) return <Empty />;

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Forecasting</h1>
        <p className="text-slate-500 text-sm">LightGBM primary model, walk-forward validated, compared against baselines.</p>
      </div>

      <div className="card flex flex-wrap items-end gap-4">
        <Field label="Forecast horizon (days)">
          <input className="input w-28" type="number" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
        </Field>
        <button className="btn" disabled={training} onClick={handleTrain}>
          {training ? "Training…" : "Train / Retrain Model"}
        </button>
        <Field label="Store ID">
          <input className="input w-24" type="number" value={storeId} onChange={(e) => setStoreId(Number(e.target.value))} />
        </Field>
        <Field label="Item ID">
          <input className="input w-24" type="number" value={itemId} onChange={(e) => setItemId(Number(e.target.value))} />
        </Field>
        <button className="btn-secondary" onClick={handleForecast}>Get Forecast</button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {trainResult && (
        <div className="card">
          <h2 className="font-semibold mb-3">Model Evaluation (real walk-forward metrics)</h2>
          <div className="grid grid-cols-2 gap-6 text-sm">
            <MetricsTable title="LightGBM — Validation" metrics={trainResult.val_metrics} />
            <MetricsTable title="LightGBM — Test" metrics={trainResult.test_metrics} />
          </div>
          <h3 className="font-semibold mt-4 mb-2 text-sm">Baseline comparison (test window)</h3>
          <table className="w-full text-xs">
            <thead><tr className="text-left text-slate-500"><th>Model</th><th>MAE</th><th>RMSE</th><th>WAPE</th></tr></thead>
            <tbody>
              {Object.entries(trainResult.baseline_comparison || {}).map(([name, m]: any) => (
                <tr key={name} className="border-t border-slate-100 dark:border-slate-800/50">
                  <td className="py-1">{name.replaceAll("_", " ")}</td>
                  <td>{m.mae?.toFixed(2)}</td><td>{m.rmse?.toFixed(2)}</td><td>{m.wape?.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {forecast && (
        <div className="card">
          <h2 className="font-semibold mb-3">
            Forecast — Store {forecast.store_id}, Item {forecast.item_id} ({forecast.horizon}-day horizon)
          </h2>
          <div className="flex gap-8 mb-4">
            <BigStat label="Lower Bound" value={forecast.lower_bound} />
            <BigStat label="Point Forecast" value={forecast.point_forecast} highlight />
            <BigStat label="Upper Bound" value={forecast.upper_bound} />
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-300 italic">"{forecast.explanation}"</p>
          <h3 className="font-semibold mt-4 mb-2 text-sm">Top SHAP drivers</h3>
          <ul className="text-sm space-y-1">
            {forecast.top_drivers.map((d: any, i: number) => (
              <li key={i} className={`flex justify-between ${d.direction === "increase" ? "text-emerald-600" : "text-red-600"}`}>
                <span>{d.feature.replaceAll("_", " ")}</span>
                <span>{d.direction === "increase" ? "▲" : "▼"} {d.shap_value.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function MetricsTable({ title, metrics }: { title: string; metrics: any }) {
  return (
    <div>
      <div className="font-medium mb-1">{title}</div>
      <table className="w-full text-xs">
        <tbody>
          {Object.entries(metrics).map(([k, v]: any) => (
            <tr key={k} className="border-t border-slate-100 dark:border-slate-800/50">
              <td className="py-1 text-slate-500 uppercase">{k}</td>
              <td className="text-right">{typeof v === "number" ? v.toFixed(2) : String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BigStat({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div>
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`text-3xl font-bold ${highlight ? "text-brand-600" : ""}`}>{value}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
    </div>
  );
}

function Empty() {
  return (
    <div className="card max-w-lg">
      <p className="text-slate-500 text-sm">Select a dataset in the Data Hub first.</p>
    </div>
  );
}
