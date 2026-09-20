import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppProvider, useApp } from "./state";
import Layout from "./Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import DataHub from "./pages/DataHub";
import Forecasting from "./pages/Forecasting";
import Inventory from "./pages/Inventory";
import Simulation from "./pages/Simulation";
import Analytics from "./pages/Analytics";
import Alerts from "./pages/Alerts";
import AIInsights from "./pages/AIInsights";
import Models from "./pages/Models";
import Reports from "./pages/Reports";
import InterviewMode from "./pages/InterviewMode";
import Architecture from "./pages/Architecture";
import AuditLogPage from "./pages/AuditLogPage";

function Protected({ children }: { children: React.ReactNode }) {
  const { isAuthed } = useApp();
  if (!isAuthed) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/data-hub" element={<Protected><DataHub /></Protected>} />
      <Route path="/forecasting" element={<Protected><Forecasting /></Protected>} />
      <Route path="/inventory" element={<Protected><Inventory /></Protected>} />
      <Route path="/simulation" element={<Protected><Simulation /></Protected>} />
      <Route path="/analytics" element={<Protected><Analytics /></Protected>} />
      <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
      <Route path="/insights" element={<Protected><AIInsights /></Protected>} />
      <Route path="/models" element={<Protected><Models /></Protected>} />
      <Route path="/reports" element={<Protected><Reports /></Protected>} />
      <Route path="/interview-mode" element={<Protected><InterviewMode /></Protected>} />
      <Route path="/architecture" element={<Protected><Architecture /></Protected>} />
      <Route path="/audit-log" element={<Protected><AuditLogPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppRoutes />
    </AppProvider>
  );
}
