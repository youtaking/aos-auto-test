import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Runs from "./pages/Runs";
import RunDetail from "./pages/RunDetail";
import Cases from "./pages/Cases";
import ApiTests from "./pages/ApiTests";
import Reports from "./pages/Reports";
import AIAnalysis from "./pages/AIAnalysis";
import PRPipeline from "./pages/PRPipeline";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="runs" element={<Runs />} />
          <Route path="runs/:id" element={<RunDetail />} />
          <Route path="cases" element={<Cases />} />
          <Route path="api-tests" element={<ApiTests />} />
          <Route path="reports" element={<Reports />} />
          <Route path="ai-analysis" element={<AIAnalysis />} />
          <Route path="pipelines" element={<PRPipeline />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
