import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const toLocalInput = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

export default function EditPostDialog({ post, open, onClose, onSave }) {
  const [caption, setCaption] = useState("");
  const [scheduled, setScheduled] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (post) {
      setCaption(post.caption || "");
      setScheduled(toLocalInput(post.scheduled_datetime));
      setHashtags((post.hashtags || []).join(" "));
    }
  }, [post]);

  if (!post) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        caption,
        scheduled_datetime: scheduled ? new Date(scheduled).toISOString() : undefined,
        hashtags: hashtags.split(/\s+/).filter(Boolean),
      });
      onClose();
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="edit-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Edit post</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label className="text-xs uppercase tracking-[0.18em] text-zinc-500">Caption</Label>
            <Textarea
              data-testid="edit-caption"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={9}
              className="mt-2 font-mono text-sm"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs uppercase tracking-[0.18em] text-zinc-500">Scheduled at</Label>
              <Input
                data-testid="edit-scheduled"
                type="datetime-local"
                value={scheduled}
                onChange={(e) => setScheduled(e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-[0.18em] text-zinc-500">Hashtags</Label>
              <Input
                data-testid="edit-hashtags"
                value={hashtags}
                onChange={(e) => setHashtags(e.target.value)}
                placeholder="#bagnshop #smartliving"
                className="mt-2"
              />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="edit-cancel">Cancel</Button>
          <Button onClick={handleSave} disabled={saving} data-testid="edit-save">
            {saving ? "Saving..." : "Save & mark pending"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
