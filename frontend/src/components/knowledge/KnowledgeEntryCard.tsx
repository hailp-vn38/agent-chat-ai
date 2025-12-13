import { useState } from "react";
import { useTranslation } from "react-i18next";
import { MoreVertical, Pencil, Trash2, Copy, Check } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { KnowledgeSectorBadge } from "./KnowledgeSectorBadge";
import type { KnowledgeEntry } from "@/types";
import { cn } from "@/lib/utils";

type KnowledgeEntryCardProps = {
  entry: KnowledgeEntry;
  onEdit?: (entry: KnowledgeEntry) => void;
  onDelete?: (entryId: string) => void;
  className?: string;
};

export const KnowledgeEntryCard = ({
  entry,
  onEdit,
  onDelete,
  className,
}: KnowledgeEntryCardProps) => {
  const { t, i18n } = useTranslation("agents");
  const [isCopied, setIsCopied] = useState(false);

  const truncatedContent =
    entry.content.length > 200
      ? `${entry.content.slice(0, 200)}...`
      : entry.content;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(entry.content);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const formatDate = (dateValue: string | number | undefined | null) => {
    if (!dateValue) return null;
    const date = new Date(dateValue);
    if (isNaN(date.getTime())) return null;
    return date.toLocaleDateString(i18n.language === "vi" ? "vi-VN" : "en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const displayDate =
    formatDate(entry.created_at) || formatDate(entry.last_seen_at);

  return (
    <Card className={cn("group transition-shadow hover:shadow-md", className)}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0 space-y-2">
            {/* Sector Badge */}
            <div className="flex items-center gap-2 flex-wrap">
              <KnowledgeSectorBadge
                sector={entry.primary_sector}
                locale={i18n.language as "en" | "vi"}
              />
              {entry.tags.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {entry.tags.slice(0, 3).map((tag) => (
                    <Badge
                      key={tag}
                      variant="secondary"
                      className="text-xs px-1.5 py-0"
                    >
                      {tag}
                    </Badge>
                  ))}
                  {entry.tags.length > 3 && (
                    <Badge variant="secondary" className="text-xs px-1.5 py-0">
                      +{entry.tags.length - 3}
                    </Badge>
                  )}
                </div>
              )}
            </div>

            {/* Content */}
            <p className="text-sm text-foreground whitespace-pre-wrap">
              {truncatedContent}
            </p>

            {/* Metadata */}
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              {displayDate && <span>{displayDate}</span>}
              {entry.salience > 0.5 && (
                <span className="text-amber-600">{t("high_salience")}</span>
              )}
            </div>
          </div>

          {/* Actions */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleCopy}>
                {isCopied ? (
                  <Check className="h-4 w-4 mr-2" />
                ) : (
                  <Copy className="h-4 w-4 mr-2" />
                )}
                {isCopied ? t("copied") : t("copy")}
              </DropdownMenuItem>
              {onEdit && (
                <DropdownMenuItem onClick={() => onEdit(entry)}>
                  <Pencil className="h-4 w-4 mr-2" />
                  {t("edit")}
                </DropdownMenuItem>
              )}
              {onDelete && (
                <DropdownMenuItem
                  onClick={() => onDelete(entry.id)}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  {t("delete")}
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
};
