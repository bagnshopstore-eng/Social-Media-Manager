import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ExternalLink, TrendingUp, Lightbulb } from "lucide-react";

export default function Competitors() {
  const [list, setList] = useState([]);
  const [content, setContent] = useState([]);
  const [hooks, setHooks] = useState(null);

  useEffect(() => {
    Promise.all([
      api.get("/competitors"),
      api.get("/competitor-content", { params: { limit: 30 }}),
      api.get("/hook-patterns"),
    ]).then(([a,b,c]) => { setList(a.data); setContent(b.data); setHooks(c.data); });
  }, []);

  return (
    <div className="space-y-10" data-testid="competitors-page">
      <div>
        <div className="text-xs uppercase tracking-[0.22em] text-zinc-500 font-semibold mb-2">Research</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Competitor Intel</h1>
        <p className="text-sm text-zinc-500 mt-1">Tracked accounts, winning hooks, and content gaps you can own.</p>
      </div>

      {/* Tracked accounts */}
      <section>
        <h2 className="font-display text-xl font-semibold mb-4">Tracked accounts ({list.length})</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="competitor-list">
          {list.map((c) => (
            <div key={c.id} className="border border-zinc-200 rounded-lg p-4 bg-white">
              <div className="font-semibold">{c.name}</div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                {Object.entries(c.handles).map(([k,v]) => v && (
                  <a key={k} href={v} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-zinc-600 hover:text-zinc-900 underline">
                    {k} <ExternalLink size={10} />
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Hook patterns */}
      <section>
        <h2 className="font-display text-xl font-semibold mb-4 flex items-center gap-2"><TrendingUp size={18}/> Winning hook patterns</h2>
        {!hooks || hooks.hook_patterns?.length === 0 ? (
          <div className="text-sm text-zinc-500 border border-dashed border-zinc-300 rounded-lg p-6 text-center">
            No hook patterns yet. Run the Strategist agent.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {hooks.hook_patterns.map((h, i) => (
              <div key={i} className="border border-zinc-200 rounded-lg p-4 bg-white">
                <div className="font-display font-semibold text-lg">"{h.pattern}"</div>
                <div className="text-sm text-zinc-600 mt-1">{h.description}</div>
                {h.example && <div className="text-xs text-zinc-500 mt-2 italic">e.g. {h.example}</div>}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Content gaps */}
      {hooks?.content_gaps?.length > 0 && (
        <section>
          <h2 className="font-display text-xl font-semibold mb-4 flex items-center gap-2"><Lightbulb size={18}/> Content gaps to own</h2>
          <div className="space-y-2">
            {hooks.content_gaps.map((g, i) => (
              <div key={i} className="border border-zinc-200 rounded-lg p-4 bg-white">
                <div className="font-semibold">{g.title}</div>
                <div className="text-sm text-zinc-600 mt-1">{g.description}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recent top competitor posts */}
      <section>
        <h2 className="font-display text-xl font-semibold mb-4">Top competitor posts</h2>
        {content.length === 0 ? (
          <div className="text-sm text-zinc-500">No scraped content yet.</div>
        ) : (
          <div className="border border-zinc-200 rounded-lg divide-y divide-zinc-200 bg-white">
            {content.slice(0, 15).map((c) => (
              <div key={c.id} className="p-4 flex flex-col sm:flex-row gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-zinc-500 mb-1">
                    <span className="font-semibold text-zinc-700">{c.competitor_name}</span> · {c.platform} · {c.format}
                  </div>
                  <div className="font-display font-semibold text-sm">"{c.hook}"</div>
                  <div className="text-sm text-zinc-600 line-clamp-2 mt-1">{c.caption}</div>
                </div>
                <div className="text-xs text-zinc-500 font-mono whitespace-nowrap">
                  ER {c.engagement_rate}% · ❤ {c.likes} · 💬 {c.comments}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
