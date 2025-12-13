"use client";

import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { DeviceSelector } from "@/components/device-selector";
import type { Device } from "@/types";

type ChatHeaderProps = {
  userName?: string;
  isConnected: boolean;
  isConnecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  selectedDevice?: Device | null;
  devices?: Device[];
  isLoadingDevices?: boolean;
  deviceError?: Error | null;
  onSelectDevice?: (device: Device) => void;
};

export function ChatHeader(props: ChatHeaderProps) {
  const { t } = useTranslation("chat");
  const {
    userName = "User",
    isConnected,
    isConnecting,
    onConnect,
    onDisconnect,
    selectedDevice,
    devices = [],
    isLoadingDevices = false,
    deviceError = null,
    onSelectDevice,
  } = props;

  return (
    <div className="flex-none border-b p-3 bg-card shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{t("chat_title")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("chat_welcome", { name: userName })}
            {selectedDevice && (
              <span className="ml-2 text-xs font-semibold bg-primary/10 text-primary px-2 py-1 rounded">
                {selectedDevice.device_name || selectedDevice.mac_address}
              </span>
            )}
          </p>
        </div>

        {/* Center spacer - empty */}
        <div className="flex-1" />

        {/* Device Selector + Button Group */}
        <div className="flex items-center gap-2">
          {/* Device Selector */}
          {onSelectDevice && (
            <div className="max-w-sm">
              <DeviceSelector
                devices={devices}
                selectedDeviceId={selectedDevice?.id}
                onSelectDevice={onSelectDevice}
                isLoading={isLoadingDevices}
                error={deviceError}
                disabled={isConnected}
              />
            </div>
          )}

          {/* Connection Status Indicator */}
          <div
            className={`w-3 h-3 rounded-full ${
              isConnected
                ? "bg-green-500"
                : isConnecting
                ? "bg-yellow-500"
                : "bg-red-500"
            }`}
            title={
              isConnected
                ? t("connection_status_connected")
                : isConnecting
                ? t("connecting")
                : t("connection_status_disconnected")
            }
          />

          {/* Connect/Disconnect Button */}
          <Button
            onClick={isConnected ? onDisconnect : onConnect}
            disabled={isConnecting}
            variant={isConnected ? "destructive" : "default"}
            size="sm"
          >
            {isConnecting
              ? t("connecting")
              : isConnected
              ? t("disconnect")
              : t("connect")}
          </Button>
        </div>
      </div>
    </div>
  );
}
