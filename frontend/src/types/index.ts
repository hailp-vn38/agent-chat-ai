/**
 * Type definitions for the application
 */

export * from "./knowledge-base";
export * from "./mcp-config.types";
export * from "./system-mcp.types";
export * from "./agent-tool.types";
export * from "./plugin.types";

export interface Chat {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface Message {
  id: string;
  chatId: string;
  content: string;
  sender: "user" | "bot";
  createdAt: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  profile_image_base64?: string | null;
  timezone?: string | null;
}

/**
 * Input type for updating user profile
 */
export interface UpdateUserInput {
  name?: string;
  email?: string;
  timezone?: string;
  chat_history_conf?: ChatHistoryConf;
}

/**
 * Input type for changing password
 */
export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

/**
 * Response type for delete account operation
 */
export interface DeleteAccountResponse {
  message: string;
  deleted_at: string;
  restore_deadline: string;
}

/**
 * Response type for upload avatar operation
 */
export interface UploadAvatarResponse {
  profile_image_base64: string;
  message: string;
}

export interface ApiError {
  message: string;
  code?: string;
}

export type AgentStatus = "disabled" | "enabled";

/**
 * Chat history configuration for agent
 * 0 = Don't save messages (default)
 * 1 = Save text only
 * 2 = Save text + audio
 */
export type ChatHistoryConf = 0 | 1 | 2;

export const CHAT_HISTORY_CONF_VALUES = {
  DISABLED: 0,
  TEXT_ONLY: 1,
  TEXT_AND_AUDIO: 2,
} as const;

export const CHAT_HISTORY_CONF_LABELS: Record<ChatHistoryConf, string> = {
  0: "Không lưu message",
  1: "Chỉ lưu text",
  2: "Lưu text + audio",
};

export interface Device {
  id: string;
  user_id: string;
  mac_address: string;
  device_name: string | null;
  board: string | null;
  firmware_version: string | null;
  status: string | null;
  agent_id: string | null;
  last_connected_at?: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Provider Info Object - returned in GET responses
 * Contains resolved provider information including reference format
 */
export interface ProviderInfo {
  reference: string;
  id?: string;
  name: string;
  type: string;
  source: "default" | "user";
}

/**
 * Provider permission types
 */
export type ProviderPermission = "read" | "test" | "edit" | "delete";

/**
 * Provider Module Item - returned from /providers/config/modules endpoint
 * Used for dropdown selection in template creation
 */
export interface ProviderModuleItem {
  reference: string;
  id?: string;
  name: string;
  type: string;
  source: "default" | "user";
  permissions: ProviderPermission[];
}

/**
 * Agent Template - used in list responses with provider UUIDs
 * Note: is_active is determined by comparing template.id with agent.active_template_id
 */
export interface AgentTemplate {
  id: string;
  user_id: string;
  name: string;
  prompt: string;
  is_public?: boolean;
  tools?: string[] | null;
  ASR?: string | null;
  LLM?: string | null;
  VLLM?: string | null;
  TTS?: string | null;
  Memory?: string | null;
  Intent?: string | null;
  summary_memory?: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Agent Template Detail - used in GET agent detail with provider info objects
 * Provider fields contain resolved objects with reference format
 * Note: is_active is determined by comparing template.id with agent.active_template_id
 */
export interface AgentTemplateDetail {
  id: string;
  user_id: string;
  name: string;
  prompt: string;
  is_public?: boolean;
  tools?: string[] | null;
  ASR?: ProviderInfo | string | null;
  LLM?: ProviderInfo | string | null;
  VLLM?: ProviderInfo | string | null;
  TTS?: ProviderInfo | string | null;
  Memory?: ProviderInfo | string | null;
  Intent?: ProviderInfo | string | null;
  summary_memory?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: string;
  user_id: string;
  agent_name: string;
  description: string;
  status: AgentStatus;
  device_id?: string | null;
  device_mac_address?: string | null;
  active_template_id?: string | null;
  user_profile?: string | null;
  chat_history_conf?: ChatHistoryConf;
  created_at: string;
  updated_at: string;
  is_deleted?: boolean;
}

export interface AgentDetail extends Agent {
  template?: AgentTemplate | null;
  device?: Device | null;
}

export interface AgentDetailResponse {
  agent: Agent;
  device: Device | null;
  templates: AgentTemplateDetail[];
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * Agent Message Type - represents a single message in chat history
 * chat_type: 1 = User message, 2 = Assistant message
 */
export interface AgentMessage {
  id: string;
  agent_id: string;
  session_id: string;
  chat_type: 1 | 2;
  content: string;
  created_at: string;
}

/**
 * Chat Session - represents a conversation session
 */
export interface ChatSession {
  session_id: string;
  first_message_at: string;
  last_message_at: string;
  message_count: number;
}

export type AgentMessagesListResponse = PaginatedResponse<AgentMessage>;
export type ChatSessionsListResponse = PaginatedResponse<ChatSession>;

/**
 * Response for delete messages operation
 */
export interface DeleteMessagesResponse {
  success: boolean;
  message: string;
  data: {
    deleted_count: number;
  };
}

export type ReminderStatus = "pending" | "delivered" | "received" | "failed";

export interface ReminderRead {
  id: string;
  reminder_id: string;
  agent_id: string;
  content: string;
  title?: string;
  remind_at: string;
  remind_at_local: string;
  status: ReminderStatus;
  created_at: string;
  reminder_metadata?: Record<string, unknown>;
  received_at?: string;
  retry_count: number;
}

export interface CreateReminderPayload {
  content: string;
  title?: string;
  remind_at: string;
  reminder_metadata?: Record<string, unknown>;
}

export interface UpdateReminderPayload {
  content?: string;
  title?: string;
  remind_at?: string;
  reminder_metadata?: Record<string, unknown>;
}

export type AgentListResponse = PaginatedResponse<Agent>;
export type AgentTemplateListResponse = PaginatedResponse<AgentTemplate>;
export type DeviceListResponse = PaginatedResponse<Device>;

/**
 * Independent Template - returned from /api/v1/templates endpoints
 * Templates are now standalone resources that can be shared between agents
 */
export interface Template {
  id: string;
  user_id: string;
  name: string;
  prompt: string;
  is_public: boolean;
  summary_memory?: string | null;
  ASR?: ProviderInfo | null;
  LLM?: ProviderInfo | null;
  VLLM?: ProviderInfo | null;
  TTS?: ProviderInfo | null;
  Memory?: ProviderInfo | null;
  Intent?: ProviderInfo | null;
  tools?: string[] | null;
  created_at: string;
  updated_at: string;
}

/**
 * Template create/update payload
 * Provider fields accept reference strings (config:name or db:uuid)
 */
export interface TemplatePayload {
  name: string;
  prompt: string;
  is_public?: boolean;
  ASR?: string | null;
  LLM?: string | null;
  VLLM?: string | null;
  TTS?: string | null;
  Memory?: string | null;
  Intent?: string | null;
  tools?: string[] | null;
  summary_memory?: string | null;
}

export type UpdateTemplatePayload = Partial<TemplatePayload>;

/**
 * Template assignment - relationship between template and agent
 */
export interface TemplateAssignment {
  agent_id: string;
  template_id: string;
  is_active: boolean;
  assigned_at: string;
}

/**
 * Response wrapper for template assignment
 */
export interface TemplateAssignmentResponse {
  success: boolean;
  message: string;
  data: TemplateAssignment;
}

export type TemplateListResponse = PaginatedResponse<Template>;

/**
 * Provider Types
 */
export type ProviderCategory =
  | "LLM"
  | "TTS"
  | "VLLM"
  | "ASR"
  | "VAD"
  | "Memory"
  | "Intent";

export type ProviderFieldType =
  | "string"
  | "number"
  | "integer"
  | "boolean"
  | "secret"
  | "select";

export type ProviderSelectOption = string | { value: string; label: string };

export interface ProviderField {
  name: string;
  label: string;
  type: ProviderFieldType;
  required: boolean;
  placeholder?: string;
  default?: unknown;
  min?: number;
  max?: number;
  options?: ProviderSelectOption[];
}

export interface ProviderTypeSchema {
  label: string;
  description: string;
  fields: ProviderField[];
}

export interface ProviderSchemaResponse {
  categories: ProviderCategory[];
  data: Record<ProviderCategory, Record<string, ProviderTypeSchema>>;
}

export interface Provider {
  id: string;
  user_id: string;
  name: string;
  category: ProviderCategory;
  type: string;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  is_deleted?: boolean;
  /** Provider reference format (e.g., "db:uuid" or "config:name") */
  reference?: string;
  /** Provider source: "user" for database, "default" for config.yml */
  source?: "default" | "user";
  /** Allowed actions based on source */
  permissions?: ProviderPermission[];
}

export type ProviderListResponse = PaginatedResponse<Provider>;

export interface ProviderValidateRequest {
  category: ProviderCategory;
  type: string;
  config: Record<string, unknown>;
}

export interface ProviderValidateResponse {
  valid: boolean;
  normalized_config: Record<string, unknown> | null;
  errors: string[];
}

/**
 * Error codes returned from provider test endpoints
 */
export type ProviderTestErrorCode =
  | "AUTH_ERROR"
  | "CONNECTION_ERROR"
  | "TIMEOUT_ERROR"
  | "INVALID_AUDIO_FORMAT"
  | "AUDIO_TOO_LARGE"
  | "NO_OUTPUT"
  | "UNKNOWN_ERROR";

/**
 * Input data for testing providers
 * Different categories support different input fields
 */
export interface ProviderTestInputData {
  /** For LLM testing - custom prompt */
  prompt?: string;
  /** For TTS testing - custom text to synthesize */
  text?: string;
  /** For ASR testing - base64 encoded audio */
  audio_base64?: string;
  /** For ASR testing - audio format (wav, mp3, etc.) */
  audio_format?: string;
  /** For VLLM testing - base64 encoded image */
  image_base64?: string;
  /** For VLLM testing - question about the image */
  question?: string;
}

/**
 * Test output varies by provider category
 */
export interface ProviderTestOutput {
  /** Text output for LLM, ASR responses */
  text?: string;
  /** Audio output for TTS responses (base64 encoded) */
  audio_base64?: string;
  /** Audio format for TTS responses */
  audio_format?: "wav" | "mp3" | "ogg" | "aac";
  /** Audio size in bytes for TTS responses */
  audio_size_bytes?: number;
}

/**
 * Test result from provider test endpoints
 */
export interface ProviderTestResult {
  success: boolean;
  message?: string;
  latency_ms?: number;
  error?: string;
  error_code?: ProviderTestErrorCode;
  output?: ProviderTestOutput;
}

/**
 * Extended test request with optional input_data
 */
export interface ProviderTestRequest extends ProviderValidateRequest {
  input_data?: ProviderTestInputData | null;
}

/**
 * Response from POST /providers/test endpoint
 */
export interface ProviderTestResponse extends ProviderValidateResponse {
  test_result: ProviderTestResult;
}

/**
 * Request for validating provider reference format
 */
export interface ValidateReferenceRequest {
  category: string;
  reference: string;
}

/**
 * Response from POST /providers/validate-reference endpoint
 */
export interface ValidateReferenceResponse {
  valid: boolean;
  reference: string;
  resolved: {
    name: string;
    type: string;
    source: "default" | "user";
  } | null;
  errors: string[];
}

/**
 * Request for testing provider by reference string
 */
export interface TestReferenceRequest {
  reference: string;
  input_data?: ProviderTestInputData | null;
}

/**
 * Response from POST /providers/test-reference endpoint
 */
export interface TestReferenceResponse {
  valid: boolean;
  reference: string;
  source: "default" | "user" | null;
  category: string | null;
  type: string | null;
  errors: string[];
  test_result: ProviderTestResult | null;
}

/**
 * Tool Types
 */

/**
 * Tool category types
 */
export type ToolCategory =
  | "weather"
  | "music"
  | "reminder"
  | "news"
  | "agent"
  | "calendar"
  | "iot"
  | "other";

/**
 * Tool parameters schema (from function definition)
 */
export interface ToolParameters {
  type: string;
  properties?: Record<
    string,
    {
      type: string;
      description?: string;
      enum?: string[];
    }
  >;
  required?: string[];
}

/**
 * Tool schema definition (v2.0)
 */
export interface ToolSchema {
  name: string;
  display_name: string;
  description: string;
  category: ToolCategory;
  parameters?: ToolParameters;
}

/**
 * Response from GET /tools/available (v2.0)
 */
export interface ToolAvailableResponse {
  success: boolean;
  data: ToolSchema[];
  total: number;
}

/**
 * Tool option item for dropdown selection (v2.0)
 */
export interface ToolOptionItem {
  value: string;
  label: string;
  description?: string;
  category: ToolCategory;
}

/**
 * Response from GET /tools/options (v2.0)
 */
export interface ToolOptionsResponse {
  success: boolean;
  data: ToolOptionItem[];
  total: number;
}
