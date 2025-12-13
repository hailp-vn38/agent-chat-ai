import { useQuery, useMutation } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { PLUGIN_ENDPOINTS } from "@lib/api";
import type {
  PluginDetailResponse,
  PluginListResponse,
  PluginListFilters,
  TestPluginPayload,
  PluginTestResult,
  ValidatePluginPayload,
  PluginValidationResult,
  PluginCategoriesResponse,
} from "@types";

/**
 * Query Keys for Plugin Management queries
 */
export const pluginQueryKeys = {
  all: ["plugins"] as const,
  lists: (filters?: PluginListFilters) =>
    [...pluginQueryKeys.all, "list", filters] as const,
  list: (filters?: PluginListFilters) =>
    [...pluginQueryKeys.all, "list", filters] as const,
  details: () => [...pluginQueryKeys.all, "detail"] as const,
  detail: (name: string) => [...pluginQueryKeys.all, "detail", name] as const,
  categories: () => [...pluginQueryKeys.all, "categories"] as const,
  test: (name: string) => [...pluginQueryKeys.all, "test", name] as const,
};

/**
 * API Service Functions for Plugin Management
 */
const pluginAPI = {
  /**
   * GET /tools/plugins
   * Fetch list of plugins with filters
   */
  fetchPlugins: async (
    filters?: PluginListFilters
  ): Promise<PluginListResponse> => {
    const { data } = await apiClient.get<PluginListResponse>(
      PLUGIN_ENDPOINTS.LIST,
      { params: filters }
    );
    return data;
  },

  /**
   * GET /tools/plugins/{plugin_name}
   * Fetch detailed information about a specific plugin
   */
  fetchPluginDetails: async (
    pluginName: string
  ): Promise<PluginDetailResponse> => {
    const { data } = await apiClient.get<PluginDetailResponse>(
      PLUGIN_ENDPOINTS.DETAIL(pluginName)
    );
    return data;
  },

  /**
   * GET /tools/plugins/categories/list
   * Fetch available plugin categories
   */
  fetchPluginCategories: async (): Promise<PluginCategoriesResponse> => {
    const { data } = await apiClient.get<PluginCategoriesResponse>(
      PLUGIN_ENDPOINTS.CATEGORIES
    );
    return data;
  },

  /**
   * POST /tools/plugins/{plugin_name}/test
   * Test a plugin tool
   */
  testPlugin: async (
    pluginName: string,
    payload: TestPluginPayload
  ): Promise<PluginTestResult> => {
    const { data } = await apiClient.post<PluginTestResult>(
      PLUGIN_ENDPOINTS.TEST(pluginName),
      payload,
      { timeout: 30000 } // 30 second timeout
    );
    return data;
  },

  /**
   * POST /tools/plugins/{plugin_name}/validate
   * Validate plugin tool arguments
   */
  validatePluginArgs: async (
    pluginName: string,
    payload: ValidatePluginPayload
  ): Promise<PluginValidationResult> => {
    const { data } = await apiClient.post<PluginValidationResult>(
      PLUGIN_ENDPOINTS.VALIDATE(pluginName),
      payload
    );
    return data;
  },
};

/**
 * Query Hooks for Plugin Management
 */

/**
 * Hook to fetch list of plugins with optional filtering
 * @param filters - Search, category, and pagination filters
 * @param enabled - Whether the query should run
 * @returns Query result with plugin list
 *
 * @example
 * ```tsx
 * const { data } = usePlugins({
 *   search: 'weather',
 *   category: 'weather',
 *   page: 1,
 *   page_size: 10,
 * });
 * ```
 */
export const usePlugins = (filters?: PluginListFilters, enabled = true) => {
  return useQuery({
    queryKey: pluginQueryKeys.list(filters),
    queryFn: () => pluginAPI.fetchPlugins(filters),
    enabled,
    staleTime: 1000 * 60 * 15, // 15 minutes
  });
};

/**
 * Hook to fetch detailed information about a plugin
 * @param pluginName - The name of the plugin
 * @param enabled - Whether the query should run
 * @returns Query result with plugin details
 *
 * @example
 * ```tsx
 * const { data } = usePluginDetails(pluginName, !!pluginName);
 * ```
 */
export const usePluginDetails = (
  pluginName: string,
  enabled = !!pluginName
) => {
  return useQuery({
    queryKey: pluginQueryKeys.detail(pluginName),
    queryFn: () => pluginAPI.fetchPluginDetails(pluginName),
    enabled,
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
};

/**
 * Hook to fetch available plugin categories
 * @returns Query result with plugin categories
 *
 * @example
 * ```tsx
 * const { data } = usePluginCategories();
 * ```
 */
export const usePluginCategories = () => {
  return useQuery({
    queryKey: pluginQueryKeys.categories(),
    queryFn: () => pluginAPI.fetchPluginCategories(),
    staleTime: 1000 * 60 * 30, // 30 minutes (categories rarely change)
  });
};

/**
 * Mutation Hook for testing a plugin tool
 * @returns Mutation object with test function
 *
 * @example
 * ```tsx
 * const { mutate: testTool, isPending } = useTestPlugin();
 * testTool(
 *   {
 *     pluginName: 'weather',
 *     payload: { tool_name: 'get_weather', args: { city: 'Ho Chi Minh' } },
 *   },
 *   {
 *     onSuccess: (result) => {
 *       console.log('Test passed:', result);
 *     },
 *   }
 * );
 * ```
 */
export const useTestPlugin = () => {
  return useMutation({
    mutationFn: ({
      pluginName,
      payload,
    }: {
      pluginName: string;
      payload: TestPluginPayload;
    }) => pluginAPI.testPlugin(pluginName, payload),
    // No cache - fresh test each time
  });
};

/**
 * Mutation Hook for validating plugin tool arguments
 * @returns Mutation object with validate function
 *
 * @example
 * ```tsx
 * const { mutate: validateArgs, isPending } = useValidatePluginArgs();
 * validateArgs(
 *   {
 *     pluginName: 'weather',
 *     payload: { tool_name: 'get_weather', args: { city: 'Ho Chi Minh' } },
 *   },
 *   {
 *     onSuccess: (result) => {
 *       if (result.valid) console.log('Args are valid');
 *     },
 *   }
 * );
 * ```
 */
export const useValidatePluginArgs = () => {
  return useMutation({
    mutationFn: ({
      pluginName,
      payload,
    }: {
      pluginName: string;
      payload: ValidatePluginPayload;
    }) => pluginAPI.validatePluginArgs(pluginName, payload),
    // No cache - validation results are transient
  });
};
