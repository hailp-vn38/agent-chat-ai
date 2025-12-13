import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { TEMPLATE_ENDPOINTS } from "@api";
import type {
  Template,
  TemplateListResponse,
  TemplatePayload,
  UpdateTemplatePayload,
  TemplateAssignmentResponse,
  Agent,
  PaginatedResponse,
} from "@types";
import { agentQueryKeys } from "./agent-queries";

/**
 * Request payload definitions
 */
export interface TemplateListParams {
  page?: number;
  page_size?: number;
  include_public?: boolean;
}

export interface TemplateAgentsParams {
  page?: number;
  page_size?: number;
}

/**
 * Query Keys for template queries
 */
export const templateQueryKeys = {
  all: ["templates"] as const,
  lists: () => [...templateQueryKeys.all, "list"] as const,
  list: (params?: TemplateListParams) =>
    [...templateQueryKeys.lists(), params ?? {}] as const,
  details: () => [...templateQueryKeys.all, "detail"] as const,
  detail: (templateId: string) =>
    [...templateQueryKeys.details(), templateId] as const,
  agents: (templateId: string) =>
    [...templateQueryKeys.detail(templateId), "agents"] as const,
  agentsList: (templateId: string, params?: TemplateAgentsParams) =>
    [...templateQueryKeys.agents(templateId), params ?? {}] as const,
};

/**
 * API Service Functions using Axios
 */
const templateAPI = {
  fetchTemplates: async (
    params?: TemplateListParams
  ): Promise<TemplateListResponse> => {
    const { data } = await apiClient.get<TemplateListResponse>(
      TEMPLATE_ENDPOINTS.LIST,
      { params }
    );
    return data;
  },

  fetchTemplateDetail: async (templateId: string): Promise<Template> => {
    const { data } = await apiClient.get<Template>(
      TEMPLATE_ENDPOINTS.DETAIL(templateId)
    );
    return data;
  },

  createTemplate: async (payload: TemplatePayload): Promise<Template> => {
    const { data } = await apiClient.post<Template>(
      TEMPLATE_ENDPOINTS.LIST,
      payload
    );
    return data;
  },

  updateTemplate: async (
    templateId: string,
    payload: UpdateTemplatePayload
  ): Promise<Template> => {
    const { data } = await apiClient.put<Template>(
      TEMPLATE_ENDPOINTS.DETAIL(templateId),
      payload
    );
    return data;
  },

  deleteTemplate: async (templateId: string): Promise<void> => {
    await apiClient.delete(TEMPLATE_ENDPOINTS.DETAIL(templateId));
  },

  fetchTemplateAgents: async (
    templateId: string,
    params?: TemplateAgentsParams
  ): Promise<PaginatedResponse<Agent>> => {
    const { data } = await apiClient.get<PaginatedResponse<Agent>>(
      TEMPLATE_ENDPOINTS.AGENTS(templateId),
      { params }
    );
    return data;
  },

  assignTemplate: async (
    templateId: string,
    agentId: string,
    setActive?: boolean
  ): Promise<TemplateAssignmentResponse> => {
    const { data } = await apiClient.post<TemplateAssignmentResponse>(
      TEMPLATE_ENDPOINTS.ASSIGN_AGENT(templateId, agentId),
      null,
      { params: setActive ? { set_active: true } : undefined }
    );
    return data;
  },

  unassignTemplate: async (
    templateId: string,
    agentId: string
  ): Promise<void> => {
    await apiClient.delete(
      TEMPLATE_ENDPOINTS.UNASSIGN_AGENT(templateId, agentId)
    );
  },
};

/**
 * Query Hooks
 */
export const useTemplateList = (params?: TemplateListParams) => {
  return useQuery({
    queryKey: templateQueryKeys.list(params),
    queryFn: () => templateAPI.fetchTemplates(params),
  });
};

export const useTemplateDetail = (templateId: string, enabled = true) => {
  return useQuery({
    queryKey: templateQueryKeys.detail(templateId),
    queryFn: () => templateAPI.fetchTemplateDetail(templateId),
    enabled: Boolean(templateId) && enabled,
  });
};

export const useTemplateAgents = (
  templateId: string,
  params?: TemplateAgentsParams
) => {
  return useQuery({
    queryKey: templateQueryKeys.agentsList(templateId, params),
    queryFn: () => templateAPI.fetchTemplateAgents(templateId, params),
    enabled: Boolean(templateId),
  });
};

/**
 * Mutation Hooks
 */
export const useCreateTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TemplatePayload) =>
      templateAPI.createTemplate(payload),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateQueryKeys.lists() });
    },
  });
};

export const useUpdateTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      templateId,
      payload,
    }: {
      templateId: string;
      payload: UpdateTemplatePayload;
    }) => templateAPI.updateTemplate(templateId, payload),
    retry: false,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateQueryKeys.detail(variables.templateId),
      });
      queryClient.invalidateQueries({ queryKey: templateQueryKeys.lists() });
    },
  });
};

export const useDeleteTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateId: string) => templateAPI.deleteTemplate(templateId),
    retry: false,
    onMutate: async (templateId) => {
      await queryClient.cancelQueries({ queryKey: templateQueryKeys.lists() });

      const previousData = queryClient.getQueryData<TemplateListResponse>(
        templateQueryKeys.list()
      );

      if (previousData) {
        queryClient.setQueryData<TemplateListResponse>(
          templateQueryKeys.list(),
          {
            ...previousData,
            data: previousData.data.filter(
              (template) => template.id !== templateId
            ),
            total: previousData.total - 1,
          }
        );
      }

      queryClient.removeQueries({
        queryKey: templateQueryKeys.detail(templateId),
      });

      return { previousData };
    },
    onError: (_err, _templateId, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(
          templateQueryKeys.list(),
          context.previousData
        );
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateQueryKeys.lists() });
    },
  });
};

export const useAssignTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      templateId,
      agentId,
      setActive,
    }: {
      templateId: string;
      agentId: string;
      setActive?: boolean;
    }) => templateAPI.assignTemplate(templateId, agentId, setActive),
    retry: false,
    onSuccess: (_data, variables) => {
      // Invalidate both template and agent queries
      queryClient.invalidateQueries({
        queryKey: templateQueryKeys.agents(variables.templateId),
      });
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(variables.agentId),
      });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

export const useUnassignTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      templateId,
      agentId,
    }: {
      templateId: string;
      agentId: string;
    }) => templateAPI.unassignTemplate(templateId, agentId),
    retry: false,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateQueryKeys.agents(variables.templateId),
      });
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(variables.agentId),
      });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

/**
 * Combined mutation: Create template and assign to agent
 */
export const useCreateAndAssignTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      payload,
      agentId,
      setActive = true,
    }: {
      payload: TemplatePayload;
      agentId: string;
      setActive?: boolean;
    }) => {
      // Step 1: Create template
      const template = await templateAPI.createTemplate(payload);

      // Step 2: Assign to agent
      await templateAPI.assignTemplate(template.id, agentId, setActive);

      return template;
    },
    retry: false,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: templateQueryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(variables.agentId),
      });
    },
  });
};
