"use client";

import { useState } from "react";
import { Search, LayoutTemplate, Check, Loader2, Globe } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useTemplateList } from "@/queries/template-queries";
import type { Template } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";

export interface SelectTemplateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (templateId: string, setActive: boolean) => Promise<void>;
  isLoading?: boolean;
  excludeTemplateIds?: string[];
}

export function SelectTemplateDialog({
  open,
  onOpenChange,
  onSelect,
  isLoading = false,
  excludeTemplateIds = [],
}: SelectTemplateDialogProps) {
  const { t } = useTranslation("agents");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null
  );
  const [setAsActive, setSetAsActive] = useState(true);

  const { data, isLoading: isLoadingTemplates } = useTemplateList({
    page: 1,
    page_size: 50,
    include_public: true,
  });

  const templates = data?.data ?? [];

  // Filter templates by search query and exclude already assigned ones
  const filteredTemplates = templates.filter((template) => {
    const isExcluded = excludeTemplateIds.includes(template.id);
    if (isExcluded) return false;

    if (!searchQuery) return true;

    const query = searchQuery.toLowerCase();
    return (
      template.name.toLowerCase().includes(query) ||
      template.prompt?.toLowerCase().includes(query)
    );
  });

  const handleSelect = async () => {
    if (!selectedTemplateId) return;

    try {
      await onSelect(selectedTemplateId, setAsActive);
      handleClose();
    } catch (error) {
      console.error("Select template error:", error);
    }
  };

  const handleClose = () => {
    setSearchQuery("");
    setSelectedTemplateId(null);
    setSetAsActive(true);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <LayoutTemplate className="h-5 w-5" />
            {t("select_template")}
          </DialogTitle>
          <DialogDescription>{t("select_template_desc")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t("search_templates")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Templates List */}
          <ScrollArea className="h-[300px] pr-4">
            {isLoadingTemplates ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full rounded-lg" />
                ))}
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                <LayoutTemplate className="h-10 w-10 mb-2" />
                <p className="text-sm">
                  {searchQuery
                    ? t("no_templates_found")
                    : t("no_available_templates")}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredTemplates.map((template) => (
                  <TemplateItem
                    key={template.id}
                    template={template}
                    isSelected={selectedTemplateId === template.id}
                    onSelect={() => setSelectedTemplateId(template.id)}
                  />
                ))}
              </div>
            )}
          </ScrollArea>

          {/* Set as Active Checkbox */}
          {selectedTemplateId && (
            <div className="flex items-center gap-2 pt-2 border-t">
              <Checkbox
                id="set-active"
                checked={setAsActive}
                onCheckedChange={(checked) => setSetAsActive(checked === true)}
              />
              <label
                htmlFor="set-active"
                className="text-sm text-muted-foreground cursor-pointer"
              >
                {t("set_as_active_template")}
              </label>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={isLoading}
            >
              {t("common:cancel")}
            </Button>
            <Button
              onClick={handleSelect}
              disabled={!selectedTemplateId || isLoading}
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("add_template")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface TemplateItemProps {
  template: Template;
  isSelected: boolean;
  onSelect: () => void;
}

function TemplateItem({ template, isSelected, onSelect }: TemplateItemProps) {
  const { t } = useTranslation("templates");

  const modelsList = [
    { label: "ASR", value: template.ASR?.name },
    { label: "LLM", value: template.LLM?.name },
    { label: "TTS", value: template.TTS?.name },
  ].filter((item) => item.value);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-lg border transition-colors ${
        isSelected
          ? "border-primary bg-primary/5"
          : "border-border hover:border-primary/50 hover:bg-accent/50"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">
              {template.name}
            </span>
            {template.is_public && (
              <Badge variant="outline" className="gap-1 text-xs">
                <Globe className="h-3 w-3" />
                {t("public")}
              </Badge>
            )}
          </div>
          {template.prompt && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
              {template.prompt}
            </p>
          )}
          {modelsList.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {modelsList.map((model) => (
                <Badge
                  key={model.label}
                  variant="secondary"
                  className="text-xs"
                >
                  {model.label}: {model.value}
                </Badge>
              ))}
            </div>
          )}
        </div>
        {isSelected && (
          <div className="flex-shrink-0">
            <Check className="h-5 w-5 text-primary" />
          </div>
        )}
      </div>
    </button>
  );
}
