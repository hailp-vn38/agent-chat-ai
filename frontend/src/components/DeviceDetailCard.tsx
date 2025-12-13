import { memo, useCallback, useState } from "react";
import { Copy, Check, Cpu, MoreVertical, Edit, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { Device } from "@types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
};

export interface DeviceDetailCardProps {
  device?: Device | null;
  className?: string;
  isLoading?: boolean;
  onEdit?: () => void;
  onDelete?: () => void;
}

interface CopyState {
  copied: boolean;
  field: string | null;
}

const DeviceDetailCardComponent = ({
  device,
  className,
  isLoading = false,
  onEdit,
  onDelete,
}: DeviceDetailCardProps) => {
  const [copyState, setCopyState] = useState<CopyState>({
    copied: false,
    field: null,
  });
  const { t } = useTranslation("agents");

  const handleCopy = useCallback((text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopyState({ copied: true, field });
    setTimeout(() => {
      setCopyState({ copied: false, field: null });
    }, 2000);
  }, []);

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-2">
          <Skeleton className="h-5 w-32 mb-1" />
          <Skeleton className="h-3 w-40" />
        </CardHeader>
        <CardContent className="pt-0 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!device) {
    return (
      <Card className={cn("w-full border-dashed", className)}>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Cpu className="h-5 w-5 text-muted-foreground" />
            {t("device")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("no_device_bound")}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="rounded-lg border-2 border-dashed border-muted-foreground/30 p-4 text-center">
            <Cpu className="h-6 w-6 text-muted-foreground/40 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground font-medium">
              {t("no_device_config")}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t("bind_device")}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            {t("device_details")}
          </CardTitle>
          {(onEdit || onDelete) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-sm" className="h-6 w-6">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onEdit && (
                  <DropdownMenuItem onClick={onEdit}>
                    <Edit className="h-4 w-4 mr-2" />
                    {t("edit")}
                  </DropdownMenuItem>
                )}
                {onDelete && (
                  <DropdownMenuItem
                    onClick={onDelete}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    {t("delete")}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
        <CardDescription className="text-xs">
          {t("device_info")}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {/* Device Name */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("device_name")}
            </p>
            <p className="text-xs font-medium text-foreground truncate">
              {device.device_name || "—"}
            </p>
          </div>

          {/* MAC Address */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("mac_address")}
            </p>
            <div className="flex items-center gap-1">
              <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded flex-1 truncate">
                {device.mac_address || "—"}
              </code>
              {device.mac_address && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="h-6 w-6 flex-shrink-0"
                  onClick={() => handleCopy(device.mac_address, "mac")}
                >
                  {copyState.copied && copyState.field === "mac" ? (
                    <Check className="h-3 w-3 text-green-600" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              )}
            </div>
          </div>

          {/* Board */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("board")}
            </p>
            <p className="text-xs text-foreground truncate">
              {device.board || "—"}
            </p>
          </div>

          {/* Firmware Version */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("firmware_version")}
            </p>
            <p className="text-xs font-mono text-foreground truncate">
              {device.firmware_version || "—"}
            </p>
          </div>

          {/* Status */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("device_status")}
            </p>
            <Badge
              variant={device.status === "active" ? "success" : "secondary"}
              className="w-fit capitalize text-xs"
            >
              {device.status || "—"}
            </Badge>
          </div>

          {/* Last Connected */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("last_connected")}
            </p>
            <p className="text-xs text-foreground">
              {device.last_connected_at
                ? formatTimestamp(device.last_connected_at)
                : "—"}
            </p>
          </div>

          {/* Created At */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("binding_date")}
            </p>
            <p className="text-xs text-foreground">
              {formatTimestamp(device.created_at)}
            </p>
          </div>

          {/* Updated At */}
          <div className="space-y-0.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              {t("last_updated")}
            </p>
            <p className="text-xs text-foreground">
              {formatTimestamp(device.updated_at)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export const DeviceDetailCard = memo(DeviceDetailCardComponent);
