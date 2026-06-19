import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard, CalendarDays, BarChart3, Search,
  Settings, LogOut, Sparkles, Menu, X,
} from "lucide-react";
import { useState } from "react";

const links = [
  { to: "/", label: "Approvals", icon: LayoutDashboard, testid: "nav-approvals" },
  { to: "/calendar", label: "Calendar", icon: CalendarDays, testid: "nav-calendar" },
  { to: "/insights", label: "Insights", icon: BarChart3, testid: "nav-insights" },
  { to: "/competitors", label: "Competitor Intel", icon: Search, testid: "nav-competitors" },
  { to: "/settings", label: "Settings", icon: Settings, testid: "nav-settings" },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => { logout(); navigate("/login"); };

  return (
    <div className="min-h-screen bg-white">
      {/* Top nav */}
      <header className="sticky top-0 z-40 bg-white border-b border-zinc-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-zinc-900 text-white flex items-center justify-center">
              <Sparkles size={16} />
            </div>
            <div>
              <div className="font-display font-bold text-base leading-none">BagnShop AI</div>
              <div className="text-[10px] tracking-[0.18em] uppercase text-zinc-500 mt-0.5">Social Manager</div>
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-1" data-testid="primary-nav">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                data-testid={l.testid}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-zinc-900 text-white"
                      : "text-zinc-700 hover:bg-zinc-100"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="hidden md:flex items-center gap-3">
            <span className="text-xs text-zinc-500" data-testid="user-email">{user?.email}</span>
            <button
              onClick={handleLogout}
              data-testid="logout-btn"
              className="p-2 rounded-md hover:bg-zinc-100 text-zinc-600"
              aria-label="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
          <button
            className="md:hidden p-2 rounded-md hover:bg-zinc-100"
            onClick={() => setMobileOpen((v) => !v)}
            data-testid="mobile-menu-toggle"
            aria-label="Menu"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        {mobileOpen && (
          <div className="md:hidden border-t border-zinc-200 bg-white">
            <div className="px-4 py-3 flex flex-col gap-1">
              {links.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  end={l.to === "/"}
                  onClick={() => setMobileOpen(false)}
                  data-testid={`m-${l.testid}`}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium ${
                      isActive ? "bg-zinc-900 text-white" : "text-zinc-700"
                    }`
                  }
                >
                  <l.icon size={16} /> {l.label}
                </NavLink>
              ))}
              <button
                onClick={handleLogout}
                data-testid="m-logout-btn"
                className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-zinc-700"
              >
                <LogOut size={16} /> Logout
              </button>
            </div>
          </div>
        )}
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">{children}</main>
    </div>
  );
}
