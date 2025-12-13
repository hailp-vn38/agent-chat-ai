import { useQuery } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { TOOL_ENDPOINTS } from "@lib/api";
import type {
  ToolSchema,
  ToolAvailableResponse,
  ToolOptionsResponse,
  ToolCategory,
} from "@types";

/**
 * Query Keys for tool queries (v2.0)
 */
export const toolQueryKeys = {
  all: ["tools"] as const,
  available: (q?: string) => [...toolQueryKeys.all, "available", q] as const,
  options: () => [...toolQueryKeys.all, "options"] as const,
};

/**
 * API Service Functions using Axios (v2.0)
 */
const toolAPI = {
  // GET /tools/available - Lấy danh sách system functions có sẵn
  fetchAvailable: async (q?: string): Promise<ToolAvailableResponse> => {
    const { data } = await apiClient.get<ToolAvailableResponse>(
      TOOL_ENDPOINTS.AVAILABLE,
      { params: q ? { q } : undefined }
    );
    return data;
  },

  // GET /tools/options - Lấy tool options cho dropdown
  fetchOptions: async (): Promise<ToolOptionsResponse> => {
    const { data } = await apiClient.get<ToolOptionsResponse>(
      TOOL_ENDPOINTS.OPTIONS
    );
    return data;
  },
};

/**
 * Query Hooks (v2.0)
 */

/**
 * Lấy danh sách tools có sẵn
 * Response format: { success, data: ToolSchema[], total }
 */
export const useToolAvailable = (q?: string) => {
  return useQuery({
    queryKey: toolQueryKeys.available(q),
    queryFn: () => toolAPI.fetchAvailable(q),
    staleTime: 1000 * 60 * 60, // Cache 1 hour (schemas ít thay đổi)
  });
};

/**
 * Lấy tool options cho dropdown (cần auth)
 * Response format: { success, data: ToolOptionItem[], total }
 */
export const useToolOptions = (enabled = true) => {
  return useQuery({
    queryKey: toolQueryKeys.options(),
    queryFn: () => toolAPI.fetchOptions(),
    enabled,
    staleTime: 1000 * 60 * 5, // Cache 5 minutes
  });
};

/**
 * Helper function to get tools by category
 */
export const filterToolsByCategory = (
  tools: ToolSchema[],
  category: ToolCategory
): ToolSchema[] => {
  return tools.filter((tool) => tool.category === category);
};
