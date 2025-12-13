"use client";

import { useTranslation } from "react-i18next";
import { CheckCircle2, XCircle, Zap, Clock } from "lucide-react";

import { useProviderSheetStore } from "@/store/provider-sheet.store";

/**
 * ProviderTestResults component
 * Displays validation and test connection results
 */
export function ProviderTestResults() {
  const { t } = useTranslation(["providers"]);
  const { validationResult, testResult } = useProviderSheetStore();

  if (!validationResult && !testResult) {
    return null;
  }

  return (
    <>
      {/* Validation Result */}
      {validationResult && (
        <div
          className={`rounded-lg border p-3 ${
            validationResult.valid
              ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950"
              : "border-destructive/50 bg-destructive/10"
          }`}
        >
          <div className="flex items-center gap-2">
            {validationResult.valid ? (
              <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-destructive" />
            )}
            <span className="text-sm font-medium">
              {validationResult.valid
                ? t("providers:validation_passed")
                : t("providers:validation_failed")}
            </span>
          </div>
          {validationResult.errors.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-sm text-destructive">
              {validationResult.errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Test Result */}
      {testResult && (
        <div
          className={`rounded-lg border p-3 ${
            testResult.success
              ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950"
              : "border-destructive/50 bg-destructive/10"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {testResult.success ? (
                <Zap className="h-4 w-4 text-green-600 dark:text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-destructive" />
              )}
              <span className="text-sm font-medium">
                {testResult.success
                  ? testResult.message || t("providers:connection_success")
                  : testResult.error || t("providers:connection_failed")}
              </span>
            </div>
            {testResult.latency_ms && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                <span>{testResult.latency_ms}ms</span>
              </div>
            )}
          </div>

          {/* Text Output for LLM/ASR */}
          {testResult.success && testResult.text_output && (
            <div className="mt-3 space-y-2">
              <p className="text-sm font-medium text-muted-foreground">
                {t("providers:output")}:
              </p>
              <div className="max-h-32 overflow-y-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 text-sm">
                {testResult.text_output}
              </div>
            </div>
          )}

          {/* Audio Preview for TTS */}
          {testResult.success &&
            testResult.audio_base64 &&
            testResult.audio_format && (
              <div className="mt-3 space-y-2">
                <p className="text-sm font-medium text-muted-foreground">
                  {t("providers:audio_preview")}
                </p>
                <audio
                  src={createAudioUrl(
                    testResult.audio_base64,
                    testResult.audio_format
                  )}
                  controls
                  className="h-8 w-full"
                />
              </div>
            )}
        </div>
      )}
    </>
  );
}

/**
 * Decode base64 audio and create playable URL
 */
function createAudioUrl(base64: string, format: string): string {
  try {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: `audio/${format}` });
    return URL.createObjectURL(blob);
  } catch (error) {
    console.error("Failed to create audio URL:", error);
    return "";
  }
}
