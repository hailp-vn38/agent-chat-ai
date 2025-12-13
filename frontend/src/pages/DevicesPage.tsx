import { useMemo, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Cpu, AlertCircle } from "lucide-react";

import { useDeviceList } from "@/hooks";
import { DeviceDetailCard, PageHead } from "@/components";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const DEFAULT_PAGE_SIZE = 10;

export function DevicesPage() {
  const { t } = useTranslation(["devices", "common"]);
  const [searchParams, setSearchParams] = useSearchParams();

  // Get pagination from URL params
  const page = useMemo(() => {
    const p = searchParams.get("page");
    return p ? parseInt(p, 10) : 1;
  }, [searchParams]);

  const pageSize = useMemo(() => {
    const ps = searchParams.get("pageSize");
    return ps ? parseInt(ps, 10) : DEFAULT_PAGE_SIZE;
  }, [searchParams]);

  // Fetch devices with pagination
  const { data, isLoading, error } = useDeviceList({
    page,
    page_size: pageSize,
  });

  // Navigation handlers
  const handlePreviousPage = useCallback(() => {
    if (page > 1) {
      setSearchParams({
        page: String(page - 1),
        pageSize: String(pageSize),
      });
    }
  }, [page, pageSize, setSearchParams]);

  const handleNextPage = useCallback(() => {
    if (data && page < data.total_pages) {
      setSearchParams({
        page: String(page + 1),
        pageSize: String(pageSize),
      });
    }
  }, [page, pageSize, data, setSearchParams]);

  // Calculate pagination info
  const totalPages = data?.total_pages ?? 1;
  const totalDevices = data?.total ?? 0;
  const hasPrevious = page > 1;
  const hasNext = page < totalPages;

  // Render loading skeleton grid
  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("devices")}</h1>
          <p className="text-muted-foreground mt-2">
            {t("devices_description")}
          </p>
        </div>

        {/* Skeleton Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-background p-4"
            >
              <Skeleton className="h-6 w-32 mb-2" />
              <Skeleton className="h-4 w-24 mb-4" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("devices")}</h1>
          <p className="text-muted-foreground mt-2">
            {t("devices_description")}
          </p>
        </div>

        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t("error", { ns: "common" })}</AlertTitle>
          <AlertDescription>
            {error instanceof Error
              ? error.message
              : t("error_loading_devices")}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // Render empty state
  if (!data || data.data.length === 0) {
    return (
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("devices")}</h1>
          <p className="text-muted-foreground mt-2">
            {t("devices_description")}
          </p>
        </div>

        {/* Empty State */}
        <div className="rounded-lg border border-dashed border-muted-foreground/30 p-12">
          <div className="flex flex-col items-center justify-center gap-4">
            <Cpu className="h-12 w-12 text-muted-foreground/40" />
            <div className="text-center">
              <p className="font-semibold text-muted-foreground">
                {t("no_devices")}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {t("no_devices_description")}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render device grid
  return (
    <>
      <PageHead
        title="devices:page.title"
        description="devices:page.description"
        translateTitle
        translateDescription
      />
      <div className="space-y-6 p-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("devices")}</h1>
          <p className="text-muted-foreground mt-2">
            {t("devices_description")}
            {totalDevices > 0 && (
              <span className="ml-2 inline-block bg-primary text-primary-foreground px-2 py-1 rounded text-xs font-semibold">
                {totalDevices} {totalDevices === 1 ? t("device") : t("devices")}
              </span>
            )}
          </p>
        </div>

        {/* Device Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.data.map((device) => (
            <DeviceDetailCard
              key={device.id}
              device={device}
              isLoading={false}
            />
          ))}
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between rounded-lg border border-border bg-background p-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreviousPage}
              disabled={!hasPrevious}
            >
              <ChevronLeft className="h-4 w-4 mr-2" />
              {t("previous")}
            </Button>

            <div className="text-sm text-muted-foreground">
              {t("page_of", { page, total: totalPages })}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={!hasNext}
            >
              {t("next")}
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
