import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { AGENT_ENDPOINTS } from "@api";
import type {
  Agent,
  AgentListResponse,
  AgentStatus,
  ChatHistoryConf,
  Device,
  AgentDetailResponse,
  Template,
  TemplateAssignmentResponse,
  PaginatedResponse,
  AgentMessagesListResponse,
  ChatSessionsListResponse,
  DeleteMessagesResponse,
} from "@types";

/**
 * Request payload definitions
 */
export interface AgentListParams {
  page?: number;
  page_size?: number;
}

export interface AgentTemplatesParams {
  page?: number;
  page_size?: number;
}

export interface AgentMessagesParams {
  page?: number;
  page_size?: number;
}

export interface ChatSessionsParams {
  page?: number;
  page_size?: number;
}

export interface CreateAgentPayload {
  agent_name: string;
  description: string;
  user_profile?: string | null;
  status?: AgentStatus;
  chat_history_conf?: ChatHistoryConf;
}

export interface UpdateAgentPayload {
  agent_name?: string;
  description?: string;
  status?: AgentStatus;
  active_template_id?: string | null;
  user_profile?: string | null;
  chat_history_conf?: ChatHistoryConf;
}

export interface BindDevicePayload {
  code: string;
}

export interface WebhookConfig {
  agent_id: string;
  api_key: string | null;
}

export interface WebhookConfigResponse {
  success: boolean;
  message: string;
  data: WebhookConfig;
}

/**
 * Query Keys for agent queries
 */
export const agentQueryKeys = {
  all: ["agents"] as const,
  lists: () => [...agentQueryKeys.all, "list"] as const,
  list: (params?: AgentListParams) =>
    [...agentQueryKeys.lists(), params ?? {}] as const,
  details: () => [...agentQueryKeys.all, "detail"] as const,
  detail: (agentId: string) => [...agentQueryKeys.details(), agentId] as const,
  templates: (agentId: string) =>
    [...agentQueryKeys.detail(agentId), "templates"] as const,
  templatesList: (agentId: string, params?: AgentTemplatesParams) =>
    [...agentQueryKeys.templates(agentId), params ?? {}] as const,
  messages: (agentId: string) =>
    [...agentQueryKeys.detail(agentId), "messages"] as const,
  messagesList: (agentId: string, params?: AgentMessagesParams) =>
    [...agentQueryKeys.messages(agentId), params ?? {}] as const,
  sessions: (agentId: string) =>
    [...agentQueryKeys.messages(agentId), "sessions"] as const,
  sessionsList: (agentId: string, params?: ChatSessionsParams) =>
    [...agentQueryKeys.sessions(agentId), params ?? {}] as const,
  sessionMessages: (agentId: string, sessionId: string) =>
    [...agentQueryKeys.messages(agentId), sessionId] as const,
  sessionMessagesList: (
    agentId: string,
    sessionId: string,
    params?: AgentMessagesParams
  ) =>
    [
      ...agentQueryKeys.sessionMessages(agentId, sessionId),
      params ?? {},
    ] as const,
  webhooks: () => [...agentQueryKeys.all, "webhook"] as const,
  webhookConfig: (agentId: string) =>
    [...agentQueryKeys.webhooks(), agentId] as const,
};

/**
 * API Service Functions using Axios
 */
const agentAPI = {
  fetchAgents: async (params?: AgentListParams): Promise<AgentListResponse> => {
    const { data } = await apiClient.get<AgentListResponse>(
      AGENT_ENDPOINTS.LIST,
      { params }
    );
    return data;
  },

  fetchAgentDetail: async (agentId: string): Promise<AgentDetailResponse> => {
    const { data } = await apiClient.get<AgentDetailResponse>(
      AGENT_ENDPOINTS.DETAIL(agentId)
    );
    return data;
  },

  createAgent: async (payload: CreateAgentPayload): Promise<Agent> => {
    const { data } = await apiClient.post<Agent>(AGENT_ENDPOINTS.LIST, payload);
    return data;
  },

  updateAgent: async (
    agentId: string,
    payload: UpdateAgentPayload
  ): Promise<Agent> => {
    const { data } = await apiClient.put<Agent>(
      AGENT_ENDPOINTS.DETAIL(agentId),
      payload
    );
    return data;
  },

  deleteAgent: async (agentId: string): Promise<void> => {
    await apiClient.delete(AGENT_ENDPOINTS.DETAIL(agentId));
  },

  bindDevice: async (
    agentId: string,
    payload: BindDevicePayload
  ): Promise<Device> => {
    const { data } = await apiClient.post<Device>(
      AGENT_ENDPOINTS.BIND_DEVICE(agentId),
      payload
    );
    return data;
  },

  deleteDevice: async (agentId: string): Promise<void> => {
    await apiClient.delete(AGENT_ENDPOINTS.DELETE_DEVICE(agentId));
  },

  activateTemplate: async (
    agentId: string,
    templateId: string
  ): Promise<Agent> => {
    const { data } = await apiClient.put<Agent>(
      AGENT_ENDPOINTS.ACTIVATE_TEMPLATE(agentId, templateId)
    );
    return data;
  },

  fetchAgentTemplates: async (
    agentId: string,
    params?: AgentTemplatesParams
  ): Promise<PaginatedResponse<Template>> => {
    const { data } = await apiClient.get<PaginatedResponse<Template>>(
      AGENT_ENDPOINTS.TEMPLATES(agentId),
      { params }
    );
    return data;
  },

  assignTemplate: async (
    agentId: string,
    templateId: string,
    setActive?: boolean
  ): Promise<TemplateAssignmentResponse> => {
    const { data } = await apiClient.post<TemplateAssignmentResponse>(
      AGENT_ENDPOINTS.ASSIGN_TEMPLATE(agentId, templateId),
      null,
      { params: setActive ? { set_active: true } : undefined }
    );
    return data;
  },

  unassignTemplate: async (
    agentId: string,
    templateId: string
  ): Promise<void> => {
    await apiClient.delete(
      AGENT_ENDPOINTS.UNASSIGN_TEMPLATE(agentId, templateId)
    );
  },

  fetchAgentMessages: async (
    agentId: string,
    params?: AgentMessagesParams
  ): Promise<AgentMessagesListResponse> => {
    const { data } = await apiClient.get<AgentMessagesListResponse>(
      AGENT_ENDPOINTS.MESSAGES(agentId),
      { params }
    );
    return data;
  },

  fetchChatSessions: async (
    agentId: string,
    params?: ChatSessionsParams
  ): Promise<ChatSessionsListResponse> => {
    const { data } = await apiClient.get<ChatSessionsListResponse>(
      AGENT_ENDPOINTS.MESSAGES_SESSIONS(agentId),
      { params }
    );
    return data;
  },

  fetchSessionMessages: async (
    agentId: string,
    sessionId: string,
    params?: AgentMessagesParams
  ): Promise<AgentMessagesListResponse> => {
    const { data } = await apiClient.get<AgentMessagesListResponse>(
      AGENT_ENDPOINTS.MESSAGES_SESSION_DETAIL(agentId, sessionId),
      { params }
    );
    return data;
  },

  deleteAgentMessages: async (
    agentId: string,
    sessionId?: string
  ): Promise<DeleteMessagesResponse> => {
    const { data } = await apiClient.delete<DeleteMessagesResponse>(
      AGENT_ENDPOINTS.DELETE_MESSAGES(agentId),
      { params: sessionId ? { session_id: sessionId } : undefined }
    );
    return data;
  },

  getWebhookConfig: async (agentId: string): Promise<WebhookConfigResponse> => {
    const { data } = await apiClient.get<WebhookConfigResponse>(
      AGENT_ENDPOINTS.WEBHOOK_CONFIG(agentId)
    );
    return data;
  },

  createWebhookConfig: async (
    agentId: string
  ): Promise<WebhookConfigResponse> => {
    const { data } = await apiClient.post<WebhookConfigResponse>(
      AGENT_ENDPOINTS.WEBHOOK_CONFIG(agentId)
    );
    return data;
  },

  deleteWebhookConfig: async (agentId: string): Promise<void> => {
    await apiClient.delete(AGENT_ENDPOINTS.WEBHOOK_CONFIG(agentId));
  },
};

/**
 * Query Hooks
 */
export const useAgentList = (params?: AgentListParams) => {
  return useQuery({
    queryKey: agentQueryKeys.list(params),
    queryFn: () => agentAPI.fetchAgents(params),
  });
};

export const useAgentDetail = (agentId: string, enabled = true) => {
  return useQuery({
    queryKey: agentQueryKeys.detail(agentId),
    queryFn: () => agentAPI.fetchAgentDetail(agentId),
    enabled: Boolean(agentId) && enabled,
  });
};

export const useAgentTemplates = (
  agentId: string,
  params?: AgentTemplatesParams
) => {
  return useQuery({
    queryKey: agentQueryKeys.templatesList(agentId, params),
    queryFn: () => agentAPI.fetchAgentTemplates(agentId, params),
    enabled: Boolean(agentId),
  });
};

/**
 * Mutation Hooks
 */
export const useCreateAgent = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateAgentPayload) => agentAPI.createAgent(payload),
    retry: false,
    onMutate: async (payload) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: agentQueryKeys.lists() });

      // Snapshot previous data
      const previousData = queryClient.getQueryData<AgentListResponse>(
        agentQueryKeys.list()
      );

      // Create optimistic agent object
      const optimisticAgent: Agent = {
        id: `temp_${Date.now()}`, // Temporary ID
        user_id: "", // Will be populated by server
        agent_name: payload.agent_name,
        description: payload.description,
        status: payload.status || "enabled",
        device_id: null,
        device_mac_address: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Optimistically update the cache
      if (previousData) {
        queryClient.setQueryData<AgentListResponse>(agentQueryKeys.list(), {
          ...previousData,
          data: [optimisticAgent, ...previousData.data],
          total: previousData.total + 1,
        });
      }

      // Return context for rollback
      return { previousData };
    },
    onError: (_err, _payload, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(agentQueryKeys.list(), context.previousData);
      }
    },
    onSuccess: (newAgent) => {
      // Replace optimistic agent with real agent data
      const currentData = queryClient.getQueryData<AgentListResponse>(
        agentQueryKeys.list()
      );

      if (currentData) {
        const updatedData = currentData.data.map((agent) =>
          agent.id.startsWith("temp_") ? newAgent : agent
        );

        queryClient.setQueryData<AgentListResponse>(agentQueryKeys.list(), {
          ...currentData,
          data: updatedData,
        });
      }

      // Invalidate to ensure sync with server
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

export const useUpdateAgent = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      agentId,
      payload,
    }: {
      agentId: string;
      payload: UpdateAgentPayload;
    }) => agentAPI.updateAgent(agentId, payload),
    retry: false,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(variables.agentId),
      });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

export const useDeleteAgent = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (agentId: string) => agentAPI.deleteAgent(agentId),
    retry: false,
    onMutate: async (agentId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: agentQueryKeys.lists() });

      // Snapshot previous data
      const previousData = queryClient.getQueryData<AgentListResponse>(
        agentQueryKeys.list()
      );

      // Optimistically remove the agent from the list
      if (previousData) {
        queryClient.setQueryData<AgentListResponse>(agentQueryKeys.list(), {
          ...previousData,
          data: previousData.data.filter((agent) => agent.id !== agentId),
          total: previousData.total - 1,
        });
      }

      // Also invalidate detail query to ensure it's not cached
      queryClient.removeQueries({ queryKey: agentQueryKeys.detail(agentId) });

      // Return context for rollback
      return { previousData };
    },
    onError: (_err, _agentId, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(agentQueryKeys.list(), context.previousData);
      }
    },
    onSuccess: () => {
      // No additional action needed since we already updated the cache optimistically
    },
  });
};

export const useBindAgentDevice = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BindDevicePayload) =>
      agentAPI.bindDevice(agentId, payload),
    retry: false,
    onSuccess: () => {
      // Invalidate detail query to refetch updated agent data with device
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(agentId),
      });
    },
  });
};

export const useDeleteAgentDevice = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => agentAPI.deleteDevice(agentId),
    retry: false,
    onSuccess: () => {
      // Invalidate detail query to refetch updated agent data without device
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(agentId),
      });
      // Invalidate agents list to reflect device removal
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

/**
 * Activate a template for an agent
 * Uses new endpoint: PUT /agents/{agent_id}/activate-template/{template_id}
 */
export const useActivateAgentTemplate = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateId: string) =>
      agentAPI.activateTemplate(agentId, templateId),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(agentId),
      });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

/**
 * Assign a template to an agent
 * POST /agents/{agent_id}/templates/{template_id}
 */
export const useAssignAgentTemplate = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      templateId,
      setActive,
    }: {
      templateId: string;
      setActive?: boolean;
    }) => agentAPI.assignTemplate(agentId, templateId, setActive),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.templatesList(agentId),
      });
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(agentId),
      });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

/**
 * Unassign a template from an agent
 * DELETE /agents/{agent_id}/templates/{template_id}
 */
export const useUnassignAgentTemplate = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateId: string) =>
      agentAPI.unassignTemplate(agentId, templateId),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.templatesList(agentId),
      });
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.detail(agentId),
      });
      queryClient.invalidateQueries({ queryKey: agentQueryKeys.lists() });
    },
  });
};

/**
 * Fetch all messages for an agent
 * GET /agents/{agent_id}/messages
 */
export const useAgentMessages = (
  agentId: string,
  params?: AgentMessagesParams,
  enabled = true
) => {
  return useQuery({
    queryKey: agentQueryKeys.messagesList(agentId, params),
    queryFn: () => agentAPI.fetchAgentMessages(agentId, params),
    enabled: Boolean(agentId) && enabled,
  });
};

/**
 * Fetch chat sessions for an agent
 * GET /agents/{agent_id}/messages/sessions
 */
export const useChatSessions = (
  agentId: string,
  params?: ChatSessionsParams,
  enabled = true
) => {
  return useQuery({
    queryKey: agentQueryKeys.sessionsList(agentId, params),
    queryFn: () => agentAPI.fetchChatSessions(agentId, params),
    enabled: Boolean(agentId) && enabled,
  });
};

/**
 * Fetch messages for a specific chat session
 * GET /agents/{agent_id}/messages/{session_id}
 */
export const useSessionMessages = (
  agentId: string,
  sessionId: string,
  params?: AgentMessagesParams,
  enabled = true
) => {
  return useQuery({
    queryKey: agentQueryKeys.sessionMessagesList(agentId, sessionId, params),
    queryFn: () => agentAPI.fetchSessionMessages(agentId, sessionId, params),
    enabled: Boolean(agentId) && Boolean(sessionId) && enabled,
  });
};

/**
 * Delete messages for an agent or a specific session
 * DELETE /agents/{agent_id}/messages
 */
export const useDeleteAgentMessages = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId?: string) =>
      agentAPI.deleteAgentMessages(agentId, sessionId),
    retry: false,
    onMutate: async (sessionId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({
        queryKey: agentQueryKeys.messages(agentId),
      });

      // Snapshot previous data
      const previousMessagesData =
        queryClient.getQueryData<AgentMessagesListResponse>(
          agentQueryKeys.messagesList(agentId)
        );
      const previousSessionsData =
        queryClient.getQueryData<ChatSessionsListResponse>(
          agentQueryKeys.sessionsList(agentId)
        );
      const previousSessionMessagesData = sessionId
        ? queryClient.getQueryData<AgentMessagesListResponse>(
            agentQueryKeys.sessionMessagesList(agentId, sessionId)
          )
        : undefined;

      // Return context for rollback
      return {
        previousMessagesData,
        previousSessionsData,
        previousSessionMessagesData,
      };
    },
    onError: (_err, _sessionId, context) => {
      // Rollback on error
      if (context?.previousMessagesData) {
        queryClient.setQueryData(
          agentQueryKeys.messagesList(agentId),
          context.previousMessagesData
        );
      }
      if (context?.previousSessionsData) {
        queryClient.setQueryData(
          agentQueryKeys.sessionsList(agentId),
          context.previousSessionsData
        );
      }
      if (context?.previousSessionMessagesData) {
        const sessionId =
          context.previousSessionMessagesData.data[0]?.session_id;
        if (sessionId) {
          queryClient.setQueryData(
            agentQueryKeys.sessionMessagesList(agentId, sessionId),
            context.previousSessionMessagesData
          );
        }
      }
    },
    onSuccess: () => {
      // Invalidate to ensure sync with server
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.messages(agentId),
      });
    },
  });
};

/**
 * Get webhook configuration for an agent
 * GET /agents/{agent_id}/webhook-config
 */
export const useGetWebhookConfig = (agentId: string, enabled = true) => {
  return useQuery({
    queryKey: agentQueryKeys.webhookConfig(agentId),
    queryFn: () => agentAPI.getWebhookConfig(agentId),
    enabled: Boolean(agentId) && enabled,
  });
};

/**
 * Create/Generate webhook API key for an agent
 * POST /agents/{agent_id}/webhook-config
 */
export const useCreateWebhookConfig = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => agentAPI.createWebhookConfig(agentId),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.webhookConfig(agentId),
      });
    },
  });
};

/**
 * Delete webhook API key for an agent
 * DELETE /agents/{agent_id}/webhook-config
 */
export const useDeleteWebhookConfig = (agentId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => agentAPI.deleteWebhookConfig(agentId),
    retry: false,
    onMutate: async () => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({
        queryKey: agentQueryKeys.webhookConfig(agentId),
      });

      // Snapshot previous data
      const previousData = queryClient.getQueryData<WebhookConfigResponse>(
        agentQueryKeys.webhookConfig(agentId)
      );

      // Optimistically update the webhook config to null
      if (previousData) {
        queryClient.setQueryData<WebhookConfigResponse>(
          agentQueryKeys.webhookConfig(agentId),
          {
            ...previousData,
            data: {
              ...previousData.data,
              api_key: null,
            },
          }
        );
      }

      // Return context for rollback
      return { previousData };
    },
    onError: (_err, _variables, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(
          agentQueryKeys.webhookConfig(agentId),
          context.previousData
        );
      }
    },
    onSuccess: () => {
      // Invalidate to ensure sync with server
      queryClient.invalidateQueries({
        queryKey: agentQueryKeys.webhookConfig(agentId),
      });
    },
  });
};
