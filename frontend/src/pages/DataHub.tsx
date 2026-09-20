import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

export default function DataHub() {
  const { datasetId, setDatasetId } = useApp();
  const [datasets, setDatasets] = useState<any[]>([]);
  const [profile, setProfile] = useState<any>(null);
  const [txLog, setTxLog] = useState<any>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshList() {
    try { setDatasets(await api.listDatasets()); } catch { /* ignore */ }
  }

  useEffect(() => { refreshList(); }, []);

  useEffect(() => {
    if (datasetId == null) return;
    api.getDataset(datasetId).then((d) => setProfile(d.profiling_report)).catch(() => {});
    api.getTransformations(datasetId).then(setTxLog).catch(() => {});
  }, [datasetId]);

  async function handleUpload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const res = await api.uploadDataset(file, file.name.toLowerCase().includes("demo"));
      setDatasetId(res.dataset_id);
      setProfile(res.profiling_report);
      await refreshList();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  const qualityColor = (score: number) =>
    score >= 90 ? "bg-emerald-100 text-emerald-700" : score >= 70 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700";

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Data Hub</h1>
        <p className="text-slate-500 text-sm">Upload a retail sales CSV/XLSX (Date, Store, Item, Sales) to profile and clean it.</p>
      </div>

      <div className="card">
        <label className="label">Upload dataset</label>
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          disabled={uploading}
          onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
          className="text-sm"
        />
        {uploading && <p className="text-sm text-slate-500 mt-2">Uploading & profiling… this can take a moment for large files.</p>}
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      <div className="card">
        <h2 className="font-semibold mb-3">Dataset versions</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
              <th className="py-2">ID</th><th>Filename</th><th>Records</th><th>Quality</th><th></th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((d) => (
              <tr key={d.dataset_id} className="border-b border-slate-100 dark:border-slate-800/50">
                <td className="py-2">{d.dataset_id}</td>
                <td>{d.filename} {d.is_demo && <span className="badge bg-slate-100 text-slate-500 ml-1">Demo Data</span>}</td>
                <td>{d.record_count.toLocaleString()}</td>
                <td><span className={`badge ${qualityColor(d.data_quality_score)}`}>{d.data_quality_score}/100</span></td>
                <td>
                  <button className="btn-secondary" onClick={() => setDatasetId(d.dataset_id)}>
                    {datasetId === d.dataset_id ? "Selected" : "Select"}
                  </button>
                </td>
              </tr>
            ))}
            {datasets.length === 0 && <tr><td colSpan={5} className="py-4 text-slate-400">No datasets uploaded yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {profile && (
        <div className="card">
          <h2 className="font-semibold mb-3">Data Quality Profile — dataset #{datasetId}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
            <Stat label="Total Records" value={profile.total_records?.toLocaleString()} />
            <Stat label="Duplicate Rows" value={profile.duplicate_rows} />
            <Stat label="Invalid Dates" value={profile.invalid_dates} />
            <Stat label="Negative Sales" value={profile.negative_sales} />
            <Stat label="Zero-Sales %" value={`${profile.zero_sales_percentage}%`} />
            <Stat label="Outliers (IQR)" value={profile.outliers} />
            <Stat label="Unique Stores" value={profile.unique_stores} />
            <Stat label="Unique Products" value={profile.unique_products} />
          </div>
          <div className={`inline-block badge ${qualityColor(profile.data_quality_score)} text-base px-3 py-1`}>
            Data Quality Score: {profile.data_quality_score}/100
          </div>
          {profile.data_quality_breakdown && (
            <div className="text-xs text-slate-500 mt-3">
              Deductions: {Object.entries(profile.data_quality_breakdown.deductions || {}).map(([k, v]) => `${k}: -${v}`).join(" · ")}
            </div>
          )}
        </div>
      )}

      {txLog && (
        <div className="card">
          <h2 className="font-semibold mb-3">Data Transformation Log</h2>
          <ul className="text-sm space-y-1">
            {txLog.transformation_log.map((step: any, i: number) => (
              <li key={i} className="flex justify-between border-b border-slate-100 dark:border-slate-800/50 py-1">
                <span className="text-slate-600 dark:text-slate-300">{step.step.replaceAll("_", " ")}</span>
                <span className="font-mono text-xs text-slate-500">{JSON.stringify(step)}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-slate-400 mt-2">{txLog.flagged_record_count} rows flagged and available for inspection.</p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-slate-400 text-xs">{label}</div>
      <div className="font-semibold text-lg">{value}</div>
    </div>
  );
}
