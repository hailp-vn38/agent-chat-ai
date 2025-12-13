import { memo, useCallback } from "react";
import { Copy, Check, User } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Agent, AgentDetail } from "@types";
import { CHAT_HISTORY_CONF_LABELS } from "@types";
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
import { Button } from "@/components/ui/button";

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
};

const formatIdentifier = (value?: string | null) => {
  if (!value) return "—";
  return value.length > 10 ? `${value.slice(0, 4)}…${value.slice(-4)}` : value;
};

export interface AgentDetailCardProps {
  agent?: Agent | AgentDetail | null;
  className?: string;
  isLoading?: boolean;
  onAddDevice?: () => void;
}

interface CopyState {
  copied: boolean;
  field: string | null;
}

const AgentDetailCardComponent = ({
  agent,
  className,
  isLoading = false,
  onAddDevice,
}: AgentDetailCardProps) => {
  const [copyState, setCopyState] = useState<CopyState>({
    copied: false,
    field: null,
  });
  const { t } = useTranslation("agents");

  const handleCopy = useCallback((text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopyState({ copied: true, field });
    setTimeout(() => {
      setCopyState({ copied: false, field: null });
    }, 2000);
  }, []);

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-2">
          <Skeleton className="h-5 w-32 mb-1" />
          <Skeleton className="h-3 w-40" />
        </CardHeader>
        <CardContent className="pt-0 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!agent) {
    return (
      <Card className={className}>
        <CardContent className="pt-3">
          <p className="text-sm text-muted-foreground">
            No agent data available.
          </p>
        </CardContent>
      </Card>
    );
  }

  const statusVariant = agent.status === "enabled" ? "success" : "muted";

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{t("agent_details")}</CardTitle>
        <CardDescription className="text-xs">
          {t("agent_details_desc")}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {/* Agent ID */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("agent_id")}
            </p>
            <div className="flex items-center gap-1">
              <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded flex-1 truncate">
                {formatIdentifier(agent.id)}
              </code>
              <Button
                variant="ghost"
                size="icon-sm"
                className="h-6 w-6"
                onClick={() => handleCopy(agent.id, "id")}
              >
                {copyState.copied && copyState.field === "id" ? (
                  <Check className="h-3 w-3 text-green-600" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
          </div>

          {/* Name */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("name")}
            </p>
            <p className="text-xs font-medium text-foreground truncate">
              {agent.agent_name || "—"}
            </p>
          </div>

          {/* Status */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("agent_status")}
            </p>
            <Badge variant={statusVariant} className="w-fit capitalize text-xs">
              {agent.status}
            </Badge>
          </div>

          {/* Chat History Config */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("chat_history_conf", "Chat History")}
            </p>
            <p className="text-xs text-foreground">
              {agent.chat_history_conf !== undefined
                ? CHAT_HISTORY_CONF_LABELS[agent.chat_history_conf as 0 | 1 | 2]
                : CHAT_HISTORY_CONF_LABELS[0]}
            </p>
          </div>

          {/* Description */}
          <div className="space-y-0.5 sm:col-span-2 lg:col-span-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("agent_description")}
            </p>
            <p className="text-xs text-foreground line-clamp-1">
              {agent.description || t("no_description")}
            </p>
          </div>

          {/* User Profile */}
          {agent.user_profile && (
            <div className="space-y-0.5 sm:col-span-2 lg:col-span-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {t("user_profile") || "User Profile"}
              </p>
              <div className="flex items-start gap-2">
                <User className="h-4 w-4 text-accent flex-shrink-0 mt-0.5" />
                <p className="text-xs text-foreground break-words whitespace-pre-wrap">
                  {agent.user_profile}
                </p>
              </div>
            </div>
          )}

          {/* Device ID */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("device")}
            </p>
            {agent.device_id ? (
              <div className="flex items-center gap-1">
                <code className="text-xs font-mono bg-primary/5 px-1.5 py-0.5 rounded flex-1 truncate">
                  {formatIdentifier(agent.device_id)}
                </code>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="h-6 w-6"
                  onClick={() => handleCopy(agent.device_id || "", "device")}
                >
                  {copyState.copied && copyState.field === "device" ? (
                    <Check className="h-3 w-3 text-green-600" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="w-full text-xs h-6"
                onClick={onAddDevice}
              >
                {t("add_device")}
              </Button>
            )}
          </div>

          {/* Template ID */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("template_singular")}
            </p>
            {agent.active_template_id ? (
              <div className="flex items-center gap-1">
                <code className="text-xs font-mono bg-primary/5 px-1.5 py-0.5 rounded flex-1 truncate">
                  {formatIdentifier(agent.active_template_id)}
                </code>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="h-6 w-6"
                  onClick={() =>
                    handleCopy(agent.active_template_id || "", "template")
                  }
                >
                  {copyState.copied && copyState.field === "template" ? (
                    <Check className="h-3 w-3 text-green-600" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                {t("device_not_assigned")}
              </p>
            )}
          </div>

          {/* Created At */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("agent_created")}
            </p>
            <p className="text-xs text-foreground">
              {formatTimestamp(agent.created_at)}
            </p>
          </div>

          {/* Updated At */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("agent_updated")}
            </p>
            <p className="text-xs text-foreground">
              {formatTimestamp(agent.updated_at)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export const AgentDetailCard = memo(AgentDetailCardComponent);
