import { create } from "zustand";
import { devtools } from "zustand/middleware";

import type { ProviderCategory } from "@types";
import type {
  ProviderSheetStore,
  TestResultState,
  ValidationResult,
} from "@/components/provider-sheet/types";
import type { ProviderTestInputData } from "@types";

/**
 * Zustand store for ProviderSheet state management
 * Centralizes all state related to provider sheet operations
 */
export const useProviderSheetStore = create<ProviderSheetStore>()(
  devtools(
    (set, get) => ({
      // Initial state
      isOpen: false,
      mode: "create" as const,
      provider: null,
      selectedCategory: null,
      selectedType: null,
      formValues: { name: "" },
      selectedTools: [],
      errors: {},
      validationResult: null,
      testResult: null,
      testInputData: null,
      isToolsPopoverOpen: false,

      // Sheet control actions
      openSheet: (mode, provider, initialCategory) => {
        const formValues = provider
          ? { name: provider.name, ...provider.config }
          : { name: "" };

        const selectedTools = provider?.config?.functions
          ? (provider.config.functions as string[])
          : [];

        // Ưu tiên: provider.category > initialCategory > null
        const category = provider?.category ?? initialCategory ?? null;

        set({
          isOpen: true,
          mode,
          provider: provider ?? null,
          selectedCategory: category,
          selectedType: provider?.type ?? null,
          formValues,
          selectedTools,
          errors: {},
          validationResult: null,
          testResult: null,
          testInputData: null,
          isToolsPopoverOpen: false,
        });
      },

      closeSheet: () => {
        set({
          isOpen: false,
        });
      },

      // Category & Type selection
      selectCategory: (category: ProviderCategory) => {
        set({
          selectedCategory: category,
          selectedType: null,
          formValues: { name: get().formValues.name },
          validationResult: null,
          testResult: null,
          testInputData: null,
          selectedTools: [],
          errors: {},
        });
      },

      selectType: (type: string) => {
        set({
          selectedType: type,
          validationResult: null,
          testResult: null,
          selectedTools: [],
          errors: {},
        });
      },

      // Form value management
      setFieldValue: (field: string, value: unknown) => {
        const formValues = { ...get().formValues, [field]: value };
        set({ formValues });

        // Clear field error when value changes
        const errors = { ...get().errors };
        if (errors[field]) {
          delete errors[field];
          set({ errors });
        }
      },

      setFormValues: (values: Record<string, unknown>) => {
        set({ formValues: values });
      },

      // Tool management
      toggleTool: (toolRef: string) => {
        const selectedTools = get().selectedTools;
        const newTools = selectedTools.includes(toolRef)
          ? selectedTools.filter((t) => t !== toolRef)
          : [...selectedTools, toolRef];
        set({ selectedTools: newTools });
      },

      setSelectedTools: (tools: string[]) => {
        set({ selectedTools: tools });
      },

      setToolsPopoverOpen: (open: boolean) => {
        set({ isToolsPopoverOpen: open });
      },

      // Validation & testing
      setErrors: (errors: Record<string, string>) => {
        set({ errors });
      },

      clearFieldError: (field: string) => {
        const errors = { ...get().errors };
        delete errors[field];
        set({ errors });
      },

      setValidationResult: (result: ValidationResult | null) => {
        set({ validationResult: result });
      },

      setTestResult: (result: TestResultState | null) => {
        set({ testResult: result });
      },

      setTestInputData: (data: ProviderTestInputData | null) => {
        set({ testInputData: data });
      },

      // Reset functions
      resetForm: () => {
        set({
          selectedCategory: null,
          selectedType: null,
          formValues: { name: "" },
          selectedTools: [],
          errors: {},
          validationResult: null,
          testResult: null,
          testInputData: null,
          isToolsPopoverOpen: false,
        });
      },

      resetSheet: () => {
        set({
          isOpen: false,
          mode: "create" as const,
          provider: null,
          selectedCategory: null,
          selectedType: null,
          formValues: { name: "" },
          selectedTools: [],
          errors: {},
          validationResult: null,
          testResult: null,
          testInputData: null,
          isToolsPopoverOpen: false,
        });
      },
    }),
    { name: "provider-sheet" }
  )
);
