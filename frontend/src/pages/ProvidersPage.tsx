import { memo, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus, Layers, AlertCircle } from "lucide-react";

import type { Provider, ProviderCategory } from "@types";
import {
  useProviderList,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
  type CreateProviderPayload,
  type ProviderSourceFilter,
} from "@/queries";
import { ProviderCard } from "@/components/ProviderCard";
import { ProviderSheet, PageHead } from "@/components";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
import { Badge } from "@/components/ui/badge";

const DEFAULT_PAGE_SIZE = 12;

const CATEGORY_FILTERS: Array<{
  value: ProviderCategory | "all";
  label: string;
}> = [
  { value: "all", label: "All" },
  { value: "LLM", label: "LLM" },
  { value: "VLLM", label: "VLLM" },
  { value: "TTS", label: "TTS" },
  { value: "ASR", label: "ASR" },
  { value: "Memory", label: "Memory" },
  { value: "Intent", label: "Intent" },
];

const ProvidersPageComponent = () => {
  const { t } = useTranslation(["providers", "common"]);
  const [searchParams, setSearchParams] = useSearchParams();

  // URL state
  const page = useMemo(() => {
    const p = searchParams.get("page");
    return p ? parseInt(p, 10) : 1;
  }, [searchParams]);

  const categoryFilter = useMemo(() => {
    const cat = searchParams.get("category");
    return cat as ProviderCategory | null;
  }, [searchParams]);

  const sourceFilter = useMemo(() => {
    const src = searchParams.get("source");
    return (src as ProviderSourceFilter) || "all";
  }, [searchParams]);

  // Local state
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [sheetMode, setSheetMode] = useState<"create" | "update">("create");
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<Provider | null>(
    null
  );

  // Queries & Mutations
  const { data, isLoading, error, refetch } = useProviderList({
    page,
    page_size: DEFAULT_PAGE_SIZE,
    category: categoryFilter ?? undefined,
    source: sourceFilter,
  });

  const { mutateAsync: createProvider, isPending: isCreating } =
    useCreateProvider();
  const { mutateAsync: updateProvider, isPending: isUpdating } =
    useUpdateProvider();
  const { mutate: deleteProvider, isPending: isDeleting } = useDeleteProvider();

  // Handlers
  const handleCategoryChange = useCallback(
    (category: ProviderCategory | "all") => {
      const params: Record<string, string> = { page: "1" };
      if (category !== "all") {
        params.category = category;
      }
      if (sourceFilter !== "all") {
        params.source = sourceFilter;
      }
      setSearchParams(params);
    },
    [setSearchParams, sourceFilter]
  );

  const handleSourceChange = useCallback(
    (source: ProviderSourceFilter) => {
      const params: Record<string, string> = { page: "1" };
      if (categoryFilter) {
        params.category = categoryFilter;
      }
      if (source !== "all") {
        params.source = source;
      }
      setSearchParams(params);
    },
    [setSearchParams, categoryFilter]
  );

  const handlePreviousPage = useCallback(() => {
    if (page > 1) {
      const params: Record<string, string> = { page: String(page - 1) };
      if (categoryFilter) params.category = categoryFilter;
      if (sourceFilter !== "all") params.source = sourceFilter;
      setSearchParams(params);
    }
  }, [page, categoryFilter, sourceFilter, setSearchParams]);

  const handleNextPage = useCallback(() => {
    if (data && page < (data.total_pages || 1)) {
      const params: Record<string, string> = { page: String(page + 1) };
      if (categoryFilter) params.category = categoryFilter;
      if (sourceFilter !== "all") params.source = sourceFilter;
      setSearchParams(params);
    }
  }, [page, categoryFilter, sourceFilter, data, setSearchParams]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      const params: Record<string, string> = { page: String(newPage) };
      if (categoryFilter) params.category = categoryFilter;
      if (sourceFilter !== "all") params.source = sourceFilter;
      setSearchParams(params);
    },
    [categoryFilter, sourceFilter, setSearchParams]
  );

  const handleOpenCreateSheet = useCallback(() => {
    setSelectedProvider(null);
    setSheetMode("create");
    setIsSheetOpen(true);
  }, []);

  const handleViewProvider = useCallback((provider: Provider) => {
    setSelectedProvider(provider);
    setSheetMode("update");
    setIsSheetOpen(true);
  }, []);

  const handleEditProvider = useCallback((provider: Provider) => {
    setSelectedProvider(provider);
    setSheetMode("update");
    setIsSheetOpen(true);
  }, []);

  const handleDeleteClick = useCallback((provider: Provider) => {
    setProviderToDelete(provider);
    setDeleteDialogOpen(true);
  }, []);

  const handleConfirmDelete = useCallback(() => {
    if (providerToDelete) {
      deleteProvider(providerToDelete.id, {
        onSuccess: () => {
          setDeleteDialogOpen(false);
          setIsSheetOpen(false);
          setProviderToDelete(null);
          setSelectedProvider(null);
        },
      });
    }
  }, [providerToDelete, deleteProvider]);

  const handleToggleActive = useCallback(
    (provider: Provider) => {
      updateProvider({
        providerId: provider.id,
        payload: { is_active: !provider.is_active },
      });
    },
    [updateProvider]
  );

  const handleDuplicateProvider = useCallback((provider: Provider) => {
    // Close current sheet and open create mode with provider data
    setSelectedProvider(provider);
    setSheetMode("create");
    // Sheet will open in create mode with pre-filled data
  }, []);

  const handleSheetSubmit = useCallback(
    async (payload: CreateProviderPayload) => {
      if (sheetMode === "create") {
        await createProvider(payload);
      } else if (selectedProvider) {
        await updateProvider({
          providerId: selectedProvider.id,
          payload: {
            name: payload.name,
            config: payload.config,
            is_active: payload.is_active,
          },
        });
      }
      setIsSheetOpen(false);
    },
    [sheetMode, selectedProvider, createProvider, updateProvider]
  );

  // Computed values
  const totalPages = data?.total_pages ?? 1;
  const totalProviders = data?.total ?? 0;
  const hasPrevious = page > 1;
  const hasNext = page < totalPages;
  const providers = data?.data ?? [];
  const hasProviders = providers.length > 0;

  // Render loading
  if (isLoading && page === 1 && !categoryFilter) {
    return (
      <div className="space-y-4 p-3 sm:space-y-6 sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t("providers:providers")}
            </h1>
            <p className="text-muted-foreground mt-2">
              {t("providers:providers_description")}
            </p>
          </div>
          <Skeleton className="h-10 w-32" />
        </div>

        <div className="flex gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-16" />
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-48 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // Render error
  if (error) {
    return (
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {t("providers:providers")}
          </h1>
          <p className="text-muted-foreground mt-2">
            {t("providers:providers_description")}
          </p>
        </div>

        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t("common:error")}</AlertTitle>
          <AlertDescription>
            {error instanceof Error
              ? error.message
              : t("providers:error_loading")}
          </AlertDescription>
        </Alert>

        <Button onClick={() => refetch()}>{t("common:retry")}</Button>
      </div>
    );
  }

  return (
    <>
      <PageHead
        title="providers:page.title"
        description="providers:page.description"
        translateTitle
        translateDescription
      />
      <div className="space-y-4 p-3 sm:space-y-6 sm:p-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex-1">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              {t("providers:providers")}
            </h1>
            <p className="text-sm sm:text-base text-muted-foreground mt-2">
              {t("providers:providers_description")}
              {totalProviders > 0 && (
                <span className="ml-2 inline-block bg-primary text-primary-foreground px-2 py-1 rounded text-xs font-semibold">
                  {totalProviders}{" "}
                  {t("providers:provider", { count: totalProviders })}
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
            <Select
              value={sourceFilter}
              onValueChange={(value) =>
                handleSourceChange(value as ProviderSourceFilter)
              }
            >
              <SelectTrigger className="flex-1 sm:w-[160px]">
                <SelectValue placeholder={t("providers:source")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {t("providers:all_sources")}
                </SelectItem>
                <SelectItem value="user">
                  {t("providers:my_providers")}
                </SelectItem>
                <SelectItem value="config">
                  {t("providers:default_providers")}
                </SelectItem>
              </SelectContent>
            </Select>
            <Button
              onClick={handleOpenCreateSheet}
              className="gap-2 flex-1 sm:flex-none"
            >
              <Plus className="h-4 w-4" />
              {t("providers:create_provider")}
            </Button>
          </div>
        </div>

        {/* Category Filter */}
        <div className="flex flex-wrap gap-2">
          {CATEGORY_FILTERS.map((cat) => (
            <Badge
              key={cat.value}
              variant={
                (categoryFilter === null && cat.value === "all") ||
                categoryFilter === cat.value
                  ? "default"
                  : "outline"
              }
              className="cursor-pointer px-3 py-1.5 hover:opacity-80 transition-opacity"
              onClick={() => handleCategoryChange(cat.value)}
            >
              {cat.label}
            </Badge>
          ))}
        </div>

        {/* Empty State */}
        {!hasProviders && (
          <Empty className="min-h-64">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Layers className="size-6" />
              </EmptyMedia>
              <EmptyTitle>{t("providers:no_providers")}</EmptyTitle>
              <EmptyDescription>
                {t("providers:no_providers_description")}
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button onClick={handleOpenCreateSheet}>
                {t("providers:create_provider")}
              </Button>
            </EmptyContent>
          </Empty>
        )}

        {/* Providers Grid */}
        {isLoading && (categoryFilter || page > 1) ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full rounded-lg" />
            ))}
          </div>
        ) : (
          hasProviders && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {providers.map((provider, index) => (
                <ProviderCard
                  key={`${provider.source}-${
                    provider.id ?? provider.reference
                  }-${index}`}
                  provider={provider}
                  onView={handleViewProvider}
                  onEdit={handleEditProvider}
                  onDelete={handleDeleteClick}
                  onToggleActive={handleToggleActive}
                />
              ))}
            </div>
          )
        )}

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    handlePreviousPage();
                  }}
                  className={
                    !hasPrevious
                      ? "pointer-events-none opacity-50"
                      : "cursor-pointer"
                  }
                />
              </PaginationItem>

              {/* First page */}
              {page > 2 && (
                <PaginationItem>
                  <PaginationLink
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      handlePageChange(1);
                    }}
                  >
                    1
                  </PaginationLink>
                </PaginationItem>
              )}

              {/* Ellipsis before current */}
              {page > 3 && (
                <PaginationItem>
                  <PaginationEllipsis />
                </PaginationItem>
              )}

              {/* Previous page */}
              {page > 1 && (
                <PaginationItem>
                  <PaginationLink
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      handlePageChange(page - 1);
                    }}
                  >
                    {page - 1}
                  </PaginationLink>
                </PaginationItem>
              )}

              {/* Current page */}
              <PaginationItem>
                <PaginationLink href="#" isActive>
                  {page}
                </PaginationLink>
              </PaginationItem>

              {/* Next page */}
              {page < totalPages && (
                <PaginationItem>
                  <PaginationLink
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      handlePageChange(page + 1);
                    }}
                  >
                    {page + 1}
                  </PaginationLink>
                </PaginationItem>
              )}

              {/* Ellipsis after current */}
              {page < totalPages - 2 && (
                <PaginationItem>
                  <PaginationEllipsis />
                </PaginationItem>
              )}

              {/* Last page */}
              {page < totalPages - 1 && (
                <PaginationItem>
                  <PaginationLink
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      handlePageChange(totalPages);
                    }}
                  >
                    {totalPages}
                  </PaginationLink>
                </PaginationItem>
              )}

              <PaginationItem>
                <PaginationNext
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    handleNextPage();
                  }}
                  className={
                    !hasNext
                      ? "pointer-events-none opacity-50"
                      : "cursor-pointer"
                  }
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        )}

        {/* Provider Sheet */}
        <ProviderSheet
          open={isSheetOpen}
          onOpenChange={setIsSheetOpen}
          mode={sheetMode}
          provider={selectedProvider}
          initialCategory={categoryFilter}
          onSubmit={handleSheetSubmit}
          onDuplicate={handleDuplicateProvider}
          onDelete={handleDeleteClick}
          isLoading={isCreating || isUpdating}
        />

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {t("providers:delete_provider")}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {t("providers:delete_provider_confirmation", {
                  name: providerToDelete?.name,
                })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isDeleting}>
                {t("common:cancel")}
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {t("common:delete")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </>
  );
};

export const ProvidersPage = memo(ProvidersPageComponent);
