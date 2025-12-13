"use client";

import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { AlertCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";

import type { SystemMcpTestResult } from "@types";
import { useSystemMcpServer, useTestSystemMcpServer } from "@/queries";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ToolItemState {
  expanded: boolean;
}

export interface SystemMcpSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serverName?: string;
}

export const SystemMcpSheet = ({
  open,
  onOpenChange,
  serverName,
}: SystemMcpSheetProps) => {
  const { t } = useTranslation(["mcp-configs", "common"]);

  // State
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<SystemMcpTestResult | null>(
    null
  );
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedTools, setExpandedTools] = useState<
    Record<string, ToolItemState>
  >({});

  // Queries
  const { data: serverData } = useSystemMcpServer(
    serverName || "",
    open && !!serverName
  );
  const testMutation = useTestSystemMcpServer();

  const server = serverData?.data;

  // Reset state when sheet opens
  useEffect(() => {
    if (!open) return;

    setError(null);
    setTestResult(null);
    setSearchTerm("");
    setExpandedTools({});
  }, [open]);

  // Tools list with search filter
  const tools = useMemo(() => {
    const toolsList = testResult?.tools || [];
    if (!searchTerm.trim()) return toolsList;
    const term = searchTerm.toLowerCase();
    return toolsList.filter(
      (tool) =>
        tool.name.toLowerCase().includes(term) ||
        tool.description?.toLowerCase().includes(term)
    );
  }, [testResult?.tools, searchTerm]);

  // Handlers
  const handleTestConnection = async () => {
    if (!serverName) return;

    setError(null);
    setTestResult(null);

    try {
      const result = await testMutation.mutateAsync(serverName);
      setTestResult(result);
      if (!result.success) {
        setError(result.message || "Test failed");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Test failed";
      setError(message);
    }
  };

  const toggleToolExpanded = (toolName: string) => {
    setExpandedTools((prev) => ({
      ...prev,
      [toolName]: {
        expanded: !prev[toolName]?.expanded,
      },
    }));
  };

  // Render view mode content
  const renderViewContent = () => {
    if (!server) return null;

    return (
      <ScrollArea className="h-[calc(100vh-300px)] pr-4">
        <div className="space-y-6">
          {/* Server Info */}
          <div className="space-y-4">
            <div>
              <Label className="text-xs font-semibold text-muted-foreground">
                {t("name", "Name")}
              </Label>
              <p className="mt-1 font-medium">{server.name}</p>
            </div>

            {server.description && (
              <div>
                <Label className="text-xs font-semibold text-muted-foreground">
                  {t("description", "Description")}
                </Label>
                <p className="mt-1 text-sm text-muted-foreground">
                  {server.description}
                </p>
              </div>
            )}

            <div>
              <Label className="text-xs font-semibold text-muted-foreground">
                {t("type", "Type")}
              </Label>
              <Badge className="mt-1" variant="secondary">
                {server.type}
              </Badge>
            </div>

            <div>
              <Label className="text-xs font-semibold text-muted-foreground">
                {t("status", "Status")}
              </Label>
              <Badge
                className="mt-1"
                variant={server.is_active ? "success" : "secondary"}
              >
                {server.is_active
                  ? t("status_active", "Active")
                  : t("status_inactive", "Inactive")}
              </Badge>
            </div>

            {server.type === "http" && server.url && (
              <div>
                <Label className="text-xs font-semibold text-muted-foreground">
                  URL
                </Label>
                <p className="mt-1 break-all text-xs text-muted-foreground">
                  {server.url}
                </p>
              </div>
            )}

            {server.type === "sse" && server.url && (
              <div>
                <Label className="text-xs font-semibold text-muted-foreground">
                  URL
                </Label>
                <p className="mt-1 break-all text-xs text-muted-foreground">
                  {server.url}
                </p>
              </div>
            )}

            {server.type === "stdio" && server.command && (
              <div>
                <Label className="text-xs font-semibold text-muted-foreground">
                  {t("command", "Command")}
                </Label>
                <p className="mt-1 text-xs text-muted-foreground">
                  {server.command}
                </p>
              </div>
            )}
          </div>

          <Separator />

          {/* Test Connection Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold text-muted-foreground">
                {t("test_connection", "Test Connection")}
              </Label>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {testResult?.success && (
              <Alert variant="default" className="border-green-200 bg-green-50">
                <AlertDescription className="text-green-800">
                  {t("connection_success", "Connection successful")} - Found{" "}
                  {testResult.tools?.length || 0} tools
                </AlertDescription>
              </Alert>
            )}

            {testResult && !testResult.success && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{testResult.message}</AlertDescription>
              </Alert>
            )}

            <Button
              onClick={handleTestConnection}
              disabled={testMutation.isPending}
              className="w-full"
            >
              {testMutation.isPending ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  {t("testing", "Testing")}
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {t("test_btn", "Test Connection")}
                </>
              )}
            </Button>
          </div>

          {/* Tools Section */}
          {testResult?.tools && testResult.tools.length > 0 && (
            <>
              <Separator />

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-semibold text-muted-foreground">
                    {t("tools", "Tools")} ({tools.length})
                  </Label>
                </div>

                <Input
                  placeholder={t("search_tools", "Search tools...")}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="h-9"
                />

                <div className="space-y-2">
                  {tools.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      {t("no_tools_found", "No tools found")}
                    </p>
                  ) : (
                    tools.map((tool) => (
                      <div
                        key={tool.name}
                        className="rounded-lg border border-border bg-card"
                      >
                        <button
                          onClick={() => toggleToolExpanded(tool.name)}
                          className="flex w-full items-center justify-between p-3 hover:bg-muted/50"
                        >
                          <div className="flex-1 text-left">
                            <p className="text-sm font-medium">{tool.name}</p>
                            {tool.description && (
                              <p className="text-xs text-muted-foreground line-clamp-1">
                                {tool.description}
                              </p>
                            )}
                          </div>
                          {expandedTools[tool.name]?.expanded ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>

                        {expandedTools[tool.name]?.expanded && (
                          <>
                            <Separator className="m-0" />
                            <div className="space-y-2 p-3">
                              {tool.description && (
                                <div>
                                  <p className="text-xs font-semibold text-muted-foreground">
                                    {t("description", "Description")}
                                  </p>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {tool.description}
                                  </p>
                                </div>
                              )}

                              {tool.inputSchema && (
                                <div>
                                  <p className="text-xs font-semibold text-muted-foreground">
                                    {t("input_schema", "Input Schema")}
                                  </p>
                                  <pre className="mt-1 overflow-auto rounded bg-muted p-2 text-xs">
                                    {JSON.stringify(tool.inputSchema, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </ScrollArea>
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>
            {serverName || t("system_mcp_server", "System MCP Server")}
          </SheetTitle>
          <SheetDescription>
            {t(
              "view_system_mcp_details",
              "View system MCP server details and test connection"
            )}
          </SheetDescription>
        </SheetHeader>

        <div className="px-2">{renderViewContent()}</div>
      </SheetContent>
    </Sheet>
  );
};
