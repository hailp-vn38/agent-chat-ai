import { useState, memo } from "react";
import { MoreVertical, Clock, Pencil, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ReminderRead, ReminderStatus } from "@types";

interface ListRemindersProps {
  reminders: ReminderRead[];
  onEdit?: (reminder: ReminderRead) => void;
  onDelete?: (reminderId: string) => void;
}

const statusVariantMap: Record<ReminderStatus, string> = {
  pending: "bg-secondary text-secondary-foreground",
  delivered: "bg-blue-100 text-blue-800",
  received: "bg-emerald-100 text-emerald-800",
  failed: "bg-destructive text-destructive-foreground",
};

const statusLabelMap: Record<ReminderStatus, string> = {
  pending: "Đang chờ",
  delivered: "Đã gửi",
  received: "Đã nhận",
  failed: "Thất bại",
};

const formatDateTime = (value: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const ListRemindersComponent = ({
  reminders,
  onEdit,
  onDelete,
}: ListRemindersProps) => {
  const { t } = useTranslation("agents");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    const next = new Set(expanded);
    next.has(id) ? next.delete(id) : next.add(id);
    setExpanded(next);
  };

  if (!reminders || reminders.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-muted-foreground/50 p-6 text-sm text-muted-foreground">
        {t("no_reminders", "No reminders yet")}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {reminders.map((reminder) => {
        const isOpen = expanded.has(reminder.id);
        const badgeClasses = statusVariantMap[reminder.status];
        const statusLabel = statusLabelMap[reminder.status] ?? reminder.status;

        return (
          <Collapsible
            key={reminder.id}
            open={isOpen}
            onOpenChange={() => toggle(reminder.id)}
          >
            <div className="rounded-lg border bg-card">
              <CollapsibleTrigger asChild>
                <div className="w-full px-4 py-3 flex items-start gap-3 text-left">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">
                        {reminder.title || t("reminder", "Reminder")}
                      </span>
                      <Badge className={badgeClasses}>{statusLabel}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {reminder.content}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      <span>
                        {formatDateTime(
                          reminder.remind_at_local || reminder.remind_at
                        )}
                      </span>
                    </div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={(event) => {
                          event.stopPropagation();
                          onEdit?.(reminder);
                        }}
                      >
                        <Pencil className="mr-2 h-4 w-4" />
                        {t("edit", "Edit")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDelete?.(reminder.id);
                        }}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {t("delete", "Delete")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="px-4 pb-4 text-sm text-muted-foreground">
                  <div className="space-y-2">
                    <div>
                      <span className="font-medium text-foreground">
                        {t("content", "Content")}:
                      </span>
                      <p className="mt-1 whitespace-pre-wrap text-foreground">
                        {reminder.content}
                      </p>
                    </div>
                    {reminder.reminder_metadata && (
                      <div>
                        <span className="font-medium text-foreground">
                          Metadata:
                        </span>
                        <pre className="mt-1 rounded bg-muted p-2 text-xs text-foreground overflow-auto">
                          {JSON.stringify(reminder.reminder_metadata, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
};

export const ListReminders = memo(ListRemindersComponent);
