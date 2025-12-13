import { memo, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Wrench, AlertCircle } from "lucide-react";

import type { ToolSchema, ToolCategory } from "@types";
import { useToolAvailable } from "@/queries";
import { ToolCard } from "@/components/ToolCard";
import { PageHead } from "@/components/PageHead";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

/**
 * Category list for filtering
 */
const CATEGORIES: ToolCategory[] = [
  "weather",
  "music",
  "reminder",
  "news",
  "agent",
  "calendar",
  "iot",
  "other",
];

const ToolsPageComponent = () => {
  const { t } = useTranslation(["tools", "common"]);
  const [searchParams, setSearchParams] = useSearchParams();

  // URL state
  const categoryFilter = useMemo(() => {
    const cat = searchParams.get("category");
    return cat as ToolCategory | null;
  }, [searchParams]);

  // Local state
  const [selectedTool, setSelectedTool] = useState<ToolSchema | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Queries
  const { data: availableData, isLoading, error, refetch } = useToolAvailable();

  // Computed values
  const tools = useMemo(() => {
    if (!availableData?.data) return [];
    if (!categoryFilter) return availableData.data;
    return availableData.data.filter(
      (tool) => tool.category === categoryFilter
    );
  }, [availableData, categoryFilter]);

  const categories = useMemo(() => {
    if (!availableData?.data) return [];
    // Get unique categories from available tools
    const cats = new Set(availableData.data.map((t) => t.category));
    return CATEGORIES.filter((c) => cats.has(c));
  }, [availableData]);

  // Handlers
  const handleCategoryChange = useCallback(
    (category: ToolCategory | "all") => {
      if (category === "all") {
        searchParams.delete("category");
      } else {
        searchParams.set("category", category);
      }
      setSearchParams(searchParams);
    },
    [searchParams, setSearchParams]
  );

  const handleViewDetails = useCallback((tool: ToolSchema) => {
    setSelectedTool(tool);
    setIsDetailOpen(true);
  }, []);

  // Render loading
  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t("tools:tools")}
            </h1>
            <p className="text-muted-foreground mt-2">
              {t("tools:tools_description")}
            </p>
          </div>
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
            {t("tools:tools")}
          </h1>
          <p className="text-muted-foreground mt-2">
            {t("tools:tools_description")}
          </p>
        </div>

        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t("common:error")}</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : t("tools:error_loading")}
          </AlertDescription>
        </Alert>

        <Button onClick={() => refetch()}>{t("common:retry")}</Button>
      </div>
    );
  }

  return (
    <>
      <PageHead
        title="tools:page.title"
        description="tools:page.description"
        translateTitle
        translateDescription
      />
      <div className="space-y-6 p-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t("tools:tools")}
            </h1>
            <p className="text-muted-foreground mt-2">
              {t("tools:tools_description")}
              {availableData && (
                <span className="ml-2 inline-block bg-primary text-primary-foreground px-2 py-1 rounded text-xs font-semibold">
                  {availableData.total} {t("tools:available")}
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Category Filter */}
        <div className="flex flex-wrap gap-2">
          <Badge
            variant={categoryFilter === null ? "default" : "outline"}
            className="cursor-pointer px-3 py-1"
            onClick={() => handleCategoryChange("all")}
          >
            {t("common:all")}
          </Badge>
          {categories.map((cat) => (
            <Badge
              key={cat}
              variant={categoryFilter === cat ? "default" : "outline"}
              className="cursor-pointer px-3 py-1 capitalize"
              onClick={() => handleCategoryChange(cat)}
            >
              {cat}
            </Badge>
          ))}
        </div>

        {/* Tools Grid */}
        {tools.length === 0 ? (
          <Empty className="min-h-64">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Wrench className="size-6" />
              </EmptyMedia>
              <EmptyTitle>{t("tools:no_tools")}</EmptyTitle>
              <EmptyDescription>
                {t("tools:no_tools_description")}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {tools.map((tool) => (
              <ToolCard
                key={tool.name}
                tool={tool}
                onViewDetails={handleViewDetails}
              />
            ))}
          </div>
        )}

        {/* Tool Details Sheet */}
        <Sheet open={isDetailOpen} onOpenChange={setIsDetailOpen}>
          <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Wrench className="h-5 w-5" />
                {selectedTool?.name}
              </SheetTitle>
              <SheetDescription>{selectedTool?.description}</SheetDescription>
            </SheetHeader>

            {selectedTool && (
              <div className="space-y-6 py-4">
                {/* Basic Info */}
                <div className="space-y-2">
                  <h3 className="font-medium">{t("tools:basic_info")}</h3>
                  <div className="rounded-lg border p-3 space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        {t("tools:tool_name")}
                      </span>
                      <code className="bg-muted px-1.5 py-0.5 rounded">
                        {selectedTool.name}
                      </code>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        {t("tools:category")}
                      </span>
                      <Badge variant="secondary" className="capitalize">
                        {selectedTool.category}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Parameters */}
                {selectedTool.parameters?.properties && (
                  <div className="space-y-2">
                    <h3 className="font-medium">{t("tools:parameters")}</h3>
                    <div className="rounded-lg border divide-y">
                      {Object.entries(selectedTool.parameters.properties).map(
                        ([name, param]) => (
                          <div key={name} className="p-3 space-y-1">
                            <div className="flex items-center gap-2">
                              <code className="text-sm font-medium">
                                {name}
                              </code>
                              <Badge variant="outline" className="text-xs">
                                {param.type}
                              </Badge>
                              {selectedTool.parameters?.required?.includes(
                                name
                              ) && (
                                <Badge
                                  variant="destructive"
                                  className="text-xs"
                                >
                                  {t("common:required")}
                                </Badge>
                              )}
                            </div>
                            {param.description && (
                              <p className="text-sm text-muted-foreground">
                                {param.description}
                              </p>
                            )}
                            {param.enum && (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {param.enum.map((v) => (
                                  <Badge
                                    key={v}
                                    variant="secondary"
                                    className="text-xs"
                                  >
                                    {v}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
};

export const ToolsPage = memo(ToolsPageComponent);
