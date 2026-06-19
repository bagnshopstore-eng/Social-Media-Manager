import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("bagnshopstore@gmail.com");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      toast.error("Invalid email or password");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-white flex">
      {/* Left: form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-6" data-testid="login-form">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-zinc-900 text-white flex items-center justify-center">
              <Sparkles size={18} />
            </div>
            <div>
              <div className="font-display font-bold text-lg leading-none">BagnShop AI</div>
              <div className="text-[10px] tracking-[0.18em] uppercase text-zinc-500 mt-1">Social Manager</div>
            </div>
          </div>
          <div>
            <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Welcome back.</h1>
            <p className="text-sm text-zinc-500 mt-2">Sign in to review this week's queue.</p>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold">Email</label>
              <input
                data-testid="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 w-full px-3 py-2.5 rounded-md border border-zinc-300 focus:border-zinc-900 focus:ring-0 outline-none text-sm"
                required
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold">Password</label>
              <input
                data-testid="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-2 w-full px-3 py-2.5 rounded-md border border-zinc-300 focus:border-zinc-900 focus:ring-0 outline-none text-sm"
                required
              />
            </div>
          </div>
          <button
            data-testid="login-submit"
            disabled={busy}
            type="submit"
            className="w-full bg-zinc-900 text-white text-sm font-semibold py-2.5 rounded-md hover:bg-zinc-700 active:scale-[0.99] transition disabled:opacity-50"
          >
            {busy ? "Signing in..." : "Sign in"}
          </button>
          <p className="text-xs text-zinc-400">Single-admin app. No registration.</p>
        </form>
      </div>
      {/* Right: editorial panel */}
      <div className="hidden lg:flex flex-1 bg-zinc-950 text-white p-12 flex-col justify-between">
        <div className="text-xs tracking-[0.24em] uppercase text-zinc-400 font-semibold">Approval-Gated · Autonomous · Honest</div>
        <div>
          <h2 className="font-display text-4xl xl:text-5xl font-bold leading-tight tracking-tight">
            Six agents do the work.<br />
            <span className="text-zinc-400">You spend two minutes a day.</span>
          </h2>
          <p className="text-zinc-400 mt-6 text-sm max-w-md leading-relaxed">
            Research, plan, write, design — all autonomous. Nothing ever publishes without your tap.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-6 text-xs text-zinc-500">
          <div><div className="text-2xl font-display font-bold text-white">5/4/3</div>IG / FB / LI per week</div>
          <div><div className="text-2xl font-display font-bold text-white">30d</div>Rolling calendar</div>
          <div><div className="text-2xl font-display font-bold text-white">100%</div>Approval-gated</div>
        </div>
      </div>
    </div>
  );
}
