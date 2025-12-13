"use client";

import { useTranslation } from "react-i18next";

import type { ProviderField } from "@types";
import { useProviderSheetStore } from "@/store/provider-sheet.store";
import { ProviderTestInput } from "@/components/ProviderTestInput";
import { ProviderToolSelector } from "./ProviderToolSelector";
import { ProviderRefSelector } from "./ProviderRefSelector";
import { ProviderTestResults } from "./ProviderTestResults";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ProviderConfigFormProps {
  selectedFields: ProviderField[];
  isEditDisabled?: boolean;
}

/**
 * ProviderConfigForm component
 * Renders dynamic form fields based on provider schema
 */
export function ProviderConfigForm({
  selectedFields,
  isEditDisabled = false,
}: ProviderConfigFormProps) {
  const { t } = useTranslation(["providers", "common"]);
  const {
    selectedCategory,
    formValues,
    errors,
    setFieldValue,
    setTestInputData,
  } = useProviderSheetStore();

  // Determine if tool selector should be shown (Intent category with functions field)
  const hasFunctionsField =
    selectedCategory === "Intent" &&
    selectedFields.some((field) => field.name === "functions");

  // Get the llm_provider field for ProviderRefSelector (for Intent category)
  // Check by field name or label containing "llm" and "provider"
  const llmProviderField =
    selectedCategory === "Intent"
      ? selectedFields.find(
          (field) =>
            field.name === "llm_provider" ||
            field.name.toLowerCase().includes("llm") ||
            field.label?.toLowerCase().includes("llm provider")
        )
      : undefined;

  // Get the llm field for ProviderRefSelector (for Memory category - mem_local_short)
  // Check by field name "llm" to select LLM provider
  const memoryLlmField =
    selectedCategory === "Memory"
      ? selectedFields.find((field) => field.name === "llm")
      : undefined;

  // Filter out special fields that have custom selectors
  const filteredFields = selectedFields.filter((field) => {
    if (hasFunctionsField && field.name === "functions") return false;
    if (llmProviderField && field.name === llmProviderField.name) return false;
    if (memoryLlmField && field.name === memoryLlmField.name) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Provider Name */}
      <div className="space-y-2">
        <Label htmlFor="name">{t("providers:name")}</Label>
        <Input
          id="name"
          placeholder={t("providers:name_placeholder")}
          disabled={isEditDisabled}
          value={String(formValues.name ?? "")}
          onChange={(e) => setFieldValue("name", e.target.value)}
        />
        {errors.name && (
          <p className="text-sm text-destructive">{errors.name}</p>
        )}
      </div>

      {/* Dynamic Fields */}
      {filteredFields.map((field) => renderField(field, isEditDisabled))}

      {/* Tool Selector for Intent category with functions field */}
      {hasFunctionsField && <ProviderToolSelector disabled={isEditDisabled} />}

      {/* LLM Provider Selector for Intent category with llm_provider field */}
      {llmProviderField && (
        <ProviderRefSelector
          field={llmProviderField}
          providerCategory="LLM"
          disabled={isEditDisabled}
        />
      )}

      {/* LLM Provider Selector for Memory category with llm field (mem_local_short) */}
      {memoryLlmField && (
        <ProviderRefSelector
          field={memoryLlmField}
          providerCategory="LLM"
          disabled={isEditDisabled}
        />
      )}

      {/* Advanced Test Options */}
      <ProviderTestInput
        category={selectedCategory}
        onInputChange={setTestInputData}
        disabled={isEditDisabled}
      />

      {/* Test Results */}
      <ProviderTestResults />
    </div>
  );
}

/**
 * ProviderFieldRenderer component
 * Renders a single field based on type
 */
function ProviderFieldRenderer({
  field,
  isEditDisabled,
}: {
  field: ProviderField;
  isEditDisabled: boolean;
}) {
  const { formValues, errors, setFieldValue } = useProviderSheetStore();
  const value = formValues[field.name];
  const error = errors[field.name];

  return (
    <div key={field.name} className="space-y-2">
      <Label htmlFor={field.name}>
        {field.label}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </Label>

      {field.type === "select" && field.options ? (
        <select
          id={field.name}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isEditDisabled}
          value={String(value ?? "")}
          onChange={(e) => setFieldValue(field.name, e.target.value)}
        >
          <option value="">Select...</option>
          {field.options.map((opt, index) => {
            const optValue = typeof opt === "string" ? opt : opt.value;
            const optLabel = typeof opt === "string" ? opt : opt.label;
            return (
              <option
                key={`${field.name}-opt-${index}-${optValue}`}
                value={optValue}
              >
                {optLabel}
              </option>
            );
          })}
        </select>
      ) : field.type === "boolean" ? (
        <div className="flex items-center space-x-2">
          <input
            type="checkbox"
            id={field.name}
            className="h-4 w-4 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isEditDisabled}
            checked={Boolean(value)}
            onChange={(e) => setFieldValue(field.name, e.target.checked)}
          />
          <Label htmlFor={field.name} className="text-sm font-normal">
            {field.label}
          </Label>
        </div>
      ) : (
        <Input
          id={field.name}
          type={
            field.type === "secret"
              ? "password"
              : field.type === "number" || field.type === "integer"
              ? "number"
              : "text"
          }
          placeholder={field.placeholder}
          disabled={isEditDisabled}
          value={String(value ?? "")}
          onChange={(e) => {
            const newValue =
              field.type === "number" || field.type === "integer"
                ? e.target.value === ""
                  ? ""
                  : Number(e.target.value)
                : e.target.value;
            setFieldValue(field.name, newValue);
          }}
        />
      )}

      {(field.min !== undefined || field.max !== undefined) && (
        <p className="text-xs text-muted-foreground">
          {field.min !== undefined && `Min: ${field.min}`}
          {field.min !== undefined && field.max !== undefined && " | "}
          {field.max !== undefined && `Max: ${field.max}`}
        </p>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}

/**
 * Render field based on type
 */
function renderField(
  field: ProviderField,
  isEditDisabled: boolean
): React.ReactNode {
  return (
    <ProviderFieldRenderer field={field} isEditDisabled={isEditDisabled} />
  );
}
