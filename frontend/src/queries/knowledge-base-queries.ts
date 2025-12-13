import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { KNOWLEDGE_BASE_ENDPOINTS } from "@api";
import type {
  KnowledgeBaseHealthResponse,
  KnowledgeBaseSectorsResponse,
  KnowledgeEntryResponse,
  KnowledgeEntryListResponse,
  KnowledgeSearchResponse,
  KnowledgeDeleteResponse,
  KnowledgeIngestResponse,
  CreateKnowledgeEntryPayload,
  UpdateKnowledgeEntryPayload,
  KnowledgeSearchPayload,
  IngestFilePayload,
  IngestUrlPayload,
  KnowledgeListParams,
} from "@types";

/**
 * Query Keys for knowledge base queries
 */
export const knowledgeBaseQueryKeys = {
  all: ["knowledge-base"] as const,
  health: () => [...knowledgeBaseQueryKeys.all, "health"] as const,
  sectors: () => [...knowledgeBaseQueryKeys.all, "sectors"] as const,
  agentItems: (agentId: string) =>
    [...knowledgeBaseQueryKeys.all, "agent", agentId, "items"] as const,
  agentItemsList: (agentId: string, params?: KnowledgeListParams) =>
    [...knowledgeBaseQueryKeys.agentItems(agentId), params ?? {}] as const,
  agentItemDetail: (agentId: string, itemId: string) =>
    [...knowledgeBaseQueryKeys.agentItems(agentId), itemId] as const,
  agentSearch: (agentId: string) =>
    [...knowledgeBaseQueryKeys.all, "agent", agentId, "search"] as const,
};

/**
 * API Service Functions
 */
const knowledgeBaseAPI = {
  // Health & Info
  checkHealth: async (): Promise<KnowledgeBaseHealthResponse> => {
    const { data } = await apiClient.get<KnowledgeBaseHealthResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.HEALTH
    );
    return data;
  },

  getSectors: async (): Promise<KnowledgeBaseSectorsResponse> => {
    const { data } = await apiClient.get<KnowledgeBaseSectorsResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.SECTORS
    );
    return data;
  },

  // CRUD Operations
  listItems: async (
    agentId: string,
    params?: KnowledgeListParams
  ): Promise<KnowledgeEntryListResponse> => {
    const { data } = await apiClient.get<KnowledgeEntryListResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.ITEMS(agentId),
      { params }
    );
    return data;
  },

  getItem: async (
    agentId: string,
    itemId: string
  ): Promise<KnowledgeEntryResponse> => {
    const { data } = await apiClient.get<KnowledgeEntryResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.ITEM_DETAIL(agentId, itemId)
    );
    return data;
  },

  createItem: async (
    agentId: string,
    payload: CreateKnowledgeEntryPayload
  ): Promise<KnowledgeEntryResponse> => {
    const { data } = await apiClient.post<KnowledgeEntryResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.ITEMS(agentId),
      payload
    );
    return data;
  },

  updateItem: async (
    agentId: string,
    itemId: string,
    payload: UpdateKnowledgeEntryPayload
  ): Promise<KnowledgeEntryResponse> => {
    const { data } = await apiClient.patch<KnowledgeEntryResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.ITEM_DETAIL(agentId, itemId),
      payload
    );
    return data;
  },

  deleteItem: async (
    agentId: string,
    itemId: string
  ): Promise<KnowledgeDeleteResponse> => {
    const { data } = await apiClient.delete<KnowledgeDeleteResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.ITEM_DETAIL(agentId, itemId)
    );
    return data;
  },

  // Search
  search: async (
    agentId: string,
    payload: KnowledgeSearchPayload
  ): Promise<KnowledgeSearchResponse> => {
    const { data } = await apiClient.post<KnowledgeSearchResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.SEARCH(agentId),
      payload
    );
    return data;
  },

  // Ingestion
  ingestFile: async (
    agentId: string,
    payload: IngestFilePayload
  ): Promise<KnowledgeIngestResponse> => {
    const { data } = await apiClient.post<KnowledgeIngestResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.INGEST_FILE(agentId),
      payload
    );
    return data;
  },

  ingestUrl: async (
    agentId: string,
    payload: IngestUrlPayload
  ): Promise<KnowledgeIngestResponse> => {
    const { data } = await apiClient.post<KnowledgeIngestResponse>(
      KNOWLEDGE_BASE_ENDPOINTS.INGEST_URL(agentId),
      payload
    );
    return data;
  },
};

/**
 * Query Hooks
 */
export const useKnowledgeBaseHealth = () => {
  return useQuery({
    queryKey: knowledgeBaseQueryKeys.health(),
    queryFn: () => knowledgeBaseAPI.checkHealth(),
    staleTime: 60 * 1000, // 1 minute
    retry: false,
  });
};

export const useKnowledgeBaseSectors = () => {
  return useQuery({
    queryKey: knowledgeBaseQueryKeys.sectors(),
    queryFn: () => knowledgeBaseAPI.getSectors(),
    staleTime: 5 * 60 * 1000, // 5 minutes - sectors rarely change
    retry: false,
  });
};

export const useKnowledgeBaseItems = (
  agentId: string,
  params?: KnowledgeListParams,
  enabled = true
) => {
  return useQuery({
    queryKey: knowledgeBaseQueryKeys.agentItemsList(agentId, params),
    queryFn: () => knowledgeBaseAPI.listItems(agentId, params),
    enabled: Boolean(agentId) && enabled,
    retry: false,
  });
};

export const useKnowledgeBaseItem = (
  agentId: string,
  itemId: string,
  enabled = true
) => {
  return useQuery({
    queryKey: knowledgeBaseQueryKeys.agentItemDetail(agentId, itemId),
    queryFn: () => knowledgeBaseAPI.getItem(agentId, itemId),
    enabled: Boolean(agentId) && Boolean(itemId) && enabled,
    retry: false,
  });
};

/**
 * Mutation Hooks
 */
export const useCreateKnowledgeEntry = (agentId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateKnowledgeEntryPayload) =>
      knowledgeBaseAPI.createItem(agentId, payload),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: knowledgeBaseQueryKeys.agentItems(agentId),
      });
    },
  });
};

export const useUpdateKnowledgeEntry = (agentId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      itemId,
      payload,
    }: {
      itemId: string;
      payload: UpdateKnowledgeEntryPayload;
    }) => knowledgeBaseAPI.updateItem(agentId, itemId, payload),
    retry: false,
    onSuccess: (_, { itemId }) => {
      queryClient.invalidateQueries({
        queryKey: knowledgeBaseQueryKeys.agentItemDetail(agentId, itemId),
      });
      queryClient.invalidateQueries({
        queryKey: knowledgeBaseQueryKeys.agentItems(agentId),
      });
    },
  });
};

export const useDeleteKnowledgeEntry = (agentId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: string) =>
      knowledgeBaseAPI.deleteItem(agentId, itemId),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: knowledgeBaseQueryKeys.agentItems(agentId),
      });
    },
  });
};

export const useKnowledgeBaseSearch = (agentId: string) => {
  return useMutation({
    mutationFn: (payload: KnowledgeSearchPayload) =>
      knowledgeBaseAPI.search(agentId, payload),
  });
};

export const useIngestFile = (agentId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: IngestFilePayload) =>
      knowledgeBaseAPI.ingestFile(agentId, payload),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: knowledgeBaseQueryKeys.agentItems(agentId),
      });
    },
  });
};

export const useIngestUrl = (agentId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: IngestUrlPayload) =>
      knowledgeBaseAPI.ingestUrl(agentId, payload),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: knowledgeBaseQueryKeys.agentItems(agentId),
      });
    },
  });
};

/**
 * Export API for direct usage if needed
 */
export { knowledgeBaseAPI };
