/**
 * Plugin Management Types
 * Based on plugin-management-endpoints.md
 */

/**
 * Plugin category
 */
export type PluginCategory = string; // Could be enum if fixed set exists

/**
 * Tool provided by a plugin
 */
export interface PluginTool {
  name: string;
  description: string;
  input_schema?: Record<string, unknown>;
}

/**
 * Plugin information
 */
export interface Plugin {
  name: string;
  display_name: string;
  description: string;
  version: string;
  category: PluginCategory;
  enabled: boolean;
  tools_count: number;
  tools?: PluginTool[];
}

/**
 * Response for plugin list endpoint
 */
export interface PluginListResponse {
  success: boolean;
  data: Plugin[];
  total: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
}

/**
 * Response for plugin detail endpoint
 */
export interface PluginDetailResponse {
  success: boolean;
  data: Plugin;
}

/**
 * Payload for testing a plugin tool
 */
export interface TestPluginPayload {
  tool_name: string;
  args?: Record<string, unknown>;
}

/**
 * Result of plugin tool test
 */
export interface PluginTestResult {
  success: boolean;
  result?: unknown;
  error?: string;
  message?: string;
}

/**
 * Payload for validating plugin arguments
 */
export interface ValidatePluginPayload {
  tool_name: string;
  args?: Record<string, unknown>;
}

/**
 * Result of plugin argument validation
 */
export interface PluginValidationResult {
  success: boolean;
  valid: boolean;
  errors?: Array<{
    field: string;
    message: string;
  }>;
}

/**
 * Plugin category info
 */
export interface PluginCategoryInfo {
  name: PluginCategory;
  display_name: string;
  description?: string;
}

/**
 * Response for plugin categories endpoint
 */
export interface PluginCategoriesResponse {
  success: boolean;
  data: PluginCategoryInfo[];
}

/**
 * Filters for listing plugins
 */
export interface PluginListFilters {
  page?: number;
  page_size?: number;
  search?: string;
  category?: PluginCategory;
  enabled?: boolean;
}
