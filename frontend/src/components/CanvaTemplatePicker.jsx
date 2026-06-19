import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { RefreshCw, ExternalLink, Image as ImageIcon, FileCheck } from "lucide-react";

export default function CanvaTemplatePicker({ open, onClose, onDesignReady, slots = [], onPostCreated }) {
  const [status, setStatus] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [textValue, setTextValue] = useState("");
  const [fieldName, setFieldName] = useState("title");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [chosenSlot, setChosenSlot] = useState("");
  const [creatingPost, setCreatingPost] = useState(false);

  const loadStatus = async () => {
    try {
      const r = await api.get("/canva/status");
      setStatus(r.data);
      return r.data;
    } catch (e) {
      setStatus({ connected: false, configured: false });
      return null;
    }
  };

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const r = await api.get("/canva/templates");
      setTemplates(r.data.items || []);
      if ((r.data.items || []).length === 0) {
        toast.message("No brand templates found in your Canva account.");
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || "Failed to load templates";
      toast.error(msg);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!open) {
      setSelected(null); setTextValue(""); setResult(null); setChosenSlot("");
      return;
    }
    // Pre-select the slot if only one was passed (per-slot launch from Calendar)
    if (slots && slots.length === 1) {
      setChosenSlot(slots[0].id);
    }
    (async () => {
      const s = await loadStatus();
      if (s?.connected) await loadTemplates();
    })();
  }, [open, slots]);

  const connect = async () => {
    try {
      const r = await api.get("/canva/connect");
      window.location.href = r.data.authorize_url;
    } catch (e) {
      toast.error("Could not start Canva OAuth. Check CANVA_CLIENT_ID/SECRET in backend .env.");
    }
  };

  const runAutofill = async () => {
    if (!selected) return toast.error("Pick a template first");
    setRunning(true);
    setResult(null);
    try {
      const payload = {
        template_id: selected.id,
        title: `BagnShop AI — ${selected.title}`,
        data: {
          [fieldName || "title"]: { type: "text", text: textValue || selected.title },
        },
      };
      const r = await api.post("/canva/autofill", payload);
      setResult(r.data);
      const job = r.data?.result || {};
      const url = job?.result?.design?.url || job?.urls?.view_url;
      if (job.status === "success" || url) {
        toast.success("Canva design ready!");
        onDesignReady?.({
          template_id: selected.id,
          template_title: selected.title,
          design_url: url,
          thumbnail_url: job?.result?.design?.thumbnail?.url,
          job_id: r.data.job_id,
        });
      } else {
        toast.message(`Job status: ${job.status || "in_progress"}. Reopen to refresh.`);
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || "Autofill failed";
      toast.error(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally { setRunning(false); }
  };

  const createPost = async () => {
    if (!selected || !chosenSlot) return toast.error("Pick a template and a calendar slot");
    setCreatingPost(true);
    try {
      const r = await api.post("/canva/create-post", {
        slot_id: chosenSlot,
        template_id: selected.id,
        fields: { [fieldName || "title"]: textValue || selected.title },
        title: `BagnShop AI — ${selected.title}`,
      });
      toast.success(`Post created (${r.data.status}). Check Approvals.`);
      onPostCreated?.(r.data);
      onClose();
    } catch (e) {
      const msg = e?.response?.data?.detail || "Failed to create post";
      toast.error(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally { setCreatingPost(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl" data-testid="canva-picker">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            <ImageIcon size={18} /> Canva — Brand Templates
          </DialogTitle>
        </DialogHeader>

        {!status?.connected ? (
          <div className="py-10 text-center space-y-4" data-testid="canva-not-connected">
            <p className="text-sm text-zinc-600">
              Canva is {status?.configured ? "configured but not connected" : "not configured"}.
              Connect once to enable brand-template autofill in the Creative Agent.
            </p>
            <Button onClick={connect} data-testid="canva-connect-btn">
              Connect Canva
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded">
                Connected{status?.expires_at ? ` · token expires ${new Date(status.expires_at).toLocaleTimeString()}` : ""}
              </div>
              <button onClick={loadTemplates} disabled={loading}
                      className="text-xs px-3 py-1.5 border border-zinc-300 rounded-md hover:bg-zinc-100 flex items-center gap-1"
                      data-testid="canva-refresh-templates">
                <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
              </button>
            </div>

            {loading && <div className="text-sm text-zinc-500">Loading templates…</div>}

            {!loading && templates.length === 0 && (
              <div className="text-sm text-zinc-500 border border-dashed border-zinc-300 rounded-lg p-6 text-center">
                No brand templates in this account.
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-64 overflow-y-auto" data-testid="canva-templates-grid">
              {templates.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setSelected(t)}
                  data-testid={`canva-tpl-${t.id}`}
                  className={`border rounded-lg p-2 text-left hover:border-zinc-900 transition ${
                    selected?.id === t.id ? "border-zinc-900 ring-2 ring-zinc-900/10" : "border-zinc-200"
                  }`}
                >
                  {t.thumbnail_url ? (
                    <img src={t.thumbnail_url} alt={t.title} className="w-full h-24 object-cover rounded-md mb-2" />
                  ) : (
                    <div className="w-full h-24 bg-zinc-100 rounded-md mb-2 flex items-center justify-center text-zinc-400">
                      <ImageIcon size={20} />
                    </div>
                  )}
                  <div className="text-xs font-medium truncate">{t.title}</div>
                  <div className="text-[10px] text-zinc-500 font-mono truncate">{t.id}</div>
                </button>
              ))}
            </div>

            {selected && (
              <div className="border-t border-zinc-200 pt-4 space-y-3" data-testid="canva-autofill-form">
                <div className="text-sm">
                  <span className="text-zinc-500">Selected: </span>
                  <span className="font-medium">{selected.title}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <Label className="text-xs uppercase tracking-[0.16em] text-zinc-500">Field name</Label>
                    <Input value={fieldName} onChange={(e) => setFieldName(e.target.value)}
                           placeholder="title"
                           className="mt-1.5" data-testid="canva-field-name" />
                  </div>
                  <div className="sm:col-span-2">
                    <Label className="text-xs uppercase tracking-[0.16em] text-zinc-500">Text value</Label>
                    <Textarea rows={2} value={textValue}
                              onChange={(e) => setTextValue(e.target.value)}
                              placeholder={`e.g. "${selected.title}" or your hook`}
                              className="mt-1.5" data-testid="canva-field-value" />
                  </div>
                </div>

                {slots.length > 0 && (
                  <div className="bg-zinc-50 border border-zinc-200 rounded-md p-3 space-y-2">
                    <Label className="text-xs uppercase tracking-[0.16em] text-zinc-500">Attach to calendar slot (creates a Post)</Label>
                    <Select value={chosenSlot} onValueChange={setChosenSlot}>
                      <SelectTrigger data-testid="canva-slot-select">
                        <SelectValue placeholder={`${slots.length} planned slots — choose one`} />
                      </SelectTrigger>
                      <SelectContent className="max-h-72">
                        {slots.map((s) => (
                          <SelectItem key={s.id} value={s.id} data-testid={`canva-slot-${s.id}`}>
                            <span className="font-mono text-[10px] mr-2">{s.date}</span>
                            <span className="uppercase text-[10px] mr-2">{s.platform?.slice(0,2)}</span>
                            <span className="text-xs">{(s.hook || s.topic || "").slice(0,50)}</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                <p className="text-xs text-zinc-500">
                  Field name must match a data field defined in your Canva brand template.
                  Use the field&apos;s <code>name</code> (not its label).
                </p>
              </div>
            )}

            {result?.result && (
              <div className="border border-emerald-200 bg-emerald-50 rounded-lg p-3 text-sm" data-testid="canva-result">
                <div className="font-semibold text-emerald-800">
                  Status: {result.result.status || "in_progress"}
                </div>
                {result.result?.result?.design?.url && (
                  <a href={result.result.result.design.url} target="_blank" rel="noreferrer"
                     className="text-emerald-700 inline-flex items-center gap-1 underline mt-1">
                    Open in Canva <ExternalLink size={12} />
                  </a>
                )}
                {result.job_id && (
                  <div className="text-[10px] font-mono text-zinc-500 mt-1">Job: {result.job_id}</div>
                )}
              </div>
            )}
          </div>
        )}

        <DialogFooter className="flex-wrap gap-2">
          <Button variant="outline" onClick={onClose} data-testid="canva-close">Close</Button>
          {status?.connected && (
            <>
              <Button variant="outline" onClick={runAutofill}
                      disabled={!selected || running}
                      data-testid="canva-autofill-btn">
                {running ? "Generating…" : "Preview only"}
              </Button>
              <Button onClick={createPost}
                      disabled={!selected || !chosenSlot || creatingPost}
                      data-testid="canva-create-post-btn"
                      className="bg-zinc-900 hover:bg-zinc-700">
                <FileCheck size={14} className="mr-1.5" />
                {creatingPost ? "Creating post…" : "Create post for slot"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
