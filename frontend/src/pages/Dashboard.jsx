import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import PostCard from "@/components/PostCard";
import EditPostDialog from "@/components/EditPostDialog";
import { toast } from "sonner";
import { Sparkles, Send, RefreshCw, Inbox } from "lucide-react";

const groupByDate = (posts) => {
  const groups = {};
  posts.forEach((p) => {
    const d = new Date(p.scheduled_datetime);
    const key = d.toDateString();
    (groups[key] ||= []).push(p);
  });
  return Object.entries(groups).sort(([a], [b]) => new Date(a) - new Date(b));
};

export default function Dashboard() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [filter, setFilter] = useState("pending_approval");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/posts", { params: filter !== "all" ? { status: filter } : {} });
      setPosts(r.data);
    } finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const approve = async (post) => {
    await api.post(`/posts/${post.id}/status`, { status: "approved" });
    toast.success("Approved.");
    load();
  };
  const reject = async (post) => {
    await api.post(`/posts/${post.id}/status`, { status: "rejected" });
    toast.success("Rejected.");
    load();
  };
  const saveEdit = async (changes) => {
    await api.put(`/posts/${editing.id}`, changes);
    await api.post(`/posts/${editing.id}/status`, { status: "pending_approval" });
    toast.success("Saved.");
    load();
  };
  const regenerate = async (post) => {
    toast.loading("Regenerating...", { id: "regen" });
    try {
      await api.post(`/posts/${post.id}/regenerate`);
      toast.success("Regenerated.", { id: "regen" });
      load();
    } catch (e) { toast.error("Failed to regenerate", { id: "regen" }); }
  };
  const bulkApprove = async (platform) => {
    const r = await api.post("/posts/bulk-approve", platform ? { platform } : {});
    toast.success(`Approved ${r.data.approved_count} posts.`);
    load();
  };

  const generateWeek = async () => {
    setGenerating(true);
    toast.loading("Running Audit → Strategist → Creative (this may take ~1–2 min)...", { id: "gen" });
    try {
      const r = await api.post("/agents/full-cycle/run", null, { params: { days: 7, creative_count: 7 }, timeout: 180000 });
      toast.success(`Generated ${r.data.creatives_generated} posts.`, { id: "gen" });
      setFilter("pending_approval");
      load();
    } catch (e) {
      toast.error("Generation failed. Check backend logs.", { id: "gen" });
    } finally { setGenerating(false); }
  };

  const runPublisher = async () => {
    setPublishing(true);
    try {
      const r = await api.post("/agents/publisher/run");
      toast.success(`Published ${r.data.published}, expired ${r.data.expired}.`);
      load();
    } finally { setPublishing(false); }
  };

  const grouped = groupByDate(posts);
  const pendingCount = posts.filter((p) => p.status === "pending_approval").length;

  return (
    <div className="space-y-8" data-testid="dashboard">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-zinc-500 font-semibold mb-2">Weekly Queue</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Approvals</h1>
          <p className="text-sm text-zinc-500 mt-1">Approve, edit, regenerate or reject. Only approved posts publish.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={generateWeek}
            disabled={generating}
            data-testid="generate-week"
            className="flex items-center gap-2 bg-zinc-900 text-white text-sm font-medium px-4 py-2 rounded-md hover:bg-zinc-700 active:scale-[0.99] transition disabled:opacity-50"
          >
            <Sparkles size={14} /> {generating ? "Generating..." : "Generate next week"}
          </button>
          <button
            onClick={runPublisher}
            disabled={publishing}
            data-testid="run-publisher"
            className="flex items-center gap-2 border border-zinc-300 text-zinc-800 text-sm font-medium px-4 py-2 rounded-md hover:bg-zinc-100 active:scale-[0.99] transition disabled:opacity-50"
            title="Publish all approved posts whose scheduled time has passed"
          >
            <Send size={14} /> Run publisher
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="stats-bar">
        {[
          { label: "Pending", value: posts.filter(p=>p.status==="pending_approval").length, status: "pending_approval" },
          { label: "Approved", value: posts.filter(p=>p.status==="approved").length, status: "approved" },
          { label: "Needs edit", value: posts.filter(p=>p.status==="needs_edit").length, status: "needs_edit" },
          { label: "Published", value: posts.filter(p=>p.status==="published").length, status: "published" },
        ].map((s) => (
          <button
            key={s.label}
            onClick={() => setFilter(s.status)}
            data-testid={`filter-${s.status}`}
            className={`text-left p-4 rounded-lg border transition ${
              filter === s.status ? "border-zinc-900 bg-zinc-50" : "border-zinc-200 bg-white hover:border-zinc-400"
            }`}
          >
            <div className="text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold">{s.label}</div>
            <div className="font-display text-3xl font-bold mt-2">{s.value}</div>
          </button>
        ))}
      </div>

      {/* Bulk actions */}
      {pendingCount > 0 && (
        <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-4 flex flex-wrap items-center gap-3" data-testid="bulk-actions">
          <span className="text-sm font-medium">Bulk actions:</span>
          <button onClick={() => bulkApprove(null)} data-testid="bulk-approve-all" className="text-xs font-semibold bg-zinc-900 text-white px-3 py-1.5 rounded-md hover:bg-zinc-700">Approve all ({pendingCount})</button>
          <button onClick={() => bulkApprove("instagram")} data-testid="bulk-approve-ig" className="text-xs font-semibold border border-zinc-300 px-3 py-1.5 rounded-md hover:bg-zinc-100">Approve Instagram</button>
          <button onClick={() => bulkApprove("facebook")} data-testid="bulk-approve-fb" className="text-xs font-semibold border border-zinc-300 px-3 py-1.5 rounded-md hover:bg-zinc-100">Approve Facebook</button>
          <button onClick={() => bulkApprove("linkedin")} data-testid="bulk-approve-li" className="text-xs font-semibold border border-zinc-300 px-3 py-1.5 rounded-md hover:bg-zinc-100">Approve LinkedIn</button>
        </div>
      )}

      {loading && (
        <div className="text-center text-zinc-500 py-12 flex items-center justify-center gap-2"><RefreshCw className="animate-spin" size={16} /> Loading...</div>
      )}

      {!loading && grouped.length === 0 && (
        <div className="text-center py-20 border border-dashed border-zinc-300 rounded-lg" data-testid="empty-state">
          <Inbox className="mx-auto text-zinc-400 mb-3" size={32} />
          <h3 className="font-display text-xl font-semibold">No posts in this view.</h3>
          <p className="text-sm text-zinc-500 mt-2">Click "Generate next week" to kick off the agents.</p>
        </div>
      )}

      {grouped.map(([date, items]) => (
        <section key={date} data-testid={`date-group-${date}`}>
          <div className="flex items-baseline gap-3 mb-4">
            <h2 className="font-display text-xl font-semibold tracking-tight">
              {new Date(date).toLocaleDateString("en-IN", { weekday: "long", month: "short", day: "numeric" })}
            </h2>
            <span className="text-xs text-zinc-500 font-mono">{items.length} post{items.length>1?"s":""}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {items.map((p) => (
              <PostCard
                key={p.id}
                post={p}
                onApprove={approve}
                onReject={reject}
                onEdit={(post) => setEditing(post)}
                onApproveAfterEdit={(post) => setEditing(post)}
                onRegenerate={regenerate}
              />
            ))}
          </div>
        </section>
      ))}

      <EditPostDialog
        post={editing}
        open={!!editing}
        onClose={() => setEditing(null)}
        onSave={saveEdit}
      />
    </div>
  );
}
