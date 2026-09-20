import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";

export default function AuditLogPage() {
  const { role } = useApp();
  const [logs, setLogs] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getAuditLogs().then(setLogs).catch((err) => setError(err.message));
  }, []);

  if (role !== "admin") {
    return <div className="card max-w-lg"><p className="text-slate-500 text-sm">Audit logs are visible to admins only.</p></div>;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <p className="text-slate-500 text-sm">Every login, upload, training run, and status change is tracked.</p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-800">
              <th className="py-2">Time</th><th>User</th><th>Action</th><th>Entity</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-b border-slate-100 dark:border-slate-800/50">
                <td className="py-2 text-xs text-slate-400">{new Date(l.timestamp).toLocaleString()}</td>
                <td>{l.user_email}</td>
                <td>{l.action}</td>
                <td className="text-xs text-slate-500">{l.entity}</td>
              </tr>
            ))}
            {logs.length === 0 && <tr><td colSpan={4} className="py-4 text-slate-400">No activity yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
