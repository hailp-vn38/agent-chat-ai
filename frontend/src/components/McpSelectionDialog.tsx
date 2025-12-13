import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, AlertCircle, Search } from "lucide-react";

import type {
  AgentMcpSelection,
  AvailableMcpServer,
  McpSelectionMode,
  MCPServerReference,
} from "@types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";

export interface McpSelectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentId?: string;
  agentName?: string;
  currentSelection: AgentMcpSelection | null | undefined;
  availableServers: AvailableMcpServer[];
  isLoading?: boolean;
  isSubmitting?: boolean;
  onSubmit: (
    mode: McpSelectionMode,
    servers: MCPServerReference[]
  ) => Promise<void>;
}

export const McpSelectionDialog = ({
  open,
  onOpenChange,
  agentName = "Agent",
  currentSelection,
  availableServers,
  isLoading = false,
  isSubmitting = false,
  onSubmit,
}: McpSelectionDialogProps) => {
  const { t } = useTranslation(["agents", "common"]);
  const [mode, setMode] = useState<McpSelectionMode>("all");
  const [selectedServers, setSelectedServers] = useState<Set<string>>(
    new Set()
  );
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Reset state when dialog opens
  useEffect(() => {
    if (!open) return;

    setError(null);
    if (currentSelection) {
      const mode =
        currentSelection.mcp_selection_mode || currentSelection.mode || "all";
      setMode(mode as McpSelectionMode);
      const servers = new Set<string>();

      if (Array.isArray(currentSelection.servers)) {
        currentSelection.servers.forEach((server) => {
          servers.add(server.reference);
        });
      }

      setSelectedServers(servers);
    } else {
      setMode("all");
      setSelectedServers(new Set());
    }
  }, [open, currentSelection]);

  const filteredServers = useMemo(() => {
    if (!Array.isArray(availableServers)) return [];
    return availableServers.filter(
      (server) =>
        server.name.toLowerCase().includes(search.toLowerCase()) ||
        server.reference.toLowerCase().includes(search.toLowerCase())
    );
  }, [availableServers, search]);

  const handleServerToggle = (reference: string) => {
    setSelectedServers((prev) => {
      const next = new Set(prev);
      if (next.has(reference)) {
        next.delete(reference);
      } else {
        next.add(reference);
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    try {
      setError(null);

      const selectedServerList = Array.from(selectedServers).map(
        (reference) => ({
          reference,
        })
      );

      await onSubmit(mode, selectedServerList as MCPServerReference[]);
      onOpenChange(false);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : t("error_unknown", "Unknown error");
      setError(message);
    }
  };

  const userServers = availableServers.filter((s) => s.source === "user");
  const configServers = availableServers.filter((s) => s.source === "config");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {t("mcp_selection_title", "Manage MCP Servers for {{agent}}", {
              agent: agentName,
            })}
          </DialogTitle>
          <DialogDescription>
            {t(
              "mcp_selection_description",
              "Select MCP servers to assign to this agent. User-created and system servers are available."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Mode Selection */}
          <div className="space-y-3">
            <Label className="text-base font-semibold">
              {t("server_selection_mode", "Selection Mode")}
            </Label>
            <RadioGroup
              value={mode}
              onValueChange={(value) => setMode(value as McpSelectionMode)}
              disabled={isSubmitting}
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="all" id="mode-all" />
                <Label
                  htmlFor="mode-all"
                  className="cursor-pointer font-normal"
                >
                  {t(
                    "use_all_servers_mode",
                    "Use all available MCP servers ({{count}})",
                    { count: availableServers.length }
                  )}
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="selected" id="mode-selected" />
                <Label
                  htmlFor="mode-selected"
                  className="cursor-pointer font-normal"
                >
                  {t(
                    "use_selected_servers_mode",
                    "Use selected servers only ({{count}} selected)",
                    { count: selectedServers.size }
                  )}
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Server Selection - Only visible when "selected" mode */}
          {mode === "selected" && (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="mcp-search" className="text-sm">
                  {t("search_servers", "Search servers")}
                </Label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="mcp-search"
                    placeholder={t("search_placeholder", "Search by name...")}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-10"
                    disabled={isSubmitting || isLoading}
                  />
                </div>
              </div>

              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : availableServers.length === 0 ? (
                <div className="rounded-lg border border-dashed bg-muted/50 py-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    {t("no_servers_available", "No MCP servers available")}
                  </p>
                </div>
              ) : (
                <ScrollArea className="h-[400px] rounded-lg border">
                  <div className="p-4 space-y-4">
                    {/* User Servers Section */}
                    {userServers.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-semibold text-muted-foreground">
                          {t("user_servers", "My Servers")} (
                          {userServers.length})
                        </h4>
                        <div className="space-y-2">
                          {userServers
                            .filter((server) =>
                              filteredServers.some(
                                (s) => s.reference === server.reference
                              )
                            )
                            .map((server) => (
                              <div
                                key={server.reference}
                                className="flex items-start space-x-3 rounded-lg border p-3 hover:bg-muted/50"
                              >
                                <Checkbox
                                  id={server.reference}
                                  checked={selectedServers.has(
                                    server.reference
                                  )}
                                  onCheckedChange={() =>
                                    handleServerToggle(server.reference)
                                  }
                                  disabled={isSubmitting}
                                  className="mt-1"
                                />
                                <div className="flex-1 min-w-0">
                                  <Label
                                    htmlFor={server.reference}
                                    className="cursor-pointer font-medium leading-none"
                                  >
                                    {server.name}
                                  </Label>
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {server.type}
                                  </p>
                                </div>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}

                    {/* Config Servers Section */}
                    {configServers.length > 0 && (
                      <div className="space-y-2 border-t pt-4">
                        <h4 className="text-sm font-semibold text-muted-foreground">
                          {t("system_servers", "System Servers")} (
                          {configServers.length})
                        </h4>
                        <div className="space-y-2">
                          {configServers
                            .filter((server) =>
                              filteredServers.some(
                                (s) => s.reference === server.reference
                              )
                            )
                            .map((server) => (
                              <div
                                key={server.reference}
                                className="flex items-start space-x-3 rounded-lg border p-3 hover:bg-muted/50"
                              >
                                <Checkbox
                                  id={server.reference}
                                  checked={selectedServers.has(
                                    server.reference
                                  )}
                                  onCheckedChange={() =>
                                    handleServerToggle(server.reference)
                                  }
                                  disabled={isSubmitting}
                                  className="mt-1"
                                />
                                <div className="flex-1 min-w-0">
                                  <Label
                                    htmlFor={server.reference}
                                    className="cursor-pointer font-medium leading-none"
                                  >
                                    {server.name}
                                  </Label>
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {server.type}
                                  </p>
                                </div>
                                <span className="text-xs font-medium px-2 py-1 rounded bg-primary/10 text-primary whitespace-nowrap">
                                  {t("system", "System")}
                                </span>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}

                    {filteredServers.length === 0 &&
                      availableServers.length > 0 && (
                        <div className="py-8 text-center">
                          <p className="text-sm text-muted-foreground">
                            {t(
                              "no_matching_servers",
                              "No servers match your search"
                            )}
                          </p>
                        </div>
                      )}
                  </div>
                </ScrollArea>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t pt-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            {t("btn_cancel", "Cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || isLoading}>
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t("btn_save_changes", "Save Changes")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
