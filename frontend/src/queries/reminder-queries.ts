import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { REMINDER_ENDPOINTS } from "@api";
import type {
  ReminderRead,
  ReminderStatus,
  PaginatedResponse,
  CreateReminderPayload,
  UpdateReminderPayload,
} from "@types";

export interface ReminderListParams {
  status?: ReminderStatus;
  q?: string;
  page?: number;
  page_size?: number;
}

export const reminderQueryKeys = {
  all: ["reminders"] as const,
  agent: (agentId: string) =>
    [...reminderQueryKeys.all, "agent", agentId] as const,
  list: (agentId: string, params?: ReminderListParams) =>
    [...reminderQueryKeys.agent(agentId), "list", params ?? {}] as const,
  detail: (reminderId: string) =>
    [...reminderQueryKeys.all, "detail", reminderId] as const,
};

const reminderAPI = {
  fetchAgentReminders: async (
    agentId: string,
    params?: ReminderListParams
  ): Promise<PaginatedResponse<ReminderRead>> => {
    const { data } = await apiClient.get<PaginatedResponse<ReminderRead>>(
      REMINDER_ENDPOINTS.LIST(agentId),
      { params }
    );
    return data;
  },

  fetchReminderDetail: async (reminderId: string): Promise<ReminderRead> => {
    const { data } = await apiClient.get<ReminderRead>(
      REMINDER_ENDPOINTS.DETAIL(reminderId)
    );
    return data;
  },

  createReminder: async (
    agentId: string,
    payload: CreateReminderPayload
  ): Promise<ReminderRead> => {
    const { data } = await apiClient.post<ReminderRead>(
      REMINDER_ENDPOINTS.LIST(agentId),
      payload
    );
    return data;
  },

  updateReminder: async (
    reminderId: string,
    payload: UpdateReminderPayload
  ): Promise<ReminderRead> => {
    const { data } = await apiClient.patch<ReminderRead>(
      REMINDER_ENDPOINTS.DETAIL(reminderId),
      payload
    );
    return data;
  },

  deleteReminder: async (reminderId: string): Promise<void> => {
    await apiClient.delete(REMINDER_ENDPOINTS.DETAIL(reminderId));
  },
};

export const useAgentReminders = (
  agentId: string,
  params?: ReminderListParams
) => {
  return useQuery({
    queryKey: reminderQueryKeys.list(agentId, params),
    queryFn: () => reminderAPI.fetchAgentReminders(agentId, params),
    enabled: Boolean(agentId),
  });
};

interface CreateReminderVariables {
  agentId: string;
  payload: CreateReminderPayload;
}

export const useCreateReminder = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ agentId, payload }: CreateReminderVariables) =>
      reminderAPI.createReminder(agentId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: reminderQueryKeys.agent(variables.agentId),
      });
    },
  });
};

interface UpdateReminderVariables {
  reminderId: string;
  payload: UpdateReminderPayload;
  agentId?: string;
}

export const useUpdateReminder = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ reminderId, payload }: UpdateReminderVariables) =>
      reminderAPI.updateReminder(reminderId, payload),
    onSuccess: (_data, variables) => {
      if (variables.agentId) {
        queryClient.invalidateQueries({
          queryKey: reminderQueryKeys.agent(variables.agentId),
        });
      }
      queryClient.invalidateQueries({
        queryKey: reminderQueryKeys.detail(variables.reminderId),
      });
    },
  });
};

interface DeleteReminderVariables {
  reminderId: string;
  agentId?: string;
}

export const useDeleteReminder = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ reminderId }: DeleteReminderVariables) =>
      reminderAPI.deleteReminder(reminderId),
    onSuccess: (_data, variables) => {
      if (variables.agentId) {
        queryClient.invalidateQueries({
          queryKey: reminderQueryKeys.agent(variables.agentId),
        });
      }
      queryClient.invalidateQueries({
        queryKey: reminderQueryKeys.detail(variables.reminderId),
      });
    },
  });
};

export const useReminderDetail = (reminderId?: string) => {
  return useQuery({
    queryKey: reminderQueryKeys.detail(reminderId ?? ""),
    queryFn: () => reminderAPI.fetchReminderDetail(reminderId ?? ""),
    enabled: Boolean(reminderId),
  });
};
