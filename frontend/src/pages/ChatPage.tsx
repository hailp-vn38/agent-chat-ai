"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useDeviceList } from "@/hooks";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import type { ChatServiceConfig } from "@/types/chat";
import type { Device } from "@/types";
import { ChatHeader } from "@/components/ChatHeader";
import { ChatErrorAlert } from "@/components/ChatErrorAlert";
import { ActivationDialog } from "@/components/ActivationDialog";
import { ChatInputArea } from "@/components/ChatInputArea";
import { ChatMessages } from "@/components/ChatMessages";
import { PageHead } from "@/components/PageHead";

/**
 * Generate a random UUID v4 for clientId
 */
function generateRandomClientId(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function ChatPage() {
  const { user } = useAuth();

  // Fetch devices once on mount
  const {
    data: deviceListData,
    isLoading: isLoadingDevices,
    error: deviceError,
  } = useDeviceList({
    page: 1,
    page_size: 100, // Fetch up to 100 devices
  });

  const devices = useMemo(() => deviceListData?.data || [], [deviceListData]);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const clientIdRef = useRef<string>(generateRandomClientId());

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const visualizerAnimationRef = useRef<number | null>(null);

  // Initialize chat service
  const {
    isConnected,
    isConnecting,
    isRecording,
    messages,
    error,
    activation,
    connect,
    disconnect,
    sendMessage,
    startRecording,
    stopRecording,
    clearError,
    clearActivation,
    audioFrequencyData,
  } = useChatWebSocket({
    config: {
      deviceId: selectedDevice?.mac_address || "web_test_client",
      deviceMac: selectedDevice?.mac_address || "00:11:22:33:44:55",
      deviceName: selectedDevice?.device_name || "Web Chat Client",
      clientId: clientIdRef.current,
      token: user?.id || "test-token",
      otaUrl: import.meta.env.VITE_OTA_URL,
    } as ChatServiceConfig,
  });

  // Log when messages array changes
  useEffect(() => {
    console.log(
      `[ChatPage] Messages state updated: ${messages.length} total`,
      messages
    );
  }, [messages]);

  // Draw audio visualizer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !audioFrequencyData) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = () => {
      // Clear canvas
      ctx.fillStyle = "#fafafa";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      if (!audioFrequencyData) return;

      const barWidth = (canvas.width / audioFrequencyData.length) * 2.5;
      let x = 0;

      for (let i = 0; i < audioFrequencyData.length; i++) {
        const barHeight = audioFrequencyData[i] / 2;

        // Gradient color from red to orange
        const hue = (1 - barHeight / 128) * 30; // 0-30 range (red to orange)
        ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

        x += barWidth + 1;
      }

      if (isRecording) {
        visualizerAnimationRef.current = requestAnimationFrame(draw);
      }
    };

    if (isRecording) {
      draw();
    } else {
      ctx.fillStyle = "#fafafa";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    return () => {
      if (visualizerAnimationRef.current) {
        cancelAnimationFrame(visualizerAnimationRef.current);
      }
    };
  }, [audioFrequencyData, isRecording]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!messagesEndRef.current) {
      return;
    }
    messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = (message: string) => {
    sendMessage(message);
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      try {
        await startRecording();
      } catch (err) {
        console.error("Failed to start recording:", err);
      }
    }
  };

  return (
    <>
      <PageHead
        title="chat:page.title"
        description="chat:page.description"
        translateTitle
        translateDescription
      />
      <div className="flex flex-col h-full min-h-0 overflow-hidden bg-background">
        {/* Header */}
        <ChatHeader
          userName={user?.name}
          isConnected={isConnected}
          isConnecting={isConnecting}
          onConnect={connect}
          onDisconnect={disconnect}
          selectedDevice={selectedDevice}
          devices={devices}
          isLoadingDevices={isLoadingDevices}
          deviceError={deviceError}
          onSelectDevice={setSelectedDevice}
        />

        {/* Error Alert */}
        <ChatErrorAlert error={error} onDismiss={clearError} />

        {/* Activation Dialog */}
        <ActivationDialog activation={activation} onDismiss={clearActivation} />

        {/* Messages Container - flex-1 scrollable only */}
        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2 bg-background">
          <ChatMessages messages={messages} isConnected={isConnected} />
          <div ref={messagesEndRef} aria-hidden />
        </div>

        {/* Audio Visualizer - flex-none
        {isRecording && (
          <div className="flex-none p-3 border-t bg-background">
            <canvas
              ref={canvasRef}
              width={800}
              height={64}
              className="w-full h-16 border border-border rounded-lg"
            />
          </div>
        )} */}

        {/* Input Area - flex-none */}
        <div className="flex-none border-t p-4 bg-card">
          <div className="flex justify-center">
            <div className="w-full lg:w-1/2">
              <ChatInputArea
                isConnected={isConnected}
                isRecording={isRecording}
                onSendMessage={handleSendMessage}
                onToggleRecording={handleToggleRecording}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default ChatPage;
