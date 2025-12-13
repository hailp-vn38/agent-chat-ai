/**
 * MCP Configuration Types
 * Based on mcp-config-endpoints.md
 */

/**
 * Transport type for MCP connection
 */
export type McpTransportType = "stdio" | "sse" | "http";

/**
 * MCP Configuration Interface
 */
export interface McpConfig {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  type: McpTransportType;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string; // For sse and http types
  headers?: Record<string, string>; // For http type
  tools?: McpTool[]; // Tools list from MCP server
  tools_last_synced_at?: string; // ISO 8601 timestamp
  is_active: boolean;
  is_deleted: boolean; // Soft delete flag
  created_at: string;
  updated_at: string;
}

/**
 * Payload for creating MCP configuration
 */
export interface McpConfigCreatePayload {
  name: string;
  description?: string;
  type: McpTransportType;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  tools?: McpToolInfo[]; // Optional tools list
  is_active?: boolean;
}

/**
 * Payload for updating MCP configuration
 */
export interface McpConfigUpdatePayload {
  name?: string;
  description?: string;
  type?: McpTransportType;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  tools?: McpToolInfo[]; // Optional tools list
  is_active?: boolean;
}

/**
 * Response type for MCP config list endpoint
 */
export interface McpConfigListResponse {
  success: boolean;
  data: McpConfig[];
  total: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
}

/**
 * Response type for MCP config detail endpoint
 */
export interface McpConfigDetailResponse {
  success: boolean;
  data: McpConfig;
}

/**
 * Tool information from MCP server
 */
export interface McpTool {
  name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
  inputSchema?: Record<string, unknown>; // API may return camelCase
}

/**
 * Tool information for create/update payloads
 */
export interface McpToolInfo {
  name: string; // Required
  description?: string | null;
  inputSchema?: Record<string, unknown> | null;
}

/**
 * Test result for MCP configuration
 */
export interface McpTestResult {
  success: boolean;
  latency?: number; // in milliseconds
  tools?: McpTool[];
  error?: string | null;
  message?: string;
}

/**
 * Tool change in refresh response
 */
export interface McpToolChange {
  name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
}

/**
 * Response from refresh-tools endpoint
 */
export interface McpRefreshToolsResponse {
  agent_id: string;
  config_id: string;
  config_name: string;
  mcp_server: string;
  tools: McpTool[];
  added: McpToolChange[];
  removed: McpToolChange[];
  updated: McpToolChange[];
  tools_last_synced_at: string;
  timestamp: string;
}

/**
 * Payload for test-raw endpoint (test config before saving)
 */
export interface McpTestRawPayload {
  name: string;
  type: McpTransportType;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
}

/**
 * Response from test-raw endpoint
 */
export interface McpTestRawResponse {
  success: boolean;
  message: string;
  name?: string;
  tools?: McpTool[];
  error?: string | null;
}

/**
 * Pagination parameters for list queries
 */
export interface McpListParams {
  page?: number;
  page_size?: number;
  search?: string; // Optional search filter
}
