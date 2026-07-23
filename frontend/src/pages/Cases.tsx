import { useEffect, useState } from "react";
import { listProjects, listSuites } from "../api/projects";
import { get } from "../api/client";
import type { TestSuite, TestCase } from "../api/types";

export default function Cases() {
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [cases, setCases] = useState<TestCase[]>([]);

  useEffect(() => {
    listProjects().then((projs) => {
      if (projs.length > 0) listSuites(projs[0].id).then(setSuites);
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (suites.length === 0) return;
    Promise.all(
      suites.map((s) => get<TestCase[]>(`/suites/${s.id}/cases`))
    ).then((results) => setCases(results.flat())).catch(console.error);
  }, [suites]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">用例管理</h1>
      <p className="text-gray-500">共 {cases.length} 个用例，{suites.length} 个套件</p>
      {suites.map((suite) => {
        const suiteCases = cases.filter((c) => c.suite_id === suite.id);
        return (
          <div key={suite.id} className="bg-white rounded-xl shadow-sm p-4">
            <h2 className="text-lg font-semibold mb-2">{suite.name}</h2>
            <p className="text-sm text-gray-500 mb-3">{suite.description}</p>
            <div className="space-y-1">
              {suiteCases.map((c) => (
                <div key={c.id} className="flex items-center gap-3 px-3 py-1.5 bg-gray-50 rounded">
                  <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                    c.priority === "P0" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                  }`}>{c.priority}</span>
                  <span className="text-sm">{c.name}</span>
                  <span className="text-xs text-gray-400 ml-auto">{c.function_name}</span>
                </div>
              ))}
              {suiteCases.length === 0 && (
                <p className="text-sm text-gray-400 px-3">暂无用例</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
