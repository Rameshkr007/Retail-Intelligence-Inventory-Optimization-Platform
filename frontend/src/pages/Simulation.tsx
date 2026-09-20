import React, { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

export default function Simulation() {
  const { datasetId, storeId, setStoreId, itemId, setItemId } = useApp();
  const [growth, setGrowth] = useState(0);
  const [leadTime, setLeadTime] = useState(7);
  const [currentStock, setCurrentStock] = useState(100);
  const [result, setResult] = useState<any>(null);
  const [planning, setPlanning] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!datasetId) return;
    setError(null);
    try {
      setResult(await api.whatIf(datasetId, {
        lead_time_days: leadTime, current_stock: currentStock, demand_growth_pct: growth,
      }));
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function runPlanning() {
    if (!datasetId) return;
    setError(null);
    try {
      const res = await api.getScenarioPlanning(datasetId, storeId, itemId, currentStock);
      setPlanning(res.scenarios);
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!datasetId) return <div className="card max-w-lg"><p className="text-slate-500 text-sm">Select a dataset in the Data Hub first.</p></div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">What-If Simulator</h1>
        <p className="text-slate-500 text-sm">"What happens if demand grows X% or lead time changes?" — recomputed live from real formulas.</p>
      </div>

      <div className="card grid grid-cols-2 md:grid-cols-4 gap-4">
        <Field label="Store ID"><input className="input" type="number" value={storeId} onChange={(e) => setStoreId(Number(e.target.value))} /></Field>
        <Field label="Item ID"><input className="input" type="number" value={itemId} onChange={(e) => setItemId(Number(e.target.value))} /></Field>
        <Field label="Current Stock"><input className="input" type="number" value={currentStock} onChange={(e) => setCurrentStock(Number(e.target.value))} /></Field>
        <Field label="Lead Time (days)"><input className="input" type="number" value={leadTime} onChange={(e) => setLeadTime(Number(e.target.value))} /></Field>
        <Field label="Demand growth %">
          <input className="input" type="range" min={-50} max={100} value={growth} onChange={(e) => setGrowth(Number(e.target.value))} />
          <div className="text-sm mt-1">{growth > 0 ? "+" : ""}{growth}%</div>
        </Field>
        <div className="flex items-end"><button className="btn" onClick={run}>Run Simulation</button></div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="card">
          <h2 className="font-semibold mb-4">Baseline vs After Scenario</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <th className="py-2">Metric</th><th>Baseline</th><th>After ({growth > 0 ? "+" : ""}{growth}%)</th><th>Delta</th>
              </tr>
            </thead>
            <tbody>
              <Row label="Safety Stock" a={result.baseline.safety_stock} b={result.after_scenario.safety_stock} d={result.delta.safety_stock} />
              <Row label="Reorder Point" a={result.baseline.reorder_point} b={result.after_scenario.reorder_point} d={result.delta.reorder_point} />
              <Row label="EOQ" a={result.baseline.eoq} b={result.after_scenario.eoq} d={0} noDelta />
              <Row label="Suggested Order" a={result.baseline.suggested_order} b={result.after_scenario.suggested_order} d={result.delta.suggested_order} />
            </tbody>
          </table>
          <div className="mt-4 flex gap-4 text-sm">
            <span>Baseline risk: <b>{result.baseline.stockout_risk}</b></span>
            <span>After risk: <b>{result.after_scenario.stockout_risk}</b></span>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-2">
        <div>
          <h2 className="text-lg font-semibold">Scenario Planning</h2>
          <p className="text-slate-500 text-sm">5 standard business scenarios, same real formulas, side by side.</p>
        </div>
        <button className="btn-secondary" onClick={runPlanning}>Run All Scenarios</button>
      </div>

      {planning && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <th className="py-2">Scenario</th><th>Forecast Demand</th><th>Lead Time</th><th>Safety Stock</th><th>ROP</th><th>Suggested Order</th><th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(planning).map(([name, s]: any) => (
                <tr key={name} className="border-b border-slate-100 dark:border-slate-800/50">
                  <td className="py-2 font-medium">{name.replaceAll("_", " ")}</td>
                  <td>{s.forecast_demand}</td>
                  <td>{s.lead_time_days}d</td>
                  <td>{s.safety_stock}</td>
                  <td>{s.reorder_point}</td>
                  <td className="font-semibold">{s.suggested_order}</td>
                  <td>{s.stockout_risk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Row({ label, a, b, d, noDelta }: { label: string; a: number; b: number; d: number; noDelta?: boolean }) {
  return (
    <tr className="border-b border-slate-100 dark:border-slate-800/50">
      <td className="py-2">{label}</td><td>{a}</td><td className="font-semibold">{b}</td>
      <td className={noDelta ? "" : d > 0 ? "text-red-600" : d < 0 ? "text-emerald-600" : ""}>{noDelta ? "—" : (d > 0 ? "+" : "") + d}</td>
    </tr>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="label">{label}</label>{children}</div>;
}
