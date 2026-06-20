import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, assetUrl } from "@/lib/api";
import { toast } from "sonner";
import { Package, ArrowRight, RefreshCw } from "lucide-react";

export default function BulkProductMatchDialog({ open, onClose, onApplied }) {
  const [scope, setScope] = useState("pending");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);

  const runPreview = async (s = scope) => {
    setLoading(true);
    try {
      const r = await api.post("/posts/bulk-regenerate-images", { scope: s, dry_run: true });
      setPreview(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Preview failed");
    } finally { setLoading(false); }
  };

  useEffect(() => { if (open) runPreview(scope); }, [open]);

  const commit = async () => {
    setCommitting(true);
    try {
      const r = await api.post("/posts/bulk-regenerate-images", { scope, dry_run: false });
      toast.success(`Updated ${r.data.matched_count} post image${r.data.matched_count === 1 ? "" : "s"}.`);
      onApplied?.();
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Bulk update failed");
    } finally { setCommitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl" data-testid="bulk-match-dialog">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            <Package size={18} /> Bulk match — Shopify products
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-xs uppercase tracking-[0.16em] text-zinc-500 font-semibold">Scope</span>
            <Select value={scope} onValueChange={(v) => { setScope(v); runPreview(v); }}>
              <SelectTrigger className="w-64" data-testid="bulk-scope">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pending">Pending approval only</SelectItem>
                <SelectItem value="all">All posts (incl. approved/needs_edit)</SelectItem>
              </SelectContent>
            </Select>
            <button onClick={() => runPreview()} disabled={loading}
                    className="text-xs px-3 py-1.5 border border-zinc-300 rounded-md hover:bg-zinc-100 flex items-center gap-1"
                    data-testid="bulk-refresh">
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>

          {loading && <div className="text-sm text-zinc-500 py-8 text-center">Matching products…</div>}

          {preview && !loading && (
            <>
              <div className="text-xs text-zinc-500">
                <span className="font-medium text-zinc-900">{preview.matched_count}</span> of{" "}
                <span className="font-medium text-zinc-900">{preview.candidates}</span> posts will be updated with their best-matching Shopify product image
                {preview.skipped_count > 0 && <> · {preview.skipped_count} skipped</>}
              </div>

              <div className="max-h-96 overflow-y-auto border border-zinc-200 rounded-lg divide-y divide-zinc-100" data-testid="bulk-preview-list">
                {(preview.matched || []).map((m) => (
                  <div key={m.id} className="p-3 flex items-center gap-3" data-testid={`bulk-match-row-${m.id}`}>
                    {/* old preview */}
                    <img src={assetUrl(m.old_url)} alt="" className="w-14 h-14 rounded-md object-cover bg-zinc-100 shrink-0" onError={(e) => e.target.style.visibility = 'hidden'} />
                    <ArrowRight size={14} className="text-zinc-400 shrink-0" />
                    <img src={m.new_url} alt="" className="w-14 h-14 rounded-md object-cover bg-zinc-100 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-mono uppercase text-zinc-500">{m.platform}</div>
                      <div className="text-sm truncate">{m.hook || "(no hook)"}</div>
                      <div className="text-xs text-emerald-700 truncate">→ {m.product_title} {m.product_price ? `· ₹${m.product_price}` : ""}</div>
                    </div>
                  </div>
                ))}
                {(preview.matched || []).length === 0 && (
                  <div className="p-8 text-center text-sm text-zinc-500">Nothing to update — all posts already have product images or scope is empty.</div>
                )}
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="bulk-cancel">Cancel</Button>
          <Button onClick={commit}
                  disabled={committing || !preview?.matched_count}
                  className="bg-zinc-900 hover:bg-zinc-700"
                  data-testid="bulk-commit">
            {committing ? "Updating…" : `Apply to ${preview?.matched_count || 0} post${preview?.matched_count === 1 ? "" : "s"}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
