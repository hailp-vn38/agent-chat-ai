"use client";

import { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Cpu, Database, Zap } from "lucide-react";

import type { SystemMcpServer } from "@types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export interface SystemMcpCardProps {
  server: SystemMcpServer;
  toolsCount?: number;
  onViewDetails: (serverName: string) => void;
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

const SystemMcpCardComponent = ({
  server,
  toolsCount = 0,
  onViewDetails,
}: SystemMcpCardProps) => {
  const { t } = useTranslation(["mcp-configs", "common"]);

  const statusBadge = useMemo(
    () => ({
      variant: server.is_active ? ("success" as const) : ("secondary" as const),
      label: server.is_active
        ? t("status_active", "Active")
        : t("status_inactive", "Inactive"),
    }),
    [server.is_active, t]
  );

  return (
    <Card
      className={cn(
        "relative transition-all hover:shadow-lg cursor-pointer",
        server.is_active && "border-blue-200 bg-gradient-to-br from-blue-50/50"
      )}
      onClick={() => onViewDetails(server.name)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1 space-y-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Cpu className="h-4 w-4" />
              {server.name}
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              {server.type}
            </CardDescription>
          </div>
          <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            {getTransportIcon(server.type)}
            <span className="font-medium capitalize">{server.type}</span>
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

        {server.type === "sse" && server.url && (
          <div className="truncate text-xs text-muted-foreground">
            <span className="font-medium">URL:</span> {server.url}
          </div>
        )}

        {server.type === "http" && server.url && (
          <div className="truncate text-xs text-muted-foreground">
            <span className="font-medium">URL:</span> {server.url}
          </div>
        )}

        {server.type === "stdio" && server.command && (
          <div className="truncate text-xs text-muted-foreground">
            <span className="font-medium">Command:</span> {server.command}
          </div>
        )}

        {server.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {server.description}
          </p>
        )}
      </CardContent>
    </Card>
  );
};

export const SystemMcpCard = memo(SystemMcpCardComponent);
