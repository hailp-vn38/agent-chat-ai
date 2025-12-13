import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  CreateReminderPayload,
  ReminderRead,
  UpdateReminderPayload,
} from "@types";

interface ReminderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reminder?: ReminderRead | null;
  onSubmit: (
    payload: CreateReminderPayload | UpdateReminderPayload
  ) => void | Promise<void>;
  isLoading?: boolean;
}

const toInitialMetadata = (metadata?: Record<string, unknown> | null) => {
  if (!metadata) return "";
  try {
    return JSON.stringify(metadata, null, 2);
  } catch {
    return "";
  }
};

export const ReminderDialog = ({
  open,
  onOpenChange,
  reminder,
  onSubmit,
  isLoading = false,
}: ReminderDialogProps) => {
  const { t } = useTranslation("agents");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [remindAtLocal, setRemindAtLocal] = useState("");
  const [metadata, setMetadata] = useState("");
  const [error, setError] = useState<string | null>(null);

  const modeLabel = useMemo(
    () =>
      reminder
        ? t("update_reminder", "Update reminder")
        : t("create_reminder", "Create reminder"),
    [reminder, t]
  );

  useEffect(() => {
    setTitle(reminder?.title ?? "");
    setContent(reminder?.content ?? "");
    setRemindAtLocal(toLocalInputValue(reminder?.remind_at_local));
    setMetadata(toInitialMetadata(reminder?.reminder_metadata));
    setError(null);
  }, [reminder, open]);

  const toLocalInputValue = (value?: string | null) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const offsetMs = date.getTimezoneOffset() * 60000;
    const localISO = new Date(date.getTime() - offsetMs)
      .toISOString()
      .slice(0, 16);
    return localISO;
  };

  const toOffsetDateTime = (value: string) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    const pad = (num: number) => String(num).padStart(2, "0");
    const year = date.getFullYear();
    const month = pad(date.getMonth() + 1);
    const day = pad(date.getDate());
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    const seconds = pad(date.getSeconds());
    const tzMinutes = date.getTimezoneOffset();
    const sign = tzMinutes > 0 ? "-" : "+";
    const abs = Math.abs(tzMinutes);
    const offset = `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
    return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${offset}`;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    let parsedMetadata: Record<string, unknown> | undefined;
    if (metadata.trim()) {
      try {
        parsedMetadata = JSON.parse(metadata);
      } catch (err) {
        setError(t("invalid_metadata", "Metadata JSON không hợp lệ"));
        return;
      }
    }

    const payload: CreateReminderPayload | UpdateReminderPayload = {
      title: title || undefined,
      content,
      remind_at: toOffsetDateTime(remindAtLocal),
      reminder_metadata: parsedMetadata,
    };

    await onSubmit(payload);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{modeLabel}</DialogTitle>
          <DialogDescription>
            {t(
              "reminder_dialog_desc",
              "Thiết lập nhắc nhở với thời gian có múi giờ (ISO-8601)"
            )}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="reminder-title">{t("title", "Tiêu đề")}</Label>
            <Input
              id="reminder-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={t(
                "reminder_title_placeholder",
                "Ví dụ: Nhắc đi ngủ"
              )}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="reminder-content">{t("content", "Nội dung")}</Label>
            <Textarea
              id="reminder-content"
              required
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder={t(
                "reminder_content_placeholder",
                "Nội dung nhắc nhở"
              )}
              rows={4}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="reminder-remind-at">
              {t("remind_at", "Thời gian (giờ địa phương)")}
            </Label>
            <Input
              id="reminder-remind-at"
              type="datetime-local"
              required
              value={remindAtLocal}
              onChange={(event) => setRemindAtLocal(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {t(
                "remind_at_hint_local",
                "Chọn thời gian theo giờ địa phương; hệ thống tự thêm múi giờ"
              )}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="reminder-metadata">Metadata (JSON)</Label>
            <Textarea
              id="reminder-metadata"
              value={metadata}
              onChange={(event) => setMetadata(event.target.value)}
              placeholder={`{\n  "priority": "high"\n}`}
              rows={3}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t("cancel", "Hủy")}
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? t("saving", "Đang lưu...") : t("save", "Lưu")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
