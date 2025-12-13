"use client";

import { useState } from "react";
import { Search, Bot, Check, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAgentList } from "@/queries/agent-queries";
import type { Agent } from "@/types";
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

export interface SelectAgentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (agentId: string, setActive: boolean) => Promise<void>;
  isLoading?: boolean;
  excludeAgentIds?: string[];
}

export function SelectAgentDialog({
  open,
  onOpenChange,
  onSelect,
  isLoading = false,
  excludeAgentIds = [],
}: SelectAgentDialogProps) {
  const { t } = useTranslation("templates");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [setAsActive, setSetAsActive] = useState(true);

  const { data, isLoading: isLoadingAgents } = useAgentList({
    page: 1,
    page_size: 50,
  });

  const agents = data?.data ?? [];

  // Filter agents by search query and exclude already assigned ones
  const filteredAgents = agents.filter((agent) => {
    const isExcluded = excludeAgentIds.includes(agent.id);
    if (isExcluded) return false;

    if (!searchQuery) return true;

    const query = searchQuery.toLowerCase();
    return (
      agent.agent_name.toLowerCase().includes(query) ||
      agent.description?.toLowerCase().includes(query)
    );
  });

  const handleSelect = async () => {
    if (!selectedAgentId) return;

    try {
      await onSelect(selectedAgentId, setAsActive);
      handleClose();
    } catch (error) {
      console.error("Select agent error:", error);
    }
  };

  const handleClose = () => {
    setSearchQuery("");
    setSelectedAgentId(null);
    setSetAsActive(true);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            {t("select_agent")}
          </DialogTitle>
          <DialogDescription>{t("select_agent_desc")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t("search_agents")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Agents List */}
          <ScrollArea className="h-[300px] pr-4">
            {isLoadingAgents ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full rounded-lg" />
                ))}
              </div>
            ) : filteredAgents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                <Bot className="h-10 w-10 mb-2" />
                <p className="text-sm">
                  {searchQuery
                    ? t("no_agents_found")
                    : t("no_available_agents")}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredAgents.map((agent) => (
                  <AgentItem
                    key={agent.id}
                    agent={agent}
                    isSelected={selectedAgentId === agent.id}
                    onSelect={() => setSelectedAgentId(agent.id)}
                  />
                ))}
              </div>
            )}
          </ScrollArea>

          {/* Set as Active Checkbox */}
          {selectedAgentId && (
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
                {t("set_as_active_for_agent")}
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
              disabled={!selectedAgentId || isLoading}
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("add_agent")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface AgentItemProps {
  agent: Agent;
  isSelected: boolean;
  onSelect: () => void;
}

function AgentItem({ agent, isSelected, onSelect }: AgentItemProps) {
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
              {agent.agent_name}
            </span>
            <Badge
              variant={agent.status === "enabled" ? "success" : "secondary"}
              className="text-xs"
            >
              {agent.status}
            </Badge>
          </div>
          {agent.description && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
              {agent.description}
            </p>
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
