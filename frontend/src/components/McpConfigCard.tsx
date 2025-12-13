import { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Cpu, Database, Zap } from "lucide-react";

import type { McpConfig } from "@types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export interface McpConfigCardProps {
  config: McpConfig;
  toolsCount?: number;
  onViewDetails: (configId: string) => void;
}

const getTransportIcon = (type: string) => {
  switch (type) {
    case "stdio":
      return <Database className="h-4 w-4" />;
    case "sse":
      return <Zap className="h-4 w-4" />;
    case "http":
      return <Cpu className="h-4 w-4" />;
    default:
      return <Cpu className="h-4 w-4" />;
  }
};

const McpConfigCardComponent = ({
  config,
  toolsCount = 0,
  onViewDetails,
}: McpConfigCardProps) => {
  const { t } = useTranslation(["mcp-configs", "common"]);

  const statusBadge = useMemo(
    () => ({
      variant: config.is_active ? ("success" as const) : ("secondary" as const),
      label: config.is_active
        ? t("status_active", "Active")
        : t("status_inactive", "Inactive"),
    }),
    [config.is_active, t]
  );

  return (
    <Card
      className={cn(
        "relative transition-all hover:shadow-lg cursor-pointer",
        config.is_active &&
          "border-green-200 bg-gradient-to-br from-green-50/50"
      )}
      onClick={() => onViewDetails(config.id)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1 space-y-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Cpu className="h-4 w-4" />
              {config.name}
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              {config.type}
            </CardDescription>
          </div>
          <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            {getTransportIcon(config.type)}
            <span className="font-medium capitalize">{config.type}</span>
          </div>
          <div className="flex items-center gap-1">
            <Cpu className="h-3.5 w-3.5" />
            <span className="text-muted-foreground">
              {toolsCount > 0
                ? t("tools_count", "{{count}} tools", { count: toolsCount })
                : t("no_tools", "No tools")}
            </span>
          </div>
        </div>

        {config.type === "sse" && config.url && (
          <div className="truncate text-xs text-muted-foreground">
            <span className="font-medium">URL:</span> {config.url}
          </div>
        )}

        {config.type === "stdio" && config.command && (
          <div className="truncate text-xs text-muted-foreground">
            <span className="font-medium">Command:</span> {config.command}
          </div>
        )}

        {config.tools && config.tools.length > 0 && (
          <div className="space-y-1 pt-2 border-t">
            <p className="text-xs font-medium text-muted-foreground">
              {t("tools", "Tools")}:
            </p>
            <div className="flex flex-wrap gap-1">
              {config.tools.slice(0, 5).map((tool) => (
                <span
                  key={tool.name}
                  className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground"
                >
                  {tool.name}
                </span>
              ))}
              {config.tools.length > 5 && (
                <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                  +{config.tools.length - 5} {t("more", "more")}
                </span>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export const McpConfigCard = memo(McpConfigCardComponent);
