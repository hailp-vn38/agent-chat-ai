import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { MCP_ENDPOINTS } from "@lib/api";
import type {
  McpConfigCreatePayload,
  McpConfigUpdatePayload,
  McpConfigListResponse,
  McpConfigDetailResponse,
  McpTestResult,
  McpListParams,
  McpTestRawPayload,
  McpTestRawResponse,
  McpRefreshToolsResponse,
} from "@types";

/**
 * Query Keys for MCP config queries
 */
export const mcpQueryKeys = {
  all: ["mcp-configs"] as const,
  lists: (params?: McpListParams) =>
    [...mcpQueryKeys.all, "list", params] as const,
  list: (params?: McpListParams) =>
    [...mcpQueryKeys.all, "list", params] as const,
  details: () => [...mcpQueryKeys.all, "detail"] as const,
  detail: (id: string) => [...mcpQueryKeys.all, "detail", id] as const,
  test: (id: string) => [...mcpQueryKeys.all, "test", id] as const,
};

/**
 * API Service Functions for MCP Configurations
 */
const mcpConfigAPI = {
  /**
   * GET /users/me/mcp-configs
   * Fetch list of MCP configurations with pagination support
   */
  fetchMcpConfigs: async (
    params?: McpListParams
  ): Promise<McpConfigListResponse> => {
    const { data } = await apiClient.get<McpConfigListResponse>(
      MCP_ENDPOINTS.LIST,
      { params }
    );
    return data;
  },

  /**
   * GET /users/me/mcp-configs/{config_id}
   * Fetch a specific MCP configuration
   */
  fetchMcpConfig: async (
    configId: string
  ): Promise<McpConfigDetailResponse> => {
    const { data } = await apiClient.get<McpConfigDetailResponse>(
      MCP_ENDPOINTS.DETAIL(configId)
    );
    return data;
  },

  /**
   * POST /users/me/mcp-configs
   * Create a new MCP configuration
   */
  createMcpConfig: async (
    payload: McpConfigCreatePayload
  ): Promise<McpConfigDetailResponse> => {
    const { data } = await apiClient.post<McpConfigDetailResponse>(
      MCP_ENDPOINTS.LIST,
      payload
    );
    return data;
  },

  /**
   * PUT /users/me/mcp-configs/{config_id}
   * Update an existing MCP configuration
   */
  updateMcpConfig: async (
    configId: string,
    payload: McpConfigUpdatePayload
  ): Promise<McpConfigDetailResponse> => {
    const { data } = await apiClient.put<McpConfigDetailResponse>(
      MCP_ENDPOINTS.DETAIL(configId),
      payload
    );
    return data;
  },

  /**
   * DELETE /users/me/mcp-configs/{config_id}
   * Delete an MCP configuration
   */
  deleteMcpConfig: async (configId: string): Promise<{ success: boolean }> => {
    const { data } = await apiClient.delete<{ success: boolean }>(
      MCP_ENDPOINTS.DETAIL(configId)
    );
    return data;
  },

  /**
   * POST /users/me/mcp-configs/{config_id}/test
   * Test an MCP configuration connection
   */
  testMcpConfig: async (configId: string): Promise<McpTestResult> => {
    const { data } = await apiClient.post<McpTestResult>(
      MCP_ENDPOINTS.TEST(configId)
    );
    return data;
  },

  /**
   * POST /users/me/mcp-configs/test-raw
   * Test MCP configuration before saving to database
   */
  testRawMcpConfig: async (
    payload: McpTestRawPayload
  ): Promise<McpTestRawResponse> => {
    const { data } = await apiClient.post<McpTestRawResponse>(
      MCP_ENDPOINTS.TEST_RAW,
      payload,
      { timeout: 30000 } // 30s timeout
    );
    return data;
  },

  /**
   * POST /users/me/mcp-configs/{config_id}/refresh-tools
   * Refresh tools list from MCP server
   */
  refreshMcpTools: async (
    configId: string
  ): Promise<McpRefreshToolsResponse> => {
    const { data } = await apiClient.post<McpRefreshToolsResponse>(
      MCP_ENDPOINTS.REFRESH_TOOLS(configId)
    );
    return data;
  },
};

/**
 * Query Hooks for MCP Configurations
 */

/**
 * Hook to fetch list of MCP configurations
 * @param params - Pagination and filter parameters
 * @param enabled - Whether the query should run
 * @returns Query result with list of MCP configs
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useMcpConfigs({ page: 1, page_size: 10 });
 * ```
 */
export const useMcpConfigs = (params?: McpListParams, enabled = true) => {
  return useQuery({
    queryKey: mcpQueryKeys.list(params),
    queryFn: () => mcpConfigAPI.fetchMcpConfigs(params),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

/**
 * Hook to fetch a specific MCP configuration
 * @param configId - The ID of the MCP configuration
 * @param enabled - Whether the query should run
 * @returns Query result with MCP config details
 *
 * @example
 * ```tsx
 * const { data } = useMcpConfig(configId, !!configId);
 * ```
 */
export const useMcpConfig = (configId: string, enabled = !!configId) => {
  return useQuery({
    queryKey: mcpQueryKeys.detail(configId),
    queryFn: () => mcpConfigAPI.fetchMcpConfig(configId),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

/**
 * Mutation Hook for creating MCP configuration
 * @returns Mutation object with create function
 *
 * @example
 * ```tsx
 * const { mutate: createConfig } = useCreateMcpConfig();
 * createConfig(payload, {
 *   onSuccess: () => console.log('Created'),
 * });
 * ```
 */
export const useCreateMcpConfig = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: McpConfigCreatePayload) =>
      mcpConfigAPI.createMcpConfig(payload),
    onSuccess: (data) => {
      // Invalidate list query to refetch
      queryClient.invalidateQueries({
        queryKey: mcpQueryKeys.lists(),
      });
      // Add new config to cache
      queryClient.setQueryData(mcpQueryKeys.detail(data.data.id), {
        data: data.data,
      });
    },
  });
};

/**
 * Mutation Hook for updating MCP configuration
 * @returns Mutation object with update function
 *
 * @example
 * ```tsx
 * const { mutate: updateConfig } = useUpdateMcpConfig();
 * updateConfig({ configId, payload });
 * ```
 */
export const useUpdateMcpConfig = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      configId,
      payload,
    }: {
      configId: string;
      payload: McpConfigUpdatePayload;
    }) => mcpConfigAPI.updateMcpConfig(configId, payload),
    onSuccess: (data, variables) => {
      // Update detail query cache
      queryClient.setQueryData(mcpQueryKeys.detail(variables.configId), {
        data: data.data,
      });
      // Invalidate list query
      queryClient.invalidateQueries({
        queryKey: mcpQueryKeys.lists(),
      });
    },
  });
};

/**
 * Mutation Hook for deleting MCP configuration
 * @returns Mutation object with delete function
 *
 * @example
 * ```tsx
 * const { mutate: deleteConfig } = useDeleteMcpConfig();
 * deleteConfig(configId);
 * ```
 */
export const useDeleteMcpConfig = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (configId: string) => mcpConfigAPI.deleteMcpConfig(configId),
    onSuccess: (_, configId) => {
      // Remove from detail cache
      queryClient.removeQueries({
        queryKey: mcpQueryKeys.detail(configId),
      });
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: mcpQueryKeys.lists(),
      });
    },
  });
};

/**
 * Mutation Hook for testing MCP configuration connection
 * @returns Mutation object with test function
 *
 * @example
 * ```tsx
 * const { mutate: testConfig } = useTestMcpConfig();
 * testConfig(configId, {
 *   onSuccess: (result) => {
 *     if (result.success) console.log('Connection OK');
 *   },
 * });
 * ```
 */
export const useTestMcpConfig = () => {
  return useMutation({
    mutationFn: (configId: string) => mcpConfigAPI.testMcpConfig(configId),
    // No cache - fresh test each time
  });
};

/**
 * Mutation Hook for testing raw MCP configuration before saving
 * @returns Mutation object with test-raw function
 *
 * @example
 * ```tsx
 * const { mutate: testRaw } = useTestRawMcpConfig();
 * testRaw(payload, {
 *   onSuccess: (result) => {
 *     if (result.success) console.log('Test OK', result.tools);
 *   },
 * });
 * ```
 */
export const useTestRawMcpConfig = () => {
  return useMutation({
    mutationFn: (payload: McpTestRawPayload) =>
      mcpConfigAPI.testRawMcpConfig(payload),
    // No caching - always fresh test
  });
};

/**
 * Mutation Hook for refreshing tools from MCP server
 * @returns Mutation object with refresh function
 *
 * @example
 * ```tsx
 * const { mutate: refreshTools } = useRefreshMcpTools();
 * refreshTools(configId, {
 *   onSuccess: (result) => {
 *     console.log('Added:', result.added.length);
 *   },
 * });
 * ```
 */
export const useRefreshMcpTools = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (configId: string) => mcpConfigAPI.refreshMcpTools(configId),
    onSuccess: (data, configId) => {
      // Update config detail cache with new tools
      queryClient.setQueryData(mcpQueryKeys.detail(configId), (old: any) => ({
        ...old,
        data: {
          ...old?.data,
          tools: data.tools,
          tools_last_synced_at: data.tools_last_synced_at,
        },
      }));
      // Invalidate list to update tools count in cards
      queryClient.invalidateQueries({
        queryKey: mcpQueryKeys.lists(),
      });
    },
  });
};
