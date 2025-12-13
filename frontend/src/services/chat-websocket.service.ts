/**
 * ChatWebSocketService - Core WebSocket service for real-time chat
 * Manages WebSocket connection, Opus codec, audio streaming, and message routing
 *
 * Audio Playback Architecture (Hybrid Decode Loop):
 * 1. WebSocket packets arrive → handleAudioPacket() queues to pendingPackets (fast path)
 * 2. decodePacketsLoop() [async] continuously decodes from pendingPackets → activeQueue
 * 3. startAudioPlayback() [event-driven] reads pre-decoded samples from activeQueue
 *
 * Benefits:
 * - Decode loop is non-blocking (separate async task)
 * - Playback is smooth (reads pre-decoded data)
 * - Better error recovery (failed packets retried)
 * - Stable buffer management (prevents underruns)
 *
 * Based on test_page.html implementation, refactored for TypeScript and reusability
 */

import { OpusEncoder, OpusDecoder, convertFloat32ToInt16 } from "./opus-codec";
import { AudioBuffer } from "./audio-buffer";
import type {
  ChatServiceConfig,
  ChatServiceError,
  ChatServiceCallbacks,
  ActivationData,
  HelloMessage,
  ListenMessage,
} from "@/types/chat";
import { CONNECTION_STATUS, RECORDING_STATE } from "@/types/chat";

const SAMPLE_RATE = 16000;
const CHANNELS = 1;
const FRAME_SIZE = 960; // 60ms @ 16kHz

// Hybrid Decode Loop Constants
const MIN_BUFFER_SAMPLES = Math.floor(SAMPLE_RATE * 0.3); // 300ms buffering
const MAX_PENDING_PACKETS = 50; // ~2.5MB max queue
const MAX_DECODE_BATCH = 5; // Packets per loop iteration
const DECODE_LOOP_INTERVAL = 10; // ms between iterations
const TTS_GAP_GRACE_MS = 1500; // Grace period while waiting for next TTS chunk

// Type for pending Opus packets
interface PendingPacket {
  data: Uint8Array;
  timestamp: number;
  attempts: number;
}

interface McpPayload {
  method?: string;
  id?: number | string;
  params?: Record<string, unknown>;
  [key: string]: unknown;
}

const MCP_DEVICE_TOOLS = [
  {
    name: "self.get_device_status",
    description:
      "Provides the real-time information of the device, including the current status of the audio speaker, screen, battery, network, etc.\nUse this tool for: \n1. Answering questions about current condition (e.g. what is the current volume of the audio speaker?)\n2. As the first step to control the device (e.g. turn up / down the volume of the audio speaker, etc.)",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "self.audio_speaker.set_volume",
    description:
      "Set the volume of the audio speaker. If the current volume is unknown, you must call `self.get_device_status` tool first and then call this tool.",
    inputSchema: {
      type: "object",
      properties: {
        volume: {
          type: "integer",
          minimum: 0,
          maximum: 100,
        },
      },
      required: ["volume"],
    },
  },
  {
    name: "self.screen.set_brightness",
    description: "Set the brightness of the screen.",
    inputSchema: {
      type: "object",
      properties: {
        brightness: {
          type: "integer",
          minimum: 0,
          maximum: 100,
        },
      },
      required: ["brightness"],
    },
  },
  {
    name: "self.screen.set_theme",
    description:
      "Set the theme of the screen. The theme can be 'light' or 'dark'.",
    inputSchema: {
      type: "object",
      properties: { theme: { type: "string" } },
      required: ["theme"],
    },
  },
] as const;

export class ChatWebSocketService {
  private ws: WebSocket | null = null;
  private config: ChatServiceConfig | null = null;
  private callbacks: ChatServiceCallbacks = {};

  // Connection state
  private connectionStatus: (typeof CONNECTION_STATUS)[keyof typeof CONNECTION_STATUS] =
    CONNECTION_STATUS.IDLE;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelays = [1000, 2000, 5000, 10000]; // Exponential backoff in ms
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private helloTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private userInitiatedDisconnect = false; // Track if user manually disconnected
  private helloAcknowledged = false;
  private sessionId: string = "";
  private pendingHelloResolvers: Array<(value: boolean) => void> = [];
  private debugLoggingEnabled = false;

  // Recording state
  private recordingState: (typeof RECORDING_STATE)[keyof typeof RECORDING_STATE] =
    RECORDING_STATE.IDLE;
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private mediaSource: MediaStreamAudioSourceNode | null = null;
  private audioProcessor: ScriptProcessorNode | AudioWorkletNode | null = null;
  private analyser: AnalyserNode | null = null;

  // Opus codec
  private opusEncoder: OpusEncoder | null = null;
  private opusDecoder: OpusDecoder | null = null;

  // Audio buffering
  private pcmBuffer = new Int16Array();
  private audioBufferQueue = new AudioBuffer();
  private isPlayingAudio = false;

  // Hybrid Decode Loop
  private pendingPackets: PendingPacket[] = [];
  private activeQueue: Float32Array = new Float32Array();
  private isDecodeLoopActive = false;
  private decodeLoopPromise: Promise<void> | null = null;
  private endOfStream = false;
  private isAudioStreaming = false;

  // Playback state tracking
  private playbackTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private lastPlaybackWarningTime = 0;
  private consecutiveUnderruns = 0;
  private ttsStreamActive = false;
  private lastAudioPacketTime = 0;
  private lastTtsEventTime = 0;

  constructor() {
    this.ensureAudioContext();
  }

  private logDebug(...args: unknown[]): void {
    if (!this.debugLoggingEnabled) {
      return;
    }
    console.debug(...args);
  }

  /**
   * Ensure AudioContext is initialized
   */
  private ensureAudioContext(): void {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext ||
        (window as any).webkitAudioContext)({
        sampleRate: SAMPLE_RATE,
        latencyHint: "interactive",
      });
    }
  }

  /**
   * Set configuration and callbacks
   */
  setConfig(config: ChatServiceConfig): void {
    this.config = config;
    this.debugLoggingEnabled = Boolean(config.debugLogging);
  }

  setCallbacks(callbacks: ChatServiceCallbacks): void {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }

  /**
   * Connect to WebSocket server via OTA negotiation
   */
  async connect(): Promise<void> {
    try {
      if (!this.config) {
        throw this.createError("Configuration not set", "NO_CONFIG", false);
      }

      // Reset user-initiated disconnect flag when connecting
      this.userInitiatedDisconnect = false;
      this.helloAcknowledged = false;
      this.sessionId = "";
      this.pendingHelloResolvers = [];

      this.setConnectionStatus(CONNECTION_STATUS.CONNECTING);

      // Fetch WebSocket URL from OTA server
      const { wsUrl, activation } = await this.fetchOtaWebSocketUrl();

      // Trigger activation callback if present
      if (activation) {
        this.callbacks.onActivation?.(activation);
        // Block WebSocket connection when activation is required
        this.setConnectionStatus(CONNECTION_STATUS.DISCONNECTED);
        this.callbacks.onDisconnected?.();
        return;
      }

      // Create WebSocket connection
      this.ws = new WebSocket(wsUrl);
      this.ws.binaryType = "arraybuffer";

      // Setup WebSocket handlers
      this.ws.onopen = () => this.handleWebSocketOpen();
      this.ws.onmessage = (event) => this.handleWebSocketMessage(event);
      this.ws.onclose = (event) =>
        this.handleWebSocketClose(event as CloseEvent);
      this.ws.onerror = (event) => this.handleWebSocketError(event);
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    try {
      // Mark user-initiated disconnect
      this.userInitiatedDisconnect = true;
      this.helloAcknowledged = false;
      this.sessionId = "";

      // Cancel hello timeout
      this.cancelHelloTimeout();

      // Stop recording if active
      if (this.recordingState === RECORDING_STATE.RECORDING) {
        this.stopRecording();
      }

      this.resetPlaybackState();

      // Close WebSocket
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.close();
      }

      // Cancel reconnect timer
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }

      this.setConnectionStatus(CONNECTION_STATUS.DISCONNECTED);
      this.reconnectAttempts = 0;
      this.resolveHelloWaiters(false);
    } catch (error) {
      console.error("Error during disconnect:", error);
    }
  }

  /**
   * Send text message
   */
  sendMessage(text: string): void {
    try {
      this.ensureHandshakeReady("send messages");

      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        throw this.createError(
          "WebSocket not connected",
          "WS_NOT_CONNECTED",
          false
        );
      }

      const message: ListenMessage = {
        type: "listen",
        mode: "manual",
        state: "detect",
        text,
        session_id: this.sessionId,
      };

      this.ws.send(JSON.stringify(message));
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  /**
   * Start voice recording
   */
  async startRecording(): Promise<void> {
    try {
      const acked = await this.waitForHelloAck();
      if (!acked) {
        console.warn(
          "[WS] Hello handshake not acknowledged before recording, proceeding anyway"
        );
      }

      if (this.recordingState === RECORDING_STATE.RECORDING) {
        console.warn("Already recording");
        return;
      }

      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        throw this.createError(
          "WebSocket not connected",
          "WS_NOT_CONNECTED",
          false
        );
      }

      // Initialize Opus encoder if needed
      if (!this.opusEncoder) {
        this.opusEncoder = new OpusEncoder();
        const success = await this.opusEncoder.init();
        if (!success) {
          throw this.createError(
            "Failed to initialize Opus encoder",
            "OPUS_INIT_FAILED",
            true
          );
        }
      }

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: SAMPLE_RATE,
          channelCount: CHANNELS,
        },
      });

      this.mediaStream = stream;
      this.ensureAudioContext();

      if (this.audioContext?.state === "suspended") {
        try {
          await this.audioContext.resume();
          this.logDebug("[Recording] ✅ AudioContext resumed for recording");
        } catch (error) {
          console.warn(
            "[Recording] ⚠️ Failed to resume AudioContext before recording",
            error
          );
        }
      }

      this.mediaSource = this.audioContext!.createMediaStreamSource(stream);

      // Create analyser for frequency visualization
      if (!this.analyser) {
        this.analyser = this.audioContext!.createAnalyser();
        this.analyser.fftSize = 2048;
      }
      this.mediaSource.connect(this.analyser);

      // Create AudioWorkletNode for PCM capture (replaces deprecated ScriptProcessorNode)
      try {
        await this.audioContext!.audioWorklet.addModule(
          "/audio-processor-worklet.js"
        );
        this.audioProcessor = new AudioWorkletNode(
          this.audioContext!,
          "pcm-processor-worklet"
        );

        this.mediaSource.connect(this.audioProcessor);

        // Create gain node to mute the output (we don't want to hear recording input)
        const gain = this.audioContext!.createGain();
        gain.gain.setValueAtTime(0, this.audioContext!.currentTime); // Mute (0 volume)

        // CRITICAL: Connect audio chain to destination to force Web Audio engine to pull data
        this.audioProcessor.connect(gain);
        gain.connect(this.audioContext!.destination);

        // ALSO connect analyser AFTER worklet to force continuous audio pull through worklet
        // This ensures process() callback is invoked
        this.audioProcessor.connect(this.analyser);

        this.logDebug(
          "[Recording] ✅ AudioWorkletNode connected with gain control (muted)"
        );
        this.logDebug(
          "[Recording] ✅ Analyser connected to force continuous audio pull"
        );

        // Handle messages from AudioWorklet
        this.audioProcessor.port.onmessage = (e) => {
          this.logDebug(
            `[AudioWorklet] 📨 Message received - type=${e.data.type}, buffer=${
              e.data.buffer?.length || 0
            }`
          );
          if (e.data.type === "buffer") {
            this.processAudioWorkletBuffer(e.data.buffer);
          } else {
            console.warn(
              `[AudioWorklet] ⚠️ Unknown message type: ${e.data.type}`
            );
          }
        };
      } catch (error) {
        console.warn(
          "AudioWorkletNode not supported, falling back to ScriptProcessorNode:",
          error
        );
        // Fallback for older browsers
        const scriptProcessor = this.audioContext!.createScriptProcessor(
          4096,
          CHANNELS,
          CHANNELS
        );
        this.audioProcessor = scriptProcessor;
        this.mediaSource.connect(scriptProcessor);
        scriptProcessor.connect(this.audioContext!.destination);
        scriptProcessor.onaudioprocess = (e) => this.processPCMData(e);
      }

      // Reset buffer
      this.pcmBuffer = new Int16Array();
      this.recordingState = RECORDING_STATE.RECORDING;
      this.isAudioStreaming = false;

      // Send recording start message to server before streaming audio
      const startMessage: ListenMessage = {
        type: "listen",
        state: "start",
        mode: "manual",
        session_id: this.sessionId,
      };

      this.ws.send(JSON.stringify(startMessage));

      // Now enable streaming (mirrors legacy flow)
      this.isAudioStreaming = true;
      this.controlAudioProcessor("start");

      // Give worklet time to start processing audio
      // (process() callback timing can vary between browsers)
      await this.sleep(50);

      this.encodeAvailableFrames();
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  /**
   * Stop voice recording
   */
  stopRecording(): void {
    try {
      if (this.recordingState !== RECORDING_STATE.RECORDING) {
        console.warn("Not recording");
        return;
      }

      this.recordingState = RECORDING_STATE.STOPPING;
      this.isAudioStreaming = false;
      this.stopActiveAudioProcessor();
      this.encodeAvailableFrames(true);

      // Encode and send remaining PCM data
      if (this.pcmBuffer.length > 0 && this.opusEncoder) {
        const padded = new Int16Array(FRAME_SIZE);
        padded.set(this.pcmBuffer);
        const encoded = this.opusEncoder.encode(padded);
        if (encoded && this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(encoded.buffer);
        }
        this.pcmBuffer = new Int16Array();
      }

      // Send end-of-stream marker (empty Opus packet)
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(new Uint8Array(0).buffer);
      }

      // Send stop message
      const stopMessage: ListenMessage = {
        type: "listen",
        mode: "manual",
        state: "stop",
        session_id: this.sessionId,
      };
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(stopMessage));
      }

      // Cleanup audio resources
      this.cleanupRecordingNodes();
      this.finalizeRecordingState();
    } catch (error) {
      console.error("Error stopping recording:", error);
      this.cleanupRecordingNodes();
      this.finalizeRecordingState();
    }
  }

  private stopActiveAudioProcessor(): void {
    if (this.audioProcessor instanceof AudioWorkletNode) {
      this.controlAudioProcessor("stop");
    }
  }

  private cleanupRecordingNodes(): void {
    if (this.audioProcessor) {
      try {
        this.audioProcessor.disconnect();
      } catch {
        /* ignore disconnect errors */
      }

      if ("onaudioprocess" in this.audioProcessor) {
        (this.audioProcessor as ScriptProcessorNode).onaudioprocess = null;
      }

      if (this.audioProcessor instanceof AudioWorkletNode) {
        this.audioProcessor.port.onmessage = null;
      }

      this.audioProcessor = null;
    }

    if (this.mediaSource) {
      try {
        this.mediaSource.disconnect();
      } catch {
        /* ignore disconnect errors */
      }
      this.mediaSource = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
  }

  private finalizeRecordingState(): void {
    this.isAudioStreaming = false;
    this.recordingState = RECORDING_STATE.IDLE;
    this.pcmBuffer = new Int16Array();
  }

  private resetPlaybackState(): void {
    if (this.playbackTimeoutId) {
      clearTimeout(this.playbackTimeoutId);
      this.playbackTimeoutId = null;
    }

    this.isPlayingAudio = false;
    this.consecutiveUnderruns = 0;
    this.lastPlaybackWarningTime = 0;
    this.endOfStream = true;
    this.pendingPackets = [];
    this.activeQueue = new Float32Array();
    this.audioBufferQueue.clear();
    this.ttsStreamActive = false;
    this.lastAudioPacketTime = 0;
    this.lastTtsEventTime = 0;
  }

  private abortRecordingDueToDisconnect(): void {
    if (this.recordingState === RECORDING_STATE.IDLE) {
      return;
    }

    this.stopActiveAudioProcessor();
    this.cleanupRecordingNodes();
    this.finalizeRecordingState();
  }

  /**
   * Get connection status
   */
  getConnectionStatus(): string {
    return this.connectionStatus;
  }

  /**
   * Get recording state
   */
  getRecordingState(): string {
    return this.recordingState;
  }

  /**
   * Get audio frequency data for visualizer
   */
  getAudioFrequencyData(): Uint8Array | null {
    if (!this.analyser || this.recordingState !== RECORDING_STATE.RECORDING) {
      return null;
    }

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);
    return dataArray;
  }

  /**
   * Destroy service and cleanup resources
   */
  destroy(): void {
    this.disconnect();

    // Clear playback timeout
    if (this.playbackTimeoutId) {
      clearTimeout(this.playbackTimeoutId);
      this.playbackTimeoutId = null;
    }

    // Stop decode loop
    this.stopDecodeLoop().catch(() => {
      /* ignore */
    });

    if (this.opusEncoder) {
      this.opusEncoder.destroy();
      this.opusEncoder = null;
    }

    if (this.opusDecoder) {
      this.opusDecoder.destroy();
      this.opusDecoder = null;
    }

    if (this.audioContext) {
      this.audioContext.close().catch(() => {
        /* ignore */
      });
      this.audioContext = null;
    }

    this.audioBufferQueue.clear();
    this.pendingPackets = [];
    this.activeQueue = new Float32Array();
    this.consecutiveUnderruns = 0;
    this.lastPlaybackWarningTime = 0;
  }

  // ============ PRIVATE METHODS ============

  /**
   * Sleep/delay utility for async loops
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Check buffer health and log warnings
   */
  private checkBufferHealth(): void {
    const pendingKB = (this.pendingPackets.length * 50) / 1024;
    const activeSec = this.activeQueue.length / SAMPLE_RATE;

    if (pendingKB > 500) {
      console.warn(
        `[Audio] Pending queue overloaded: ${pendingKB.toFixed(1)}KB`
      );
    }
    if (activeSec > 3) {
      console.warn(`[Audio] Active queue too large: ${activeSec.toFixed(1)}s`);
    }
  }

  /**
   * Convert Int16 array to Float32 (normalized to [-1, 1])
   */
  private convertInt16ToFloat32(int16Data: Int16Array): Float32Array {
    const float32 = new Float32Array(int16Data.length);
    for (let i = 0; i < int16Data.length; i++) {
      float32[i] = int16Data[i] / (int16Data[i] < 0 ? 0x8000 : 0x7fff);
    }
    return float32;
  }

  private async fetchOtaWebSocketUrl(): Promise<{
    wsUrl: string;
    activation?: ActivationData;
  }> {
    if (!this.config) {
      throw this.createError("Configuration not set", "NO_CONFIG", false);
    }

    try {
      const response = await fetch(this.config.otaUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Device-Id": this.config.deviceId,
          "Client-Id": this.config.clientId,
        },
        body: JSON.stringify({
          version: 0,
          uuid: "",
          application: {
            name: "home-chat-bot-web",
            version: "1.0.0",
          },
          board: {
            mac: this.config.deviceMac,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(
          `OTA fetch failed: ${response.status} ${response.statusText}`
        );
      }

      const data = await response.json();

      if (!data.websocket || !data.websocket.url) {
        throw new Error("Invalid OTA response: missing websocket.url");
      }

      const wsUrl = new URL(data.websocket.url);

      // Add auth token if provided
      if (data.websocket.token) {
        const token = data.websocket.token.startsWith("Bearer ")
          ? data.websocket.token
          : `Bearer ${data.websocket.token}`;
        wsUrl.searchParams.append("authorization", token);
      }

      // Add device identifiers
      wsUrl.searchParams.append("device-id", this.config.deviceId);
      wsUrl.searchParams.append("client-id", this.config.clientId);

      // Extract activation data if present
      const activation = data.activation
        ? {
            message: data.activation.message,
            code: data.activation.code,
            challenge: data.activation.challenge,
            timeout_ms: data.activation.timeout_ms,
          }
        : undefined;

      return {
        wsUrl: wsUrl.toString(),
        activation,
      };
    } catch (error) {
      throw this.createError(
        `OTA fetch error: ${
          error instanceof Error ? error.message : String(error)
        }`,
        "OTA_FETCH_FAILED",
        true
      );
    }
  }

  private async handleWebSocketOpen(): Promise<void> {
    this.setConnectionStatus(CONNECTION_STATUS.CONNECTING);
    this.reconnectAttempts = 0;

    try {
      // Initialize Opus decoder early (before decode loop starts)
      if (!this.opusDecoder) {
        this.opusDecoder = new OpusDecoder();
        const success = await this.opusDecoder.init();
        if (!success) {
          console.warn(
            "[WS] Failed to initialize decoder during open, will retry on playback"
          );
          this.opusDecoder = null;
        } else {
          this.logDebug("[WS] ✅ Opus decoder initialized successfully");
        }
      }

      // Start decode loop
      this.startDecodeLoop();

      // Send hello handshake
      this.sendHelloMessage();
    } catch (error) {
      console.error("[WS] Error in handleWebSocketOpen:", error);
      this.handleError(error as Error);
    }
  }

  private sendHelloMessage(): void {
    if (!this.ws || !this.config) {
      return;
    }

    const hello: HelloMessage = {
      type: "hello",
      device_id: this.config.deviceId,
      device_name: this.config.deviceName,
      device_mac: this.config.deviceMac,
      token: this.config.token,
      features: { mcp: true },
    };

    try {
      this.ws.send(JSON.stringify(hello));
      this.logDebug(
        "[WS] 👋 Hello message sent, waiting for acknowledgement..."
      );

      // Start hello timeout - if no ack in 10s, disconnect
      this.startHelloTimeout();
    } catch (error) {
      console.error("Failed to send hello message:", error);
    }
  }

  private handleWebSocketMessage(event: MessageEvent): void {
    try {
      if (typeof event.data === "string") {
        // Text message
        const message = JSON.parse(event.data);
        this.logDebug(
          `[WS] 📨 Text message received: type=${message.type as string}`
        );
        this.routeTextMessage(message);
      } else if (event.data instanceof ArrayBuffer) {
        // Binary audio data
        const packet = new Uint8Array(event.data);
        this.logDebug(`[WS] 🔊 Audio packet received: ${packet.length} bytes`);
        this.handleAudioPacket(packet);
      }
    } catch (error) {
      console.error("[WS] ❌ Error handling WebSocket message:", error);
    }
  }

  private routeTextMessage(message: Record<string, unknown>): void {
    const type = message.type as string;

    // Log all non-audio messages for debugging (audio packets are binary, don't log)
    if (type !== "audio") {
      this.logDebug(`[WS] Message received - type: ${type}`, message);
    }

    switch (type) {
      case "error":
        {
          const errorMessage =
            (message.message as string) || "Unknown error from server";
          this.logDebug(`[WS] ❌ Server error: ${errorMessage}`);
          const error = this.createError(
            `Server error: ${errorMessage}`,
            "SERVER_ERROR",
            true
          );
          this.handleError(error);
          // Close WebSocket after server error
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.close(1008, "Server error");
          }
        }
        break;

      case "hello":
        this.logDebug("[WS] ✅ Server handshake received");
        this.handleHelloAcknowledgement(message);
        break;

      case "llm":
        {
          // LLM Response - Display on UI
          const llmText = (message.text as string) || "";
          this.logDebug(
            `[LLM] Response received: "${llmText.substring(0, 50)}..."`
          );
          this.callbacks.onMessage?.({
            type: "server",
            text: llmText,
          });
        }
        break;

      case "stt":
        {
          // Speech-to-Text Recognition Result - Display as user message (right side)
          const sttText = (message.text as string) || "";
          this.logDebug(`[STT] Recognized: "${sttText}"`);
          this.callbacks.onMessage?.({
            type: "stt",
            text: sttText,
          });
        }
        break;

      case "tts":
        {
          // TTS Control Message - Display audio text on UI when available
          const ttsState = (message.state as string) || "";
          const ttsText = (message.text as string) || "";

          this.logDebug(
            `[TTS] State: ${ttsState}${ttsText ? ` - Text: "${ttsText}"` : ""}`
          );

          // Only display if there's actual text content
          if (ttsText && ttsState === "sentence_start") {
            this.callbacks.onMessage?.({
              type: "tts",
              text: ttsText,
            });
          }
          this.handleTtsState(ttsState);
        }
        break;

      case "mcp":
        this.handleMcpMessage(message);
        break;

      default:
        this.logDebug(`[WS] ⚠️ Unknown message type: ${type}`);
    }
  }

  private handleMcpMessage(message: Record<string, unknown>): void {
    const payload = message.payload as McpPayload | undefined;

    if (!payload) {
      console.warn("[MCP] ⚠️ Received MCP message without payload", message);
      return;
    }

    const method = typeof payload.method === "string" ? payload.method : "";
    this.logDebug(`[MCP] 📨 Payload received - method=${method || "unknown"}`);

    switch (method) {
      case "tools/list":
        this.respondToMcpToolsList(payload);
        break;
      case "tools/call":
        this.respondToMcpToolsCall(payload);
        break;
      default:
        console.warn(
          `[MCP] ⚠️ Unhandled MCP method: ${method || "unknown"}`,
          payload
        );
    }
  }

  private respondToMcpToolsList(payload: McpPayload): void {
    this.sendMcpResponse({
      jsonrpc: "2.0",
      id: payload.id ?? null,
      result: {
        tools: MCP_DEVICE_TOOLS,
      },
    });
    this.logDebug("[MCP] ✅ Responded to tools/list request");
  }

  private respondToMcpToolsCall(payload: McpPayload): void {
    const params = (payload.params as Record<string, unknown>) || {};
    const toolName =
      (params.name as string) || (params.tool as string) || "unknown";

    this.sendMcpResponse({
      jsonrpc: "2.0",
      id: payload.id ?? null,
      result: {
        content: [
          {
            type: "text",
            text: "true",
          },
        ],
        isError: false,
      },
    });
    this.logDebug(`[MCP] ✅ tools/call acknowledged for tool=${toolName}`);
  }

  private sendMcpResponse(payload: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn("[MCP] ❌ Cannot send MCP response, WebSocket not ready");
      return;
    }

    const response = {
      session_id: this.sessionId,
      type: "mcp",
      payload,
    };

    try {
      this.ws.send(JSON.stringify(response));
    } catch (error) {
      console.error("[MCP] ❌ Failed to send MCP response:", error);
    }
  }

  private handleHelloAcknowledgement(message: Record<string, unknown>): void {
    if (this.helloAcknowledged) {
      return;
    }

    // Cancel hello timeout since we got acknowledgement
    this.cancelHelloTimeout();

    this.helloAcknowledged = true;
    this.sessionId = (message.session_id as string) || "";
    const sessionId = this.sessionId || "unknown";
    this.logDebug(`[WS] 🤝 Hello ACK session=${sessionId}`);

    this.setConnectionStatus(CONNECTION_STATUS.CONNECTED);
    this.callbacks.onConnected?.();
    this.resolveHelloWaiters(true);
  }

  private handleAudioPacket(packet: Uint8Array): void {
    if (packet.length === 0) {
      // End-of-stream marker
      this.endOfStream = true;
      this.ttsStreamActive = false;
      this.lastAudioPacketTime = Date.now();
      this.lastTtsEventTime = this.lastAudioPacketTime;
      this.logDebug("[Audio] Stream ended (EOS)");
      return;
    }

    this.endOfStream = false;
    this.ttsStreamActive = true;
    this.lastAudioPacketTime = Date.now();
    this.lastTtsEventTime = Math.max(
      this.lastTtsEventTime,
      this.lastAudioPacketTime
    );

    // Queue packet for background decoding (non-blocking)
    if (this.pendingPackets.length < MAX_PENDING_PACKETS) {
      this.pendingPackets.push({
        data: packet,
        timestamp: Date.now(),
        attempts: 0,
      });
    } else {
      console.warn("[Audio] Pending queue full, dropping packet");
    }

    // Start playback if ready, but don't wait (fire and forget)
    if (!this.isPlayingAudio && this.activeQueue.length >= MIN_BUFFER_SAMPLES) {
      // Start playback without awaiting
      this.startAudioPlayback().catch((error) => {
        console.error("[Audio] Playback error:", error);
      });
    }
  }

  private handleTtsState(state: string): void {
    if (!state) {
      return;
    }

    if (state === "stop") {
      this.handleTtsStop();
      return;
    }

    this.ttsStreamActive = true;
    this.lastTtsEventTime = Date.now();
    this.endOfStream = false;
  }

  private handleTtsStop(): void {
    this.ttsStreamActive = false;
    this.lastTtsEventTime = Date.now();
    this.logDebug("[Audio] TTS stop received, marking end of stream");
    this.endOfStream = true;

    if (this.pendingPackets.length === 0 && this.activeQueue.length === 0) {
      this.resetPlaybackState();
    }
  }

  private shouldSuppressUnderrunWarning(): boolean {
    if (!this.ttsStreamActive) {
      return false;
    }

    const lastActivity = Math.max(
      this.lastAudioPacketTime,
      this.lastTtsEventTime
    );

    if (lastActivity === 0) {
      return false;
    }

    return Date.now() - lastActivity < TTS_GAP_GRACE_MS;
  }

  private async startAudioPlayback(): Promise<void> {
    if (this.isPlayingAudio) {
      return;
    }

    this.isPlayingAudio = true;
    this.consecutiveUnderruns = 0;

    try {
      // Ensure AudioContext is initialized and resumed
      this.ensureAudioContext();

      if (!this.audioContext) {
        throw this.createError(
          "AudioContext not available",
          "AUDIO_CONTEXT_UNAVAILABLE",
          true
        );
      }

      // Resume AudioContext if suspended (required by modern browsers)
      if (this.audioContext.state === "suspended") {
        this.logDebug("[Audio] AudioContext suspended, attempting resume...");
        await this.audioContext.resume();
        this.logDebug(
          `[Audio] AudioContext resumed: ${this.audioContext.state}`
        );
      }

      // Initialize decoder if needed (for backward compat)
      if (!this.opusDecoder) {
        this.logDebug("[Audio] Decoder not ready, initializing now...");
        this.opusDecoder = new OpusDecoder();
        const success = await this.opusDecoder.init();
        if (!success) {
          throw this.createError(
            "Failed to initialize Opus decoder",
            "OPUS_DECODE_INIT_FAILED",
            true
          );
        }
      }

      // Double-check decoder is actually initialized
      if (!this.opusDecoder.isInitialized()) {
        throw this.createError(
          "Opus decoder failed to initialize properly",
          "OPUS_DECODER_NOT_READY",
          true
        );
      }

      this.logDebug("[Audio] ✅ Playback initialized, starting audio loop");

      // Playback loop - plays continuously without blocking
      this.playNextAudioBuffer();
    } catch (error) {
      this.handleError(error as Error);
      this.isPlayingAudio = false;
    }
  }

  /**
   * Play next audio buffer from queue (event-driven, non-blocking)
   * Implements exponential backoff to prevent CPU spinning when buffer is empty
   */
  private playNextAudioBuffer(backoffMs: number = 10): void {
    // Clear previous timeout if any
    if (this.playbackTimeoutId) {
      clearTimeout(this.playbackTimeoutId);
      this.playbackTimeoutId = null;
    }

    if (!this.isPlayingAudio) {
      this.logDebug("[Audio] Playback stopped");
      return;
    }

    try {
      // Check if we have enough samples to play
      if (this.activeQueue.length < MIN_BUFFER_SAMPLES && !this.endOfStream) {
        // Not enough data yet, wait with exponential backoff
        this.consecutiveUnderruns++;
        const suppressUnderrun = this.shouldSuppressUnderrunWarning();
        const now = Date.now();

        if (suppressUnderrun) {
          this.logDebug(
            `[Audio] ⏳ Waiting for next TTS chunk (${this.activeQueue.length}/${MIN_BUFFER_SAMPLES} samples)`
          );
        } else if (now - this.lastPlaybackWarningTime > 5000) {
          console.warn(
            `[Audio] ⏸️ Buffer underrun (${this.activeQueue.length}/${MIN_BUFFER_SAMPLES} samples). Queue: ${this.pendingPackets.length} packets pending. Backoff: ${backoffMs}ms`
          );
          this.lastPlaybackWarningTime = now;
        }

        // Exponential backoff: 10ms → 50ms → 100ms → 200ms (capped at 500ms)
        const waitMs = suppressUnderrun
          ? Math.min(Math.max(backoffMs, 20), 80)
          : backoffMs;
        const nextBackoff = suppressUnderrun
          ? waitMs
          : Math.min(backoffMs * 2, 500);

        this.playbackTimeoutId = setTimeout(() => {
          this.playNextAudioBuffer(nextBackoff);
        }, waitMs);

        return;
      }

      // Reset underrun counter and backoff when we have data
      if (this.consecutiveUnderruns > 0) {
        this.logDebug("[Audio] ✅ Buffer recovered, resuming playback");
        this.consecutiveUnderruns = 0;
      }

      // No more samples and stream ended
      if (this.activeQueue.length === 0) {
        this.logDebug("[Audio] 🏁 Playback complete (EOS reached)");
        this.isPlayingAudio = false;
        return;
      }

      // Prepare audio samples
      const sampleCount = Math.min(
        this.activeQueue.length,
        this.audioContext!.sampleRate
      );

      const samples = this.activeQueue.slice(0, sampleCount);
      this.activeQueue = this.activeQueue.slice(sampleCount);

      this.logDebug(
        `[Audio] 🎵 Playing ${sampleCount} samples (queue: ${this.activeQueue.length} remaining)`
      );

      // Create audio buffer
      const audioBuffer = this.audioContext!.createBuffer(
        CHANNELS,
        samples.length,
        SAMPLE_RATE
      );

      audioBuffer.copyToChannel(samples, 0);

      const source = this.audioContext!.createBufferSource();
      source.buffer = audioBuffer;

      // Add gain for fade-in/out
      const gain = this.audioContext!.createGain();
      source.connect(gain);
      gain.connect(this.audioContext!.destination);

      const now = this.audioContext!.currentTime;
      const fadeInDuration = 0.02; // 20ms fade-in
      const fadeOutDuration = 0.02; // 20ms fade-out

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(1, now + fadeInDuration);

      const duration = audioBuffer.duration;
      if (duration > fadeOutDuration * 2) {
        gain.gain.setValueAtTime(1, now + duration - fadeOutDuration);
        gain.gain.linearRampToValueAtTime(0, now + duration);
      }

      // Schedule next buffer when this one ends (non-blocking)
      source.onended = () => {
        // Schedule next playback asynchronously to prevent blocking
        this.playbackTimeoutId = setTimeout(() => {
          this.playNextAudioBuffer(10); // Reset backoff on successful play
        }, 0);
      };

      source.start();
    } catch (error) {
      console.error("[Audio] ❌ Playback error:", error);

      // Try to recover: resume AudioContext if suspended
      if (this.audioContext && this.audioContext.state === "suspended") {
        this.logDebug(
          "[Audio] Attempting to recover from suspended context..."
        );
        this.audioContext
          .resume()
          .then(() => {
            this.logDebug("[Audio] ✅ Context resumed, retrying playback");
            this.playNextAudioBuffer(10);
          })
          .catch((err) => {
            console.error("[Audio] Failed to resume context:", err);
            this.isPlayingAudio = false;
          });
      } else {
        this.isPlayingAudio = false;
      }
    }
  }

  private handleWebSocketClose(event: CloseEvent): void {
    this.setConnectionStatus(CONNECTION_STATUS.DISCONNECTED);
    this.helloAcknowledged = false;
    this.sessionId = "";

    // Cancel hello timeout
    this.cancelHelloTimeout();
    this.abortRecordingDueToDisconnect();
    this.resetPlaybackState();

    this.resolveHelloWaiters(false);

    // Stop decode loop
    this.stopDecodeLoop().catch((err) =>
      console.error("Error stopping decode loop:", err)
    );

    // Trigger onDisconnected callback to update UI (resets isConnecting button state)
    this.callbacks.onDisconnected?.();

    // Check close code to determine if server intentionally closed connection
    // 1000 = Normal Closure (server OK, no reconnect)
    // 1001 = Going Away (server shutting down, no reconnect)
    // 1002 = Protocol Error (server error, no reconnect)
    // 1003 = Unsupported Data (server error, no reconnect)
    // 1008 = Policy Violation (server error, no reconnect)
    // Others = Network error (should reconnect)
    const normalClosureCodes = [1000, 1001, 1002, 1003, 1008];
    const isServerInitiatedClose = normalClosureCodes.includes(event.code);

    if (isServerInitiatedClose) {
      this.logDebug(
        `Server closed connection with code ${event.code}: ${
          event.reason || "no reason"
        }`
      );
      this.reconnectAttempts = 0; // Reset attempts so it won't auto-reconnect
      return;
    }

    // Only auto-reconnect if user didn't manually disconnect
    if (this.userInitiatedDisconnect) {
      this.logDebug("User initiated disconnect, no auto-reconnect");
      return;
    }

    // Try to reconnect on network errors
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      const delay =
        this.reconnectDelays[
          Math.min(this.reconnectAttempts, this.reconnectDelays.length - 1)
        ];
      this.reconnectAttempts++;

      this.logDebug(
        `Network error detected (code ${event.code}), reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`
      );

      this.reconnectTimer = setTimeout(() => {
        this.connect();
      }, delay);
    } else {
      this.logDebug("Max reconnect attempts reached");
    }
  }

  private handleWebSocketError(event: Event): void {
    console.error("WebSocket error:", event);
    this.handleError(
      this.createError("WebSocket error occurred", "WS_ERROR", true)
    );
  }

  private processPCMData(event: AudioProcessingEvent): void {
    if (
      this.recordingState !== RECORDING_STATE.RECORDING ||
      !this.opusEncoder
    ) {
      return;
    }

    try {
      const inputData = event.inputBuffer.getChannelData(0);

      // Convert Float32 to Int16
      const int16Data = convertFloat32ToInt16(new Float32Array(inputData));

      this.appendPcmSamples(int16Data);
    } catch (error) {
      console.error("Error processing PCM data:", error);
    }
  }

  private processAudioWorkletBuffer(buffer: Int16Array | number[]): void {
    this.logDebug(
      `[AudioWorklet] 🎤 Handler called - buffer=${
        buffer.length
      } samples, state=${this.recordingState}, encoder=${!!this
        .opusEncoder}, streaming=${this.isAudioStreaming}`
    );

    if (
      this.recordingState === RECORDING_STATE.IDLE ||
      !this.opusEncoder ||
      buffer.length === 0
    ) {
      const reason =
        this.recordingState === RECORDING_STATE.IDLE
          ? "IDLE state"
          : !this.opusEncoder
          ? "No encoder"
          : "Empty buffer";
      const message = `[AudioWorklet] ❌ Handler exit early - reason: ${reason} (state=${
        this.recordingState
      }, encoder=${!!this.opusEncoder}, len=${buffer.length})`;
      if (reason === "IDLE state") {
        this.logDebug(message);
      } else {
        console.warn(message);
      }
      return;
    }

    try {
      const data =
        buffer instanceof Int16Array ? buffer : Int16Array.from(buffer);
      this.logDebug(
        `[AudioWorklet] ✅ Processing buffer - ${data.length} samples, converting to PCM`
      );
      this.appendPcmSamples(data);
    } catch (error) {
      console.error("Error processing AudioWorklet int16 buffer:", error);
    }
  }

  private ensureHandshakeReady(action: string): void {
    if (!this.helloAcknowledged) {
      throw this.createError(
        `Cannot ${action} before completing hello handshake`,
        "HELLO_PENDING",
        true
      );
    }
  }

  private waitForHelloAck(timeoutMs: number = 3000): Promise<boolean> {
    if (this.helloAcknowledged) {
      return Promise.resolve(true);
    }

    return new Promise((resolve) => {
      const resolver = (value: boolean): void => {
        clearTimeout(timer);
        resolve(value);
      };

      const timer = setTimeout(() => {
        this.pendingHelloResolvers = this.pendingHelloResolvers.filter(
          (fn) => fn !== resolver
        );
        resolve(false);
      }, timeoutMs);

      this.pendingHelloResolvers.push(resolver);
    });
  }

  private resolveHelloWaiters(value: boolean): void {
    if (this.pendingHelloResolvers.length === 0) {
      return;
    }

    const waiters = [...this.pendingHelloResolvers];
    this.pendingHelloResolvers = [];
    waiters.forEach((resolve) => resolve(value));
  }

  private controlAudioProcessor(command: "start" | "stop"): void {
    this.logDebug(
      `[Control] 📤 Sending control command to worklet: ${command}`
    );
    if (this.audioProcessor instanceof AudioWorkletNode) {
      this.audioProcessor.port.postMessage({
        type: "control",
        command,
      });
      this.logDebug(`[Control] ✅ Message sent to worklet`);
    } else {
      console.warn(
        `[Control] ❌ audioProcessor is not AudioWorkletNode, type=${typeof this
          .audioProcessor}`
      );
    }
  }

  private appendPcmSamples(int16Data: Int16Array): void {
    this.logDebug(
      `[PCM] 📥 appendPcmSamples called - data=${int16Data.length}, streaming=${this.isAudioStreaming}, state=${this.recordingState}`
    );

    if (
      !this.isAudioStreaming &&
      this.recordingState !== RECORDING_STATE.STOPPING
    ) {
      console.warn(
        `[PCM] ❌ Skip append - streaming disabled and not stopping (streaming=${this.isAudioStreaming}, state=${this.recordingState})`
      );
      return;
    }

    const newBuffer = new Int16Array(this.pcmBuffer.length + int16Data.length);
    newBuffer.set(this.pcmBuffer);
    newBuffer.set(int16Data, this.pcmBuffer.length);
    this.pcmBuffer = newBuffer;
    this.logDebug(
      `[PCM] ✅ Appended ${int16Data.length} samples, total buffer now=${this.pcmBuffer.length}`
    );

    const forceEncode = this.recordingState === RECORDING_STATE.STOPPING;
    this.logDebug(
      `[PCM] → Calling encodeAvailableFrames(force=${forceEncode})`
    );
    this.encodeAvailableFrames(forceEncode);
  }

  private encodeAvailableFrames(force: boolean = false): void {
    this.logDebug(
      `[Encode] ▶️ encodeAvailableFrames called - force=${force}, pcmBuffer=${this.pcmBuffer.length} bytes`
    );

    // Step 1: Check encoder exists
    if (!this.opusEncoder) {
      console.warn("[Encode] ❌ Encoder not initialized, skipping");
      return;
    }
    this.logDebug("[Encode] ✅ Step 1: Encoder ready");

    // Step 2: Check if we can stream audio:
    // - WebSocket is open
    // - Audio streaming is enabled
    // - (force=true ignores conditions, for final flush on stop)
    const wsReady = this.ws && this.ws.readyState === WebSocket.OPEN;
    const streamingEnabled = this.isAudioStreaming;
    const canStream = wsReady && streamingEnabled;

    this.logDebug(
      `[Encode] Step 2: Check stream conditions - WS ready=${wsReady}, streaming=${streamingEnabled}, canStream=${canStream}, force=${force}`
    );

    if (!force && !canStream) {
      this.logDebug(
        `[Encode] ⏭️ Skipping encode - conditions not met (force=${force}, canStream=${canStream})`
      );
      return;
    }
    this.logDebug(
      `[Encode] ✅ Step 2: Stream conditions met (or force=true), proceeding to encode`
    );

    // Step 3: Encode frames in loop
    let frameCount = 0;
    let totalBytesSent = 0;

    while (this.pcmBuffer.length >= FRAME_SIZE) {
      frameCount++;
      this.logDebug(
        `[Encode] Step 3.${frameCount}: Processing frame - buffer=${this.pcmBuffer.length} bytes, need=${FRAME_SIZE}`
      );

      // Step 3a: Extract frame data
      const frameData = this.pcmBuffer.slice(0, FRAME_SIZE);
      this.pcmBuffer = this.pcmBuffer.slice(FRAME_SIZE);
      this.logDebug(
        `[Encode] Step 3.${frameCount}a: ✅ Extracted frame (960 samples), remaining buffer=${this.pcmBuffer.length} bytes`
      );

      // Step 3b: Encode frame
      const encoded = this.opusEncoder.encode(frameData);
      if (!encoded) {
        console.error(
          `[Encode] Step 3.${frameCount}b: ❌ Encoding failed, returned null`
        );
        continue;
      }
      this.logDebug(
        `[Encode] Step 3.${frameCount}b: ✅ Encoded frame: ${encoded.length} bytes`
      );

      // Step 3c: Send encoded frame
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(encoded.buffer);
        totalBytesSent += encoded.length;
        this.logDebug(
          `[Encode] Step 3.${frameCount}c: ✅ Sent encoded frame via WS - ${encoded.length} bytes (total sent: ${totalBytesSent})`
        );
      } else {
        console.warn(
          `[Encode] Step 3.${frameCount}c: ❌ WebSocket not ready, cannot send (state=${this.ws?.readyState})`
        );
      }
    }

    // Step 4: Summary
    if (frameCount === 0) {
      this.logDebug(
        `[Encode] Step 4: ℹ️ No complete frames to encode (buffer=${this.pcmBuffer.length}/${FRAME_SIZE} bytes)`
      );
    } else {
      this.logDebug(
        `[Encode] ✅ Step 4: Encoding complete - ${frameCount} frames processed, ${totalBytesSent} bytes sent, remaining buffer=${this.pcmBuffer.length} bytes`
      );
    }
  }

  private setConnectionStatus(
    status: (typeof CONNECTION_STATUS)[keyof typeof CONNECTION_STATUS]
  ): void {
    this.connectionStatus = status;
  }

  private handleError(error: Error): void {
    console.error("ChatWebSocketService error:", error);

    // Reset connecting state on error to prevent stuck UI
    if (this.connectionStatus === CONNECTION_STATUS.CONNECTING) {
      this.setConnectionStatus(CONNECTION_STATUS.DISCONNECTED);
    }

    const chatError = error as ChatServiceError;
    this.callbacks.onError?.(chatError);
  }

  private createError(
    message: string,
    code: string,
    recoverable: boolean
  ): ChatServiceError {
    const error = new Error(message) as ChatServiceError;
    error.code = code;
    error.recoverable = recoverable;
    return error;
  }

  /**
   * Start the continuous decode loop
   */
  private startDecodeLoop(): void {
    if (this.isDecodeLoopActive) {
      return;
    }

    this.isDecodeLoopActive = true;
    this.endOfStream = false;

    this.decodeLoopPromise = this.decodePacketsLoop().catch((error) => {
      console.error("[Decode Loop] Unexpected error:", error);
    });
  }

  /**
   * Stop the continuous decode loop
   */
  private async stopDecodeLoop(): Promise<void> {
    if (!this.isDecodeLoopActive) {
      return;
    }

    this.isDecodeLoopActive = false;

    // Wait for loop to finish
    if (this.decodeLoopPromise) {
      await this.decodeLoopPromise;
      this.decodeLoopPromise = null;
    }
  }

  /**
   * Main async decode loop - continuously processes pending packets
   */
  private async decodePacketsLoop(): Promise<void> {
    let decoderInitAttempts = 0;
    const maxDecoderInitAttempts = 3;

    while (this.isDecodeLoopActive) {
      try {
        // 1. Try to initialize decoder if not ready
        if (!this.opusDecoder && decoderInitAttempts < maxDecoderInitAttempts) {
          this.logDebug(
            `[Decode] Initializing decoder (attempt ${
              decoderInitAttempts + 1
            }/${maxDecoderInitAttempts})...`
          );
          this.opusDecoder = new OpusDecoder();
          const success = await this.opusDecoder.init();
          if (!success) {
            console.warn(
              "[Decode] Decoder init failed, will retry next iteration"
            );
            this.opusDecoder = null;
            decoderInitAttempts++;
            await this.sleep(1000); // Wait before retry
            continue;
          } else {
            this.logDebug("[Decode] ✅ Decoder initialized successfully");
            decoderInitAttempts = 0; // Reset on success
          }
        }

        // 2. Check if pending queue is empty
        if (this.pendingPackets.length === 0) {
          await this.sleep(DECODE_LOOP_INTERVAL);
          continue;
        }

        // 3. Skip decoding if decoder not ready (will wait for init)
        if (!this.opusDecoder) {
          console.warn("[Decode] Decoder not ready, skipping batch");
          await this.sleep(DECODE_LOOP_INTERVAL);
          continue;
        }

        // 4. Batch decode packets
        const batchSize = Math.min(
          MAX_DECODE_BATCH,
          this.pendingPackets.length
        );
        const batch = this.pendingPackets.splice(0, batchSize);

        for (const packet of batch) {
          if (!this.opusDecoder) {
            // Decoder went away, re-queue packet
            this.pendingPackets.unshift(packet);
            continue;
          }

          try {
            const decoded = this.opusDecoder.decode(packet.data);
            if (decoded && decoded.length > 0) {
              // Convert Int16 → Float32
              const float32 = this.convertInt16ToFloat32(decoded);

              // Append to active queue
              const newQueue = new Float32Array(
                this.activeQueue.length + float32.length
              );
              newQueue.set(this.activeQueue);
              newQueue.set(float32, this.activeQueue.length);
              this.activeQueue = newQueue;

              this.logDebug(
                `[Decode] ✅ Decoded packet: ${float32.length} samples (total queue: ${this.activeQueue.length})`
              );
            }
          } catch (decodeError) {
            console.error(
              `[Decode] ❌ Failed to decode packet (attempt ${packet.attempts}):`,
              decodeError
            );

            // Retry up to 3 times
            if (packet.attempts < 3) {
              packet.attempts++;
              this.pendingPackets.push(packet);
            } else {
              console.warn("[Decode] Dropping packet after 3 failed attempts");
            }
          }
        }

        // 5. Check buffer health
        if (Math.random() < 0.1) {
          // Log every ~10 iterations to avoid spam
          this.checkBufferHealth();
        }

        // 6. Yield to event loop
        await this.sleep(0);
      } catch (error) {
        console.error("[Decode Loop] Unexpected error in loop:", error);
        await this.sleep(DECODE_LOOP_INTERVAL);
      }
    }

    this.logDebug("[Decode Loop] ✋ Decode loop stopped");
  }

  /**
   * Start hello acknowledgement timeout (10 seconds)
   * If server doesn't respond with hello ack, disconnect and report error
   */
  private startHelloTimeout(): void {
    // Cancel any existing timeout first
    this.cancelHelloTimeout();

    this.helloTimeoutTimer = setTimeout(() => {
      console.error(
        "[WS] ❌ Hello acknowledgement timeout - no response from server after 10s"
      );

      // Create error and handle it
      const error = this.createError(
        "Server did not respond to hello handshake within 10 seconds",
        "HELLO_TIMEOUT",
        false
      );

      this.handleError(error);

      // Disconnect WebSocket
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.close(1000, "Hello acknowledgement timeout");
      }

      // Update connection status
      this.setConnectionStatus(CONNECTION_STATUS.DISCONNECTED);

      // Resolve any waiters with false
      this.resolveHelloWaiters(false);

      // Trigger callback to notify UI
      this.callbacks.onDisconnected?.();
    }, 10000); // 10 seconds timeout
  }

  /**
   * Cancel hello acknowledgement timeout
   */
  private cancelHelloTimeout(): void {
    if (this.helloTimeoutTimer) {
      clearTimeout(this.helloTimeoutTimer);
      this.helloTimeoutTimer = null;
      this.logDebug("[WS] ✅ Hello timeout cancelled (ack received)");
    }
  }
}
