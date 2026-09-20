import React, { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

const RISK_COLOR: Record<string, string> = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

export default function Inventory() {
  const { datasetId, storeId, setStoreId, itemId, setItemId } = useApp();
  const [form, setForm] = useState({
    lead_time_days: 7, service_level: 0.95, ordering_cost: 50,
    holding_cost_per_unit_per_year: 5, current_stock: 100,
  });
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [simState, setSimState] = useState<any>(null);
  const [saleQty, setSaleQty] = useState(1);

  async function handleOptimize() {
    if (!datasetId) return;
    setError(null);
    try {
      setResult(await api.optimizeInventory(datasetId, form));
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadSimState() {
    if (!datasetId) return;
    try {
      setSimState(await api.getSimulationState(datasetId, storeId, itemId));
    } catch { /* ignore */ }
  }

  async function recordSale() {
    if (!datasetId) return;
    setError(null);
    try {
      const res = await api.simulateSale(datasetId, storeId, itemId, saleQty);
      setSimState({ status: res.status, initialized: true, current_stock: res.current_stock_after_sale });
      setResult((prev: any) => prev && { ...prev, ...res, current_stock: res.current_stock_after_sale });
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!datasetId) return <div className="card max-w-lg"><p className="text-slate-500 text-sm">Select a dataset in the Data Hub first.</p></div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Inventory Optimization</h1>
        <p className="text-slate-500 text-sm">Safety Stock, Reorder Point, EOQ — computed from real demand history and your policy inputs.</p>
      </div>

      <div className="card grid grid-cols-2 md:grid-cols-3 gap-4">
        <NumField label="Store ID" value={storeId} onChange={setStoreId} />
        <NumField label="Item ID" value={itemId} onChange={setItemId} />
        <NumField label="Current Stock" value={form.current_stock} onChange={(v) => setForm({ ...form, current_stock: v })} />
        <NumField label="Lead Time (days)" value={form.lead_time_days} onChange={(v) => setForm({ ...form, lead_time_days: v })} />
        <NumField label="Service Level" value={form.service_level} step={0.01} onChange={(v) => setForm({ ...form, service_level: v })} />
        <NumField label="Ordering Cost" value={form.ordering_cost} onChange={(v) => setForm({ ...form, ordering_cost: v })} />
        <NumField label="Holding Cost/Unit/Yr" value={form.holding_cost_per_unit_per_year} onChange={(v) => setForm({ ...form, holding_cost_per_unit_per_year: v })} />
        <div className="flex items-end"><button className="btn" onClick={handleOptimize}>Calculate</button></div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="font-semibold">Store {result.store_id} / Item {result.item_id}</h2>
            <span className={`badge ${RISK_COLOR[result.stockout_risk]}`}>Stockout Risk: {result.stockout_risk}</span>
            {result.overstock_risk && <span className="badge bg-purple-100 text-purple-700">Potential Overstock</span>}
          </div>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-4 text-sm mb-4">
            <Stat label="Avg Daily Demand" value={result.avg_daily_demand} />
            <Stat label="Safety Stock" value={result.safety_stock} />
            <Stat label="Reorder Point" value={result.reorder_point} />
            <Stat label="EOQ" value={result.eoq} />
            <Stat label="Suggested Order" value={result.suggested_order} highlight />
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">{result.reason}</p>
          {result.inventory_health_score && (
            <div className="flex items-center gap-3 border-t border-slate-100 dark:border-slate-800/50 pt-3">
              <span className="text-xs text-slate-400">Inventory Health Score</span>
              <span className={`badge ${result.inventory_health_score.score >= 70 ? "bg-emerald-100 text-emerald-700" : result.inventory_health_score.score >= 40 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
                {result.inventory_health_score.score}/100
              </span>
              <span className="text-xs text-slate-400">
                {Object.entries(result.inventory_health_score.deductions).filter(([, v]: any) => v > 0).map(([k, v]: any) => `-${v} ${k.replaceAll("_", " ")}`).join(" · ") || "no deductions"}
              </span>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <div className="flex items-center gap-2 mb-2">
          <h2 className="font-semibold">Digital Twin — Real-Time Simulation</h2>
          <span className="badge bg-purple-100 text-purple-700">SIMULATED</span>
        </div>
        <p className="text-xs text-slate-400 mb-3">
          Not a live POS feed — this decrements a simulated stock counter so you can see stock → risk → recommendation update live.
        </p>
        <div className="flex items-end gap-3">
          <div>
            <label className="label">Sale quantity</label>
            <input className="input w-24" type="number" value={saleQty} onChange={(e) => setSaleQty(Number(e.target.value))} />
          </div>
          <button className="btn" onClick={recordSale}>Record Simulated Sale</button>
          <button className="btn-secondary" onClick={loadSimState}>Refresh State</button>
        </div>
        {simState?.initialized && (
          <p className="text-sm mt-3">Simulated current stock: <b>{simState.current_stock}</b></p>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div>
      <div className="text-slate-400 text-xs">{label}</div>
      <div className={`font-bold text-xl ${highlight ? "text-brand-600" : ""}`}>{value}</div>
    </div>
  );
}

function NumField({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input className="input" type="number" step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}
