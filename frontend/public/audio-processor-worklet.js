/**
 * AudioWorkletProcessor for PCM data capture
 * Replaces deprecated ScriptProcessorNode
 */
const FRAME_SIZE = 960; // 60ms @ 16kHz

class PCMProcessorWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frameBuffer = new Int16Array(FRAME_SIZE);
    this.frameIndex = 0;
    this.isRecording = false;

    this.port.onmessage = (event) => {
      const { type, command } = event.data || {};

      if (type !== "control") {
        return;
      }

      if (command === "start") {
        this.frameIndex = 0;
        this.isRecording = true;
      } else if (command === "stop") {
        this.flushFrame();
        this.isRecording = false;
      }
    };
  }

  flushFrame() {
    if (this.frameIndex === 0) {
      return;
    }

    this.port.postMessage({
      type: "buffer",
      buffer: this.frameBuffer.slice(0, this.frameIndex),
    });
    this.frameIndex = 0;
  }

  process(inputs) {
    if (!this.isRecording) {
      return true;
    }

    const input = inputs[0];
    if (!input || input.length === 0) {
      return true;
    }

    const channel = input[0];
    if (!channel) {
      return true;
    }

    for (let i = 0; i < channel.length; i++) {
      const sample = Math.max(-1, Math.min(1, channel[i]));
      this.frameBuffer[this.frameIndex++] =
        sample < 0 ? sample * 0x8000 : sample * 0x7fff;

      if (this.frameIndex >= FRAME_SIZE) {
        this.port.postMessage({
          type: "buffer",
          buffer: this.frameBuffer.slice(0),
        });
        this.frameIndex = 0;
      }
    }

    return true;
  }
}

registerProcessor("pcm-processor-worklet", PCMProcessorWorklet);
