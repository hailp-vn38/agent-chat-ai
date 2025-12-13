import { memo, useState, useRef, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Mic, Square, RotateCcw, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

const MAX_RECORDING_DURATION = 20; // seconds

export interface AudioRecorderData {
  audioBase64: string;
  audioFormat: string;
}

export interface AudioRecorderProps {
  onRecordingComplete: (data: AudioRecorderData) => void;
  onRecordingClear?: () => void;
  disabled?: boolean;
  className?: string;
}

type RecordingState = "idle" | "recording" | "recorded" | "error";

const AudioRecorderComponent = ({
  onRecordingComplete,
  onRecordingClear,
  disabled = false,
  className,
}: AudioRecorderProps) => {
  const { t } = useTranslation(["providers", "common"]);

  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [elapsedTime, setElapsedTime] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
  }, [audioUrl]);

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  // Convert blob to base64
  const blobToBase64 = useCallback((blob: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64 = reader.result as string;
        // Remove data URL prefix (e.g., "data:audio/webm;base64,")
        const base64Data = base64.split(",")[1];
        resolve(base64Data);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }, []);

  // Get audio format from MIME type
  const getAudioFormat = useCallback((mimeType: string): string => {
    if (mimeType.includes("webm")) return "webm";
    if (mimeType.includes("ogg")) return "ogg";
    if (mimeType.includes("mp4")) return "mp4";
    if (mimeType.includes("wav")) return "wav";
    return "webm"; // default
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      setErrorMessage(null);
      audioChunksRef.current = [];

      // Check browser support
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setErrorMessage(t("providers:audio_not_supported"));
        setRecordingState("error");
        return;
      }

      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Determine supported MIME type
      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/ogg")
        ? "audio/ogg"
        : "audio/mp4";

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        const url = URL.createObjectURL(audioBlob);
        setAudioUrl(url);

        try {
          const base64 = await blobToBase64(audioBlob);
          const format = getAudioFormat(mimeType);
          onRecordingComplete({ audioBase64: base64, audioFormat: format });
          setRecordingState("recorded");
        } catch {
          setErrorMessage(t("providers:audio_conversion_error"));
          setRecordingState("error");
        }
      };

      mediaRecorder.start(100); // Collect data every 100ms
      setRecordingState("recording");
      setElapsedTime(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setElapsedTime((prev) => {
          const next = prev + 1;
          if (next >= MAX_RECORDING_DURATION) {
            stopRecording();
          }
          return next;
        });
      }, 1000);
    } catch (error) {
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        setErrorMessage(t("providers:microphone_permission_denied"));
      } else {
        setErrorMessage(t("providers:audio_recording_error"));
      }
      setRecordingState("error");
    }
  }, [t, blobToBase64, getAudioFormat, onRecordingComplete]);

  // Stop recording
  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      mediaRecorderRef.current.stop();
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  // Reset recording
  const resetRecording = useCallback(() => {
    cleanup();
    setRecordingState("idle");
    setElapsedTime(0);
    setAudioUrl(null);
    setErrorMessage(null);
    audioChunksRef.current = [];
    onRecordingClear?.();
  }, [cleanup, onRecordingClear]);

  // Format time as MM:SS
  const formatTime = useCallback((seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  }, []);

  // Calculate progress percentage
  const progressPercent = (elapsedTime / MAX_RECORDING_DURATION) * 100;

  return (
    <div className={cn("space-y-3", className)}>
      {/* Error Alert */}
      {recordingState === "error" && errorMessage && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      )}

      {/* Recording Controls */}
      <div className="flex items-center gap-3">
        {recordingState === "idle" || recordingState === "error" ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={startRecording}
            disabled={disabled}
            className="gap-2"
          >
            <Mic className="h-4 w-4" />
            {t("providers:start_recording")}
          </Button>
        ) : recordingState === "recording" ? (
          <>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={stopRecording}
              className="gap-2"
            >
              <Square className="h-4 w-4" />
              {t("providers:stop_recording")}
            </Button>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-red-500 animate-pulse" />
              <span className="text-sm font-mono">
                {formatTime(elapsedTime)}
              </span>
              <span className="text-xs text-muted-foreground">
                / {formatTime(MAX_RECORDING_DURATION)}
              </span>
            </div>
          </>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={resetRecording}
            disabled={disabled}
            className="gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            {t("providers:re_record")}
          </Button>
        )}
      </div>

      {/* Progress Bar (during recording) */}
      {recordingState === "recording" && (
        <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
          <div
            className="bg-red-500 h-full transition-all duration-1000 ease-linear"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}

      {/* Audio Preview (after recording) */}
      {recordingState === "recorded" && audioUrl && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {t("providers:audio_preview")}
            </p>
            <p className="text-xs text-muted-foreground font-mono">
              {formatTime(elapsedTime)}
            </p>
          </div>
          <audio src={audioUrl} controls className="w-full h-8" />
        </div>
      )}
    </div>
  );
};

export const AudioRecorder = memo(AudioRecorderComponent);
