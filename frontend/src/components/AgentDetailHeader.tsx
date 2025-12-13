import { memo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { MoreVertical, History, Book, Key } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AgentStatus } from "@types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

export interface AgentDetailHeaderProps {
  agentId: string;
  agentName: string;
  status: AgentStatus;
  onEdit?: () => void;
  onDelete?: () => void;
  onWebhookApi?: () => void;
  isDeleting?: boolean;
}

const AgentDetailHeaderComponent = ({
  agentId,
  agentName,
  status,
  onEdit,
  onDelete,
  onWebhookApi,
  isDeleting = false,
}: AgentDetailHeaderProps) => {
  const navigate = useNavigate();
  const { t } = useTranslation("agents");

  const statusVariant = status === "enabled" ? "success" : "muted";

  const handleDelete = useCallback(() => {
    onDelete?.();
  }, [onDelete]);

  const handleEdit = useCallback(() => {
    onEdit?.();
  }, [onEdit]);

  const handleWebhookApi = useCallback(() => {
    onWebhookApi?.();
  }, [onWebhookApi]);

  return (
    <div className="flex items-center justify-between gap-4 mb-6">
      <div className="flex-1 min-w-0">
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground truncate">
          {agentName}
        </h1>
        <div className="mt-2 flex items-center gap-2">
          <Badge variant={statusVariant} className="capitalize">
            {status}
          </Badge>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate(`/agents/${agentId}/knowledge`)}
          className="hidden sm:flex gap-2"
        >
          <Book className="h-4 w-4" />
          {t("knowledge_base", "Knowledge Base")}
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate(`/agents/${agentId}/history`)}
          className="hidden sm:flex gap-2"
        >
          <History className="h-4 w-4" />
          {t("history", "History")}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              disabled={isDeleting}
              className="h-9 w-9"
            >
              <MoreVertical className="h-5 w-5" />
              <span className="sr-only">Open menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem
              onClick={() => navigate(`/agents/${agentId}/knowledge`)}
              className="sm:hidden"
            >
              <Book className="h-4 w-4 mr-2" />
              {t("knowledge_base", "Knowledge Base")}
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => navigate(`/agents/${agentId}/history`)}
              className="sm:hidden"
            >
              <History className="h-4 w-4 mr-2" />
              {t("history", "History")}
            </DropdownMenuItem>
            <DropdownMenuSeparator className="sm:hidden" />
            <DropdownMenuItem onClick={handleWebhookApi} disabled={isDeleting}>
              <Key className="h-4 w-4 mr-2" />
              {t("webhook_api_key", "Webhook API Key")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleEdit} disabled={isDeleting}>
              {t("edit")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleDelete}
              disabled={isDeleting}
              className="text-destructive focus:bg-destructive/10 focus:text-destructive"
            >
              {isDeleting ? t("deleting") : t("delete")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};

export const AgentDetailHeader = memo(AgentDetailHeaderComponent);
