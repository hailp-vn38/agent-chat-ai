import { useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { AlertCircle, Plus } from "lucide-react";

import {
  useMcpConfigs,
  useDeleteMcpConfig,
  useSystemMcpServers,
} from "@/queries";
import { PageHead } from "@/components/PageHead";
import { McpConfigCard } from "@/components";
import { SystemMcpCard } from "@/components/SystemMcpCard";
import { McpConfigSheet } from "@/components/McpConfigSheet";
import { SystemMcpSheet } from "@/components/SystemMcpSheet";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const McpConfigsPageComponent = () => {
  const { t } = useTranslation(["mcp-configs", "common"]);

  // State
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetMode, setSheetMode] = useState<"create" | "edit" | "view" | null>(
    null
  );
  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null);
  const [selectedSystemMcpServerName, setSelectedSystemMcpServerName] =
    useState<string | null>(null);
  const [systemMcpSheetOpen, setSystemMcpSheetOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [configToDelete, setConfigToDelete] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"user" | "system">("user");

  // Queries
  const { data: configsData, isLoading, error, refetch } = useMcpConfigs();
  const { data: systemMcpServersData, isLoading: systemMcpLoading } =
    useSystemMcpServers();
  const deleteMutation = useDeleteMcpConfig();

  const configs = useMemo(() => configsData?.data || [], [configsData]);
  const systemMcpServers = useMemo(
    () => systemMcpServersData?.data || [],
    [systemMcpServersData]
  );

  // Handlers
  const handleCreateNew = useCallback(() => {
    setSelectedConfigId(null);
    setSheetMode("create");
    setSheetOpen(true);
  }, []);

  const handleViewDetails = useCallback((configId: string) => {
    setSelectedConfigId(configId);
    setSheetMode("view");
    setSheetOpen(true);
  }, []);

  const handleSheetClose = useCallback(() => {
    setSheetOpen(false);
    setSheetMode(null);
    setSelectedConfigId(null);
  }, []);

  const handleSystemMcpViewDetails = useCallback((serverName: string) => {
    setSelectedSystemMcpServerName(serverName);
    setSystemMcpSheetOpen(true);
  }, []);

  const handleSystemMcpSheetClose = useCallback(() => {
    setSystemMcpSheetOpen(false);
    setSelectedSystemMcpServerName(null);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (!configToDelete) return;

    try {
      await deleteMutation.mutateAsync(configToDelete);
      setDeleteConfirmOpen(false);
      setConfigToDelete(null);
      refetch();
    } catch (err) {
      console.error("Failed to delete config:", err);
    }
  }, [configToDelete, deleteMutation, refetch]);

  // Render loading
  if (isLoading || systemMcpLoading) {
    return (
      <div className="space-y-6 p-6">
        <PageHead
          title={t("page_title", "MCP Configurations")}
          description={t(
            "page_description",
            "Manage MCP server configurations for your agents"
          )}
        />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // Render error
  if (error) {
    return (
      <div className="space-y-6 p-6">
        <PageHead
          title={t("page_title", "MCP Configurations")}
          description={t(
            "page_description",
            "Manage MCP server configurations for your agents"
          )}
        />
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t("error", "Error")}</AlertTitle>
          <AlertDescription>
            {t("loading_error", "Failed to load MCP configurations")}
          </AlertDescription>
        </Alert>
        <Button onClick={() => refetch()}>{t("btn_retry", "Retry")}</Button>
      </div>
    );
  }

  // Render empty state
  if (configs.length === 0 && systemMcpServers.length === 0) {
    return (
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <PageHead
            title={t("page_title", "MCP Configurations")}
            description={t(
              "page_description",
              "Manage MCP server configurations for your agents"
            )}
          />
          <Button onClick={handleCreateNew}>
            <Plus className="mr-2 h-4 w-4" />
            {t("create_button", "New Configuration")}
          </Button>
        </div>

        <Empty>
          <EmptyHeader>
            <EmptyTitle>{t("empty_title", "No MCP Configurations")}</EmptyTitle>
            <EmptyDescription>
              {t(
                "empty_description",
                "Start by creating a new MCP configuration to get started"
              )}
            </EmptyDescription>
          </EmptyHeader>
        </Empty>

        {/* Unified Sheet */}
        {sheetMode && (
          <McpConfigSheet
            open={sheetOpen}
            onOpenChange={handleSheetClose}
            mode={sheetMode}
            configId={selectedConfigId || undefined}
            onModeChange={(newMode, newConfigId) => {
              setSheetMode(newMode);
              if (newConfigId) {
                setSelectedConfigId(newConfigId);
              }
            }}
            onDelete={async (deletedId) => {
              await refetch();
              if (deletedId === selectedConfigId) {
                handleSheetClose();
              }
            }}
          />
        )}
      </div>
    );
  }

  // Render configs with tabs
  return (
    <div className="space-y-6 p-6">
      <div className="space-y-2">
        <PageHead
          title={t("page_title", "MCP Configurations")}
          description={t(
            "page_description",
            "Manage MCP server configurations for your agents"
          )}
        />
        <div className="flex flex-col gap-1 text-sm text-muted-foreground">
          <p>
            {t(
              "tabs_user_desc",
              "User MCP servers are custom configurations you create for your agents"
            )}
          </p>
          <p>
            {t(
              "tabs_system_desc",
              "System MCP servers are pre-configured by your administrator"
            )}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <Tabs
          defaultValue="user"
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as "user" | "system")}
          className="flex-1"
        >
          <TabsList>
            <TabsTrigger value="user">
              {t("user_mcp", "User MCP")}
              <span className="ml-2 text-xs text-muted-foreground">
                ({configs.length}{" "}
                {configs.length === 1
                  ? t("tab_item", "item")
                  : t("tab_items", "items")}
                )
              </span>
            </TabsTrigger>
            <TabsTrigger value="system">
              {t("system_mcp", "System MCP")}
              <span className="ml-2 text-xs text-muted-foreground">
                ({systemMcpServers.length}{" "}
                {systemMcpServers.length === 1
                  ? t("tab_item", "item")
                  : t("tab_items", "items")}
                )
              </span>
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {activeTab === "user" && (
          <Button onClick={handleCreateNew}>
            <Plus className="mr-2 h-4 w-4" />
            {t("create_button", "New Configuration")}
          </Button>
        )}
      </div>

      {/* Tabs Content */}
      {activeTab === "user" && (
        <div className="space-y-4">
          {configs.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>
                  {t("empty_title", "No MCP Configurations")}
                </EmptyTitle>
                <EmptyDescription>
                  {t(
                    "empty_description",
                    "Start by creating a new MCP configuration to get started"
                  )}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {configs.map((config) => (
                <McpConfigCard
                  key={config.id}
                  config={config}
                  toolsCount={config.tools?.length || 0}
                  onViewDetails={handleViewDetails}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* System MCP Tab */}
      {activeTab === "system" && (
        <div className="space-y-4">
          {systemMcpServers.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>
                  {t("empty_system_mcp", "No System MCP Servers")}
                </EmptyTitle>
                <EmptyDescription>
                  {t(
                    "empty_system_mcp_description",
                    "No system MCP servers are configured"
                  )}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {systemMcpServers.map((server) => (
                <SystemMcpCard
                  key={server.name}
                  server={server}
                  toolsCount={0}
                  onViewDetails={handleSystemMcpViewDetails}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* User MCP Sheet */}
      {sheetMode && (
        <McpConfigSheet
          open={sheetOpen}
          onOpenChange={handleSheetClose}
          mode={sheetMode}
          configId={selectedConfigId || undefined}
          onModeChange={async (newMode, newConfigId) => {
            setSheetMode(newMode);
            if (newConfigId) {
              setSelectedConfigId(newConfigId);
            }
            // Refetch after mode change (especially after create)
            if (newMode === "view") {
              await refetch();
            }
          }}
          onDelete={async (deletedId) => {
            await refetch();
            if (deletedId === selectedConfigId) {
              handleSheetClose();
            }
          }}
        />
      )}

      {/* System MCP Sheet */}
      <SystemMcpSheet
        open={systemMcpSheetOpen}
        onOpenChange={handleSystemMcpSheetClose}
        serverName={selectedSystemMcpServerName || undefined}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("delete_confirmation", "Are you sure?")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("delete_warning", "This action cannot be undone")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogCancel>{t("btn_cancel", "Cancel")}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirmDelete}
            disabled={deleteMutation.isPending}
            className="bg-destructive hover:bg-destructive/90"
          >
            {t("btn_delete", "Delete")}
          </AlertDialogAction>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export const McpConfigsPage = McpConfigsPageComponent;
