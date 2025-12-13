/**
 * Agent MCP Selection Types
 * Refactored from tool selection to MCP server selection
 * Based on REFACTOR_AGENT_MCP_SELECTION.md
 */

/**
 * MCP selection mode for agent
 */
export type McpSelectionMode = "all" | "selected";

/**
 * MCP Server in Agent Selection
 * Contains reference and resolved metadata
 */
export interface MCPServerSelected {
  id?: string; // UUID from agent_mcp_server_selected table
  reference: string; // Format: "db:{uuid}" | "config:{name}"
  mcp_name: string; // Resolved server name
  mcp_type: string; // "stdio", "sse", "http", etc.
  mcp_description?: string; // Resolved server description
  source: "user" | "config"; // Whether from user or config
  is_active: boolean; // Whether this server is active
  resolved_at?: string; // ISO timestamp of when metadata was resolved
}

/**
 * MCP Server Reference for requests
 * Format: "db:{uuid}" (user-scoped) | "config:{name}" (system)
 *
 * @example
 * - "db:550e8400-e29b-41d4-a716-446655440000" - User MCP server
 * - "config:filesystem" - System MCP server from config.yml
 */
export interface MCPServerReference {
  reference: string; // Format: "db:{uuid}" | "config:{name}"
}

/**
 * MCP Selection for an agent
 */
export interface MCPSelection {
  mode: McpSelectionMode;
  servers: MCPServerReference[];
}

/**
 * Current MCP selection configuration for an agent
 * Based on agent_mcp_selection table with resolved server metadata
 */
export interface AgentMcpSelection {
  id?: string; // UUID from agent_mcp_selection table
  agent_id: string;
  mode?: McpSelectionMode; // "all" or "selected" (alternative field name)
  mcp_selection_mode?: McpSelectionMode; // "all" or "selected" (primary from API)
  servers: MCPServerSelected[]; // Selected servers with resolved metadata
  created_at?: string;
  updated_at?: string;
}

/**
 * Helper to get mode from AgentMcpSelection (supports both naming conventions)
 */
export const getAgentMcpMode = (
  selection: AgentMcpSelection
): McpSelectionMode => {
  return (selection.mcp_selection_mode || selection.mode) as McpSelectionMode;
};

/**
 * Payload for updating agent MCP selection
 */
export interface UpdateAgentMcpPayload {
  mode: McpSelectionMode; // "all" or "selected"
  servers?: MCPServerReference[]; // Only required if mode is "selected"
}

/**
 * Source filter for available MCP servers
 */
export type McpSourceFilter = "all" | "user" | "config";

/**
 * Available MCP server from list
 */
export interface AvailableMcpServer {
  reference: string;
  name: string;
  display_name: string;
  description: string | null;
  type: string; // "stdio", "sse", "http", etc.
  source: "user" | "config";
  permissions: Array<"read" | "test" | "edit" | "delete">;
  is_active?: boolean;
  id?: string;
  user_id?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Response type for agent MCP endpoints
 * API returns success wrapper with data containing AgentMcpSelection
 */
export interface AgentMcpSelectionResponse {
  success: boolean;
  message?: string;
  data: AgentMcpSelection;
}

/**
 * Response type for available MCP servers endpoint
 * Data structure from /agents/{id}/mcp/available
 */
export interface AvailableMcpServersResponse {
  agent_id: string;
  mcp_servers: AvailableMcpServer[];
  total: number;
  source_filter: McpSourceFilter;
}

/**
 * @deprecated Use AgentMcpSelection instead
 */
export type ToolSelectionMode = "all" | "selected";

/**
 * @deprecated Use MCPServerReference instead
 */
export type ToolType = "server_mcp" | "server_plugin";

/**
 * @deprecated Use MCPServerReference instead
 */
export interface ToolReference {
  type: ToolType;
  name: string;
}

/**
 * @deprecated Use AgentMcpSelection instead
 */
export interface AgentToolSelection {
  agent_id: string;
  mode: ToolSelectionMode;
  tools: ToolReference[];
  total_tools: number;
}

/**
 * @deprecated Use UpdateAgentMcpPayload instead
 */
export interface UpdateAgentToolsPayload {
  mode: ToolSelectionMode;
  tools?: ToolReference[];
}

/**
 * @deprecated No longer used - MCP server selection replaces tool selection
 */
export interface AvailableMcpTool {
  name: string;
  description: string;
  config_name: string;
  input_schema?: Record<string, unknown>;
}

/**
 * @deprecated No longer used - MCP server selection replaces tool selection
 */
export interface AvailablePluginTool {
  name: string;
  description: string;
  plugin_name: string;
  category?: string;
  input_schema?: Record<string, unknown>;
}

/**
 * @deprecated Use AgentMcpSelectionResponse instead
 */
export interface AgentToolSelectionResponse {
  success: boolean;
  data: AgentToolSelection;
}

/**
 * @deprecated Use AvailableMcpServersResponse instead
 */
export interface AvailableMcpToolsResponse {
  success: boolean;
  data: AvailableMcpTool[];
  total: number;
}

/**
 * @deprecated Removed in refactor - no more plugin tools
 */
export interface AvailablePluginToolsResponse {
  success: boolean;
  data: AvailablePluginTool[];
  total: number;
}
