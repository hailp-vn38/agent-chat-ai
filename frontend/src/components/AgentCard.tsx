import { memo, useMemo } from "react";
import type { KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Cpu, LayoutTemplate, Power, History, Book } from "lucide-react";

import type { Agent } from "@types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      day: "2-digit",
      month: "short",
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

export interface AgentCardProps {
  agent: Agent;
  className?: string;
  onClick?: (agent: Agent) => void;
}

const AgentCardComponent = ({ agent, className, onClick }: AgentCardProps) => {
  const { t } = useTranslation("agents");
  const navigate = useNavigate();
  const isReady = Boolean(agent.device_id && agent.active_template_id);
  const clickable = typeof onClick === "function";

  const readinessCopy = useMemo(
    () =>
      isReady
        ? { label: t("active"), variant: "success" as const }
        : { label: t("inactive"), variant: "secondary" as const },
    [isReady, t]
  );

  const statusVariant = agent.status === "enabled" ? "success" : "muted";

  const handleClick = () => {
    if (!clickable) return;
    onClick?.(agent);
  };

  const handleHistoryClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/agents/${agent.id}/history`);
  };

  const handleKnowledgeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/agents/${agent.id}/knowledge`);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!clickable) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onClick?.(agent);
    }
  };

  return (
    <Card
      className={cn(
        "group cursor-pointer flex h-full flex-col justify-between border-border/70 bg-gradient-to-b from-background via-background to-muted/30 transition-colors",
        clickable &&
          "hover:border-primary/40 hover:bg-gradient-to-b hover:from-background/80 hover:via-background/80 hover:to-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2",
        className
      )}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      <CardHeader className="space-y-2">
        <div className="flex-1">
          <CardTitle className="text-xl font-semibold text-foreground">
            {agent.agent_name}
          </CardTitle>
          <CardDescription className="mt-1 text-sm text-muted-foreground">
            {agent.description || t("agent_description")}
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant} className="capitalize">
            {agent.status}
          </Badge>
          <Badge variant={readinessCopy.variant}>
            <Power className="mr-1.5 h-3.5 w-3.5" />
            {readinessCopy.label}
          </Badge>
          <Badge variant="outline" className="font-mono text-[10px] uppercase">
            {formatIdentifier(agent.id)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 p-6 pt-0 sm:grid-cols-2">
        <div
          className={`rounded-xl border border-dashed p-4 ${
            agent.device_id
              ? "border-primary/40 bg-primary/5"
              : "border-border/60 bg-muted/50"
          }`}
        >
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground font-medium text-foreground">
            <Cpu className="h-4 w-4 text-primary" />
            {t("device_type")}
          </div>
        </div>

        <div
          className={`rounded-xl border border-dashed p-4 ${
            agent.active_template_id
              ? "border-primary/40 bg-primary/5"
              : "border-border/60 bg-muted/50"
          }`}
        >
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground font-medium text-foreground">
            <LayoutTemplate className="h-4 w-4 text-primary" />
            {t("templates")}
          </div>
        </div>
      </CardContent>
      <CardFooter className="flex flex-col gap-3 pt-2">
        <div className="flex w-full gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 gap-2"
            onClick={handleHistoryClick}
          >
            <History className="h-4 w-4" />
            {t("history", "History")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 gap-2"
            onClick={handleKnowledgeClick}
          >
            <Book className="h-4 w-4" />
            {t("knowledge_base", "Knowledge")}
          </Button>
        </div>
        <div className="flex w-full items-center justify-between text-xs text-muted-foreground">
          <span>
            {t("agent_created")}: {formatTimestamp(agent.created_at)}
          </span>
          <span>
            {t("agent_updated")}: {formatTimestamp(agent.updated_at)}
          </span>
        </div>
      </CardFooter>
    </Card>
  );
};

export const AgentCard = memo(AgentCardComponent);
