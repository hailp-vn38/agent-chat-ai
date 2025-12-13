import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { PROVIDER_ENDPOINTS } from "@lib/api";
import type {
  Provider,
  ProviderListResponse,
  ProviderCategory,
  ProviderSchemaResponse,
  ProviderValidateRequest,
  ProviderValidateResponse,
  ProviderTestRequest,
  ProviderTestResponse,
  ValidateReferenceRequest,
  ValidateReferenceResponse,
  TestReferenceRequest,
  TestReferenceResponse,
  ProviderModuleItem,
} from "@types";

/**
 * Provider source filter options
 */
export type ProviderSourceFilter = "all" | "config" | "user";

/**
 * Request payload definitions
 */
export interface ProviderListParams {
  category?: ProviderCategory;
  source?: ProviderSourceFilter;
  page?: number;
  page_size?: number;
}

export interface CreateProviderPayload {
  name: string;
  category: ProviderCategory;
  type: string;
  config: Record<string, unknown>;
  is_active?: boolean;
}

export interface UpdateProviderPayload {
  name?: string;
  config?: Record<string, unknown>;
  is_active?: boolean;
}

export interface ProviderModulesResponse {
  LLM?: ProviderModuleItem[];
  TTS?: ProviderModuleItem[];
  ASR?: ProviderModuleItem[];
  VAD?: ProviderModuleItem[];
  Memory?: ProviderModuleItem[];
  Intent?: ProviderModuleItem[];
  VLLM?: ProviderModuleItem[];
}

/**
 * Query Keys for provider queries
 */
export const providerQueryKeys = {
  all: ["providers"] as const,
  lists: () => [...providerQueryKeys.all, "list"] as const,
  list: (params?: ProviderListParams) =>
    [...providerQueryKeys.lists(), params ?? {}] as const,
  details: () => [...providerQueryKeys.all, "detail"] as const,
  detail: (providerId: string) =>
    [...providerQueryKeys.details(), providerId] as const,
  schemas: () => [...providerQueryKeys.all, "schemas"] as const,
  schemaCategories: () =>
    [...providerQueryKeys.schemas(), "categories"] as const,
  configModules: (includeDefaults?: boolean) =>
    [...providerQueryKeys.all, "config-modules", { includeDefaults }] as const,
};

/**
 * API Service Functions using Axios
 */
const providerAPI = {
  // Schema endpoints (không yêu cầu auth)
  fetchSchemas: async (): Promise<Record<string, unknown>> => {
    const { data } = await apiClient.get<Record<string, unknown>>(
      PROVIDER_ENDPOINTS.SCHEMAS
    );
    return data;
  },

  fetchSchemaCategories: async (): Promise<ProviderSchemaResponse> => {
    const { data } = await apiClient.get<ProviderSchemaResponse>(
      PROVIDER_ENDPOINTS.SCHEMA_CATEGORIES
    );
    return data;
  },

  // Validation endpoints
  validateConfig: async (
    payload: ProviderValidateRequest
  ): Promise<ProviderValidateResponse> => {
    const { data } = await apiClient.post<ProviderValidateResponse>(
      PROVIDER_ENDPOINTS.VALIDATE,
      payload
    );
    return data;
  },

  testConnection: async (
    payload: ProviderTestRequest
  ): Promise<ProviderTestResponse> => {
    const { data } = await apiClient.post<ProviderTestResponse>(
      PROVIDER_ENDPOINTS.TEST,
      payload
    );
    return data;
  },

  // CRUD endpoints
  fetchProviders: async (
    params?: ProviderListParams
  ): Promise<ProviderListResponse> => {
    const { data } = await apiClient.get<ProviderListResponse>(
      PROVIDER_ENDPOINTS.LIST,
      { params }
    );
    return data;
  },

  fetchProviderDetail: async (providerId: string): Promise<Provider> => {
    const { data } = await apiClient.get<Provider>(
      PROVIDER_ENDPOINTS.DETAIL(providerId)
    );
    return data;
  },

  createProvider: async (payload: CreateProviderPayload): Promise<Provider> => {
    const { data } = await apiClient.post<Provider>(
      PROVIDER_ENDPOINTS.LIST,
      payload
    );
    return data;
  },

  updateProvider: async (
    providerId: string,
    payload: UpdateProviderPayload
  ): Promise<Provider> => {
    const { data } = await apiClient.put<Provider>(
      PROVIDER_ENDPOINTS.DETAIL(providerId),
      payload
    );
    return data;
  },

  deleteProvider: async (providerId: string): Promise<void> => {
    await apiClient.delete(PROVIDER_ENDPOINTS.DETAIL(providerId));
  },

  fetchConfigModules: async (
    includeDefaults?: boolean
  ): Promise<ProviderModulesResponse> => {
    const { data } = await apiClient.get<ProviderModulesResponse>(
      PROVIDER_ENDPOINTS.CONFIG_MODULES,
      { params: { include_defaults: includeDefaults } }
    );
    return data;
  },

  validateReference: async (
    payload: ValidateReferenceRequest
  ): Promise<ValidateReferenceResponse> => {
    const { data } = await apiClient.post<ValidateReferenceResponse>(
      PROVIDER_ENDPOINTS.VALIDATE_REFERENCE,
      payload
    );
    return data;
  },

  testReference: async (
    payload: TestReferenceRequest
  ): Promise<TestReferenceResponse> => {
    const { data } = await apiClient.post<TestReferenceResponse>(
      PROVIDER_ENDPOINTS.TEST_REFERENCE,
      payload
    );
    return data;
  },
};

/**
 * Query Hooks
 */

// Lấy tất cả schemas (không cần auth)
export const useProviderSchemas = () => {
  return useQuery({
    queryKey: providerQueryKeys.schemas(),
    queryFn: () => providerAPI.fetchSchemas(),
    staleTime: 1000 * 60 * 60, // Cache 1 hour (schemas ít thay đổi)
  });
};

// Lấy schema categories kèm fields (không cần auth)
export const useProviderSchemaCategories = () => {
  return useQuery({
    queryKey: providerQueryKeys.schemaCategories(),
    queryFn: () => providerAPI.fetchSchemaCategories(),
    staleTime: 1000 * 60 * 60, // Cache 1 hour
  });
};

// Lấy config modules theo category
export const useProviderConfigModules = (includeDefaults = true) => {
  return useQuery({
    queryKey: providerQueryKeys.configModules(includeDefaults),
    queryFn: () => providerAPI.fetchConfigModules(includeDefaults),
    staleTime: 1000 * 60 * 60, // Cache 1 hour
  });
};

// Lấy danh sách providers của user
export const useProviderList = (params?: ProviderListParams) => {
  return useQuery({
    queryKey: providerQueryKeys.list(params),
    queryFn: () => providerAPI.fetchProviders(params),
  });
};

// Lấy chi tiết provider
export const useProviderDetail = (providerId: string, enabled = true) => {
  return useQuery({
    queryKey: providerQueryKeys.detail(providerId),
    queryFn: () => providerAPI.fetchProviderDetail(providerId),
    enabled: Boolean(providerId) && enabled,
  });
};

/**
 * Mutation Hooks
 */

// Validate config trước khi save
export const useValidateProviderConfig = () => {
  return useMutation({
    mutationFn: (payload: ProviderValidateRequest) =>
      providerAPI.validateConfig(payload),
    retry: false,
  });
};

// Test connection với provider API (hỗ trợ custom input_data)
export const useTestProviderConnection = () => {
  return useMutation({
    mutationFn: (payload: ProviderTestRequest) =>
      providerAPI.testConnection(payload),
    retry: false,
  });
};

// Validate provider reference format
export const useValidateProviderReference = () => {
  return useMutation({
    mutationFn: (payload: ValidateReferenceRequest) =>
      providerAPI.validateReference(payload),
    retry: false,
  });
};

// Test provider connection by reference string (hỗ trợ custom input_data)
export const useTestProviderReference = () => {
  return useMutation({
    mutationFn: (payload: TestReferenceRequest) =>
      providerAPI.testReference(payload),
    retry: false,
  });
};

// Tạo provider mới
export const useCreateProvider = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateProviderPayload) =>
      providerAPI.createProvider(payload),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: providerQueryKeys.lists() });
      // Invalidate config modules vì danh sách providers thay đổi
      queryClient.invalidateQueries({
        queryKey: [...providerQueryKeys.all, "config-modules"],
      });
    },
  });
};

// Cập nhật provider
export const useUpdateProvider = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      providerId,
      payload,
    }: {
      providerId: string;
      payload: UpdateProviderPayload;
    }) => providerAPI.updateProvider(providerId, payload),
    retry: false,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: providerQueryKeys.detail(variables.providerId),
      });
      queryClient.invalidateQueries({ queryKey: providerQueryKeys.lists() });
      // Invalidate config modules vì provider info có thể thay đổi
      queryClient.invalidateQueries({
        queryKey: [...providerQueryKeys.all, "config-modules"],
      });
    },
  });
};

// Xóa provider
export const useDeleteProvider = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (providerId: string) => providerAPI.deleteProvider(providerId),
    retry: false,
    onMutate: async (providerId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: providerQueryKeys.lists() });

      // Get all cached provider list queries (with different params)
      const queriesData = queryClient.getQueriesData<ProviderListResponse>({
        queryKey: providerQueryKeys.lists(),
      });

      // Optimistically remove the provider from ALL cached list queries
      queriesData.forEach(([queryKey, data]) => {
        if (data) {
          queryClient.setQueryData<ProviderListResponse>(queryKey, {
            ...data,
            data: data.data.filter((provider) => provider.id !== providerId),
            total: data.total - 1,
          });
        }
      });

      // Remove detail query from cache
      queryClient.removeQueries({
        queryKey: providerQueryKeys.detail(providerId),
      });

      return { queriesData };
    },
    onError: (_err, _providerId, context) => {
      // Rollback on error - restore all previous cached data
      if (context?.queriesData) {
        context.queriesData.forEach(([queryKey, data]) => {
          if (data) {
            queryClient.setQueryData(queryKey, data);
          }
        });
      }
    },
    onSuccess: (_data, providerId) => {
      // Invalidate all list queries to ensure fresh data
      queryClient.invalidateQueries({ queryKey: providerQueryKeys.lists() });
      // Invalidate config modules vì danh sách providers thay đổi
      queryClient.invalidateQueries({
        queryKey: [...providerQueryKeys.all, "config-modules"],
      });
      // Ensure detail query is removed
      queryClient.removeQueries({
        queryKey: providerQueryKeys.detail(providerId),
      });
    },
  });
};
