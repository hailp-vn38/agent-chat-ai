/**
 * System MCP Server Types
 * Based on system-mcp.md documentation
 */

/**
 * Transport type for System MCP connection
 */
export type SystemMcpTransportType = "http" | "sse" | "stdio";

/**
 * System MCP Server Configuration from file
 */
export interface SystemMcpServer {
  name: string;
  type: SystemMcpTransportType;
  description: string;
  source: "config"; // Always 'config' for system servers
  is_active: boolean;
  url?: string; // For http and sse types
  command?: string; // For stdio type
}

/**
 * Response type for list system MCP servers endpoint
 */
export interface SystemMcpServerListResponse {
  success: boolean;
  message: string;
  data: SystemMcpServer[];
}

/**
 * Response type for get system MCP server detail endpoint
 */
export interface SystemMcpServerDetailResponse {
  success: boolean;
  message: string;
  data: SystemMcpServer;
}

/**
 * Tool information from MCP server
 */
export interface SystemMcpTool {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

/**
 * Response type for test system MCP server connection endpoint
 * Success case
 */
export interface SystemMcpTestResultSuccess {
  success: true;
  message: string;
  name: string;
  tools: SystemMcpTool[];
  error: null;
}

/**
 * Response type for test system MCP server connection endpoint
 * Failure case
 */
export interface SystemMcpTestResultFailure {
  success: false;
  message: string;
  name: string;
  tools: null;
  error: string;
}

/**
 * Response type for test system MCP server connection endpoint
 */
export type SystemMcpTestResult =
  | SystemMcpTestResultSuccess
  | SystemMcpTestResultFailure;

/**
 * Response type for reload system MCP configuration endpoint
 */
export interface SystemMcpReloadResponse {
  success: boolean;
  message: string;
  data: {
    message: string;
    servers_count: number;
    server_names: string[];
  };
}

/**
 * Pagination parameters for list queries
 */
export interface SystemMcpListParams {
  page?: number;
  page_size?: number;
  search?: string; // Optional search filter
}
