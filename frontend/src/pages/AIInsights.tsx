import React, { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

const SUGGESTIONS = [
  "Which products are at highest stockout risk?",
  "Which stores have unusual demand?",
  "Show me products with high inventory and declining demand.",
  "Explain the forecast for store 1 item 1",
  "What are the top selling products?",
];

export default function AIInsights() {
  const { datasetId } = useApp();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function ask(q?: string) {
    if (!datasetId) return;
    const query = q ?? question;
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setAnswer(await api.askInsights(datasetId, query));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!datasetId) return <div className="card max-w-lg"><p className="text-slate-500 text-sm">Select a dataset in the Data Hub first.</p></div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">AI Insights</h1>
        <p className="text-slate-500 text-sm">
          Ask a question about this dataset. Answers are computed live from real data — never invented.
        </p>
      </div>

      <div className="card">
        <div className="flex gap-2 mb-3">
          <input
            className="input"
            placeholder="e.g. Which products are at highest stockout risk?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
          />
          <button className="btn" onClick={() => ask()} disabled={loading}>{loading ? "Thinking…" : "Ask"}</button>
        </div>
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} className="btn-secondary text-xs" onClick={() => { setQuestion(s); ask(s); }}>{s}</button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {answer && (
        <div className="card">
          <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">{answer.answer}</p>
          {answer.intent === "unknown" ? (
            <p className="text-xs text-slate-400">This app doesn't guess at questions outside what it can compute — try one of the suggestions above.</p>
          ) : answer.data?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    {Object.keys(answer.data[0]).map((k) => <th key={k} className="py-1 pr-3">{k}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {answer.data.map((row: any, i: number) => (
                    <tr key={i} className="border-b border-slate-100 dark:border-slate-800/50">
                      {Object.values(row).map((v: any, j) => <td key={j} className="py-1 pr-3">{String(v)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-400">No matching records found.</p>
          )}
        </div>
      )}
    </div>
  );
}
