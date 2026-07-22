import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

function Placeholder({ name }: { name: string }) {
  return <div className="p-8"><h1 className="text-2xl font-bold">{name}</h1><p className="mt-2 text-gray-500">页面建设中...</p></div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Routes>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Placeholder name="总览" />} />
          <Route path="runs" element={<Placeholder name="运行记录" />} />
          <Route path="runs/:id" element={<Placeholder name="运行详情" />} />
          <Route path="cases" element={<Placeholder name="用例管理" />} />
          <Route path="settings" element={<Placeholder name="设置" />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
