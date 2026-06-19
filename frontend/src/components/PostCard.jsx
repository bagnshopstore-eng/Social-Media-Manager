import { useState } from "react";
import { Instagram, Facebook, Linkedin, Calendar, Clock,
  Check, X as XIcon, Pencil, RefreshCw, AlertTriangle } from "lucide-react";
import { assetUrl } from "@/lib/api";

const platformIcon = {
  instagram: Instagram, facebook: Facebook, linkedin: Linkedin,
};

const fmtDateTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit", hour12: true,
  });
};

export default function PostCard({ post, onApprove, onReject, onEdit, onRegenerate, onApproveAfterEdit }) {
  const PIcon = platformIcon[post.platform] || Instagram;
  const [showFullCaption, setShowFullCaption] = useState(false);

  const isPending = post.status === "pending_approval";
  const needsEdit = post.status === "needs_edit";

  return (
    <div
      data-testid={`post-card-${post.id}`}
      className="bg-white border border-zinc-200 rounded-lg overflow-hidden flex flex-col transition-all duration-200 hover:border-zinc-400"
    >
      {/* Image */}
      <div className="relative aspect-square bg-zinc-100">
        {post.image_urls?.[0] ? (
          <img
            src={assetUrl(post.image_urls[0])}
            alt=""
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-400 text-xs">No image</div>
        )}
        <div className="absolute top-3 left-3 flex gap-2">
          <span className={`status-pill status-${post.status}`} data-testid={`status-${post.id}`}>
            {post.status.replace("_", " ")}
          </span>
        </div>
        <div className={`absolute top-3 right-3 plat-${post.platform} px-2 py-1 rounded-md flex items-center gap-1.5 text-xs font-semibold`}>
          <PIcon size={12} /> {post.platform}
        </div>
        {post.format === "carousel" && (
          <div className="absolute bottom-3 right-3 bg-black/70 text-white text-xs px-2 py-1 rounded">
            Carousel · {post.image_urls?.length || 1}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-4 flex-1 flex flex-col gap-3">
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          <span className="flex items-center gap-1"><Calendar size={12} /> {fmtDateTime(post.scheduled_datetime).split(", ").slice(0,2).join(", ")}</span>
          <span className="flex items-center gap-1"><Clock size={12} /> {new Date(post.scheduled_datetime).toLocaleTimeString("en-IN", { hour:"numeric", minute:"2-digit" })}</span>
        </div>

        <div className="text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold">
          {post.pillar}
        </div>

        <p className={`text-sm text-zinc-800 leading-relaxed whitespace-pre-line ${showFullCaption ? "" : "line-clamp-4"}`}>
          {post.caption}
        </p>
        <button
          className="text-xs text-zinc-500 hover:text-zinc-900 self-start underline"
          onClick={() => setShowFullCaption((v) => !v)}
          data-testid={`expand-caption-${post.id}`}
        >
          {showFullCaption ? "Show less" : "Show more"}
        </button>

        {post.guardrail_issues?.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-800" data-testid={`guardrail-${post.id}`}>
            <div className="flex items-center gap-1.5 font-semibold mb-1">
              <AlertTriangle size={12} /> Guardrail flagged
            </div>
            <ul className="list-disc list-inside space-y-0.5">
              {post.guardrail_issues.map((i, idx) => (<li key={idx}>{i}</li>))}
            </ul>
          </div>
        )}

        {post.product_snapshot && (
          <div className="text-xs text-zinc-600 bg-zinc-50 rounded-md p-2 border border-zinc-200">
            <span className="font-medium">Product:</span> {post.product_snapshot.title}
            <span className="ml-2 text-zinc-900 font-semibold">₹{post.product_snapshot.price}</span>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="border-t border-zinc-200 p-3 flex flex-wrap gap-2">
        {(isPending || needsEdit) && (
          <button
            onClick={() => (needsEdit ? onApproveAfterEdit?.(post) : onApprove(post))}
            data-testid={`approve-${post.id}`}
            className="flex-1 min-w-[80px] flex items-center justify-center gap-1.5 bg-zinc-900 text-white text-sm font-medium px-3 py-2 rounded-md hover:bg-zinc-700 active:scale-95 transition"
          >
            <Check size={14} /> Approve
          </button>
        )}
        <button
          onClick={() => onEdit(post)}
          data-testid={`edit-${post.id}`}
          className="flex items-center justify-center gap-1.5 border border-zinc-300 text-zinc-800 text-sm font-medium px-3 py-2 rounded-md hover:bg-zinc-100 active:scale-95 transition"
        >
          <Pencil size={14} /> Edit
        </button>
        <button
          onClick={() => onRegenerate(post)}
          data-testid={`regen-${post.id}`}
          className="flex items-center justify-center gap-1.5 border border-zinc-300 text-zinc-800 text-sm font-medium px-3 py-2 rounded-md hover:bg-zinc-100 active:scale-95 transition"
          title="Regenerate"
        >
          <RefreshCw size={14} />
        </button>
        {(isPending || needsEdit) && (
          <button
            onClick={() => onReject(post)}
            data-testid={`reject-${post.id}`}
            className="flex items-center justify-center gap-1.5 border border-zinc-300 text-rose-600 text-sm font-medium px-3 py-2 rounded-md hover:bg-rose-50 active:scale-95 transition"
          >
            <XIcon size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
