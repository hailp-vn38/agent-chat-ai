"use client";

import { useState, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus, FileText, AlertCircle, Globe } from "lucide-react";

import type { Template } from "@types";
import {
  useTemplateList,
  useCreateTemplate,
  useUpdateTemplate,
} from "@/queries/template-queries";
import { useProviderModules } from "@/hooks";
import { PageHead } from "@/components/PageHead";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from "@/components/ui/pagination";
import { TemplateCard } from "@/components/TemplateCard";
import { CreateTemplateDialog } from "@/components/CreateTemplateDialog";

const DEFAULT_PAGE_SIZE = 12;

export const TemplatesPage = () => {
  const { t } = useTranslation(["templates", "common"]);
  const [searchParams, setSearchParams] = useSearchParams();
  const { modules, isLoading: modulesLoading } = useProviderModules(true);

  // URL state
  const page = useMemo(() => {
    const p = searchParams.get("page");
    return p ? parseInt(p, 10) : 1;
  }, [searchParams]);

  const includePublic = useMemo(() => {
    return searchParams.get("include_public") === "true";
  }, [searchParams]);

  // Local state
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(
    null
  );

  // Queries & Mutations
  const { data, isLoading, error, refetch } = useTemplateList({
    page,
    page_size: DEFAULT_PAGE_SIZE,
    include_public: includePublic,
  });

  const { mutateAsync: createTemplate, isPending: isCreating } =
    useCreateTemplate();
  const { mutateAsync: updateTemplate, isPending: isUpdating } =
    useUpdateTemplate();

  // Handlers
  const handleIncludePublicChange = useCallback(
    (checked: boolean) => {
      const params: Record<string, string> = { page: "1" };
      if (checked) {
        params.include_public = "true";
      }
      setSearchParams(params);
    },
    [setSearchParams]
  );

  const handlePageChange = useCallback(
    (newPage: number) => {
      const params: Record<string, string> = { page: String(newPage) };
      if (includePublic) {
        params.include_public = "true";
      }
      setSearchParams(params);
    },
    [setSearchParams, includePublic]
  );

  const handleCreate = useCallback(() => {
    setSelectedTemplate(null);
    setIsDialogOpen(true);
  }, []);

  const handleSubmit = async (formData: any) => {
    if (selectedTemplate) {
      // Update
      await updateTemplate({
        templateId: selectedTemplate.id,
        payload: {
          name: formData.name,
          prompt: formData.prompt,
          ASR: formData.ASR || null,
          LLM: formData.LLM || null,
          VLLM: formData.VLLM || null,
          TTS: formData.TTS || null,
          Memory: formData.Memory || null,
          Intent: formData.Intent || null,
          summary_memory: formData.summary_memory || null,
        },
      });
    } else {
      // Create
      await createTemplate({
        name: formData.name,
        prompt: formData.prompt,
        ASR: formData.ASR || null,
        LLM: formData.LLM || null,
        VLLM: formData.VLLM || null,
        TTS: formData.TTS || null,
        Memory: formData.Memory || null,
        Intent: formData.Intent || null,
        summary_memory: formData.summary_memory || null,
      });
    }
  };

  // Convert Template to AgentTemplateDetail format for dialog compatibility
  const templateForDialog = selectedTemplate
    ? {
        id: selectedTemplate.id,
        user_id: selectedTemplate.user_id,
        name: selectedTemplate.name,
        prompt: selectedTemplate.prompt,
        ASR: selectedTemplate.ASR,
        LLM: selectedTemplate.LLM,
        VLLM: selectedTemplate.VLLM,
        TTS: selectedTemplate.TTS,
        Memory: selectedTemplate.Memory,
        Intent: selectedTemplate.Intent,
        summary_memory: selectedTemplate.summary_memory,
        created_at: selectedTemplate.created_at,
        updated_at: selectedTemplate.updated_at,
      }
    : null;

  // Pagination
  const totalPages = data?.total_pages || 1;

  const renderPaginationItems = () => {
    const items = [];
    const showEllipsisStart = page > 3;
    const showEllipsisEnd = page < totalPages - 2;

    if (showEllipsisStart) {
      items.push(
        <PaginationItem key="1">
          <PaginationLink onClick={() => handlePageChange(1)}>1</PaginationLink>
        </PaginationItem>
      );
      items.push(
        <PaginationItem key="ellipsis-start">
          <PaginationEllipsis />
        </PaginationItem>
      );
    }

    for (
      let i = Math.max(1, page - 1);
      i <= Math.min(totalPages, page + 1);
      i++
    ) {
      items.push(
        <PaginationItem key={i}>
          <PaginationLink
            onClick={() => handlePageChange(i)}
            isActive={i === page}
          >
            {i}
          </PaginationLink>
        </PaginationItem>
      );
    }

    if (showEllipsisEnd) {
      items.push(
        <PaginationItem key="ellipsis-end">
          <PaginationEllipsis />
        </PaginationItem>
      );
      items.push(
        <PaginationItem key={totalPages}>
          <PaginationLink onClick={() => handlePageChange(totalPages)}>
            {totalPages}
          </PaginationLink>
        </PaginationItem>
      );
    }

    return items;
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="mt-2 h-4 w-64" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6 p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t("common:error")}</AlertTitle>
          <AlertDescription>
            {t("failed_to_load_templates")}
            <Button
              variant="link"
              className="ml-2 p-0"
              onClick={() => refetch()}
            >
              {t("common:retry")}
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const templates = data?.data || [];

  return (
    <>
      <PageHead
        title="templates:page.title"
        description="templates:page.description"
        translateTitle
        translateDescription
      />
      <div className="space-y-6 p-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t("templates")}
            </h1>
            <p className="mt-1 text-muted-foreground">
              {t("templates_description")}
            </p>
          </div>
          <Button onClick={handleCreate} className="gap-2">
            <Plus className="h-4 w-4" />
            {t("create_template")}
          </Button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="include-public"
              checked={includePublic}
              onCheckedChange={handleIncludePublicChange}
            />
            <Label htmlFor="include-public" className="flex items-center gap-1">
              <Globe className="h-4 w-4" />
              {t("include_public_templates")}
            </Label>
          </div>
        </div>

        {/* Content */}
        {templates.length === 0 ? (
          <Empty>
            <EmptyMedia>
              <FileText className="h-12 w-12 text-muted-foreground" />
            </EmptyMedia>
            <EmptyContent>
              <EmptyHeader>
                <EmptyTitle>{t("no_templates")}</EmptyTitle>
                <EmptyDescription>
                  {t("no_templates_description")}
                </EmptyDescription>
              </EmptyHeader>
            </EmptyContent>
          </Empty>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {templates.map((template) => (
                <TemplateCard key={template.id} template={template} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() => handlePageChange(Math.max(1, page - 1))}
                      aria-disabled={page === 1}
                      className={
                        page === 1 ? "pointer-events-none opacity-50" : ""
                      }
                    />
                  </PaginationItem>
                  {renderPaginationItems()}
                  <PaginationItem>
                    <PaginationNext
                      onClick={() =>
                        handlePageChange(Math.min(totalPages, page + 1))
                      }
                      aria-disabled={page === totalPages}
                      className={
                        page === totalPages
                          ? "pointer-events-none opacity-50"
                          : ""
                      }
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            )}
          </>
        )}

        {/* Create/Edit Dialog */}
        <CreateTemplateDialog
          open={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          template={templateForDialog}
          onSubmit={handleSubmit}
          isLoading={isCreating || isUpdating}
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
      </div>
    </>
  );
};
