/**
 * Chat-related types for WebSocket messaging and audio streaming
 */

// Message type constants (using as const for type inference)
export const MESSAGE_TYPE = {
  HELLO: "hello",
  LISTEN: "listen",
  TTS: "tts",
  LLM: "llm",
  AUDIO: "audio",
  STT: "stt",
  MCP: "mcp",
} as const;

export type MessageType = (typeof MESSAGE_TYPE)[keyof typeof MESSAGE_TYPE];

// Connection status constants
export const CONNECTION_STATUS = {
  IDLE: "idle",
  CONNECTING: "connecting",
  CONNECTED: "connected",
  DISCONNECTED: "disconnected",
  ERROR: "error",
} as const;

export type ConnectionStatus =
  (typeof CONNECTION_STATUS)[keyof typeof CONNECTION_STATUS];

// Recording state constants
export const RECORDING_STATE = {
  IDLE: "idle",
  RECORDING: "recording",
  STOPPING: "stopping",
} as const;

export type RecordingState =
  (typeof RECORDING_STATE)[keyof typeof RECORDING_STATE];

export interface ChatServiceConfig {
  deviceId: string;
  deviceMac: string;
  deviceName: string;
  clientId: string;
  token: string;
  otaUrl: string;
  debugLogging?: boolean;
}

export interface ActivationData {
  message: string;
  code: string;
  challenge: string;
  timeout_ms: number;
}

export interface ChatMessage {
  id?: string;
  type: "user" | "server" | "stt" | "llm" | "tts";
  text: string;
  timestamp?: number;
  isError?: boolean;
}

export interface AudioPacket {
  data: Uint8Array;
  timestamp: number;
}

export interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

export interface HelloMessage extends WebSocketMessage {
  type: "hello";
  device_id: string;
  device_name: string;
  device_mac: string;
  token: string;
  features?: {
    mcp?: boolean;
  };
  session_id?: string;
}

export interface ListenMessage extends WebSocketMessage {
  type: "listen" | "speak";
  mode: "manual" | "auto" | "realtime";
  state: "start" | "stop" | "detect";
  text?: string;
  session_id?: string;
}

export interface LLMMessage extends WebSocketMessage {
  type: "llm";
  text: string;
}

export interface STTMessage extends WebSocketMessage {
  type: "stt";
  text: string;
}

export interface TTSMessage extends WebSocketMessage {
  type: "tts";
  state: "start" | "sentence_start" | "sentence_end" | "stop";
  text?: string;
}

export interface ChatServiceError extends Error {
  code?: string;
  recoverable?: boolean;
}

export interface ChatServiceCallbacks {
  onConnected?: () => void;
  onDisconnected?: () => void;
  onMessage?: (message: ChatMessage) => void;
  onActivation?: (activation: ActivationData) => void;
  onError?: (error: ChatServiceError) => void;
}
