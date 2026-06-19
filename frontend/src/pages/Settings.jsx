import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const HealthTile = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const load = () => { setLoading(true); api.get("/integrations/health").then(r=>setData(r.data)).finally(()=>setLoading(false)); };
  useEffect(() => { load(); }, []);
  if (!data && !loading) return null;
  return (
    <section className="space-y-3" data-testid="health-tile">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-semibold">Connection health</h2>
        <button onClick={load} disabled={loading} className="text-xs px-3 py-1.5 border border-zinc-300 rounded-md hover:bg-zinc-100" data-testid="health-refresh">{loading?"…":"Refresh"}</button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {data && Object.entries(data).map(([name, v]) => (
          <div key={name} className={`p-3 rounded-lg border ${v.ok?"border-emerald-200 bg-emerald-50":"border-rose-200 bg-rose-50"}`} data-testid={`health-${name}`}>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${v.ok?"bg-emerald-500":"bg-rose-500"}`} />
              <span className="font-medium text-sm capitalize">{name.replace("_"," ")}</span>
            </div>
            <div className="text-xs text-zinc-600 mt-1 truncate" title={v.detail}>{v.status?`${v.status} · `:""}{v.detail}</div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default function Settings() {
  const [brand, setBrand] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.get("/brand").then(r => setBrand(r.data)); }, []);

  if (!brand) return <div className="text-zinc-500" data-testid="settings-loading">Loading...</div>;

  const update = (k, v) => setBrand({ ...brand, [k]: v });
  const updateList = (k, v) => update(k, v.split("\n").map(s => s.trim()).filter(Boolean));

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/brand", brand);
      toast.success("Settings saved.");
    } catch { toast.error("Save failed."); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-10 max-w-3xl" data-testid="settings-page">
      <div>
        <div className="text-xs uppercase tracking-[0.22em] text-zinc-500 font-semibold mb-2">Configuration</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-zinc-500 mt-1">Brand voice, banned claims, content pillars, and integration status.</p>
      </div>

      <HealthTile />

      <Section title="Brand">
        <Field label="Brand name"><input className="settings-input" value={brand.brand_name || ""} onChange={e=>update("brand_name", e.target.value)} data-testid="set-brand-name" /></Field>
        <Field label="Website"><input className="settings-input" value={brand.website || ""} onChange={e=>update("website", e.target.value)} /></Field>
        <Field label="Positioning"><input className="settings-input" value={brand.positioning || ""} onChange={e=>update("positioning", e.target.value)} /></Field>
        <Field label="LinkedIn angle"><textarea className="settings-input" rows={3} value={brand.linkedin_angle || ""} onChange={e=>update("linkedin_angle", e.target.value)} /></Field>
      </Section>

      <Section title="Voice rules (one per line)">
        <textarea className="settings-input" rows={5} value={(brand.voice_rules||[]).join("\n")} onChange={e=>updateList("voice_rules", e.target.value)} data-testid="set-voice-rules" />
      </Section>

      <Section title="Banned claims (one per line)">
        <textarea className="settings-input" rows={6} value={(brand.banned_claims||[]).join("\n")} onChange={e=>updateList("banned_claims", e.target.value)} data-testid="set-banned-claims" />
      </Section>

      <Section title="Content pillars (one per line)">
        <textarea className="settings-input" rows={6} value={(brand.content_pillars||[]).join("\n")} onChange={e=>updateList("content_pillars", e.target.value)} data-testid="set-pillars" />
      </Section>

      <Section title="Cadence per week">
        <div className="grid grid-cols-3 gap-3">
          {["instagram","facebook","linkedin"].map((p) => (
            <Field key={p} label={p}>
              <input
                className="settings-input"
                type="number"
                value={brand.cadence?.[p] ?? 0}
                onChange={e => update("cadence", { ...brand.cadence, [p]: parseInt(e.target.value||"0") })}
                data-testid={`set-cadence-${p}`}
              />
            </Field>
          ))}
        </div>
      </Section>

      <Section title="Integrations (M1+M2+M3 build)">
        <div className="space-y-2 text-sm">
          <IntegrationRow label="Anthropic Claude (text)" status="connected" detail="via EMERGENT_LLM_KEY" />
          <IntegrationRow label="Gemini Nano Banana (images)" status="connected" detail="via EMERGENT_LLM_KEY" />
          <IntegrationRow label="Shopify Admin" status="connected" detail={brand.website} />
          <IntegrationRow label="Postproxy (publish + analytics)" status="connected" detail="https://app.postproxy.dev/api (X-API-Key auth)" />
          <IntegrationRow label="Apify Instagram scraper" status="connected" detail="red.cars/instagram-scraper-pro actor" />
          <IntegrationRow label="Canva Connect (M6 — videos + branded)" status="connected" detail="Client ID + Secret stored; OAuth flow pending M6" />
          <IntegrationRow label="Resend (email notifications)" status="off" detail="Add RESEND_API_KEY to .env to enable" />
          <IntegrationRow label="APScheduler weekly cron" status="connected" detail="Sat 6am IST research · */15min publisher · Sun 7am optimizer" />
          <IntegrationRow label="Telegram bot" status="off" detail="Skipped" />
        </div>
      </Section>

      <div className="sticky bottom-4 flex justify-end">
        <button onClick={save} disabled={saving} data-testid="save-settings" className="bg-zinc-900 text-white text-sm font-semibold px-5 py-2.5 rounded-md hover:bg-zinc-700 disabled:opacity-50 shadow-lg">
          {saving ? "Saving..." : "Save changes"}
        </button>
      </div>

      <style>{`
        .settings-input {
          width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #d4d4d8;
          border-radius: 6px; font-size: 0.875rem; background: white;
        }
        .settings-input:focus { outline: none; border-color: #09090b; }
      `}</style>
    </div>
  );
}

const Section = ({ title, children }) => (
  <section className="space-y-3">
    <h2 className="font-display text-xl font-semibold">{title}</h2>
    <div className="space-y-3 border border-zinc-200 rounded-lg p-5 bg-white">{children}</div>
  </section>
);

const Field = ({ label, children }) => (
  <label className="block">
    <div className="text-xs uppercase tracking-[0.16em] text-zinc-500 font-semibold mb-1.5">{label}</div>
    {children}
  </label>
);

const IntegrationRow = ({ label, status, detail }) => {
  const cls = { connected: "bg-emerald-100 text-emerald-800", mocked: "bg-amber-100 text-amber-800", off: "bg-zinc-100 text-zinc-500" }[status];
  return (
    <div className="flex items-center justify-between gap-2 py-1.5">
      <div>
        <div className="font-medium">{label}</div>
        <div className="text-xs text-zinc-500">{detail}</div>
      </div>
      <span className={`text-[10px] uppercase tracking-[0.14em] font-semibold px-2 py-1 rounded ${cls}`}>{status}</span>
    </div>
  );
};
