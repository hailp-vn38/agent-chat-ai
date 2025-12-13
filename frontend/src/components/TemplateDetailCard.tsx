import { memo } from "react";
import { LayoutTemplate } from "lucide-react";

import type { AgentTemplate } from "@types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const truncateText = (text: string, maxLength: number = 200) => {
  if (!text) return "N/A";
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
};

export interface TemplateDetailCardProps {
  template?: AgentTemplate | null;
  isDefault?: boolean;
  className?: string;
  isLoading?: boolean;
}

const TemplateDetailCardComponent = ({
  template,
  isDefault = false,
  className,
  isLoading = false,
}: TemplateDetailCardProps) => {
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <Skeleton className="h-5 w-40 mb-1.5" />
          <Skeleton className="h-3 w-48" />
        </CardHeader>
        <CardContent className="pt-0 space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!template) {
    return (
      <Card className={cn("w-full border-dashed", className)}>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <LayoutTemplate className="h-5 w-5 text-muted-foreground" />
            Template
          </CardTitle>
          <CardDescription className="text-xs">
            No template assigned to this agent
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="rounded-lg border-2 border-dashed border-muted-foreground/30 p-6 text-center">
            <LayoutTemplate className="h-6 w-6 text-muted-foreground/40 mx-auto mb-2" />
            <p className="text-xs text-muted-foreground font-medium">
              No template configuration
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Create or assign a template to configure agent behavior
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const modelsList = [
    { label: "ASR Model", value: template.ASR },
    { label: "LLM Model", value: template.LLM },
    { label: "vLLM Model", value: template.VLLM },
    { label: "TTS Model", value: template.TTS },
    { label: "Memory Model", value: template.Memory },
    { label: "Intent Model", value: template.Intent },
    { label: "Summary Memory", value: template.summary_memory },
  ].filter((m) => m.value);

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <LayoutTemplate className="h-5 w-5" />
          Template Configuration
        </CardTitle>
        <CardDescription className="text-xs">
          AI and language settings for this agent
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        {/* Template Name */}
        <div className="space-y-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Template Name
          </p>
          <p className="text-xs font-medium text-foreground truncate">
            {template.name || "—"}
          </p>
        </div>

        {/* Basic Configuration */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Status */}
          <div className="space-y-1">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Status
            </p>
            {isDefault && (
              <Badge variant="success" className="w-fit text-xs">
                Default
              </Badge>
            )}
          </div>
        </div>

        {/* Model Configuration */}
        {modelsList.length > 0 && (
          <div className="space-y-2 pt-2 border-t">
            <p className="text-xs font-semibold text-foreground uppercase tracking-wide">
              Model Configuration
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {modelsList.map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-lg border border-border/50 p-2 bg-muted/30"
                >
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-0.5">
                    {label}
                  </p>
                  <p className="text-xs font-mono text-foreground truncate">
                    {value || "—"}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Prompt Preview */}
        {template.prompt && (
          <div className="space-y-1 pt-2 border-t">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              System Prompt
            </p>
            <div className="rounded-lg border border-border bg-muted/50 p-2.5 max-h-28 overflow-y-auto">
              <p className="text-xs text-foreground whitespace-pre-wrap line-clamp-3">
                {truncateText(template.prompt, 300)}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export const TemplateDetailCard = memo(TemplateDetailCardComponent);
