"use client";

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AlertCircle, Plus, Bot, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  useTemplateDetail,
  useUpdateTemplate,
  useDeleteTemplate,
  useTemplateAgents,
  useAssignTemplate,
  useUnassignTemplate,
} from "@/queries/template-queries";
import { useProviderModules } from "@/hooks";
import {
  TemplateDetailHeader,
  CreateTemplateDialog,
  SelectAgentDialog,
  PageHead,
} from "@/components";
import type { UpdateTemplatePayload } from "@/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export const TemplateDetailPage = () => {
  const { templateId } = useParams<{ templateId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation("templates");
  const { modules, isLoading: modulesLoading } = useProviderModules(true);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isSelectAgentDialogOpen, setIsSelectAgentDialogOpen] = useState(false);
  const [deleteTemplateConfirmOpen, setDeleteTemplateConfirmOpen] =
    useState(false);
  const [removeAgentConfirmOpen, setRemoveAgentConfirmOpen] = useState(false);
  const [agentToRemove, setAgentToRemove] = useState<string | null>(null);

  const { mutateAsync: updateTemplate, isPending: isUpdating } =
    useUpdateTemplate();
  const { mutateAsync: deleteTemplateMutation, isPending: isDeleting } =
    useDeleteTemplate();
  const { mutateAsync: assignTemplate, isPending: isAssigning } =
    useAssignTemplate();
  const { mutateAsync: unassignTemplate, isPending: isUnassigning } =
    useUnassignTemplate();

  if (!templateId) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">
            {t("invalid_template_id")}
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            {t("template_id_missing")}
          </p>
          <Button onClick={() => navigate("/templates")} variant="outline">
            {t("back_to_templates")}
          </Button>
        </div>
      </div>
    );
  }

  const {
    data: template,
    isLoading,
    error,
    refetch,
  } = useTemplateDetail(templateId);
  const { data: agentsData, isLoading: isLoadingAgents } =
    useTemplateAgents(templateId);

  const agents = agentsData?.data ?? [];

  const handleEdit = () => {
    setIsEditDialogOpen(true);
  };

  const handleEditSubmit = async (data: UpdateTemplatePayload) => {
    await updateTemplate({
      templateId,
      payload: data,
    });
  };

  const handleDeleteTemplate = () => {
    setDeleteTemplateConfirmOpen(true);
  };

  const handleConfirmDeleteTemplate = async () => {
    try {
      await deleteTemplateMutation(templateId);
      navigate("/templates");
    } catch (error) {
      console.error("Delete template error:", error);
    } finally {
      setDeleteTemplateConfirmOpen(false);
    }
  };

  const handleAddAgent = () => {
    setIsSelectAgentDialogOpen(true);
  };

  const handleSelectAgent = async (agentId: string, setActive: boolean) => {
    await assignTemplate({
      templateId,
      agentId,
      setActive,
    });
  };

  const handleRemoveAgent = (agentId: string) => {
    setAgentToRemove(agentId);
    setRemoveAgentConfirmOpen(true);
  };

  const handleConfirmRemoveAgent = async () => {
    if (!agentToRemove) return;

    try {
      await unassignTemplate({
        templateId,
        agentId: agentToRemove,
      });
    } catch (error) {
      console.error("Remove agent error:", error);
    } finally {
      setRemoveAgentConfirmOpen(false);
      setAgentToRemove(null);
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
        <Skeleton className="h-64 w-full rounded-lg" />
        <Skeleton className="h-48 w-full rounded-lg" />
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
                {t("failed_to_load_template")}
              </h2>
              <p className="text-sm text-muted-foreground">
                {t("unable_to_fetch_template")}
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

  if (!template) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">
            {t("template_not_found")}
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            {t("template_not_found_desc")}
          </p>
        </div>
      </div>
    );
  }

  // Store template name in sessionStorage for breadcrumb display
  if (template?.name) {
    sessionStorage.setItem("currentTemplateName", template.name);
  }

  const modelsList = [
    { label: "ASR", value: template.ASR?.name },
    { label: "LLM", value: template.LLM?.name },
    { label: "TTS", value: template.TTS?.name },
    { label: "VLLM", value: template.VLLM?.name },
    { label: "Memory", value: template.Memory?.name },
    { label: "Intent", value: template.Intent?.name },
  ].filter((item) => item.value);

  return (
    <>
      <PageHead
        title={template?.name || "Template Details"}
        description="templates:page.detail_description"
        translateDescription
      />
      <div className="p-6 space-y-4">
        {/* Header with Actions */}
        <TemplateDetailHeader
          templateId={template.id}
          templateName={template.name}
          isPublic={template.is_public}
          onEdit={handleEdit}
          onDelete={handleDeleteTemplate}
          isDeleting={isDeleting}
        />

        {/* Template Info Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("template_info")}</CardTitle>
            <CardDescription>{t("template_info_desc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Prompt */}
            <div className="space-y-1">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {t("prompt")}
              </p>
              <p className="text-sm text-foreground bg-muted/50 p-3 rounded-lg whitespace-pre-wrap">
                {template.prompt || "—"}
              </p>
            </div>

            {/* Models */}
            {modelsList.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {t("models")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {modelsList.map((model) => (
                    <Badge key={model.label} variant="secondary">
                      {model.label}: {model.value}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Config */}
            <div className="grid grid-cols-2 gap-4 pt-2 border-t">
              <div className="space-y-1">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {t("created_at")}
                </p>
                <p className="text-sm">
                  {new Date(template.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {t("updated_at")}
                </p>
                <p className="text-sm">
                  {new Date(template.updated_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Agents Using Template */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">
              {t("agents_using_template")}
            </h3>
            <Button
              size="sm"
              variant="outline"
              onClick={handleAddAgent}
              className="gap-1"
            >
              <Plus className="h-4 w-4" />
              {t("add_agent")}
            </Button>
          </div>

          {isLoadingAgents ? (
            <div className="space-y-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
              ))}
            </div>
          ) : agents.length > 0 ? (
            <div className="space-y-2">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Bot className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-sm">{agent.agent_name}</p>
                      {agent.description && (
                        <p className="text-xs text-muted-foreground line-clamp-1">
                          {agent.description}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        agent.status === "enabled" ? "success" : "secondary"
                      }
                      className="text-xs"
                    >
                      {agent.status === "enabled"
                        ? t("agents:enabled")
                        : t("common:disabled")}
                    </Badge>
                    {agent.active_template_id === templateId && (
                      <Badge variant="default" className="text-xs">
                        {t("common:default")}
                      </Badge>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => handleRemoveAgent(agent.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-muted-foreground/50 p-6">
              <div className="flex items-center gap-3 text-muted-foreground">
                <Bot className="h-5 w-5" />
                <span className="text-sm">{t("no_agents_using_template")}</span>
              </div>
            </div>
          )}
        </div>

        {/* Edit Template Dialog */}
        <CreateTemplateDialog
          open={isEditDialogOpen}
          onOpenChange={setIsEditDialogOpen}
          template={template as any}
          onSubmit={handleEditSubmit}
          isLoading={isUpdating}
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

        {/* Select Agent Dialog */}
        <SelectAgentDialog
          open={isSelectAgentDialogOpen}
          onOpenChange={setIsSelectAgentDialogOpen}
          onSelect={handleSelectAgent}
          isLoading={isAssigning}
          excludeAgentIds={agents.map((a) => a.id)}
        />

        {/* Delete Template Confirmation */}
        <AlertDialog
          open={deleteTemplateConfirmOpen}
          onOpenChange={setDeleteTemplateConfirmOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {t("delete_template_confirm")}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {t("delete_template_warning")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="flex justify-end gap-2">
              <AlertDialogCancel>{t("common:cancel")}</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmDeleteTemplate}
                disabled={isDeleting}
                className="bg-destructive hover:bg-destructive/90"
              >
                {isDeleting ? t("deleting") : t("delete")}
              </AlertDialogAction>
            </div>
          </AlertDialogContent>
        </AlertDialog>

        {/* Remove Agent Confirmation */}
        <AlertDialog
          open={removeAgentConfirmOpen}
          onOpenChange={setRemoveAgentConfirmOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("remove_agent_confirm")}</AlertDialogTitle>
              <AlertDialogDescription>
                {t("remove_agent_warning")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="flex justify-end gap-2">
              <AlertDialogCancel>{t("common:cancel")}</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmRemoveAgent}
                disabled={isUnassigning}
                className="bg-destructive hover:bg-destructive/90"
              >
                {isUnassigning ? t("removing") : t("remove")}
              </AlertDialogAction>
            </div>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </>
  );
};
