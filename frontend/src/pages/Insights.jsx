import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

export default function Insights() {
  const [data, setData] = useState(null);

  useEffect(() => { api.get("/insights").then(r => setData(r.data)); }, []);

  if (!data) return <div className="text-zinc-500" data-testid="insights-loading">Loading insights...</div>;

  const platforms = data.analytics || [];
  const learning = data.learning;
  const recent = data.recent_published || [];

  return (
    <div className="space-y-10" data-testid="insights-page">
      <div>
        <div className="text-xs uppercase tracking-[0.22em] text-zinc-500 font-semibold mb-2">Performance</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Insights</h1>
        <p className="text-sm text-zinc-500 mt-1">Audience peak times, top posts, and what the Optimizer is learning.</p>
      </div>

      {/* Platform snapshot */}
      <section>
        <h2 className="font-display text-xl font-semibold mb-4">Platform snapshot</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {platforms.map((p) => (
            <div key={p.platform} className="border border-zinc-200 rounded-lg p-5 bg-white" data-testid={`platform-${p.platform}`}>
              <div className={`plat-${p.platform} inline-block px-2 py-1 rounded text-xs font-semibold uppercase mb-3`}>{p.platform}</div>
              <div className="font-display text-3xl font-bold">{p.followers.toLocaleString()}</div>
              <div className="text-xs text-zinc-500 uppercase tracking-[0.16em] mt-1">Followers</div>
              <div className="mt-4 text-sm">
                <span className="text-zinc-500">Avg ER:</span>{" "}
                <span className="font-semibold">{p.avg_engagement_rate}%</span>
              </div>
              <div className="mt-3 text-xs text-zinc-500">
                Peak hours: <span className="font-mono text-zinc-800">{p.peak_hours.map(h=>`${h}:00`).join(", ")}</span>
              </div>
              <div className="text-xs text-zinc-500 mt-1">Peak days: <span className="font-mono text-zinc-800">{p.peak_days.join(", ")}</span></div>
            </div>
          ))}
        </div>
      </section>

      {/* Heatmap */}
      {platforms[0]?.heatmap && (
        <section>
          <h2 className="font-display text-xl font-semibold mb-4">When your audience is online ({platforms[0].platform})</h2>
          <div className="border border-zinc-200 rounded-lg p-4 bg-white overflow-x-auto">
            <div className="min-w-[600px]">
              {platforms[0].heatmap.map((row, di) => (
                <div key={di} className="flex items-center gap-1 mb-1">
                  <div className="w-10 text-xs text-zinc-500 font-mono">{["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][di]}</div>
                  {row.map((v, hi) => (
                    <div
                      key={hi}
                      title={`${hi}:00 — ${(v*100).toFixed(0)}%`}
                      className="w-5 h-5 rounded-sm"
                      style={{ backgroundColor: `rgba(9,9,11,${0.08 + v*0.85})` }}
                    />
                  ))}
                </div>
              ))}
              <div className="flex items-center gap-1 mt-2 ml-10">
                {Array.from({length:24}).map((_,i)=>(
                  <div key={i} className="w-5 text-[9px] text-zinc-400 text-center font-mono">{i}</div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Optimizer learnings */}
      <section>
        <h2 className="font-display text-xl font-semibold mb-4">Optimizer learnings</h2>
        {!learning && (
          <div className="text-sm text-zinc-500 border border-dashed border-zinc-300 rounded-lg p-6 text-center">
            No learning rollup yet. Publish a few posts and run the Optimizer.
          </div>
        )}
        {learning && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { title: "Top hooks", items: learning.top_hooks, key: "hook" },
              { title: "Top formats", items: learning.top_formats, key: "format" },
              { title: "Top pillars", items: learning.top_pillars, key: "pillar" },
            ].map((col) => (
              <div key={col.title} className="border border-zinc-200 rounded-lg p-5 bg-white">
                <div className="text-xs uppercase tracking-[0.16em] text-zinc-500 font-semibold">{col.title}</div>
                <ul className="mt-3 space-y-2 text-sm">
                  {(col.items || []).map((it, i) => (
                    <li key={i} className="flex justify-between gap-2">
                      <span className="truncate">{it[col.key]}</span>
                      <span className="font-mono text-zinc-500 text-xs">{it.avg_er}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent published */}
      <section>
        <h2 className="font-display text-xl font-semibold mb-4">Recently published</h2>
        {recent.length === 0 ? (
          <div className="text-sm text-zinc-500">Nothing published yet.</div>
        ) : (
          <div className="border border-zinc-200 rounded-lg divide-y divide-zinc-200 bg-white">
            {recent.map((p) => (
              <div key={p.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className={`inline-block plat-${p.platform} px-2 py-0.5 rounded text-[10px] font-semibold uppercase mr-2`}>{p.platform}</div>
                  <span className="text-sm font-medium">{p.hook || (p.caption || "").slice(0,80)}</span>
                </div>
                <div className="text-xs text-zinc-500 font-mono">
                  ER {p.performance?.engagement_rate || "—"}% · ❤ {p.performance?.likes || 0} · 💬 {p.performance?.comments || 0}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
