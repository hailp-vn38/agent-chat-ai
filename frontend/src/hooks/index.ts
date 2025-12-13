/**
 * Re-export all hooks and queries from their respective sources
 * Hooks are now wrappers around TanStack Query queries and mutations
 */
export {
  useChatList,
  useChat as useChatDetail,
  useMessages,
  useCreateChat,
  useDeleteChat,
  useSendMessage,
  chatQueryKeys,
} from "./useChat";

export {
  useAgentList,
  useAgentDetail,
  useCreateAgent,
  useUpdateAgent,
  useDeleteAgent,
  useBindAgentDevice,
  useDeleteAgentDevice,
  useActivateAgentTemplate,
  agentQueryKeys,
  // Template queries
  useTemplateList,
  useTemplateDetail,
  useTemplateAgents,
  useCreateTemplate,
  useUpdateTemplate,
  useDeleteTemplate,
  useAssignTemplate,
  useUnassignTemplate,
  useCreateAndAssignTemplate,
  templateQueryKeys,
} from "./useAgent";

export {
  useDeviceList,
  useDeviceDetail,
  deviceQueryKeys,
  type DeviceListParams,
  type DeviceListResponse,
} from "./useDevice";

export { useAuth } from "./useAuth";

export {
  useLogin,
  useRegister,
  useLogout,
  authQueryKeys,
} from "@/queries/auth-queries";

export { useMe, userQueryKeys } from "@/queries/user-queries";

export { useChatWebSocket } from "./use-chat-websocket";

export { useConfig } from "./use-config";

export { useBreadcrumb, type BreadcrumbItem } from "./use-breadcrumb";

export { useProviderModules } from "./use-provider-modules";

export { useDebouncedCallback } from "./use-debounce";

export { useDocumentMeta } from "./use-document-meta";
export { usePageHead, type UsePageHeadProps } from "./usePageHead";
