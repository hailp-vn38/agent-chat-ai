import type { Provider, ProviderCategory, ProviderTestInputData } from "@types";

/**
 * Test result state with output data
 */
export interface TestResultState {
  success: boolean;
  message?: string;
  error?: string;
  latency_ms?: number;
  text_output?: string;
  audio_base64?: string;
  audio_format?: string;
}

/**
 * Validation result state
 */
export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * ProviderSheet component props
 */
export interface ProviderSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "update";
  provider?: Provider | null;
  onSubmit: (data: {
    name: string;
    category: ProviderCategory;
    type: string;
    config: Record<string, unknown>;
    is_active?: boolean;
  }) => Promise<void>;
  onDuplicate?: (provider: Provider) => void;
  isLoading?: boolean;
}

/**
 * ProviderSheet Zustand store state and actions
 */
export interface ProviderSheetState {
  // Sheet state
  isOpen: boolean;
  mode: "create" | "update";

  // Provider data
  provider: Provider | null;

  // Form state
  selectedCategory: ProviderCategory | null;
  selectedType: string | null;
  formValues: Record<string, unknown>;
  selectedTools: string[];

  // Validation state
  errors: Record<string, string>;
  validationResult: ValidationResult | null;
  testResult: TestResultState | null;
  testInputData: ProviderTestInputData | null;

  // UI state
  isToolsPopoverOpen: boolean;
}

/**
 * ProviderSheet store actions
 */
export interface ProviderSheetActions {
  // Sheet control
  openSheet: (
    mode: "create" | "update",
    provider?: Provider,
    initialCategory?: ProviderCategory
  ) => void;
  closeSheet: () => void;

  // Category & Type
  selectCategory: (category: ProviderCategory) => void;
  selectType: (type: string) => void;

  // Form
  setFieldValue: (field: string, value: unknown) => void;
  setFormValues: (values: Record<string, unknown>) => void;

  // Tools
  toggleTool: (toolRef: string) => void;
  setSelectedTools: (tools: string[]) => void;
  setToolsPopoverOpen: (open: boolean) => void;

  // Validation
  setErrors: (errors: Record<string, string>) => void;
  clearFieldError: (field: string) => void;
  setValidationResult: (result: ValidationResult | null) => void;
  setTestResult: (result: TestResultState | null) => void;
  setTestInputData: (data: ProviderTestInputData | null) => void;

  // Reset
  resetForm: () => void;
  resetSheet: () => void;
}

/**
 * Combined store type
 */
export type ProviderSheetStore = ProviderSheetState & ProviderSheetActions;

/**
 * Category list configuration
 */
export const CATEGORY_LIST: ProviderCategory[] = [
  "LLM",
  "TTS",
  "ASR",
  "VAD",
  "Memory",
  "Intent",
];
