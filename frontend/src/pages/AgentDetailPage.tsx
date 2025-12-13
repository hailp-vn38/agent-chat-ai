import { useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AlertCircle, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  useAgentDetail,
  useUpdateAgent,
  useBindAgentDevice,
  useActivateAgentTemplate,
  useDeleteAgent,
  useDeleteAgentDevice,
} from "@/queries/agent-queries";
import {
  useCreateTemplate,
  useUpdateTemplate,
  useDeleteTemplate,
  useAssignTemplate,
  useUnassignTemplate,
} from "@/queries/template-queries";
import {
  useAgentReminders,
  useCreateReminder,
  useUpdateReminder,
  useDeleteReminder,
} from "@/queries/reminder-queries";
import {
  useAgentMcp,
  useAvailableMcpServers,
  useUpdateAgentMcp,
} from "@/queries/agent-mcp-queries";
import { useProviderModules } from "@/hooks";
import {
  AgentDetailHeader,
  AgentDetailCard,
  PageHead,
  DeviceDetailCard,
  TemplatesList,
  AgentDialog,
  BindDeviceDialog,
  CreateTemplateDialog,
  SelectTemplateDialog,
  ListReminders,
  ReminderDialog,
  McpSelectionDialog,
  ToolSelectionDialog,
  WebhookApiDialog,
} from "@/components";
import type { BindDeviceFormValues } from "@/components/BindDeviceDialog";
import type { AgentTemplateDetail, ReminderRead, ReminderStatus } from "@types";
import type {
  TemplatePayload,
  UpdateTemplatePayload,
  CreateReminderPayload,
  UpdateReminderPayload,
} from "@types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const AgentDetailPage = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation("agents");
  const { modules, isLoading: modulesLoading } = useProviderModules(true);
  const [isUpdateDialogOpen, setIsUpdateDialogOpen] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [isBindDeviceDialogOpen, setIsBindDeviceDialogOpen] = useState(false);
  const [isCreateTemplateDialogOpen, setIsCreateTemplateDialogOpen] =
    useState(false);
  const [isSelectTemplateDialogOpen, setIsSelectTemplateDialogOpen] =
    useState(false);
  const [selectedTemplate, _setSelectedTemplate] =
    useState<AgentTemplateDetail | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteType, setDeleteType] = useState<
    "agent" | "template" | "device" | "reminder" | null
  >(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteAgentConfirmOpen, setDeleteAgentConfirmOpen] = useState(false);
  const [isReminderDialogOpen, setIsReminderDialogOpen] = useState(false);
  const [editingReminder, setEditingReminder] = useState<ReminderRead | null>(
    null
  );
  const [isMcpSelectionDialogOpen, setIsMcpSelectionDialogOpen] =
    useState(false);
  const [isWebhookApiDialogOpen, setIsWebhookApiDialogOpen] = useState(false);

  const { mutateAsync: updateAgent, isPending: isUpdating } = useUpdateAgent();
  const { mutateAsync: bindDevice, isPending: isBindingDevice } =
    useBindAgentDevice(agentId || "");

  // MCP Selection queries
  const { data: agentMcpData, refetch: refetchAgentMcp } = useAgentMcp(
    agentId || "",
    !!agentId
  );
  const { data: availableMcpServersData } = useAvailableMcpServers(
    agentId || "",
    "all",
    !!agentId
  );
  const { mutateAsync: updateAgentMcp, isPending: isUpdatingMcp } =
    useUpdateAgentMcp();

  // Template mutations using new independent template API
  const { mutateAsync: createTemplate, isPending: isCreatingTemplate } =
    useCreateTemplate();
  const { mutateAsync: updateTemplateMutation, isPending: isUpdatingTemplate } =
    useUpdateTemplate();
  const { mutateAsync: deleteTemplateMutation, isPending: isDeletingTemplate } =
    useDeleteTemplate();
  const { mutateAsync: assignTemplate, isPending: isAssigningTemplate } =
    useAssignTemplate();
  const { mutateAsync: unassignTemplate } = useUnassignTemplate();
  const { mutateAsync: activateTemplate } = useActivateAgentTemplate(
    agentId || ""
  );
  const { mutateAsync: deleteAgentMutation, isPending: isDeletingAgent } =
    useDeleteAgent();
  const { mutateAsync: deleteDeviceMutation, isPending: isDeletingDevice } =
    useDeleteAgentDevice(agentId || "");
  const [reminderStatus, setReminderStatus] = useState<
    ReminderStatus | undefined
  >(undefined);
  const reminderParams = useMemo(
    () => (reminderStatus ? { status: reminderStatus } : undefined),
    [reminderStatus]
  );
  const {
    data: reminders,
    isLoading: isLoadingReminders,
    refetch: refetchReminders,
  } = useAgentReminders(agentId || "", reminderParams);
  const { mutateAsync: createReminder, isPending: isCreatingReminder } =
    useCreateReminder();
  const { mutateAsync: updateReminderMutation, isPending: isUpdatingReminder } =
    useUpdateReminder();
  const { mutateAsync: deleteReminderMutation, isPending: isDeletingReminder } =
    useDeleteReminder();

  if (!agentId) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">
            {t("invalid_agent_id")}
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            {t("agent_id_missing")}
          </p>
          <Button onClick={() => navigate("/agents")} variant="outline">
            {t("back_to_agents")}
          </Button>
        </div>
      </div>
    );
  }

  const { data, isLoading, error, refetch } = useAgentDetail(agentId);

  const handleEdit = () => {
    setIsUpdateDialogOpen(true);
  };

  const handleUpdateSubmit = async (formData: any) => {
    setUpdateError(null);
    try {
      await updateAgent({
        agentId,
        payload: {
          agent_name: formData.agent_name,
          description: formData.description,
          user_profile: formData.user_profile,
          status: formData.status,
          chat_history_conf: formData.chat_history_conf,
        },
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : t("agents:error_updating_agent");
      setUpdateError(errorMessage);
      throw err;
    }
  };

  const handleAddDevice = () => {
    setIsBindDeviceDialogOpen(true);
  };

  const handleBindDeviceSubmit = async (formData: BindDeviceFormValues) => {
    await bindDevice(formData);
  };

  const handleEditDevice = () => {
    console.log("Edit device");
  };

  const handleAddTemplate = () => {
    setIsSelectTemplateDialogOpen(true);
  };

  const handleAddReminder = () => {
    setEditingReminder(null);
    setIsReminderDialogOpen(true);
  };

  const handleSelectTemplate = async (
    templateId: string,
    setActive: boolean
  ) => {
    if (!agentId) return;
    await assignTemplate({
      templateId,
      agentId,
      setActive,
    });
  };

  const handleTemplateSubmit = async (
    data: TemplatePayload | UpdateTemplatePayload
  ) => {
    try {
      if (selectedTemplate) {
        // Update existing template
        await updateTemplateMutation({
          templateId: selectedTemplate.id,
          payload: data as UpdateTemplatePayload,
        });
      } else {
        // Create new template and assign to agent
        const newTemplate = await createTemplate(data as TemplatePayload);
        // Assign to current agent and set as active
        if (agentId) {
          await assignTemplate({
            templateId: newTemplate.id,
            agentId,
            setActive: true,
          });
        }
      }
    } catch (error) {
      console.error("Template submit error:", error);
    }
  };

  const handleDeleteTemplate = (templateId: string) => {
    setDeleteType("template");
    setDeleteTargetId(templateId);
    setDeleteConfirmOpen(true);
  };

  const handleEditReminder = (reminder: ReminderRead) => {
    setEditingReminder(reminder);
    setIsReminderDialogOpen(true);
  };

  const handleDeleteDevice = () => {
    setDeleteType("device");
    // Device deletion uses agentId on the API side, device id not required
    setDeleteTargetId(device?.id || null);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteReminder = (reminderId: string) => {
    setDeleteType("reminder");
    setDeleteTargetId(reminderId);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    try {
      if (deleteType === "agent" && deleteTargetId) {
        await deleteAgentMutation(deleteTargetId);
        navigate("/agents");
      } else if (deleteType === "template" && deleteTargetId) {
        // First unassign from agent if needed, then delete template
        if (agentId) {
          try {
            await unassignTemplate({ templateId: deleteTargetId, agentId });
          } catch {
            // Template might not be assigned, continue with deletion
          }
        }
        await deleteTemplateMutation(deleteTargetId);
      } else if (deleteType === "device") {
        // API deletes device by agentId, call mutation without device id
        await deleteDeviceMutation();
      } else if (deleteType === "reminder" && deleteTargetId && agentId) {
        await deleteReminderMutation({ reminderId: deleteTargetId, agentId });
        await refetchReminders();
      }
    } catch (error) {
      console.error("Delete error:", error);
    } finally {
      setDeleteConfirmOpen(false);
      setDeleteType(null);
      setDeleteTargetId(null);
    }
  };

  const handleSetDefaultTemplate = async (templateId: string) => {
    try {
      await activateTemplate(templateId);
    } catch (error) {
      console.error("Set default template error:", error);
    }
  };

  const handleSubmitReminder = async (
    payload: CreateReminderPayload | UpdateReminderPayload
  ) => {
    if (!agentId) return;
    try {
      if (editingReminder) {
        await updateReminderMutation({
          reminderId: editingReminder.id,
          payload,
          agentId,
        });
      } else {
        const createPayload = payload as CreateReminderPayload;
        await createReminder({ agentId, payload: createPayload });
      }
      await refetchReminders();
      setIsReminderDialogOpen(false);
      setEditingReminder(null);
    } catch (error) {
      console.error("Reminder submit error:", error);
    }
  };

  const handleMcpSelectionSubmit = async (mode: any, servers: any[]) => {
    if (!agentId) return;
    try {
      await updateAgentMcp({
        agentId,
        payload: {
          mode,
          servers: mode === "all" ? undefined : servers,
        },
      });
      await refetchAgentMcp();
      setIsMcpSelectionDialogOpen(false);
    } catch (error) {
      console.error("MCP selection update error:", error);
      throw error;
    }
  };

  const handleDeleteAgent = () => {
    setDeleteAgentConfirmOpen(true);
  };

  const handleConfirmDeleteAgent = async () => {
    try {
      if (agentId) {
        await deleteAgentMutation(agentId);
        navigate("/agents");
      }
    } catch (error) {
      console.error("Delete agent error:", error);
    } finally {
      setDeleteAgentConfirmOpen(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        {/* Header Skeleton */}
        <div className="flex items-center justify-between gap-4 mb-6">
          <div className="flex-1">
            <Skeleton className="h-8 w-64 mb-2" />
            <Skeleton className="h-6 w-24" />
          </div>
          <Skeleton className="h-9 w-9 rounded-md" />
        </div>

        {/* Cards Skeleton */}
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-96 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-6">
          <div className="flex items-center gap-4">
            <AlertCircle className="h-8 w-8 text-destructive flex-shrink-0" />
            <div className="flex-1">
              <h2 className="font-semibold text-foreground mb-1">
                {t("failed_to_load_agent")}
              </h2>
              <p className="text-sm text-muted-foreground">
                {t("unable_to_fetch_agent")}
              </p>
            </div>
            <Button onClick={() => refetch()} variant="outline" size="sm">
              {t("common:retry")}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">{t("agent_not_found")}</h2>
          <p className="text-sm text-muted-foreground mb-4">
            {t("agent_not_found_desc")}
          </p>
        </div>
      </div>
    );
  }

  const { agent, device, templates } = data || {};

  if (!agent) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">{t("agent_not_found")}</h2>
          <p className="text-sm text-muted-foreground mb-4">
            {t("agent_data_invalid")}
          </p>
        </div>
      </div>
    );
  }

  // Store agent name in sessionStorage for breadcrumb display
  if (agent?.agent_name) {
    sessionStorage.setItem("currentAgentName", agent.agent_name);
  }

  // console.log("Agent Detail Data:", data);

  return (
    <>
      <PageHead
        title={agent?.agent_name || t("agent_details", "Agent Details")}
        description="agents:page.detail_description"
        translateDescription
      />
      <div className="p-6 space-y-4">
        {/* Header with Actions */}
        <AgentDetailHeader
          agentId={agent.id}
          agentName={agent.agent_name}
          status={agent.status}
          onEdit={handleEdit}
          onDelete={handleDeleteAgent}
          onWebhookApi={() => setIsWebhookApiDialogOpen(true)}
        />

        {/* Detail Cards */}
        <div className="space-y-4">
          {/* Agent, Device, and Knowledge Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 gap-4">
            <AgentDetailCard agent={agent} onAddDevice={handleAddDevice} />

            {/* Device Card */}
            {device && (
              <DeviceDetailCard
                device={device}
                onEdit={handleEditDevice}
                onDelete={handleDeleteDevice}
              />
            )}

            {/* Knowledge Base Preview Card */}
            {/* <KnowledgePreviewCard agentId={agent.id} /> */}
          </div>

          {/* Templates List */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm">{t("templates")}</h3>
              <Button
                size="sm"
                variant="outline"
                onClick={handleAddTemplate}
                className="gap-1"
              >
                <Plus className="h-4 w-4" />
                {t("add_template")}
              </Button>
            </div>
            {templates && templates.length > 0 ? (
              <TemplatesList
                templates={templates}
                activeTemplateId={agent?.active_template_id}
                onDelete={handleDeleteTemplate}
                onSetDefault={handleSetDefaultTemplate}
              />
            ) : (
              <div className="rounded-lg border border-dashed border-muted-foreground/50 p-6">
                <div className="flex items-center gap-3 text-muted-foreground">
                  <span className="text-sm">{t("no_templates")}</span>
                </div>
              </div>
            )}
          </div>

          {/* MCP Selection */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h3 className="font-semibold text-sm">
                  {t("manage_mcp_servers", "Quản lý MCP Servers")}
                </h3>
                {agentMcpData?.data &&
                  (() => {
                    const currentMode =
                      agentMcpData.data.mcp_selection_mode ||
                      agentMcpData.data.mode;
                    return (
                      <Badge
                        variant={
                          currentMode === "all" ? "default" : "secondary"
                        }
                      >
                        {currentMode === "all"
                          ? t("use_all_servers", "Tất cả servers")
                          : `${agentMcpData.data.servers?.length || 0} ${t(
                              "servers",
                              "servers"
                            )}
                          `}
                      </Badge>
                    );
                  })()}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsMcpSelectionDialogOpen(true)}
                disabled={isUpdatingMcp}
              >
                {t("common.manage", "Quản lý")}
              </Button>
            </div>

            {agentMcpData?.data &&
              (() => {
                const currentMode =
                  agentMcpData.data.mcp_selection_mode ||
                  agentMcpData.data.mode;
                return (
                  <div className="space-y-2">
                    {currentMode === "selected" &&
                      agentMcpData.data.servers &&
                      agentMcpData.data.servers.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-xs text-muted-foreground">
                            {t("selected_servers", "Servers đã chọn")}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {agentMcpData.data.servers.map((server) => (
                              <Badge
                                key={server.reference}
                                variant="outline"
                                title={`${server.mcp_type}${
                                  server.mcp_description
                                    ? " - " + server.mcp_description
                                    : ""
                                }`}
                              >
                                {server.mcp_name}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    {currentMode === "all" && (
                      <p className="text-xs text-muted-foreground">
                        {t(
                          "all_servers_enabled",
                          "Tất cả MCP servers có sẵn sẽ được sử dụng"
                        )}
                      </p>
                    )}
                  </div>
                );
              })()}
          </div>

          {/* Reminders List */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm">
                {t("reminders", "Nhắc nhở (giờ địa phương)")}
              </h3>
              <div className="flex items-center gap-2">
                <Select
                  value={reminderStatus ?? "all"}
                  defaultValue="all"
                  onValueChange={(value) =>
                    setReminderStatus(
                      value === "all" ? undefined : (value as ReminderStatus)
                    )
                  }
                >
                  <SelectTrigger className="w-40">
                    <SelectValue
                      placeholder={t("select_status", "Chọn trạng thái")}
                    />
                  </SelectTrigger>
                  <SelectContent align="end">
                    <SelectItem value="all">{t("all", "Tất cả")}</SelectItem>
                    <SelectItem value="pending">
                      {t("pending", "Đang chờ")}
                    </SelectItem>
                    <SelectItem value="delivered">
                      {t("delivered", "Đã gửi")}
                    </SelectItem>
                    <SelectItem value="received">
                      {t("received", "Đã nhận")}
                    </SelectItem>
                    <SelectItem value="failed">
                      {t("failed", "Thất bại")}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleAddReminder}
                  className="gap-1"
                >
                  <Plus className="h-4 w-4" />
                  {t("add_reminder", "Thêm nhắc nhở")}
                </Button>
              </div>
            </div>
            {isLoadingReminders ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              <ListReminders
                reminders={reminders?.data ?? []}
                onEdit={handleEditReminder}
                onDelete={handleDeleteReminder}
              />
            )}
          </div>
        </div>

        {/* Update Agent Dialog */}
        {agent && (
          <AgentDialog
            open={isUpdateDialogOpen}
            onOpenChange={setIsUpdateDialogOpen}
            mode="update"
            agent={agent}
            onSubmit={handleUpdateSubmit}
            isLoading={isUpdating}
            error={updateError}
            onErrorDismiss={() => setUpdateError(null)}
          />
        )}

        {/* Bind Device Dialog */}
        <BindDeviceDialog
          open={isBindDeviceDialogOpen}
          onOpenChange={setIsBindDeviceDialogOpen}
          onSubmit={handleBindDeviceSubmit}
          isLoading={isBindingDevice}
        />

        {/* Create/Edit Template Dialog */}
        <CreateTemplateDialog
          open={isCreateTemplateDialogOpen}
          onOpenChange={setIsCreateTemplateDialogOpen}
          template={selectedTemplate}
          onSubmit={handleTemplateSubmit}
          isLoading={isCreatingTemplate || isUpdatingTemplate}
          modules={{
            ASR: modules?.ASR?.map((m) => ({
              reference: m.reference,
              id: m.id,
              name: m.name,
              type: m.type,
              source: m.source,
            })),
            TTS: modules?.TTS?.map((m) => ({
              reference: m.reference,
              id: m.id,
              name: m.name,
              type: m.type,
              source: m.source,
            })),
            LLM: modules?.LLM?.map((m) => ({
              reference: m.reference,
              id: m.id,
              name: m.name,
              type: m.type,
              source: m.source,
            })),
            VLLM: modules?.VLLM?.map((m) => ({
              reference: m.reference,
              id: m.id,
              name: m.name,
              type: m.type,
              source: m.source,
            })),
            Memory: modules?.Memory?.map((m) => ({
              reference: m.reference,
              id: m.id,
              name: m.name,
              type: m.type,
              source: m.source,
            })),
            Intent: modules?.Intent?.map((m) => ({
              reference: m.reference,
              id: m.id,
              name: m.name,
              type: m.type,
              source: m.source,
            })),
          }}
          modulesLoading={modulesLoading}
        />

        {/* Reminder Dialog */}
        <ReminderDialog
          open={isReminderDialogOpen}
          onOpenChange={setIsReminderDialogOpen}
          reminder={editingReminder}
          onSubmit={handleSubmitReminder}
          isLoading={isCreatingReminder || isUpdatingReminder}
        />

        {/* MCP Selection Dialog */}
        {agentId && (
          <McpSelectionDialog
            open={isMcpSelectionDialogOpen}
            onOpenChange={setIsMcpSelectionDialogOpen}
            agentId={agentId}
            agentName={agent?.agent_name}
            currentSelection={agentMcpData?.data}
            availableServers={
              Array.isArray(availableMcpServersData?.mcp_servers)
                ? availableMcpServersData.mcp_servers
                : []
            }
            onSubmit={handleMcpSelectionSubmit}
            isLoading={false}
          />
        )}

        {/* Tool Selection Dialog - Deprecated, kept for backward compatibility */}
        {false && agentId && (
          <ToolSelectionDialog
            open={false}
            onOpenChange={() => {}}
            agentId={agentId}
            currentSelection={null}
            availableMcpTools={[]}
            availablePluginTools={[]}
            onSubmit={async () => {}}
            isLoading={false}
          />
        )}

        {/* Webhook API Dialog */}
        {agentId && (
          <WebhookApiDialog
            open={isWebhookApiDialogOpen}
            onOpenChange={setIsWebhookApiDialogOpen}
            agentId={agentId}
            agentName={agent?.agent_name || ""}
          />
        )}

        {/* Select Template Dialog */}
        <SelectTemplateDialog
          open={isSelectTemplateDialogOpen}
          onOpenChange={setIsSelectTemplateDialogOpen}
          onSelect={handleSelectTemplate}
          isLoading={isAssigningTemplate}
          excludeTemplateIds={templates?.map((t) => t.id) ?? []}
        />

        {/* Delete Confirmation Dialog */}
        <AlertDialog
          open={deleteConfirmOpen}
          onOpenChange={setDeleteConfirmOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {deleteType === "agent"
                  ? t("delete_agent_confirm")
                  : deleteType === "template"
                  ? t("delete_template_confirm")
                  : deleteType === "reminder"
                  ? t("delete_reminder_confirm", "Xóa reminder này?")
                  : t("delete_device_confirm")}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {deleteType === "agent"
                  ? t("delete_permanent")
                  : `${t("delete_action_undo")} ${deleteType}?`}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="flex justify-end gap-2">
              <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmDelete}
                disabled={
                  isDeletingAgent ||
                  isDeletingTemplate ||
                  isDeletingDevice ||
                  isDeletingReminder
                }
                className="bg-destructive hover:bg-destructive/90"
              >
                {isDeletingAgent ||
                isDeletingTemplate ||
                isDeletingDevice ||
                isDeletingReminder
                  ? t("deleting")
                  : t("delete")}
              </AlertDialogAction>
            </div>
          </AlertDialogContent>
        </AlertDialog>

        {/* Delete Agent Confirmation Dialog */}
        <AlertDialog
          open={deleteAgentConfirmOpen}
          onOpenChange={setDeleteAgentConfirmOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("delete_agent_confirm")}</AlertDialogTitle>
              <AlertDialogDescription>
                {t("delete_permanent")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="flex justify-end gap-2">
              <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmDeleteAgent}
                disabled={isDeletingAgent}
                className="bg-destructive hover:bg-destructive/90"
              >
                {isDeletingAgent ? t("deleting") : t("delete")}
              </AlertDialogAction>
            </div>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </>
  );
};
