import { useEffect, useState } from "react";
import { ChevronDown, FileCode, TestTube } from "lucide-react";
import { listUnitTests } from "../api/unitTests";
import type { UnitTestFile } from "../api/types";

export default function UnitTestTree() {
  const [files, setFiles] = useState<UnitTestFile[]>([]);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listUnitTests()
      .then(setFiles)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const toggle = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (loading) return <div className="p-4 text-gray-500">加载中...</div>;
  if (files.length === 0) return <div className="p-4 text-gray-500">暂无单元测试用例</div>;

  const totalTests = files.reduce(
    (sum, f) => sum + f.describes.reduce((s, d) => s + d.tests.length, 0),
    0
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1 text-sm text-gray-500">
        <TestTube className="w-4 h-4" />
        {files.length} 个测试文件 / {totalTests} 个测试用例
      </div>

      {files.map((file) => {
        const fileKey = `file-${file.file_path}`;
        const fileCollapsed = !!collapsed[fileKey];
        const fileTestCount = file.describes.reduce((s, d) => s + d.tests.length, 0);

        return (
          <div key={file.file_path} className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div
              className="flex items-center gap-3 p-4 cursor-pointer select-none hover:bg-gray-50"
              onClick={() => toggle(fileKey)}
            >
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${
                  fileCollapsed ? "-rotate-90" : ""
                }`}
              />
              <FileCode className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-medium flex-1">{file.file_path}</span>
              <span className="text-xs text-gray-400">{fileTestCount} tests</span>
            </div>

            {!fileCollapsed && (
              <div className="px-4 pb-3 space-y-2">
                {file.describes.map((describe) => {
                  const dKey = `${fileKey}-${describe.name}`;
                  const dCollapsed = !!collapsed[dKey];

                  return (
                    <div key={describe.name} className="pl-4">
                      <div
                        className="flex items-center gap-2 py-1 cursor-pointer select-none"
                        onClick={() => toggle(dKey)}
                      >
                        <ChevronDown
                          className={`w-3 h-3 text-gray-400 transition-transform duration-200 ${
                            dCollapsed ? "-rotate-90" : ""
                          }`}
                        />
                        <span className="text-sm font-semibold text-gray-700">
                          {describe.name}
                        </span>
                        <span className="text-xs text-gray-400">
                          ({describe.tests.length})
                        </span>
                      </div>

                      {!dCollapsed && (
                        <div className="pl-5 space-y-0.5">
                          {describe.tests.map((t) => (
                            <div
                              key={t.id}
                              className="flex items-center gap-2 py-0.5 text-sm text-gray-600"
                            >
                              <TestTube className="w-3 h-3 text-gray-400" />
                              {t.test_name}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
