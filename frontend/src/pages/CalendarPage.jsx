import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const STATUS_COLORS = {
  planned: "bg-zinc-200 text-zinc-700",
  creative_generated: "bg-blue-100 text-blue-700",
  draft: "bg-zinc-200 text-zinc-700",
  pending_approval: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-700",
  published: "bg-zinc-900 text-white",
  expired: "bg-zinc-100 text-zinc-400",
  needs_edit: "bg-blue-100 text-blue-700",
};

export default function CalendarPage() {
  const [slots, setSlots] = useState([]);
  const [posts, setPosts] = useState([]);
  const [month, setMonth] = useState(() => {
    const d = new Date(); d.setDate(1); return d;
  });

  useEffect(() => {
    (async () => {
      const [c, p] = await Promise.all([api.get("/calendar"), api.get("/posts")]);
      setSlots(c.data); setPosts(p.data);
    })();
  }, []);

  // Map date -> [{type, item}]
  const byDate = {};
  slots.forEach((s) => {
    const k = s.date;
    (byDate[k] ||= []).push({ type: "slot", item: s });
  });
  posts.forEach((p) => {
    const k = new Date(p.scheduled_datetime).toISOString().slice(0, 10);
    (byDate[k] ||= []).push({ type: "post", item: p });
  });

  // Build calendar grid
  const year = month.getFullYear();
  const mo = month.getMonth();
  const first = new Date(year, mo, 1);
  const startWeekday = first.getDay(); // 0 Sun
  const daysInMonth = new Date(year, mo + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, mo, d));

  const fmtKey = (d) => d.toISOString().slice(0, 10);

  return (
    <div className="space-y-8" data-testid="calendar-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-zinc-500 font-semibold mb-2">Plan</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Calendar</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setMonth(new Date(year, mo - 1, 1))} className="px-3 py-1.5 border border-zinc-300 rounded-md text-sm hover:bg-zinc-100" data-testid="cal-prev">← Prev</button>
          <div className="font-display font-semibold text-lg min-w-[160px] text-center">
            {month.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}
          </div>
          <button onClick={() => setMonth(new Date(year, mo + 1, 1))} className="px-3 py-1.5 border border-zinc-300 rounded-md text-sm hover:bg-zinc-100" data-testid="cal-next">Next →</button>
        </div>
      </div>

      <div className="border border-zinc-200 rounded-lg overflow-hidden bg-white">
        <div className="grid grid-cols-7 bg-zinc-50 border-b border-zinc-200">
          {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
            <div key={d} className="px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-zinc-600">{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {cells.map((d, i) => (
            <div key={i} className="min-h-[110px] border-r border-b border-zinc-100 p-2">
              {d && (
                <>
                  <div className="text-xs text-zinc-500 font-mono">{d.getDate()}</div>
                  <div className="mt-1 space-y-1">
                    {(byDate[fmtKey(d)] || []).slice(0, 4).map((entry, idx) => {
                      const item = entry.item;
                      const status = entry.type === "post" ? item.status : item.status;
                      return (
                        <div key={idx} className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_COLORS[status] || "bg-zinc-100"} truncate`} title={item.hook || item.topic}>
                          <span className="font-semibold uppercase mr-1">{item.platform.slice(0,2)}</span>
                          {(item.hook || item.topic || "").slice(0, 22)}
                        </div>
                      );
                    })}
                    {(byDate[fmtKey(d)] || []).length > 4 && (
                      <div className="text-[10px] text-zinc-400">+{byDate[fmtKey(d)].length - 4} more</div>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-xs">
        {Object.entries(STATUS_COLORS).map(([k, c]) => (
          <span key={k} className={`px-2 py-1 rounded ${c}`}>{k.replace("_"," ")}</span>
        ))}
      </div>
    </div>
  );
}
