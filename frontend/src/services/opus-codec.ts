/**
 * Opus Audio Codec utilities for encoding and decoding
 * Based on test_page.html implementation
 */

const SAMPLE_RATE = 16000;
const CHANNELS = 1;
const FRAME_SIZE = 960; // 60ms @ 16kHz
const OPUS_APPLICATION = 2048; // OPUS_APPLICATION_VOIP (matches legacy implementation)
const OPUS_CTL_SET_BITRATE = 4002;
const OPUS_CTL_SET_COMPLEXITY = 4010;
const OPUS_CTL_SET_DTX = 4016;
const TARGET_BITRATE = 16000;
const ENCODER_COMPLEXITY = 5;
const ENABLE_DTX = 1;

interface OpusModule {
  _opus_encoder_get_size(channels: number): number;
  _opus_encoder_init(
    ptr: number,
    rate: number,
    channels: number,
    app: number
  ): number;
  _opus_encoder_ctl(encoderPtr: number, request: number, value: number): number;
  _opus_encode(
    encoderPtr: number,
    pcmPtr: number,
    frameSize: number,
    encodedPtr: number,
    maxPacketSize: number
  ): number;
  _opus_decoder_get_size(channels: number): number;
  _opus_decoder_init(ptr: number, rate: number, channels: number): number;
  _opus_decode(
    decoderPtr: number,
    opusPtr: number,
    opusLen: number,
    pcmPtr: number,
    frameSize: number,
    fec: number
  ): number;
  _malloc(size: number): number;
  _free(ptr: number): void;
  HEAP16: Int16Array;
  HEAPU8: Uint8Array;
}

export class OpusEncoder {
  private module: OpusModule | null = null;
  private encoderPtr: number | null = null;
  private channels = CHANNELS;
  private sampleRate = SAMPLE_RATE;
  private frameSize = FRAME_SIZE;
  private maxPacketSize = 4000;

  /**
   * Wait for Opus module to be available (up to 10 seconds)
   */
  private async waitForModule(timeoutMs: number = 10000): Promise<OpusModule> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      // Try Module.instance first (from libopus.js export)
      let moduleInstance = (window as any).Module?.instance;

      // Fallback to ModuleInstance if available
      if (!moduleInstance) {
        moduleInstance = (window as any).ModuleInstance;
      }

      // Fallback to Module directly
      if (!moduleInstance) {
        moduleInstance = (window as any).Module;
      }

      if (
        moduleInstance &&
        typeof moduleInstance._opus_encoder_get_size === "function" &&
        typeof moduleInstance._opus_decoder_get_size === "function"
      ) {
        return moduleInstance;
      }

      // Wait 100ms before checking again
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    throw new Error(
      `Opus library not loaded within ${timeoutMs}ms. Make sure libopus.js is loaded.`
    );
  }

  /**
   * Initialize Opus encoder
   */
  async init(): Promise<boolean> {
    try {
      // Wait for Opus module to be available
      this.module = await this.waitForModule();

      // Get encoder size
      const encoderSize = this.module._opus_encoder_get_size(this.channels);
      if (encoderSize <= 0) {
        throw new Error(`Invalid encoder size: ${encoderSize}`);
      }

      // Allocate memory for encoder
      this.encoderPtr = this.module._malloc(encoderSize);
      if (!this.encoderPtr) {
        throw new Error("Failed to allocate encoder memory");
      }

      // Initialize encoder
      const err = this.module._opus_encoder_init(
        this.encoderPtr,
        this.sampleRate,
        this.channels,
        OPUS_APPLICATION
      );

      if (err < 0) {
        this.destroy();
        throw new Error(`Opus encoder init failed: ${err}`);
      }

      // Align encoder params with legacy flow (test_page.html)
      this.module._opus_encoder_ctl(
        this.encoderPtr,
        OPUS_CTL_SET_BITRATE,
        TARGET_BITRATE
      );
      this.module._opus_encoder_ctl(
        this.encoderPtr,
        OPUS_CTL_SET_COMPLEXITY,
        ENCODER_COMPLEXITY
      );
      this.module._opus_encoder_ctl(
        this.encoderPtr,
        OPUS_CTL_SET_DTX,
        ENABLE_DTX
      );

      return true;
    } catch (error) {
      console.error("OpusEncoder.init() error:", error);
      return false;
    }
  }

  /**
   * Encode PCM data to Opus
   */
  encode(pcmData: Int16Array): Uint8Array | null {
    if (!this.module || !this.encoderPtr) {
      throw new Error("Opus encoder not initialized");
    }

    try {
      // Allocate memory for PCM data
      const pcmPtr = this.module._malloc(pcmData.length * 2);
      if (!pcmPtr) {
        throw new Error("Failed to allocate PCM memory");
      }

      // Copy PCM data to WASM memory
      for (let i = 0; i < pcmData.length; i++) {
        this.module.HEAP16[(pcmPtr >> 1) + i] = pcmData[i];
      }

      // Allocate memory for encoded data
      const encodedPtr = this.module._malloc(this.maxPacketSize);
      if (!encodedPtr) {
        this.module._free(pcmPtr);
        throw new Error("Failed to allocate encoded memory");
      }

      // Encode
      const encodedBytes = this.module._opus_encode(
        this.encoderPtr,
        pcmPtr,
        this.frameSize,
        encodedPtr,
        this.maxPacketSize
      );

      if (encodedBytes < 0) {
        this.module._free(pcmPtr);
        this.module._free(encodedPtr);
        throw new Error(`Opus encode failed: ${encodedBytes}`);
      }

      // Copy encoded data from WASM memory
      const encodedData = new Uint8Array(encodedBytes);
      for (let i = 0; i < encodedBytes; i++) {
        encodedData[i] = this.module.HEAPU8[encodedPtr + i];
      }

      // Clean up
      this.module._free(pcmPtr);
      this.module._free(encodedPtr);

      return encodedData;
    } catch (error) {
      console.error("OpusEncoder.encode() error:", error);
      return null;
    }
  }

  /**
   * Destroy encoder and free memory
   */
  destroy(): void {
    if (this.module && this.encoderPtr) {
      this.module._free(this.encoderPtr);
      this.encoderPtr = null;
    }
  }
}

export class OpusDecoder {
  private module: OpusModule | null = null;
  private decoderPtr: number | null = null;
  private channels = CHANNELS;
  private sampleRate = SAMPLE_RATE;
  private frameSize = FRAME_SIZE;
  private initialized = false;

  /**
   * Wait for Opus module to be available (up to 10 seconds)
   */
  private async waitForModule(timeoutMs: number = 10000): Promise<OpusModule> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      // Try Module.instance first (from libopus.js export)
      let moduleInstance = (window as any).Module?.instance;

      // Fallback to ModuleInstance if available
      if (!moduleInstance) {
        moduleInstance = (window as any).ModuleInstance;
      }

      // Fallback to Module directly
      if (!moduleInstance) {
        moduleInstance = (window as any).Module;
      }

      if (
        moduleInstance &&
        typeof moduleInstance._opus_encoder_get_size === "function" &&
        typeof moduleInstance._opus_decoder_get_size === "function"
      ) {
        return moduleInstance;
      }

      // Wait 100ms before checking again
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    throw new Error(
      `Opus library not loaded within ${timeoutMs}ms. Make sure libopus.js is loaded.`
    );
  }

  /**
   * Initialize Opus decoder
   */
  async init(): Promise<boolean> {
    try {
      // Wait for Opus module to be available
      this.module = await this.waitForModule();

      // Get decoder size
      const decoderSize = this.module._opus_decoder_get_size(this.channels);
      if (decoderSize <= 0) {
        throw new Error(`Invalid decoder size: ${decoderSize}`);
      }

      // Allocate memory for decoder
      this.decoderPtr = this.module._malloc(decoderSize);
      if (!this.decoderPtr) {
        throw new Error("Failed to allocate decoder memory");
      }

      // Initialize decoder
      const err = this.module._opus_decoder_init(
        this.decoderPtr,
        this.sampleRate,
        this.channels
      );

      if (err < 0) {
        this.destroy();
        throw new Error(`Opus decoder init failed: ${err}`);
      }

      this.initialized = true;
      return true;
    } catch (error) {
      console.error("OpusDecoder.init() error:", error);
      return false;
    }
  }

  /**
   * Decode Opus data to PCM
   */
  decode(opusData: Uint8Array): Int16Array | null {
    if (!this.module || !this.decoderPtr) {
      throw new Error("Opus decoder not initialized");
    }

    try {
      // Allocate memory for Opus data
      const opusPtr = this.module._malloc(opusData.length);
      if (!opusPtr) {
        throw new Error("Failed to allocate Opus memory");
      }

      // Copy Opus data to WASM memory
      this.module.HEAPU8.set(opusData, opusPtr);

      // Allocate memory for PCM output
      const pcmPtr = this.module._malloc(this.frameSize * 2);
      if (!pcmPtr) {
        this.module._free(opusPtr);
        throw new Error("Failed to allocate PCM output memory");
      }

      // Decode
      const decodedSamples = this.module._opus_decode(
        this.decoderPtr,
        opusPtr,
        opusData.length,
        pcmPtr,
        this.frameSize,
        0 // no FEC
      );

      if (decodedSamples < 0) {
        this.module._free(opusPtr);
        this.module._free(pcmPtr);
        throw new Error(`Opus decode failed: ${decodedSamples}`);
      }

      // Copy decoded data from WASM memory
      const decodedData = new Int16Array(decodedSamples);
      for (let i = 0; i < decodedSamples; i++) {
        decodedData[i] = this.module.HEAP16[(pcmPtr >> 1) + i];
      }

      // Clean up
      this.module._free(opusPtr);
      this.module._free(pcmPtr);

      return decodedData;
    } catch (error) {
      console.error("OpusDecoder.decode() error:", error);
      return null;
    }
  }

  /**
   * Destroy decoder and free memory
   */
  destroy(): void {
    if (this.module && this.decoderPtr) {
      this.module._free(this.decoderPtr);
      this.decoderPtr = null;
    }
    this.initialized = false;
  }

  /**
   * Check if decoder is properly initialized
   */
  isInitialized(): boolean {
    return this.initialized && !!this.module && !!this.decoderPtr;
  }
}

/**
 * Convert Float32 audio data to Int16
 */
export function convertFloat32ToInt16(float32Data: Float32Array): Int16Array {
  const int16Data = new Int16Array(float32Data.length);
  for (let i = 0; i < float32Data.length; i++) {
    // Clamp to [-1, 1]
    const s = Math.max(-1, Math.min(1, float32Data[i]));
    // Convert to [-32768, 32767]
    int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16Data;
}

/**
 * Convert Int16 audio data to Float32
 */
export function convertInt16ToFloat32(int16Data: Int16Array): Float32Array {
  const float32Data = new Float32Array(int16Data.length);
  for (let i = 0; i < int16Data.length; i++) {
    // Convert from [-32768, 32767] to [-1, 1]
    float32Data[i] = int16Data[i] / (int16Data[i] < 0 ? 0x8000 : 0x7fff);
  }
  return float32Data;
}

/**
 * Check if Opus module is available
 */
export function isOpusAvailable(): boolean {
  const moduleInstance =
    (window as any).ModuleInstance || (window as any).Module;
  return (
    !!moduleInstance &&
    typeof moduleInstance._opus_encoder_get_size === "function"
  );
}
