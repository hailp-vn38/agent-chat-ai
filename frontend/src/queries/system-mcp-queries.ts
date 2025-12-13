import { useQuery, useMutation } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { SYSTEM_MCP_ENDPOINTS } from "@lib/api";
import type {
  SystemMcpServerListResponse,
  SystemMcpServerDetailResponse,
  SystemMcpTestResult,
  SystemMcpReloadResponse,
  SystemMcpListParams,
} from "@types";

/**
 * Query Keys for System MCP server queries
 */
export const systemMcpQueryKeys = {
  all: ["system-mcp-servers"] as const,
  lists: (params?: SystemMcpListParams) =>
    [...systemMcpQueryKeys.all, "list", params] as const,
  list: (params?: SystemMcpListParams) =>
    [...systemMcpQueryKeys.all, "list", params] as const,
  details: () => [...systemMcpQueryKeys.all, "detail"] as const,
  detail: (serverName: string) =>
    [...systemMcpQueryKeys.all, "detail", serverName] as const,
  test: (serverName: string) =>
    [...systemMcpQueryKeys.all, "test", serverName] as const,
};

/**
 * API Service Functions for System MCP Servers (Read-only)
 */
const systemMcpAPI = {
  /**
   * GET /system/mcp-servers
   * Fetch list of all system MCP servers from configuration file
   */
  fetchSystemMcpServers: async (
    params?: SystemMcpListParams
  ): Promise<SystemMcpServerListResponse> => {
    const { data } = await apiClient.get<SystemMcpServerListResponse>(
      SYSTEM_MCP_ENDPOINTS.LIST,
      { params }
    );
    return data;
  },

  /**
   * GET /system/mcp-servers/{server_name}
   * Fetch a specific system MCP server detail by name
   */
  fetchSystemMcpServer: async (
    serverName: string
  ): Promise<SystemMcpServerDetailResponse> => {
    const { data } = await apiClient.get<SystemMcpServerDetailResponse>(
      SYSTEM_MCP_ENDPOINTS.DETAIL(serverName)
    );
    return data;
  },

  /**
   * POST /system/mcp-servers/{server_name}/test
   * Test connection to system MCP server and get tools list
   */
  testSystemMcpServer: async (
    serverName: string
  ): Promise<SystemMcpTestResult> => {
    const { data } = await apiClient.post<SystemMcpTestResult>(
      SYSTEM_MCP_ENDPOINTS.TEST(serverName)
    );
    return data;
  },

  /**
   * POST /system/mcp-servers/reload
   * Reload system MCP configuration (clear cache and reload from file)
   */
  reloadSystemMcpConfig: async (): Promise<SystemMcpReloadResponse> => {
    const { data } = await apiClient.post<SystemMcpReloadResponse>(
      SYSTEM_MCP_ENDPOINTS.RELOAD
    );
    return data;
  },
};

/**
 * Query Hooks for System MCP Servers (Read-only)
 */

/**
 * Hook to fetch list of system MCP servers
 * @param params - Pagination and filter parameters
 * @param enabled - Whether the query should run
 * @returns Query result with list of system MCP servers
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useSystemMcpServers({ page: 1, page_size: 10 });
 * ```
 */
export const useSystemMcpServers = (
  params?: SystemMcpListParams,
  enabled = true
) => {
  return useQuery({
    queryKey: systemMcpQueryKeys.list(params),
    queryFn: () => systemMcpAPI.fetchSystemMcpServers(params),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

/**
 * Hook to fetch a specific system MCP server
 * @param serverName - The name of the system MCP server
 * @param enabled - Whether the query should run
 * @returns Query result with system MCP server details
 *
 * @example
 * ```tsx
 * const { data } = useSystemMcpServer(serverName, !!serverName);
 * ```
 */
export const useSystemMcpServer = (
  serverName: string,
  enabled = !!serverName
) => {
  return useQuery({
    queryKey: systemMcpQueryKeys.detail(serverName),
    queryFn: () => systemMcpAPI.fetchSystemMcpServer(serverName),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

/**
 * Mutation Hook for testing system MCP server connection
 * @returns Mutation object with test function
 *
 * @example
 * ```tsx
 * const { mutate: testServer } = useTestSystemMcpServer();
 * testServer(serverName, {
 *   onSuccess: (result) => {
 *     if (result.success) console.log('Connection OK', result.tools);
 *   },
 * });
 * ```
 */
export const useTestSystemMcpServer = () => {
  return useMutation({
    mutationFn: (serverName: string) =>
      systemMcpAPI.testSystemMcpServer(serverName),
    // No cache - fresh test each time
  });
};

/**
 * Mutation Hook for reloading system MCP configuration
 * @returns Mutation object with reload function
 *
 * @example
 * ```tsx
 * const { mutate: reloadConfig } = useReloadSystemMcpConfig();
 * reloadConfig(undefined, {
 *   onSuccess: (result) => {
 *     console.log('Config reloaded', result.data.server_names);
 *   },
 * });
 * ```
 */
export const useReloadSystemMcpConfig = () => {
  return useMutation({
    mutationFn: () => systemMcpAPI.reloadSystemMcpConfig(),
    onSuccess: () => {
      // Invalidate all system MCP queries to refresh with new config
      // Note: useQueryClient would need to be passed in or accessed via context
      // This is a basic mutation without automatic cache invalidation
    },
  });
};
