import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Chat, Message } from "@types";
import apiClient from "@config/axios-instance";
import { CHAT_ENDPOINTS } from "@api";

/**
 * Query Keys for chat queries
 */
export const chatQueryKeys = {
  all: ["chats"] as const,
  lists: () => [...chatQueryKeys.all, "list"] as const,
  list: (filters?: Record<string, unknown>) =>
    [...chatQueryKeys.lists(), { ...filters }] as const,
  details: () => [...chatQueryKeys.all, "detail"] as const,
  detail: (id: string) => [...chatQueryKeys.details(), id] as const,
  messages: (chatId: string) =>
    [...chatQueryKeys.detail(chatId), "messages"] as const,
};

/**
 * API Service Functions using Axios
 */
const chatAPI = {
  fetchChats: async (): Promise<Chat[]> => {
    const { data } = await apiClient.get(CHAT_ENDPOINTS.LIST);
    return data;
  },

  fetchChat: async (id: string): Promise<Chat> => {
    const { data } = await apiClient.get(CHAT_ENDPOINTS.GET(id));
    return data;
  },

  fetchMessages: async (chatId: string): Promise<Message[]> => {
    const { data } = await apiClient.get(CHAT_ENDPOINTS.GET_MESSAGES(chatId));
    return data;
  },

  createChat: async (title: string): Promise<Chat> => {
    const { data } = await apiClient.post(CHAT_ENDPOINTS.CREATE, { title });
    return data;
  },

  deleteChat: async (id: string): Promise<void> => {
    await apiClient.delete(CHAT_ENDPOINTS.DELETE(id));
  },

  sendMessage: async (chatId: string, content: string): Promise<Message> => {
    const { data } = await apiClient.post(CHAT_ENDPOINTS.SEND_MESSAGE(chatId), {
      content,
    });
    return data;
  },
};

/**
 * Query Hooks
 */
export const useChatList = () => {
  return useQuery({
    queryKey: chatQueryKeys.list(),
    queryFn: chatAPI.fetchChats,
  });
};

export const useChat = (id: string) => {
  return useQuery({
    queryKey: chatQueryKeys.detail(id),
    queryFn: () => chatAPI.fetchChat(id),
  });
};

export const useMessages = (chatId: string) => {
  return useQuery({
    queryKey: chatQueryKeys.messages(chatId),
    queryFn: () => chatAPI.fetchMessages(chatId),
  });
};

/**
 * Mutation Hooks
 */
export const useCreateChat = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (title: string) => chatAPI.createChat(title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatQueryKeys.lists() });
    },
  });
};

export const useDeleteChat = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => chatAPI.deleteChat(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatQueryKeys.lists() });
    },
  });
};

export const useSendMessage = (chatId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => chatAPI.sendMessage(chatId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: chatQueryKeys.messages(chatId),
      });
    },
  });
};
