/**
 * useChatWebSocket - React hook for WebSocket chat service
 * Manages service lifecycle, state sync, and error handling
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { ChatWebSocketService } from "@/services/chat-websocket.service";
import type {
  ChatServiceConfig,
  ChatServiceError,
  ChatMessage,
  ActivationData,
} from "@/types/chat";
import { RECORDING_STATE } from "@/types/chat";

export interface UseChatWebSocketReturn {
  // State
  isConnected: boolean;
  isConnecting: boolean;
  isRecording: boolean;
  messages: ChatMessage[];
  error: ChatServiceError | null;
  activation: ActivationData | null;

  // Methods
  connect: () => Promise<void>;
  disconnect: () => void;
  sendMessage: (text: string) => void;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  clearError: () => void;
  clearActivation: () => void;

  // Utilities
  audioFrequencyData: Uint8Array | null;
}

interface UseChatWebSocketOptions {
  config: ChatServiceConfig;
  autoConnect?: boolean;
}

type TimerId = ReturnType<typeof setInterval>;

export function useChatWebSocket(
  options: UseChatWebSocketOptions
): UseChatWebSocketReturn {
  const { config, autoConnect = false } = options;

  // Service instance
  const serviceRef = useRef<ChatWebSocketService | null>(null);

  // State
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<ChatServiceError | null>(null);
  const [audioFrequencyData, setAudioFrequencyData] =
    useState<Uint8Array | null>(null);
  const [activation, setActivation] = useState<ActivationData | null>(null);

  // Frequency data polling interval
  const frequencyDataIntervalRef = useRef<TimerId | null>(null);

  // Initialize service
  useEffect(() => {
    if (!serviceRef.current) {
      serviceRef.current = new ChatWebSocketService();

      // Setup callbacks
      serviceRef.current.setCallbacks({
        onConnected: () => {
          setIsConnected(true);
          setIsConnecting(false);
          setError(null);
        },
        onDisconnected: () => {
          setIsConnected(false);
          setIsConnecting(false);
          setIsRecording(false);
        },
        onMessage: (msg) => {
          console.log(
            `[Hook] 💬 Message callback - type: ${
              msg.type
            }, text: "${msg.text.substring(0, 50)}..."`
          );
          setMessages((prev) => [...prev, msg]);
        },
        onActivation: (activation) => {
          setActivation(activation);
          console.log(`[Hook] 🔐 Activation received: ${activation.code}`);
        },
        onError: (err) => {
          setError(err);
          console.error("Chat service error:", err);
        },
      });

      if (autoConnect) {
        setIsConnecting(true);
        serviceRef.current.connect();
      }
    }

    serviceRef.current?.setConfig(config);

    return () => {
      // Cleanup on unmount
      if (frequencyDataIntervalRef.current) {
        clearInterval(frequencyDataIntervalRef.current);
      }
    };
  }, [config, autoConnect]);

  // Setup frequency data polling when recording
  useEffect(() => {
    if (isRecording && serviceRef.current) {
      console.log("[Hook] 🎙️ Starting frequency data polling");
      frequencyDataIntervalRef.current = setInterval(() => {
        const data = serviceRef.current?.getAudioFrequencyData();
        if (data) {
          setAudioFrequencyData(data);
          console.log(`[Hook] 📊 Frequency data updated: ${data.length} bins`);
        }
      }, 50); // Update 20 times per second

      return () => {
        if (frequencyDataIntervalRef.current) {
          clearInterval(frequencyDataIntervalRef.current);
          frequencyDataIntervalRef.current = null;
          console.log("[Hook] 🛑 Frequency data polling stopped");
        }
      };
    }
  }, [isRecording]);

  // Track recording state from service
  useEffect(() => {
    const checkRecordingState = setInterval(() => {
      if (serviceRef.current) {
        const state = serviceRef.current.getRecordingState();
        setIsRecording(state === RECORDING_STATE.RECORDING);
      }
    }, 100);

    return () => clearInterval(checkRecordingState);
  }, []);

  // Methods
  const connect = useCallback(async () => {
    if (!serviceRef.current) {
      return;
    }

    try {
      setIsConnecting(true);
      setError(null);
      await serviceRef.current.connect();
    } catch (err) {
      const error =
        err instanceof Error
          ? (err as ChatServiceError)
          : new Error(String(err));
      setError(error as ChatServiceError);
      setIsConnecting(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (serviceRef.current) {
      serviceRef.current.disconnect();
      setIsConnected(false);
      setIsRecording(false);
    }
  }, []);

  const sendMessage = useCallback(
    (text: string) => {
      if (!serviceRef.current || !isConnected) {
        setError({
          ...new Error("Not connected"),
          code: "NOT_CONNECTED",
          recoverable: true,
        } as ChatServiceError);
        return;
      }

      try {
        // Add user message to local state
        setMessages((prev) => [
          ...prev,
          {
            type: "user",
            text,
            timestamp: Date.now(),
          },
        ]);

        // Send via service
        serviceRef.current.sendMessage(text);
      } catch (err) {
        const error =
          err instanceof Error
            ? (err as ChatServiceError)
            : new Error(String(err));
        setError(error as ChatServiceError);
      }
    },
    [isConnected]
  );

  const startRecording = useCallback(async () => {
    if (!serviceRef.current || !isConnected) {
      setError({
        ...new Error("Not connected"),
        code: "NOT_CONNECTED",
        recoverable: true,
      } as ChatServiceError);
      return;
    }

    try {
      setError(null);
      await serviceRef.current.startRecording();
      setIsRecording(true);
    } catch (err) {
      const error =
        err instanceof Error
          ? (err as ChatServiceError)
          : new Error(String(err));
      setError(error as ChatServiceError);
      setIsRecording(false);
    }
  }, [isConnected]);

  const stopRecording = useCallback(() => {
    if (serviceRef.current) {
      serviceRef.current.stopRecording();
      setIsRecording(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const clearActivation = useCallback(() => {
    setActivation(null);
  }, []);

  return {
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
  };
}
