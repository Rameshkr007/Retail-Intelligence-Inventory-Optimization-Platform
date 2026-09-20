import React from "react";

const LAYERS = [
  { name: "Frontend", detail: "React + Vite + TypeScript + Tailwind. Talks to the backend only via the REST API — no direct DB access." },
  { name: "API", detail: "FastAPI. Validates input with Pydantic, issues/verifies JWTs, enforces RBAC per endpoint." },
  { name: "Data Processing", detail: "Schema auto-detection, profiling, documented Data Quality Score, non-destructive cleaning with a full transformation log." },
  { name: "Feature Engineering", detail: "Calendar, lag (1–90 days), rolling (7–30 days), and demand-behavior features — all leakage-safe (shift-before-window)." },
  { name: "ML Model", detail: "LightGBM, trained per dataset with early stopping; baselines (naive/seasonal-naive/moving-avg/exp-smoothing) computed for honest comparison." },
  { name: "Forecast Engine", detail: "Chronological train/val/test split (never random); uncertainty bounds from the model's own validation residual std." },
  { name: "Inventory Optimization", detail: "Safety Stock, Reorder Point, EOQ from standard formulas over real computed demand mean/std/annual totals." },
  { name: "Database", detail: "PostgreSQL (SQLite fallback for local dev) via SQLAlchemy — dataset versions, model versions, inventory recs, audit logs." },
];

const QA = [
  { q: "Why LightGBM?", a: "Gradient-boosted trees handle tabular, non-linear, mixed categorical/numeric features (calendar + lag + rolling) well, train fast even on 900K+ rows, and support early stopping against a validation set — a good fit for daily Store×SKU demand data without requiring the manual seasonal decomposition classical statistical models need." },
  { q: "Why a time-series (chronological) split instead of random?", a: "Random splitting lets the model see future rows during training, which leaks information it wouldn't have at prediction time in production and makes the reported accuracy meaningless. A chronological split — train on the past, validate/test on the future — is the only split that measures what the model will actually do when deployed." },
  { q: "Why lag and rolling features instead of feeding LightGBM raw dates?", a: "Tree models split on feature values, so 'yesterday's demand' or 'the last 28-day average' gives the model direct access to the autocorrelation and trend that drives near-term demand, which a bare calendar date can't express by itself." },
  { q: "Why Safety Stock and Reorder Point specifically?", a: "They're the standard, explainable inventory-theory formulas: Safety Stock buffers against demand variability during lead time (z·σ·√L), and Reorder Point (lead-time demand + safety stock) is the trigger level at which to place a new order — both are auditable by a supply-chain reviewer rather than a black box." },
  { q: "Why EOQ?", a: "EOQ balances ordering cost against holding cost to minimize total inventory cost for a given annual demand — it answers 'how much to order', complementing ROP's 'when to order'." },
  { q: "Why SHAP?", a: "SHAP gives a mathematically consistent attribution of each feature's contribution to a specific prediction (local) and across the dataset (global), so a forecast can be explained in plain business language instead of trusted blindly." },
  { q: "Why is AI Insights a rule-based query router instead of an LLM chatbot?", a: "An LLM asked to answer from 'the data' can still hallucinate specific numbers. Routing recognized questions to the same deterministic computations used elsewhere in the app (and explicitly declining unrecognized questions) guarantees every number in an answer traces to a real computation — by construction, not by hoping the model behaves." },
];

export default function Architecture() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Technical Architecture</h1>
        <p className="text-slate-500 text-sm">For interviews and project viva — the system layer by layer, and why each choice was made.</p>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-4">Pipeline</h2>
        <div className="space-y-2">
          {LAYERS.map((l, i) => (
            <div key={l.name} className="flex gap-4 items-start">
              <div className="w-6 text-right text-slate-400 text-xs pt-0.5">{i + 1}</div>
              <div>
                <div className="font-medium text-sm">{l.name}</div>
                <div className="text-sm text-slate-500">{l.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-4">Design decisions (Q&A)</h2>
        <div className="space-y-4">
          {QA.map((item) => (
            <div key={item.q}>
              <div className="font-medium text-sm text-brand-700 dark:text-brand-400">{item.q}</div>
              <div className="text-sm text-slate-600 dark:text-slate-300">{item.a}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-2">Honest limitations</h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Metrics are computed only from the dataset currently loaded and may not generalize to other
          periods or unseen store/item combinations. Inventory figures depend on configurable business
          assumptions (lead time, service level, costs) supplied by the user, not fitted from data.
          No feature claims to be "real-time" unless backed by a live data connection — this build's
          data flow is batch upload → compute → serve.
        </p>
      </div>
    </div>
  );
}
