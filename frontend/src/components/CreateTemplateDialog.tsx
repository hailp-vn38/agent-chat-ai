"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import type { AgentTemplate, AgentTemplateDetail } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Provider Module Option - matches API response from /providers/config/modules
 * Uses reference format: config:{name} or db:{uuid}
 */
interface ModuleOption {
  reference: string;
  id?: string;
  name: string;
  type?: string;
  source?: "default" | "user";
}

interface CreateTemplateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template?: AgentTemplate | AgentTemplateDetail | null;
  onSubmit: (data: any) => Promise<void>;
  isLoading?: boolean;
  modules?: {
    ASR?: ModuleOption[];
    TTS?: ModuleOption[];
    LLM?: ModuleOption[];
    VLLM?: ModuleOption[];
    Memory?: ModuleOption[];
    Intent?: ModuleOption[];
  };
  modulesLoading?: boolean;
}

export function CreateTemplateDialog({
  open,
  onOpenChange,
  template,
  onSubmit,
  isLoading = false,
  modules,
  modulesLoading = false,
}: CreateTemplateDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { t } = useTranslation("agents");

  /**
   * Extract provider reference from provider field
   * Handles both string (reference) and object (ProviderInfo) formats
   * Returns reference string for form value
   */
  const getProviderReference = (
    provider: string | { reference?: string; id?: string } | undefined | null
  ): string => {
    if (!provider) return "";
    if (typeof provider === "string") return provider;
    // Prefer reference over id for new API format
    return provider.reference || provider.id || "";
  };

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
    reset,
  } = useForm({
    defaultValues: {
      name: template?.name || "",
      prompt: template?.prompt || "",
      ASR: getProviderReference(template?.ASR),
      TTS: getProviderReference(template?.TTS),
      LLM: getProviderReference(template?.LLM),
      VLLM: getProviderReference(template?.VLLM),
      Memory: getProviderReference(template?.Memory),
      Intent: getProviderReference(template?.Intent),
      summary_memory: template?.summary_memory || "",
    },
  });

  useEffect(() => {
    if (template) {
      reset({
        name: template.name,
        prompt: template.prompt,
        ASR: getProviderReference(template.ASR),
        TTS: getProviderReference(template.TTS),
        LLM: getProviderReference(template.LLM),
        VLLM: getProviderReference(template.VLLM),
        Memory: getProviderReference(template.Memory),
        Intent: getProviderReference(template.Intent),
        summary_memory: template.summary_memory || "",
      });
    } else {
      reset();
    }
  }, [template, open, reset]);

  const onSubmitHandler = async (data: any) => {
    setIsSubmitting(true);
    try {
      // Build payload
      const payload: any = {
        name: data.name,
        prompt: data.prompt,
        summary_memory: data.summary_memory || null,
        ASR: data.ASR || null,
        LLM: data.LLM || null,
        VLLM: data.VLLM || null,
        TTS: data.TTS || null,
        Memory: data.Memory || null,
        Intent: data.Intent || null,
      };

      await onSubmit(payload);
      onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isSubmittingForm = isSubmitting || isLoading;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full max-w-[95vw] lg:max-w-5xl lg:w-[70vw] max-h-[90vh] lg:max-h-[85vh] overflow-y-auto">
        <div className="flex h-full flex-col">
          <DialogHeader className="px-6 pt-6 text-left">
            <DialogTitle>
              {template ? t("edit_template") : t("create_template")}
            </DialogTitle>
            <DialogDescription>
              {template ? t("update_template_desc") : t("create_template_desc")}
            </DialogDescription>
          </DialogHeader>

          <form
            onSubmit={handleSubmit(onSubmitHandler)}
            className="flex-1 overflow-y-auto px-6 pb-6"
          >
            <div className="space-y-8">
              <div className="grid gap-4 lg:grid-cols-2">
                {/* Template Name */}
                <div className="space-y-2">
                  <Label htmlFor="name">{t("template_name")} *</Label>
                  <Input
                    id="name"
                    placeholder={t("enter_template_name")}
                    {...register("name", {
                      required: t("template_name_required"),
                    })}
                    disabled={isSubmittingForm}
                  />
                  {errors.name && (
                    <p className="text-xs text-destructive">
                      {errors.name.message}
                    </p>
                  )}
                </div>

                {/* Prompt */}
                <div className="space-y-2 lg:col-span-2">
                  <Label htmlFor="prompt">{t("prompt")} *</Label>
                  <textarea
                    id="prompt"
                    placeholder={t("enter_system_prompt")}
                    rows={6}
                    className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    {...register("prompt", {
                      required: t("prompt_required"),
                    })}
                    disabled={isSubmittingForm}
                  />
                  {errors.prompt && (
                    <p className="text-xs text-destructive">
                      {errors.prompt.message}
                    </p>
                  )}
                </div>
              </div>

              {/* Models Grid */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {/* ASR Model */}
                <div className="space-y-2">
                  <Label htmlFor="ASR">ASR</Label>
                  <ModelSelect
                    name="ASR"
                    options={modules?.ASR || []}
                    value={watch("ASR")}
                    onChange={(value) => setValue("ASR", value)}
                    disabled={modulesLoading || isSubmittingForm}
                  />
                </div>

                {/* LLM Model */}
                <div className="space-y-2">
                  <Label htmlFor="LLM">LLM</Label>
                  <ModelSelect
                    name="LLM"
                    options={modules?.LLM || []}
                    value={watch("LLM")}
                    onChange={(value) => setValue("LLM", value)}
                    disabled={modulesLoading || isSubmittingForm}
                  />
                </div>

                {/* VLLM Model */}
                <div className="space-y-2">
                  <Label htmlFor="VLLM">VLLM</Label>
                  <ModelSelect
                    name="VLLM"
                    options={modules?.VLLM || []}
                    value={watch("VLLM")}
                    onChange={(value) => setValue("VLLM", value)}
                    disabled={modulesLoading || isSubmittingForm}
                  />
                </div>

                {/* TTS Model */}
                <div className="space-y-2">
                  <Label htmlFor="TTS">TTS</Label>
                  <ModelSelect
                    name="TTS"
                    options={modules?.TTS || []}
                    value={watch("TTS")}
                    onChange={(value) => setValue("TTS", value)}
                    disabled={modulesLoading || isSubmittingForm}
                  />
                </div>

                {/* Memory Model */}
                <div className="space-y-2">
                  <Label htmlFor="Memory">Memory</Label>
                  <ModelSelect
                    name="Memory"
                    options={modules?.Memory || []}
                    value={watch("Memory")}
                    onChange={(value) => setValue("Memory", value)}
                    disabled={modulesLoading || isSubmittingForm}
                  />
                </div>

                {/* Intent Model */}
                <div className="space-y-2">
                  <Label htmlFor="Intent">Intent</Label>
                  <ModelSelect
                    name="Intent"
                    options={modules?.Intent || []}
                    value={watch("Intent")}
                    onChange={(value) => setValue("Intent", value)}
                    disabled={modulesLoading || isSubmittingForm}
                  />
                </div>

                {/* Summary Memory */}
                <div className="space-y-2 md:col-span-2 lg:col-span-3">
                  <Label htmlFor="summary_memory">Summary Memory</Label>
                  <Input
                    id="summary_memory"
                    placeholder="Enter summary memory"
                    {...register("summary_memory")}
                    disabled={isSubmittingForm}
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 border-t pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                  disabled={isSubmittingForm}
                >
                  {t("cancel")}
                </Button>
                <Button type="submit" disabled={isSubmittingForm}>
                  {isSubmittingForm
                    ? t("saving")
                    : template
                    ? t("update_template")
                    : t("create_template")}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Helper component for model select with provider reference support
interface ModelSelectProps {
  name: string;
  options: ModuleOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

function ModelSelect({
  name,
  options,
  value,
  onChange,
  disabled,
}: ModelSelectProps) {
  const { t } = useTranslation("agents");

  return (
    <select
      name={name}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <option value="">{t("use_server_default")}</option>
      {options.map((option) => {
        const sourceLabel =
          option.source === "default" ? t("default") : t("custom");
        return (
          <option key={option.reference} value={option.reference}>
            {option.name} ({sourceLabel})
          </option>
        );
      })}
    </select>
  );
}
