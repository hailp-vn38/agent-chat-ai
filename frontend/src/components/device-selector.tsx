"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertCircle, ChevronsUpDown, Check } from "lucide-react";

import type { Device } from "@/types";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface DeviceSelectorProps {
  devices: Device[];
  selectedDeviceId?: string;
  onSelectDevice: (device: Device) => void;
  isLoading?: boolean;
  error?: Error | null;
  disabled?: boolean;
}

/**
 * DeviceSelector - Combobox component for selecting a device
 * Fetches device list and allows in-memory search
 */
export function DeviceSelector({
  devices,
  selectedDeviceId,
  onSelectDevice,
  isLoading = false,
  error = null,
  disabled = false,
}: DeviceSelectorProps) {
  const { t } = useTranslation(["chat", "common"]);
  const [open, setOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");

  const selectedDevice = devices.find((d) => d.id === selectedDeviceId);
  const selectedLabel =
    selectedDevice?.device_name ||
    selectedDevice?.mac_address ||
    (selectedDeviceId ? `Device ${selectedDeviceId.slice(0, 8)}` : null);

  const handleSelectDevice = (deviceId: string) => {
    const device = devices.find((d) => d.id === deviceId);
    if (device) {
      onSelectDevice(device);
      setOpen(false);
      setSearchValue("");
    }
  };

  // Loading state
  if (isLoading) {
    return <Skeleton className="h-9 w-full rounded-md" />;
  }

  // Error state
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{t("common:error")}</AlertTitle>
        <AlertDescription>
          {error instanceof Error ? error.message : t("error_loading_devices")}
        </AlertDescription>
      </Alert>
    );
  }

  // Empty devices state
  if (devices.length === 0) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{t("no_devices")}</AlertTitle>
        <AlertDescription>{t("no_devices_desc")}</AlertDescription>
      </Alert>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between"
            disabled={disabled || devices.length === 0}
          >
            <span className={cn(!selectedLabel && "text-muted-foreground")}>
              {selectedLabel || t("select_device_placeholder")}
            </span>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={t("search_device")}
              value={searchValue}
              onValueChange={setSearchValue}
            />
            <CommandList>
              <CommandEmpty>{t("no_devices_found")}</CommandEmpty>
              <CommandGroup>
                {devices
                  .filter(
                    (device) =>
                      (device.device_name
                        ?.toLowerCase()
                        .includes(searchValue.toLowerCase()) ??
                        false) ||
                      device.mac_address
                        .toLowerCase()
                        .includes(searchValue.toLowerCase())
                  )
                  .map((device) => (
                    <CommandItem
                      key={device.id}
                      value={device.id}
                      onSelect={handleSelectDevice}
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4",
                          selectedDeviceId === device.id
                            ? "opacity-100"
                            : "opacity-0"
                        )}
                      />
                      <div className="flex flex-col">
                        <span>{device.device_name || "Unnamed Device"}</span>
                        <span className="text-xs text-muted-foreground">
                          {device.mac_address}
                        </span>
                      </div>
                    </CommandItem>
                  ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
  );
}
