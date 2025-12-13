import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { AGENT_MCP_ENDPOINTS } from "@lib/api";
import type {
  UpdateAgentMcpPayload,
  AgentMcpSelectionResponse,
  AvailableMcpServersResponse,
  McpSourceFilter,
} from "@types";

/**
 * Query Keys for Agent MCP Selection queries
 * Refactored from agent tool selection
 */
export const agentMcpQueryKeys = {
  all: ["agent-mcp"] as const,
  byAgent: (agentId: string) =>
    [...agentMcpQueryKeys.all, "agent", agentId] as const,
  selection: (agentId: string) =>
    [...agentMcpQueryKeys.byAgent(agentId), "selection"] as const,
  availableServers: (agentId: string, source?: McpSourceFilter) =>
    [
      ...agentMcpQueryKeys.byAgent(agentId),
      "available",
      source || "all",
    ] as const,
};

/**
 * API Service Functions for Agent MCP Selection
 */
const agentMcpAPI = {
  /**
   * GET /agents/{agent_id}/mcp
   * Fetch current MCP selection for an agent
   */
  fetchAgentMcp: async (
    agentId: string
  ): Promise<AgentMcpSelectionResponse> => {
    const { data } = await apiClient.get<AgentMcpSelectionResponse>(
      AGENT_MCP_ENDPOINTS.SELECTION(agentId)
    );
    return data;
  },

  /**
   * PUT /agents/{agent_id}/mcp
   * Update MCP selection for an agent
   */
  updateAgentMcp: async (
    agentId: string,
    payload: UpdateAgentMcpPayload
  ): Promise<AgentMcpSelectionResponse> => {
    const { data } = await apiClient.put<AgentMcpSelectionResponse>(
      AGENT_MCP_ENDPOINTS.SELECTION(agentId),
      payload
    );
    return data;
  },

  /**
   * GET /agents/{agent_id}/mcp/available?source=all|user|config
   * Fetch available MCP servers for an agent
   */
  fetchAvailableMcpServers: async (
    agentId: string,
    source: McpSourceFilter = "all"
  ): Promise<AvailableMcpServersResponse> => {
    const { data } = await apiClient.get<{
      success: boolean;
      message: string;
      data: AvailableMcpServersResponse;
    }>(AGENT_MCP_ENDPOINTS.AVAILABLE_SERVERS(agentId), { params: { source } });
    return data.data;
  },
};

/**
 * Query Hooks for Agent MCP Selection
 */

/**
 * Hook to fetch current MCP selection for an agent
 * @param agentId - The ID of the agent
 * @param enabled - Whether the query should run (defaults to checking agentId)
 * @returns Query result with current MCP selection
 *
 * @example
 * ```tsx
 * const { data } = useAgentMcp(agentId, !!agentId);
 * ```
 */
export const useAgentMcp = (agentId: string, enabled = !!agentId) => {
  return useQuery({
    queryKey: agentMcpQueryKeys.selection(agentId),
    queryFn: () => agentMcpAPI.fetchAgentMcp(agentId),
    enabled,
    staleTime: 1000 * 60 * 3, // 3 minutes
  });
};

/**
 * Hook to fetch available MCP servers for an agent
 * @param agentId - The ID of the agent
 * @param source - Filter by source ("all", "user", "config")
 * @param enabled - Whether the query should run
 * @returns Query result with available MCP servers
 *
 * @example
 * ```tsx
 * const { data } = useAvailableMcpServers(agentId, "all");
 * ```
 */
export const useAvailableMcpServers = (
  agentId: string,
  source: McpSourceFilter = "all",
  enabled = !!agentId
) => {
  return useQuery({
    queryKey: agentMcpQueryKeys.availableServers(agentId, source),
    queryFn: () => agentMcpAPI.fetchAvailableMcpServers(agentId, source),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

/**
 * Mutation Hook for updating agent MCP selection
 * @returns Mutation object with update function
 *
 * @example
 * ```tsx
 * const { mutate: updateMcp } = useUpdateAgentMcp();
 * updateMcp(
 *   { agentId, payload },
 *   {
 *     onSuccess: () => {
 *       // Handle success
 *     },
 *   }
 * );
 * ```
 */
export const useUpdateAgentMcp = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      agentId,
      payload,
    }: {
      agentId: string;
      payload: UpdateAgentMcpPayload;
    }) => agentMcpAPI.updateAgentMcp(agentId, payload),
    onSuccess: (data, variables) => {
      const { agentId } = variables;

      // Update MCP selection cache
      queryClient.setQueryData(agentMcpQueryKeys.selection(agentId), data);

      // Invalidate agent detail query to reflect changes
      queryClient.invalidateQueries({
        queryKey: ["agents", agentId],
      });
    },
  });
};
