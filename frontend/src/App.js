import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import CalendarPage from "@/pages/CalendarPage";
import Insights from "@/pages/Insights";
import Competitors from "@/pages/Competitors";
import Settings from "@/pages/Settings";
import "@/App.css";

const Private = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-12 text-zinc-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
};

const PublicOnly = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-12 text-zinc-500">Loading...</div>;
  if (user) return <Navigate to="/" replace />;
  return children;
};

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" richColors />
        <Routes>
          <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
          <Route path="/" element={<Private><Dashboard /></Private>} />
          <Route path="/calendar" element={<Private><CalendarPage /></Private>} />
          <Route path="/insights" element={<Private><Insights /></Private>} />
          <Route path="/competitors" element={<Private><Competitors /></Private>} />
          <Route path="/settings" element={<Private><Settings /></Private>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
