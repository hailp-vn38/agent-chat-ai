import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, AlertCircle, Search } from "lucide-react";

import type {
  AgentToolSelection,
  AvailableMcpTool,
  AvailablePluginTool,
  ToolSelectionMode,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";

export interface ToolSelectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentId?: string;
  currentSelection: AgentToolSelection | null | undefined;
  availableMcpTools: AvailableMcpTool[];
  availablePluginTools: AvailablePluginTool[];
  isLoading?: boolean;
  isSubmitting?: boolean;
  onSubmit: (
    mode: ToolSelectionMode,
    tools: Array<{ type: "server_mcp" | "server_plugin"; name: string }>
  ) => Promise<void>;
}

export const ToolSelectionDialog = ({
  open,
  onOpenChange,
  currentSelection,
  availableMcpTools,
  availablePluginTools,
  isLoading = false,
  isSubmitting = false,
  onSubmit,
}: ToolSelectionDialogProps) => {
  const { t } = useTranslation(["agents", "common"]);
  const [mode, setMode] = useState<ToolSelectionMode>("all");
  const [selectedMcpTools, setSelectedMcpTools] = useState<Set<string>>(
    new Set()
  );
  const [selectedPluginTools, setSelectedPluginTools] = useState<Set<string>>(
    new Set()
  );
  const [mcpSearch, setMcpSearch] = useState("");
  const [pluginSearch, setPluginSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Reset state when dialog opens
  useEffect(() => {
    if (!open) return;

    setError(null);
    if (currentSelection) {
      setMode(currentSelection.mode);
      const mcpTools = new Set<string>();
      const pluginTools = new Set<string>();

      if (Array.isArray(currentSelection.tools)) {
        currentSelection.tools.forEach((tool) => {
          if (tool.type === "server_mcp") {
            mcpTools.add(tool.name);
          } else {
            pluginTools.add(tool.name);
          }
        });
      }

      setSelectedMcpTools(mcpTools);
      setSelectedPluginTools(pluginTools);
    } else {
      setMode("all");
      setSelectedMcpTools(new Set());
      setSelectedPluginTools(new Set());
    }
  }, [open, currentSelection]);

  const filteredMcpTools = useMemo(() => {
    if (!Array.isArray(availableMcpTools)) return [];
    return availableMcpTools.filter(
      (tool) =>
        tool.name.toLowerCase().includes(mcpSearch.toLowerCase()) ||
        tool.description.toLowerCase().includes(mcpSearch.toLowerCase())
    );
  }, [availableMcpTools, mcpSearch]);

  const filteredPluginTools = useMemo(() => {
    if (!Array.isArray(availablePluginTools)) return [];
    return availablePluginTools.filter(
      (tool) =>
        tool.name.toLowerCase().includes(pluginSearch.toLowerCase()) ||
        tool.description.toLowerCase().includes(pluginSearch.toLowerCase())
    );
  }, [availablePluginTools, pluginSearch]);

  const handleMcpToolChange = (toolName: string, checked: boolean) => {
    const newSelected = new Set(selectedMcpTools);
    if (checked) {
      newSelected.add(toolName);
    } else {
      newSelected.delete(toolName);
    }
    setSelectedMcpTools(newSelected);
  };

  const handlePluginToolChange = (toolName: string, checked: boolean) => {
    const newSelected = new Set(selectedPluginTools);
    if (checked) {
      newSelected.add(toolName);
    } else {
      newSelected.delete(toolName);
    }
    setSelectedPluginTools(newSelected);
  };

  const handleSubmit = async () => {
    try {
      setError(null);

      const tools: Array<{
        type: "server_mcp" | "server_plugin";
        name: string;
      }> = [];

      if (mode === "all") {
        // Don't send tools if using "all" mode
      } else {
        selectedMcpTools.forEach((toolName) => {
          tools.push({ type: "server_mcp", name: toolName });
        });
        selectedPluginTools.forEach((toolName) => {
          tools.push({ type: "server_plugin", name: toolName });
        });
      }

      await onSubmit(mode, tools);
      onOpenChange(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "An error occurred";
      setError(message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>
            {t("manage_agent_tools", "Manage Agent Tools")}
          </DialogTitle>
          <DialogDescription>
            {t(
              "tool_selection_desc",
              "Choose which tools are available for this agent to use"
            )}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="flex flex-col gap-4 overflow-hidden flex-1">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Mode Selection */}
            <div className="space-y-3">
              <Label className="font-semibold">
                {t("tool_mode", "Tool Mode")}
              </Label>
              <RadioGroup
                value={mode}
                onValueChange={(value) => setMode(value as ToolSelectionMode)}
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="all" id="mode-all" />
                  <Label
                    htmlFor="mode-all"
                    className="font-normal cursor-pointer"
                  >
                    {t("use_all_tools", "Use all available tools")}
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="selected" id="mode-selected" />
                  <Label
                    htmlFor="mode-selected"
                    className="font-normal cursor-pointer"
                  >
                    {t("use_selected_tools", "Use only selected tools")}
                  </Label>
                </div>
              </RadioGroup>
            </div>

            {/* Tool Selection Tabs */}
            {mode === "selected" && (
              <Tabs
                defaultValue="mcp"
                className="flex flex-col flex-1 overflow-hidden"
              >
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="mcp">
                    {t("mcp_tools", "MCP Tools")} ({selectedMcpTools.size})
                  </TabsTrigger>
                  <TabsTrigger value="plugin">
                    {t("plugin_tools", "Plugin Tools")} (
                    {selectedPluginTools.size})
                  </TabsTrigger>
                </TabsList>

                <TabsContent
                  value="mcp"
                  className="flex flex-col gap-3 flex-1 overflow-hidden"
                >
                  <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t("search_mcp_tools", "Search MCP tools...")}
                      value={mcpSearch}
                      onChange={(e) => setMcpSearch(e.target.value)}
                      className="pl-8"
                    />
                  </div>

                  <ScrollArea className="flex-1 overflow-hidden">
                    {filteredMcpTools.length > 0 ? (
                      <div className="space-y-2 pr-4">
                        {filteredMcpTools.map((tool) => (
                          <div
                            key={tool.name}
                            className="flex items-start space-x-3 py-2 pr-4"
                          >
                            <Checkbox
                              id={`mcp-${tool.name}`}
                              checked={selectedMcpTools.has(tool.name)}
                              onCheckedChange={(checked) =>
                                handleMcpToolChange(
                                  tool.name,
                                  checked as boolean
                                )
                              }
                              className="mt-1"
                              disabled={isSubmitting}
                            />
                            <div className="flex-1 min-w-0">
                              <Label
                                htmlFor={`mcp-${tool.name}`}
                                className="font-medium cursor-pointer text-sm"
                              >
                                {tool.name}
                              </Label>
                              <p className="text-xs text-muted-foreground">
                                {tool.config_name} • {tool.description}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex items-center justify-center py-8 text-muted-foreground">
                        {t("no_mcp_tools", "No MCP tools available")}
                      </div>
                    )}
                  </ScrollArea>
                </TabsContent>

                <TabsContent
                  value="plugin"
                  className="flex flex-col gap-3 flex-1 overflow-hidden"
                >
                  <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t(
                        "search_plugin_tools",
                        "Search plugin tools..."
                      )}
                      value={pluginSearch}
                      onChange={(e) => setPluginSearch(e.target.value)}
                      className="pl-8"
                    />
                  </div>

                  <ScrollArea className="flex-1 overflow-hidden">
                    {filteredPluginTools.length > 0 ? (
                      <div className="space-y-2 pr-4">
                        {filteredPluginTools.map((tool) => (
                          <div
                            key={tool.name}
                            className="flex items-start space-x-3 py-2 pr-4"
                          >
                            <Checkbox
                              id={`plugin-${tool.name}`}
                              checked={selectedPluginTools.has(tool.name)}
                              onCheckedChange={(checked) =>
                                handlePluginToolChange(
                                  tool.name,
                                  checked as boolean
                                )
                              }
                              className="mt-1"
                              disabled={isSubmitting}
                            />
                            <div className="flex-1 min-w-0">
                              <Label
                                htmlFor={`plugin-${tool.name}`}
                                className="font-medium cursor-pointer text-sm"
                              >
                                {tool.name}
                              </Label>
                              <p className="text-xs text-muted-foreground">
                                {tool.plugin_name} • {tool.description}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex items-center justify-center py-8 text-muted-foreground">
                        {t("no_plugin_tools", "No plugin tools available")}
                      </div>
                    )}
                  </ScrollArea>
                </TabsContent>
              </Tabs>
            )}

            {/* Actions */}
            <div className="flex gap-2 border-t pt-4">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
                className="flex-1"
              >
                {t("btn_cancel", "Cancel")}
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="flex-1"
              >
                {isSubmitting
                  ? t("saving", "Saving...")
                  : t("btn_save", "Save")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
