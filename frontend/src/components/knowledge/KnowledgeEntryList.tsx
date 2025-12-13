import { useTranslation } from "react-i18next";
import { Brain, Plus } from "lucide-react";
import { KnowledgeEntryCard } from "./KnowledgeEntryCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { KnowledgeEntry } from "@/types";

type KnowledgeEntryListProps = {
  entries: KnowledgeEntry[];
  isLoading?: boolean;
  onEdit?: (entry: KnowledgeEntry) => void;
  onDelete?: (entryId: string) => void;
  onAddNew?: () => void;
  emptyMessage?: string;
};

export const KnowledgeEntryList = ({
  entries,
  isLoading = false,
  onEdit,
  onDelete,
  onAddNew,
  emptyMessage,
}: KnowledgeEntryListProps) => {
  const { t } = useTranslation("agents");

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center border rounded-lg border-dashed">
        <Brain className="h-12 w-12 text-muted-foreground/50 mb-4" />
        <h3 className="text-lg font-medium mb-2">
          {emptyMessage || t("no_knowledge_entries")}
        </h3>
        <p className="text-sm text-muted-foreground mb-4 max-w-md">
          {t("no_knowledge_entries_desc")}
        </p>
        {onAddNew && (
          <Button onClick={onAddNew} className="gap-2">
            <Plus className="h-4 w-4" />
            {t("add_first_entry")}
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <KnowledgeEntryCard
          key={entry.id}
          entry={entry}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
};
