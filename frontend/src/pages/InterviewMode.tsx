import React from "react";

const PIPELINE = [
  "Frontend (React + Vite + TS + Tailwind)",
  "FastAPI REST API (JWT auth, RBAC)",
  "Data Ingestion & Quality Engine",
  "Feature Engineering (leakage-safe)",
  "LightGBM Forecasting + Baselines",
  "SHAP Explainability",
  "Inventory Optimization Engine",
  "Risk Detection & Segmentation",
  "PostgreSQL",
];

const QA = [
  {
    q: "Why LightGBM?",
    a: "Gradient-boosted trees handle tabular, mixed-scale features (lags, rolling stats, calendar flags) well without heavy preprocessing, train fast even on hundreds of thousands of rows, and expose feature importances / SHAP values natively for explainability — which a black-box deep model wouldn't give as cheaply.",
  },
  {
    q: "Why a time-based split instead of random train/test split?",
    a: "Sales data is autocorrelated in time. A random split would let the model see 'future' rows during training (e.g. a lag feature computed from a day that's technically in the test set), which inflates accuracy and doesn't reflect real deployment where you only ever have the past to predict the future.",
  },
  {
    q: "Why lag and rolling features instead of feeding raw dates?",
    a: "Demand is driven by recent momentum and seasonal recurrence, not just the calendar date itself. Lag features (last week, last month) and rolling means/stds let the model learn 'what happened recently and how volatile is it', which raw date fields can't express on their own.",
  },
  {
    q: "Why Safety Stock, and why that formula?",
    a: "Safety Stock = z·σ·√L buffers against demand variability during the lead time, at a chosen service level (z-score). It's a standard, textbook inventory formula — not something we fit to data — so results are explainable and auditable, and z scales the buffer to how much stockout risk the business is willing to accept.",
  },
  {
    q: "Why Reorder Point and EOQ specifically?",
    a: "ROP tells you *when* to reorder (lead-time demand + safety stock); EOQ tells you *how much* to order to balance ordering cost against holding cost. Together they turn a forecast into an actual operational decision, which is the core research gap this project targets — forecasting in isolation vs. forecasting connected to inventory action.",
  },
  {
    q: "Why SHAP instead of just feature importance?",
    a: "Global feature importance tells you what matters across all predictions on average. SHAP gives a per-prediction breakdown — for THIS forecast, which features pushed it up or down — which is what a manager actually needs to trust and act on an individual forecast, not just an aggregate ranking.",
  },
  {
    q: "Why is the 'AI Insights' feature a rule-based query engine and not a chatbot LLM?",
    a: "A generic LLM answering from a prompt can fabricate plausible-sounding numbers. This project's own requirement is that the assistant 'must never fabricate data.' A deterministic intent classifier that routes recognized questions to the same computed functions used elsewhere in the app guarantees every number is real — verified by testing that an out-of-scope question is correctly refused rather than answered with a guess.",
  },
  {
    q: "Why is 'real-time' inventory simulation explicitly labeled SIMULATED?",
    a: "There's no live POS/ERP feed connected. Rather than fake that connection, the response payload explicitly says status: SIMULATED, so the demo is honest about what it is — a state machine showing how stock, risk, and recommendations would update if a real feed existed.",
  },
];

export default function InterviewMode() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Technical Architecture / Interview Mode</h1>
        <p className="text-slate-500 text-sm">A quick-reference for explaining this project's design decisions.</p>
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3">Pipeline</h2>
        <div className="flex flex-col gap-1">
          {PIPELINE.map((step, i) => (
            <div key={step} className="flex items-center gap-2 text-sm">
              <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold">{i + 1}</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        {QA.map((item) => (
          <div key={item.q} className="card">
            <div className="font-semibold text-sm mb-1">{item.q}</div>
            <div className="text-sm text-slate-600 dark:text-slate-300">{item.a}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
