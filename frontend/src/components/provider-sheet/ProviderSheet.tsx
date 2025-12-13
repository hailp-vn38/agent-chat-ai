"use client";

import { memo, useCallback, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Copy, Loader2, Trash2 } from "lucide-react";

import type { Provider, ProviderCategory } from "@types";
import { useProviderSheetStore } from "@/store/provider-sheet.store";
import {
  useProviderSchemaCategories,
  useValidateProviderConfig,
  useTestProviderConnection,
  useTestProviderReference,
} from "@/queries";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ProviderCategoryTabs } from "./ProviderCategoryTabs";

export interface ProviderSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "update";
  provider?: Provider | null;
  /** Initial category khi mở sheet ở create mode */
  initialCategory?: ProviderCategory | null;
  onSubmit: (data: {
    name: string;
    category: ProviderCategory;
    type: string;
    config: Record<string, unknown>;
    is_active?: boolean;
  }) => Promise<void>;
  onDuplicate?: (provider: Provider) => void;
  onDelete?: (provider: Provider) => void;
  isLoading?: boolean;
}

function ProviderSheetComponent({
  open,
  onOpenChange,
  mode,
  provider,
  initialCategory,
  onSubmit,
  onDuplicate,
  onDelete,
  isLoading = false,
}: ProviderSheetProps) {
  const { t } = useTranslation(["providers", "common"]);

  // Store actions and state
  const {
    selectedCategory,
    selectedType,
    formValues,
    openSheet,
    closeSheet,
    setErrors,
    setValidationResult,
    setTestResult,
  } = useProviderSheetStore();

  // Check if provider is editable (only user providers can be edited)
  const isReadOnly = mode === "update" && provider?.source === "default";
  const canEdit = provider?.permissions?.includes("edit") ?? true;
  const canTest = provider?.permissions?.includes("test") ?? true;
  const canDelete = provider?.permissions?.includes("delete") ?? true;

  // Schema data
  const { data: schemaData, isLoading: isSchemaLoading } =
    useProviderSchemaCategories();

  // Mutations
  const { mutate: validateConfig, isPending: isValidating } =
    useValidateProviderConfig();
  const { mutate: testConnection, isPending: isTesting } =
    useTestProviderConnection();
  const { mutate: testReference, isPending: isTestingReference } =
    useTestProviderReference();

  // Get fields for selected type
  const selectedFields = useMemo(() => {
    if (!schemaData?.data || !selectedCategory || !selectedType) return [];
    const typeSchema =
      schemaData.data[selectedCategory as keyof typeof schemaData.data]?.[
        selectedType as keyof (typeof schemaData.data)[keyof typeof schemaData.data]
      ];
    return typeSchema?.fields ?? [];
  }, [schemaData, selectedCategory, selectedType]);

  // Reset state when sheet opens/closes
  useEffect(() => {
    if (open) {
      openSheet(mode, provider ?? undefined, initialCategory ?? undefined);
    } else {
      closeSheet();
    }
  }, [open, mode, provider, initialCategory, openSheet, closeSheet]);

  const isFormDisabled =
    isLoading || isValidating || isTesting || isTestingReference;
  // Disable inputs khi đang loading hoặc không có quyền edit
  const isInputsDisabled = isFormDisabled || (mode === "update" && !canEdit);
  const canSubmit = Boolean(
    selectedCategory &&
      selectedType &&
      formValues.name &&
      !isReadOnly &&
      canEdit
  );
  const canTestConnection = isReadOnly
    ? canTest && Boolean(provider?.reference)
    : Boolean(selectedCategory && selectedType);

  // Form validation
  const validateForm = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    // Validate name
    if (!formValues.name || String(formValues.name).trim() === "") {
      newErrors.name = t("providers:name_required");
    }

    // Validate required fields
    selectedFields.forEach((field) => {
      if (field.required) {
        const value = formValues[field.name];
        if (value === undefined || value === null || value === "") {
          newErrors[field.name] = `${field.label} is required`;
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formValues, selectedFields, setErrors, t]);

  // Validate configuration
  const handleValidate = useCallback(() => {
    if (!selectedCategory || !selectedType || !validateForm()) return;

    const config = Object.fromEntries(
      Object.entries(formValues).filter(([key]) => key !== "name")
    );

    // Get fresh selectedTools from store
    const { selectedTools: currentSelectedTools } =
      useProviderSheetStore.getState();

    // Add selected tools to config for Intent category (if tools selected)
    const finalConfig = { ...config };
    if (selectedCategory === "Intent" && currentSelectedTools.length > 0) {
      finalConfig.functions = currentSelectedTools;
    }

    validateConfig(
      {
        category: selectedCategory,
        type: selectedType,
        config: finalConfig as Record<string, unknown>,
      },
      {
        onSuccess: (result) => {
          setValidationResult({
            valid: result.valid,
            errors: result.errors,
          });
        },
        onError: (error) => {
          setValidationResult({
            valid: false,
            errors: [error.message],
          });
        },
      }
    );
  }, [
    selectedCategory,
    selectedType,
    formValues,
    validateForm,
    validateConfig,
    setValidationResult,
  ]);

  // Test connection
  const handleTestConnection = useCallback(() => {
    // For default providers with reference, use test-reference endpoint
    if (isReadOnly && provider?.reference) {
      const { testInputData } = useProviderSheetStore.getState();
      testReference(
        {
          reference: provider.reference,
          input_data: testInputData,
        },
        {
          onSuccess: (result) => {
            setValidationResult({
              valid: result.valid,
              errors: result.errors,
            });
            if (result.test_result) {
              setTestResult({
                success: result.test_result.success,
                message: result.test_result.message,
                error: result.test_result.error,
                latency_ms: result.test_result.latency_ms,
                text_output: result.test_result.output?.text,
                audio_base64: result.test_result.output?.audio_base64,
                audio_format: result.test_result.output?.audio_format,
              });
            }
          },
          onError: (error) => {
            setTestResult({
              success: false,
              error: error.message,
            });
          },
        }
      );
      return;
    }

    // For user providers, validate form and use test endpoint
    if (!selectedCategory || !selectedType || !validateForm()) return;

    const config = Object.fromEntries(
      Object.entries(formValues).filter(([key]) => key !== "name")
    );
    const { testInputData, selectedTools: currentSelectedTools } =
      useProviderSheetStore.getState();

    // Add selected tools to config for Intent category (if tools selected)
    const finalConfig = { ...config };
    if (selectedCategory === "Intent" && currentSelectedTools.length > 0) {
      finalConfig.functions = currentSelectedTools;
    }

    testConnection(
      {
        category: selectedCategory,
        type: selectedType,
        config: finalConfig as Record<string, unknown>,
        input_data: testInputData,
      },
      {
        onSuccess: (result) => {
          setValidationResult({
            valid: result.valid,
            errors: result.errors,
          });
          setTestResult({
            success: result.test_result.success,
            message: result.test_result.message,
            error: result.test_result.error,
            latency_ms: result.test_result.latency_ms,
            text_output: result.test_result.output?.text,
            audio_base64: result.test_result.output?.audio_base64,
            audio_format: result.test_result.output?.audio_format,
          });
        },
        onError: (error) => {
          setTestResult({
            success: false,
            error: error.message,
          });
        },
      }
    );
  }, [
    isReadOnly,
    provider?.reference,
    selectedCategory,
    selectedType,
    formValues,
    validateForm,
    testReference,
    testConnection,
    setValidationResult,
    setTestResult,
  ]);

  // Form submission
  const handleFormSubmit = useCallback(async () => {
    if (!selectedCategory || !selectedType || !validateForm()) return;

    // Get fresh state from store to ensure we have latest selectedTools
    const {
      formValues: currentFormValues,
      selectedTools: currentSelectedTools,
    } = useProviderSheetStore.getState();

    const { name, ...config } = currentFormValues;

    // Add selected tools to config for Intent category (if tools selected)
    const finalConfig = { ...config };
    if (selectedCategory === "Intent" && currentSelectedTools.length > 0) {
      finalConfig.functions = currentSelectedTools;
    }

    await onSubmit({
      name: String(name),
      category: selectedCategory,
      type: selectedType,
      config: finalConfig,
      is_active: provider?.is_active ?? true,
    });
  }, [selectedCategory, selectedType, validateForm, onSubmit, provider]);

  // Handle duplicate provider
  const handleDuplicate = useCallback(() => {
    if (!provider || !onDuplicate) return;

    const duplicateProvider: Provider = {
      ...provider,
      id: "",
      name: `${formValues.name || provider.name} (Copy)`,
      config: { ...provider.config },
      source: "user",
      permissions: ["edit", "delete", "test"],
    };

    // Update config from current form values
    selectedFields.forEach((field) => {
      if (formValues[field.name] !== undefined) {
        duplicateProvider.config[field.name] = formValues[field.name];
      }
    });

    onDuplicate(duplicateProvider);
  }, [provider, onDuplicate, formValues, selectedFields]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg px-0">
        <SheetHeader className="px-6">
          <SheetTitle>
            {mode === "create"
              ? t("providers:create_provider")
              : t("providers:update_provider")}
          </SheetTitle>
          <SheetDescription>
            {isReadOnly
              ? t("providers:default_provider_readonly")
              : mode === "create"
              ? t("providers:create_provider_description")
              : t("providers:update_provider_description")}
          </SheetDescription>
        </SheetHeader>

        {isSchemaLoading ? (
          <div className="space-y-4 py-4 px-6">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : (
          // Always show tabs - form visibility is controlled inside ProviderCategoryTabs
          <div className="space-y-6 py-4 px-6">
            <ProviderCategoryTabs
              schemaData={schemaData?.data}
              isFormDisabled={isInputsDisabled}
            />
          </div>
        )}

        <SheetFooter className="flex flex-row flex-wrap gap-2 pt-4 px-6 mb-[50px]">
          {/* Delete Button - Show in update mode if has delete permission */}
          {mode === "update" && onDelete && canDelete && (
            <Button
              type="button"
              variant="destructive"
              onClick={() => provider && onDelete(provider)}
              disabled={isFormDisabled}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t("common:delete")}
            </Button>
          )}

          {/* Duplicate Button - Show in update mode */}
          {mode === "update" && onDuplicate && (
            <Button
              type="button"
              variant="secondary"
              onClick={handleDuplicate}
              disabled={isFormDisabled}
            >
              <Copy className="mr-2 h-4 w-4" />
              {t("providers:duplicate")}
            </Button>
          )}

          {/* Validate Button - Only for editable providers */}
          {!isReadOnly && (
            <Button
              type="button"
              variant="outline"
              onClick={handleValidate}
              disabled={!canSubmit || isFormDisabled}
            >
              {isValidating && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {t("providers:validate")}
            </Button>
          )}

          {/* Test Connection Button */}
          <Button
            type="button"
            variant="outline"
            onClick={handleTestConnection}
            disabled={!canTestConnection || isTesting || isTestingReference}
          >
            {(isTesting || isTestingReference) && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {t("providers:test_connection")}
          </Button>

          {/* Save Button - Only show for editable providers */}
          {!isReadOnly && canEdit && (
            <Button
              type="button"
              onClick={handleFormSubmit}
              disabled={!canSubmit || isFormDisabled}
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === "create"
                ? t("providers:create")
                : t("providers:update")}
            </Button>
          )}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export const ProviderSheet = memo(ProviderSheetComponent);
