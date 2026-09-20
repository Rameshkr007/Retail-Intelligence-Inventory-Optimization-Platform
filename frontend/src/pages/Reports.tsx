import React, { useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

export default function Reports() {
  const { datasetId } = useApp();
  const [error, setError] = useState<string | null>(null);

  async function download(kind: "csv" | "xlsx" | "pdf") {
    if (!datasetId) return;
    setError(null);
    try {
      if (kind === "csv") await api.downloadReport(`/api/reports/forecast.csv?dataset_id=${datasetId}`, `forecast_metrics_${datasetId}.csv`);
      if (kind === "xlsx") await api.downloadReport(`/api/reports/inventory.xlsx?dataset_id=${datasetId}`, `inventory_recommendations_${datasetId}.xlsx`);
      if (kind === "pdf") await api.downloadReport(`/api/reports/executive.pdf?dataset_id=${datasetId}`, `executive_report_${datasetId}.pdf`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!datasetId) return <div className="card max-w-lg"><p className="text-slate-500 text-sm">Select a dataset in the Data Hub first.</p></div>;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Reports</h1>
        <p className="text-slate-500 text-sm">Downloadable reports generated from this dataset's real training/inventory results.</p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="card space-y-4">
        <ReportRow title="Forecast Metrics (CSV)" desc="Latest model's validation/test metrics." onClick={() => download("csv")} />
        <ReportRow title="Inventory Recommendations (Excel)" desc="Every Safety Stock/ROP/EOQ calculation run for this dataset." onClick={() => download("xlsx")} />
        <ReportRow title="Executive Report (PDF)" desc="Dataset summary, model metrics, and documented limitations." onClick={() => download("pdf")} />
      </div>
    </div>
  );
}

function ReportRow({ title, desc, onClick }: { title: string; desc: string; onClick: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/50 pb-3 last:border-0 last:pb-0">
      <div>
        <div className="font-medium text-sm">{title}</div>
        <div className="text-xs text-slate-400">{desc}</div>
      </div>
      <button className="btn" onClick={onClick}>Download</button>
    </div>
  );
}
