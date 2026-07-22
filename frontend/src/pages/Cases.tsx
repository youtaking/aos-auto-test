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
    if (suites.length > 0) get<TestCase[]>(`/suites/${suites[0].id}/cases`).then(setCases).catch(console.error);
  }, [suites]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">用例管理</h1>
      {suites.map((suite) => (
        <div key={suite.id} className="bg-white rounded-xl shadow-sm p-4">
          <h2 className="text-lg font-semibold mb-3">{suite.name}</h2>
          <p className="text-sm text-gray-500 mb-2">{suite.description}</p>
          <div className="text-sm text-gray-400">
            用例数: {cases.filter((c) => c.suite_id === suite.id).length}
          </div>
        </div>
      ))}
    </div>
  );
}
