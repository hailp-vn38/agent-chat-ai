import { memo, useState, useCallback, useRef, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ImagePlus, X, Info } from "lucide-react";

import type { ProviderCategory, ProviderTestInputData } from "@types";
import { AudioRecorder, type AudioRecorderData } from "./AudioRecorder";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

export interface ProviderTestInputProps {
  category: ProviderCategory | null;
  onInputChange: (inputData: ProviderTestInputData | null) => void;
  disabled?: boolean;
  className?: string;
}

const CATEGORIES_WITH_INPUT: ProviderCategory[] = ["LLM", "TTS", "ASR", "VLLM"];

const ProviderTestInputComponent = ({
  category,
  onInputChange,
  disabled = false,
  className,
}: ProviderTestInputProps) => {
  const { t } = useTranslation(["providers", "common"]);

  const [isOpen, setIsOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [text, setText] = useState("");
  const [audioData, setAudioData] = useState<AudioRecorderData | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [question, setQuestion] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Build input data based on category
  const buildInputData = useCallback((): ProviderTestInputData | null => {
    if (!category) return null;

    switch (category) {
      case "LLM":
        return prompt.trim() ? { prompt: prompt.trim() } : null;
      case "TTS":
        return text.trim() ? { text: text.trim() } : null;
      case "ASR":
        return audioData
          ? {
              audio_base64: audioData.audioBase64,
              audio_format: audioData.audioFormat,
            }
          : null;
      case "VLLM":
        if (imageBase64) {
          return {
            image_base64: imageBase64,
            question: question.trim() || undefined,
          };
        }
        return null;
      default:
        return null;
    }
  }, [category, prompt, text, audioData, imageBase64, question]);

  // Handle prompt change (LLM)
  const handlePromptChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setPrompt(value);
      onInputChange(value.trim() ? { prompt: value.trim() } : null);
    },
    [onInputChange]
  );

  // Handle text change (TTS)
  const handleTextChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setText(value);
      onInputChange(value.trim() ? { text: value.trim() } : null);
    },
    [onInputChange]
  );

  // Handle audio recording complete (ASR)
  const handleRecordingComplete = useCallback(
    (data: AudioRecorderData) => {
      setAudioData(data);
      onInputChange({
        audio_base64: data.audioBase64,
        audio_format: data.audioFormat,
      });
    },
    [onInputChange]
  );

  // Handle audio clear
  const handleRecordingClear = useCallback(() => {
    setAudioData(null);
    onInputChange(null);
  }, [onInputChange]);

  // Handle image upload (VLLM)
  const handleImageUpload = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      // Validate file type
      if (!file.type.startsWith("image/")) {
        return;
      }

      // Read file as base64
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64 = reader.result as string;
        const base64Data = base64.split(",")[1];
        setImageBase64(base64Data);
        setImagePreview(base64);
        onInputChange({
          image_base64: base64Data,
          question: question.trim() || undefined,
        });
      };
      reader.readAsDataURL(file);
    },
    [question, onInputChange]
  );

  // Handle image remove
  const handleImageRemove = useCallback(() => {
    setImageBase64(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onInputChange(null);
  }, [onInputChange]);

  // Handle question change (VLLM)
  const handleQuestionChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setQuestion(value);
      if (imageBase64) {
        onInputChange({
          image_base64: imageBase64,
          question: value.trim() || undefined,
        });
      }
    },
    [imageBase64, onInputChange]
  );

  // Check if category supports custom input
  const hasCustomInput = category && CATEGORIES_WITH_INPUT.includes(category);

  // Get current input data for display
  const currentInputData = buildInputData();
  const hasInputValue = currentInputData !== null;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("space-y-2", className)}
    >
      <CollapsibleTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="flex w-full justify-between px-2 hover:bg-muted"
          disabled={disabled}
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            {t("providers:advanced_test_options")}
            {hasInputValue && (
              <span className="h-2 w-2 rounded-full bg-primary" />
            )}
          </span>
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform duration-200",
              isOpen && "rotate-180"
            )}
          />
        </Button>
      </CollapsibleTrigger>

      <CollapsibleContent className="space-y-4 pt-2">
        {!hasCustomInput ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground p-3 bg-muted/50 rounded-md">
            <Info className="h-4 w-4" />
            <span>{t("providers:no_custom_input_needed")}</span>
          </div>
        ) : (
          <>
            {/* LLM: Prompt Input */}
            {category === "LLM" && (
              <div className="space-y-2">
                <Label htmlFor="test-prompt">
                  {t("providers:test_prompt")}
                </Label>
                <Textarea
                  id="test-prompt"
                  placeholder={t("providers:test_prompt_placeholder")}
                  value={prompt}
                  onChange={handlePromptChange}
                  disabled={disabled}
                  rows={3}
                  className="resize-none"
                />
              </div>
            )}

            {/* TTS: Text Input */}
            {category === "TTS" && (
              <div className="space-y-2">
                <Label htmlFor="test-text">{t("providers:test_text")}</Label>
                <Textarea
                  id="test-text"
                  placeholder={t("providers:test_text_placeholder")}
                  value={text}
                  onChange={handleTextChange}
                  disabled={disabled}
                  rows={3}
                  className="resize-none"
                />
              </div>
            )}

            {/* ASR: Audio Recording */}
            {category === "ASR" && (
              <div className="space-y-2">
                <Label>{t("providers:test_audio")}</Label>
                <AudioRecorder
                  onRecordingComplete={handleRecordingComplete}
                  onRecordingClear={handleRecordingClear}
                  disabled={disabled}
                />
              </div>
            )}

            {/* VLLM: Image + Question */}
            {category === "VLLM" && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{t("providers:test_image")}</Label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleImageUpload}
                    disabled={disabled}
                    className="hidden"
                  />
                  {imagePreview ? (
                    <div className="relative inline-block">
                      <img
                        src={imagePreview}
                        alt="Preview"
                        className="max-h-32 rounded-md border"
                      />
                      <Button
                        type="button"
                        variant="destructive"
                        size="icon"
                        className="absolute -top-2 -right-2 h-6 w-6"
                        onClick={handleImageRemove}
                        disabled={disabled}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={disabled}
                      className="gap-2"
                    >
                      <ImagePlus className="h-4 w-4" />
                      {t("providers:upload_image")}
                    </Button>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="test-question">
                    {t("providers:test_question")}
                  </Label>
                  <Textarea
                    id="test-question"
                    placeholder={t("providers:test_question_placeholder")}
                    value={question}
                    onChange={handleQuestionChange}
                    disabled={disabled}
                    rows={2}
                    className="resize-none"
                  />
                </div>
              </div>
            )}
          </>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
};

export const ProviderTestInput = memo(ProviderTestInputComponent);
