import { NavLink } from "react-router-dom";
import { LayoutDashboard, PlayCircle, ListChecks, Settings, Eye } from "lucide-react";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "总览" },
  { to: "/runs", icon: PlayCircle, label: "运行记录" },
  { to: "/cases", icon: ListChecks, label: "用例管理" },
  { to: "/settings", icon: Settings, label: "设置" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 bg-gray-900 text-white flex flex-col min-h-screen">
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Eye className="w-6 h-6 text-green-400" />
          <span className="font-bold text-lg">AutoTest</span>
        </div>
      </div>
      <nav className="flex-1 p-2">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                isActive ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-800"
              }`
            }
          >
            <Icon className="w-5 h-5" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
