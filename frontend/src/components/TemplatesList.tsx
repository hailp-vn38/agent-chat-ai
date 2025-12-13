import { useState } from "react";
import {
  ChevronDown,
  AlertCircle,
  MoreVertical,
  Eye,
  Trash2,
  Star,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AgentTemplate, AgentTemplateDetail } from "@/types";

interface TemplatesListProps {
  templates: (AgentTemplate | AgentTemplateDetail)[];
  activeTemplateId?: string | null;
  onDelete?: (templateId: string) => void;
  onSetDefault?: (templateId: string) => void;
}

export const TemplatesList = ({
  templates,
  activeTemplateId,
  onDelete,
  onSetDefault,
}: TemplatesListProps) => {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const { t } = useTranslation("agents");
  const navigate = useNavigate();

  const toggleExpanded = (templateId: string) => {
    const newExpanded = new Set(expandedIds);
    if (newExpanded.has(templateId)) {
      newExpanded.delete(templateId);
    } else {
      newExpanded.add(templateId);
    }
    setExpandedIds(newExpanded);
  };

  if (!templates || templates.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-muted-foreground/50 p-6">
        <div className="flex items-center gap-3 text-muted-foreground">
          <AlertCircle className="h-5 w-5" />
          <span className="text-sm">{t("no_templates")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {templates.map((template) => {
        const isExpanded = expandedIds.has(template.id);
        const isDefault = activeTemplateId === template.id;

        return (
          <Collapsible
            key={template.id}
            open={isExpanded}
            onOpenChange={() => toggleExpanded(template.id)}
            className="border rounded-lg overflow-hidden"
          >
            {/* Collapsible Header */}
            <div className="flex items-center hover:bg-accent/50 transition-colors">
              <CollapsibleTrigger asChild>
                <button className="flex-1 px-4 py-3 flex items-center justify-between text-left">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">
                        {template.name}
                      </span>
                      {isDefault && (
                        <Badge variant="default">{t("template_default")}</Badge>
                      )}
                    </div>
                  </div>
                  <ChevronDown
                    className={`h-4 w-4 transition-transform ${
                      isExpanded ? "rotate-180" : ""
                    }`}
                  />
                </button>
              </CollapsibleTrigger>

              <div className="flex items-center gap-1 mr-2">
                {/* Set Default Button - only show if not already default */}
                {onSetDefault && !isDefault && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    className="h-8 w-8"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSetDefault(template.id);
                    }}
                    title={t("set_default")}
                  >
                    <Star className="h-4 w-4" />
                  </Button>
                )}

                {/* Menu for View Detail and Delete */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="h-8 w-8"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => navigate(`/templates/${template.id}`)}
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      {t("view_detail")}
                    </DropdownMenuItem>
                    {onDelete && (
                      <DropdownMenuItem
                        onClick={() => onDelete(template.id)}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        {t("delete")}
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* Collapsible Content */}
            <CollapsibleContent className="border-t px-4 py-3 space-y-3 bg-muted/30">
              {/* Template Details Grid */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                {/* ASR Model */}
                {template.ASR && (
                  <div>
                    <span className="text-muted-foreground text-xs font-medium">
                      ASR
                    </span>
                    <p className="text-foreground">
                      {typeof template.ASR === "string"
                        ? template.ASR
                        : template.ASR.name}
                    </p>
                  </div>
                )}

                {/* TTS Model */}
                {template.TTS && (
                  <div>
                    <span className="text-muted-foreground text-xs font-medium">
                      TTS
                    </span>
                    <p className="text-foreground">
                      {typeof template.TTS === "string"
                        ? template.TTS
                        : template.TTS.name}
                    </p>
                  </div>
                )}

                {/* LLM Model */}
                {template.LLM && (
                  <div>
                    <span className="text-muted-foreground text-xs font-medium">
                      LLM
                    </span>
                    <p className="text-foreground">
                      {typeof template.LLM === "string"
                        ? template.LLM
                        : template.LLM.name}
                    </p>
                  </div>
                )}

                {/* VLLM Model */}
                {template.VLLM && (
                  <div>
                    <span className="text-muted-foreground text-xs font-medium">
                      VLLM
                    </span>
                    <p className="text-foreground">
                      {typeof template.VLLM === "string"
                        ? template.VLLM
                        : template.VLLM.name}
                    </p>
                  </div>
                )}

                {/* Memory Model */}
                {template.Memory && (
                  <div>
                    <span className="text-muted-foreground text-xs font-medium">
                      Memory
                    </span>
                    <p className="text-foreground">
                      {typeof template.Memory === "string"
                        ? template.Memory
                        : template.Memory.name}
                    </p>
                  </div>
                )}
              </div>

              {/* Prompt Section */}
              <div className="space-y-2 border-t pt-3">
                <span className="text-muted-foreground text-xs font-medium">
                  {t("prompt")}
                </span>
                <p className="text-sm text-foreground bg-background/50 p-2 rounded border text-wrap break-words">
                  {template.prompt}
                </p>
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground border-t pt-3">
                <div>
                  <span className="font-medium">{t("template_created")}</span>
                  <p>{new Date(template.created_at).toLocaleDateString()}</p>
                </div>
                <div>
                  <span className="font-medium">{t("template_updated")}</span>
                  <p>{new Date(template.updated_at).toLocaleDateString()}</p>
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>
        );
      })}
    </div>
  );
};
