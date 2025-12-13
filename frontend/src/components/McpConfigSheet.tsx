import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertCircle,
  Eye,
  EyeOff,
  RefreshCw,
  Edit,
  Trash2,
} from "lucide-react";
import { Spinner } from "@/components/ui/spinner";

import type {
  McpConfigCreatePayload,
  McpConfigUpdatePayload,
  McpTestRawPayload,
  McpTestRawResponse,
  McpRefreshToolsResponse,
} from "@types";
import {
  useMcpConfig,
  useCreateMcpConfig,
  useUpdateMcpConfig,
  useDeleteMcpConfig,
  useTestRawMcpConfig,
  useRefreshMcpTools,
} from "@/queries";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Trash2 as TrashIcon, Plus } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface FormState {
  name: string;
  description: string;
  type: "stdio" | "sse" | "http";
  command: string;
  args: string[];
  env: Array<{ key: string; value: string }>;
  url: string;
  headers: Array<{ key: string; value: string }>;
  is_active: boolean;
}

interface ValidationErrors {
  name?: string;
  command?: string;
  url?: string;
}

export interface McpConfigSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit" | "view";
  configId?: string;
  onDelete?: (configId: string) => void;
  onModeChange?: (mode: "create" | "edit" | "view", configId?: string) => void;
}

const validateForm = (form: FormState): ValidationErrors => {
  const errors: ValidationErrors = {};

  if (!form.name.trim()) {
    errors.name = "Name is required";
  } else if (!/^[a-z0-9_]{3,255}$/.test(form.name)) {
    errors.name =
      "Name must be 3-255 chars, lowercase, numbers, underscores only";
  }

  if (form.type === "stdio") {
    if (!form.command.trim()) {
      errors.command = "Command is required for stdio type";
    }
  } else {
    if (!form.url.trim()) {
      errors.url = "URL is required for sse/http type";
    } else {
      try {
        new URL(form.url);
      } catch {
        errors.url = "Invalid URL format";
      }
    }
  }

  return errors;
};

const maskValue = (value: string): string => {
  if (!value || value.length <= 4) return "*".repeat(8);
  return (
    value.slice(0, 2) +
    "*".repeat(Math.max(4, value.length - 4)) +
    value.slice(-2)
  );
};

export const McpConfigSheet = ({
  open,
  onOpenChange,
  mode,
  configId,
  onDelete,
  onModeChange,
}: McpConfigSheetProps) => {
  const { t } = useTranslation(["mcp-configs", "common"]);

  // Internal mode state for transitions
  const [internalMode, setInternalMode] = useState<"create" | "edit" | "view">(
    mode
  );
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>(
    {}
  );
  const [testResult, setTestResult] = useState<McpTestRawResponse | null>(null);
  const [refreshDiff, setRefreshDiff] =
    useState<McpRefreshToolsResponse | null>(null);
  const [showSensitive, setShowSensitive] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  // Queries
  const { data: configData, refetch: refetchConfig } = useMcpConfig(
    configId || "",
    (mode === "edit" || mode === "view") && !!configId
  );
  const createMutation = useCreateMcpConfig();
  const updateMutation = useUpdateMcpConfig();
  const deleteMutation = useDeleteMcpConfig();
  const testRawMutation = useTestRawMcpConfig();
  const refreshMutation = useRefreshMcpTools();

  const config = configData?.data;

  // Form state
  const [form, setForm] = useState<FormState>({
    name: "",
    description: "",
    type: "stdio",
    command: "",
    args: [],
    env: [],
    url: "",
    headers: [],
    is_active: true,
  });

  // Sync internal mode with prop mode
  useEffect(() => {
    setInternalMode(mode);
  }, [mode]);

  // Reset form when sheet opens or config changes
  useEffect(() => {
    if (!open) return;

    setError(null);
    setValidationErrors({});
    setTestResult(null);
    setRefreshDiff(null);
    setShowSensitive(false);
    setSearchTerm("");

    if (internalMode === "create") {
      setForm({
        name: "",
        description: "",
        type: "stdio",
        command: "",
        args: [],
        env: [],
        url: "",
        headers: [],
        is_active: true,
      });
    } else if (config && (internalMode === "edit" || internalMode === "view")) {
      setForm({
        name: config.name,
        description: config.description || "",
        type: config.type,
        command: config.command || "",
        args: config.args || [],
        env: config.env
          ? Object.entries(config.env).map(([key, value]) => ({
              key,
              value: value as string,
            }))
          : [],
        url: config.url || "",
        headers: config.headers
          ? Object.entries(config.headers).map(([key, value]) => ({
              key,
              value: value as string,
            }))
          : [],
        is_active: config.is_active,
      });
    }
  }, [open, config, internalMode]);

  // Tools list with search filter
  const tools = useMemo(() => {
    const toolsList =
      internalMode === "view" && config?.tools
        ? config.tools
        : testResult?.tools || [];
    if (!searchTerm.trim()) return toolsList;
    const term = searchTerm.toLowerCase();
    return toolsList.filter(
      (tool) =>
        tool.name.toLowerCase().includes(term) ||
        tool.description?.toLowerCase().includes(term)
    );
  }, [config?.tools, testResult?.tools, searchTerm, internalMode]);

  // Handlers
  const handleTestConnection = async () => {
    setError(null);
    setTestResult(null);

    const errors = validateForm(form);
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    try {
      const envObject = form.env.reduce((acc, item) => {
        if (item.key) acc[item.key] = item.value;
        return acc;
      }, {} as Record<string, string>);

      const headersObject = form.headers.reduce((acc, item) => {
        if (item.key) acc[item.key] = item.value;
        return acc;
      }, {} as Record<string, string>);

      const payload: McpTestRawPayload = {
        name: form.name,
        type: form.type,
        ...(form.type === "stdio"
          ? {
              command: form.command,
              args: form.args.length > 0 ? form.args : undefined,
              env: Object.keys(envObject).length > 0 ? envObject : undefined,
            }
          : {
              url: form.url,
              headers:
                Object.keys(headersObject).length > 0
                  ? headersObject
                  : undefined,
            }),
      };

      const result = await testRawMutation.mutateAsync(payload);
      setTestResult(result);
      if (!result.success) {
        setError(result.message || "Test failed");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Test failed";
      setError(message);
    }
  };

  const handleSave = async () => {
    setError(null);

    const errors = validateForm(form);
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    // For create mode, require successful test
    if (internalMode === "create" && (!testResult || !testResult.success)) {
      setError("Please test connection before saving");
      return;
    }

    try {
      const envObject = form.env.reduce((acc, item) => {
        if (item.key) acc[item.key] = item.value;
        return acc;
      }, {} as Record<string, string>);

      const headersObject = form.headers.reduce((acc, item) => {
        if (item.key) acc[item.key] = item.value;
        return acc;
      }, {} as Record<string, string>);

      const payload: McpConfigCreatePayload | McpConfigUpdatePayload = {
        name: form.name,
        description: form.description || undefined,
        type: form.type,
        command: form.type === "stdio" ? form.command : undefined,
        args:
          form.type === "stdio" && form.args.length > 0 ? form.args : undefined,
        env:
          form.type === "stdio" && Object.keys(envObject).length > 0
            ? envObject
            : undefined,
        url: form.type !== "stdio" ? form.url : undefined,
        headers:
          form.type !== "stdio" && Object.keys(headersObject).length > 0
            ? headersObject
            : undefined,
        is_active: form.is_active,
        // Include tools from test result for create mode
        ...(internalMode === "create" && testResult?.tools
          ? {
              tools: testResult.tools.map((tool) => ({
                name: tool.name,
                description: tool.description || null,
                inputSchema: tool.input_schema || null,
              })),
            }
          : {}),
      };

      if (internalMode === "create") {
        const result = await createMutation.mutateAsync(
          payload as McpConfigCreatePayload
        );
        const savedId = result.data.id;
        if (savedId && onModeChange) {
          // Update parent to switch to view mode with saved ID
          onModeChange("view", savedId);
        } else if (savedId) {
          setInternalMode("view");
        }
        // Refetch will happen via parent's refetch
      } else if (configId) {
        await updateMutation.mutateAsync({
          configId,
          payload: payload as McpConfigUpdatePayload,
        });
        await refetchConfig();
        setInternalMode("view");
        if (onModeChange) {
          onModeChange("view", configId);
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Save failed";
      setError(message);
    }
  };

  const handleRefreshTools = async () => {
    if (!configId) return;

    setError(null);
    setRefreshDiff(null);

    try {
      const result = await refreshMutation.mutateAsync(configId);
      setRefreshDiff(result);
      await refetchConfig();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Refresh failed";
      setError(message);
    }
  };

  const handleEdit = () => {
    setInternalMode("edit");
  };

  const handleCancelEdit = () => {
    if (config) {
      setForm({
        name: config.name,
        description: config.description || "",
        type: config.type,
        command: config.command || "",
        args: config.args || [],
        env: config.env
          ? Object.entries(config.env).map(([key, value]) => ({
              key,
              value: value as string,
            }))
          : [],
        url: config.url || "",
        headers: config.headers
          ? Object.entries(config.headers).map(([key, value]) => ({
              key,
              value: value as string,
            }))
          : [],
        is_active: config.is_active,
      });
    }
    setInternalMode("view");
    setError(null);
    setValidationErrors({});
    setTestResult(null);
  };

  const handleDelete = () => {
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!configId) return;

    try {
      await deleteMutation.mutateAsync(configId);
      setDeleteConfirmOpen(false);
      onOpenChange(false);
      if (onDelete) {
        onDelete(configId);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Delete failed";
      setError(message);
    }
  };

  const getDisplayValue = (value: string | undefined) => {
    if (!value) return "—";
    return showSensitive ? value : maskValue(value);
  };

  const isLoading =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    testRawMutation.isPending ||
    refreshMutation.isPending ||
    (internalMode !== "create" && !config);

  const modeLabel =
    internalMode === "create"
      ? t("new_mcp_config", "New MCP Configuration")
      : internalMode === "edit"
      ? t("edit_mcp_config", "Edit MCP Configuration")
      : t("view_mcp_config", "MCP Configuration Details");

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full max-w-xl overflow-y-auto p-6 sm:max-w-lg md:max-w-xl">
          <SheetHeader>
            <SheetTitle className="flex items-center justify-between">
              <span>{modeLabel}</span>
              {internalMode === "view" && config && (
                <Badge variant={config.is_active ? "success" : "secondary"}>
                  {config.is_active
                    ? t("status_active", "Active")
                    : t("status_inactive", "Inactive")}
                </Badge>
              )}
            </SheetTitle>
            <SheetDescription>
              {internalMode === "create"
                ? t(
                    "mcp_config_dialog_desc",
                    "Configure MCP server connection for your agents"
                  )
                : config?.name || ""}
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-6 py-4">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* CREATE MODE */}
            {internalMode === "create" && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSave();
                }}
                className="space-y-6"
              >
                {/* Form fields - same as Dialog */}
                {/* Basic Info */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-sm">
                    {t("basic_info", "Basic Information")}
                  </h3>

                  <div className="space-y-2">
                    <Label htmlFor="name">{t("field_name", "Name")}</Label>
                    <Input
                      id="name"
                      placeholder="e.g., openai-mcp"
                      value={form.name}
                      onChange={(e) =>
                        setForm({ ...form, name: e.target.value })
                      }
                      disabled={isLoading}
                    />
                    {validationErrors.name && (
                      <p className="text-xs text-destructive">
                        {validationErrors.name}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">
                      {t("field_description", "Description")}
                    </Label>
                    <Input
                      id="description"
                      placeholder="Optional description"
                      value={form.description}
                      onChange={(e) =>
                        setForm({ ...form, description: e.target.value })
                      }
                      disabled={isLoading}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="type">{t("field_type", "Type")}</Label>
                    <Select
                      value={form.type}
                      onValueChange={(value) =>
                        setForm({
                          ...form,
                          type: value as "stdio" | "sse" | "http",
                        })
                      }
                      disabled={isLoading}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="stdio">Standard I/O</SelectItem>
                        <SelectItem value="sse">Server-Sent Events</SelectItem>
                        <SelectItem value="http">HTTP</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Stdio Config */}
                {form.type === "stdio" && (
                  <div className="space-y-4">
                    <h3 className="font-semibold text-sm">
                      {t("stdio_config", "Standard I/O Configuration")}
                    </h3>

                    <div className="space-y-2">
                      <Label htmlFor="command">
                        {t("field_command", "Command")}
                      </Label>
                      <Input
                        id="command"
                        placeholder="e.g., node"
                        value={form.command}
                        onChange={(e) =>
                          setForm({ ...form, command: e.target.value })
                        }
                        disabled={isLoading}
                      />
                      {validationErrors.command && (
                        <p className="text-xs text-destructive">
                          {validationErrors.command}
                        </p>
                      )}
                    </div>

                    {/* Args */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>{t("field_args", "Arguments")}</Label>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setForm({ ...form, args: [...form.args, ""] })
                          }
                          disabled={isLoading}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        {form.args.map((arg, index) => (
                          <div key={index} className="flex gap-2">
                            <Input
                              value={arg}
                              onChange={(e) => {
                                const newArgs = [...form.args];
                                newArgs[index] = e.target.value;
                                setForm({ ...form, args: newArgs });
                              }}
                              placeholder={`Argument ${index + 1}`}
                              disabled={isLoading}
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const newArgs = form.args.filter(
                                  (_, i) => i !== index
                                );
                                setForm({ ...form, args: newArgs });
                              }}
                              disabled={isLoading}
                            >
                              <TrashIcon className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Environment Variables */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>{t("field_env", "Environment Variables")}</Label>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setForm({
                              ...form,
                              env: [...form.env, { key: "", value: "" }],
                            })
                          }
                          disabled={isLoading}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        {form.env.map((item, index) => (
                          <div key={index} className="flex gap-2">
                            <Input
                              value={item.key}
                              onChange={(e) => {
                                const newEnv = [...form.env];
                                newEnv[index] = {
                                  ...newEnv[index],
                                  key: e.target.value,
                                };
                                setForm({ ...form, env: newEnv });
                              }}
                              placeholder="KEY"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Input
                              value={item.value}
                              onChange={(e) => {
                                const newEnv = [...form.env];
                                newEnv[index] = {
                                  ...newEnv[index],
                                  value: e.target.value,
                                };
                                setForm({ ...form, env: newEnv });
                              }}
                              placeholder="VALUE"
                              type="password"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const newEnv = form.env.filter(
                                  (_, i) => i !== index
                                );
                                setForm({ ...form, env: newEnv });
                              }}
                              disabled={isLoading}
                            >
                              <TrashIcon className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* SSE/HTTP Config */}
                {(form.type === "sse" || form.type === "http") && (
                  <div className="space-y-4">
                    <h3 className="font-semibold text-sm">
                      {form.type === "sse"
                        ? t("sse_config", "SSE Configuration")
                        : t("http_config", "HTTP Configuration")}
                    </h3>

                    <div className="space-y-2">
                      <Label htmlFor="url">{t("field_url", "URL")}</Label>
                      <Input
                        id="url"
                        placeholder="https://example.com"
                        value={form.url}
                        onChange={(e) =>
                          setForm({ ...form, url: e.target.value })
                        }
                        disabled={isLoading}
                      />
                      {validationErrors.url && (
                        <p className="text-xs text-destructive">
                          {validationErrors.url}
                        </p>
                      )}
                    </div>

                    {/* Headers */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>{t("field_headers", "HTTP Headers")}</Label>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setForm({
                              ...form,
                              headers: [
                                ...form.headers,
                                { key: "", value: "" },
                              ],
                            })
                          }
                          disabled={isLoading}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        {form.headers.map((item, index) => (
                          <div key={index} className="flex gap-2">
                            <Input
                              value={item.key}
                              onChange={(e) => {
                                const newHeaders = [...form.headers];
                                newHeaders[index] = {
                                  ...newHeaders[index],
                                  key: e.target.value,
                                };
                                setForm({ ...form, headers: newHeaders });
                              }}
                              placeholder="Header Name"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Input
                              value={item.value}
                              onChange={(e) => {
                                const newHeaders = [...form.headers];
                                newHeaders[index] = {
                                  ...newHeaders[index],
                                  value: e.target.value,
                                };
                                setForm({ ...form, headers: newHeaders });
                              }}
                              placeholder="Header Value"
                              type="password"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const newHeaders = form.headers.filter(
                                  (_, i) => i !== index
                                );
                                setForm({ ...form, headers: newHeaders });
                              }}
                              disabled={isLoading}
                            >
                              <TrashIcon className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Test Result */}
                {testResult && (
                  <div className="space-y-4">
                    <Alert
                      variant={testResult.success ? "default" : "destructive"}
                    >
                      <AlertDescription>
                        {testResult.success ? (
                          <div className="space-y-2">
                            <p>{testResult.message}</p>
                            {testResult.tools &&
                              testResult.tools.length > 0 && (
                                <Badge variant="outline">
                                  {testResult.tools.length}{" "}
                                  {t("tools_found", "tools found")}
                                </Badge>
                              )}
                          </div>
                        ) : (
                          <div>
                            <p>{testResult.message}</p>
                            {testResult.error && (
                              <p className="text-sm text-muted-foreground mt-1">
                                {testResult.error}
                              </p>
                            )}
                          </div>
                        )}
                      </AlertDescription>
                    </Alert>

                    {/* Tools List */}
                    {testResult.success &&
                      testResult.tools &&
                      testResult.tools.length > 0 && (
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold">
                            {t("available_tools", "Available Tools")}
                          </h4>
                          <div className="max-h-[300px] space-y-2 overflow-y-auto rounded-lg border bg-muted/30 p-3">
                            {testResult.tools.map((tool) => {
                              const schema =
                                tool.inputSchema || tool.input_schema;
                              return (
                                <div
                                  key={tool.name}
                                  className="space-y-1 border-b last:border-0 pb-2 last:pb-0"
                                >
                                  <p className="text-sm font-medium">
                                    {tool.name}
                                  </p>
                                  <p className="text-xs text-muted-foreground line-clamp-3">
                                    {tool.description || "No description"}
                                  </p>
                                  {schema && (
                                    <details className="text-xs text-muted-foreground">
                                      <summary className="cursor-pointer hover:text-foreground">
                                        {t("input_schema", "Input schema")}
                                      </summary>
                                      <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 text-[10px]">
                                        {JSON.stringify(schema, null, 2)}
                                      </pre>
                                    </details>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                  </div>
                )}

                {/* Form Actions */}
                <SheetFooter className="flex-row gap-2 pt-6 border-t">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => onOpenChange(false)}
                    disabled={isLoading}
                  >
                    {t("btn_cancel", "Cancel")}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleTestConnection}
                    disabled={isLoading || testRawMutation.isPending}
                  >
                    {testRawMutation.isPending ? (
                      <>
                        <Spinner className="mr-2 h-4 w-4" />
                        {t("testing", "Testing...")}
                      </>
                    ) : (
                      t("btn_test_connection", "Test Connection")
                    )}
                  </Button>
                  <Button
                    type="submit"
                    disabled={isLoading || !testResult?.success}
                  >
                    {isLoading
                      ? t("saving", "Saving...")
                      : t("btn_save", "Save")}
                  </Button>
                </SheetFooter>
              </form>
            )}

            {/* EDIT MODE */}
            {internalMode === "edit" && config && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSave();
                }}
                className="space-y-6"
              >
                {/* Same form fields as create mode, but pre-filled */}
                {/* Basic Info */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-sm">
                    {t("basic_info", "Basic Information")}
                  </h3>

                  <div className="space-y-2">
                    <Label htmlFor="name">{t("field_name", "Name")}</Label>
                    <Input
                      id="name"
                      placeholder="e.g., openai-mcp"
                      value={form.name}
                      onChange={(e) =>
                        setForm({ ...form, name: e.target.value })
                      }
                      disabled={isLoading}
                    />
                    {validationErrors.name && (
                      <p className="text-xs text-destructive">
                        {validationErrors.name}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">
                      {t("field_description", "Description")}
                    </Label>
                    <Input
                      id="description"
                      placeholder="Optional description"
                      value={form.description}
                      onChange={(e) =>
                        setForm({ ...form, description: e.target.value })
                      }
                      disabled={isLoading}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="type">{t("field_type", "Type")}</Label>
                    <Select
                      value={form.type}
                      onValueChange={(value) =>
                        setForm({
                          ...form,
                          type: value as "stdio" | "sse" | "http",
                        })
                      }
                      disabled={true} // Type is read-only in edit mode
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="stdio">Standard I/O</SelectItem>
                        <SelectItem value="sse">Server-Sent Events</SelectItem>
                        <SelectItem value="http">HTTP</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Stdio Config - same as create */}
                {form.type === "stdio" && (
                  <div className="space-y-4">
                    <h3 className="font-semibold text-sm">
                      {t("stdio_config", "Standard I/O Configuration")}
                    </h3>

                    <div className="space-y-2">
                      <Label htmlFor="command">
                        {t("field_command", "Command")}
                      </Label>
                      <Input
                        id="command"
                        placeholder="e.g., node"
                        value={form.command}
                        onChange={(e) =>
                          setForm({ ...form, command: e.target.value })
                        }
                        disabled={isLoading}
                      />
                      {validationErrors.command && (
                        <p className="text-xs text-destructive">
                          {validationErrors.command}
                        </p>
                      )}
                    </div>

                    {/* Args */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>{t("field_args", "Arguments")}</Label>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setForm({ ...form, args: [...form.args, ""] })
                          }
                          disabled={isLoading}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        {form.args.map((arg, index) => (
                          <div key={index} className="flex gap-2">
                            <Input
                              value={arg}
                              onChange={(e) => {
                                const newArgs = [...form.args];
                                newArgs[index] = e.target.value;
                                setForm({ ...form, args: newArgs });
                              }}
                              placeholder={`Argument ${index + 1}`}
                              disabled={isLoading}
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const newArgs = form.args.filter(
                                  (_, i) => i !== index
                                );
                                setForm({ ...form, args: newArgs });
                              }}
                              disabled={isLoading}
                            >
                              <TrashIcon className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Environment Variables */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>{t("field_env", "Environment Variables")}</Label>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setForm({
                              ...form,
                              env: [...form.env, { key: "", value: "" }],
                            })
                          }
                          disabled={isLoading}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        {form.env.map((item, index) => (
                          <div key={index} className="flex gap-2">
                            <Input
                              value={item.key}
                              onChange={(e) => {
                                const newEnv = [...form.env];
                                newEnv[index] = {
                                  ...newEnv[index],
                                  key: e.target.value,
                                };
                                setForm({ ...form, env: newEnv });
                              }}
                              placeholder="KEY"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Input
                              value={item.value}
                              onChange={(e) => {
                                const newEnv = [...form.env];
                                newEnv[index] = {
                                  ...newEnv[index],
                                  value: e.target.value,
                                };
                                setForm({ ...form, env: newEnv });
                              }}
                              placeholder="VALUE"
                              type="password"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const newEnv = form.env.filter(
                                  (_, i) => i !== index
                                );
                                setForm({ ...form, env: newEnv });
                              }}
                              disabled={isLoading}
                            >
                              <TrashIcon className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* SSE/HTTP Config */}
                {(form.type === "sse" || form.type === "http") && (
                  <div className="space-y-4">
                    <h3 className="font-semibold text-sm">
                      {form.type === "sse"
                        ? t("sse_config", "SSE Configuration")
                        : t("http_config", "HTTP Configuration")}
                    </h3>

                    <div className="space-y-2">
                      <Label htmlFor="url">{t("field_url", "URL")}</Label>
                      <Input
                        id="url"
                        placeholder="https://example.com"
                        value={form.url}
                        onChange={(e) =>
                          setForm({ ...form, url: e.target.value })
                        }
                        disabled={isLoading}
                      />
                      {validationErrors.url && (
                        <p className="text-xs text-destructive">
                          {validationErrors.url}
                        </p>
                      )}
                    </div>

                    {/* Headers */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>{t("field_headers", "HTTP Headers")}</Label>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setForm({
                              ...form,
                              headers: [
                                ...form.headers,
                                { key: "", value: "" },
                              ],
                            })
                          }
                          disabled={isLoading}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        {form.headers.map((item, index) => (
                          <div key={index} className="flex gap-2">
                            <Input
                              value={item.key}
                              onChange={(e) => {
                                const newHeaders = [...form.headers];
                                newHeaders[index] = {
                                  ...newHeaders[index],
                                  key: e.target.value,
                                };
                                setForm({ ...form, headers: newHeaders });
                              }}
                              placeholder="Header Name"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Input
                              value={item.value}
                              onChange={(e) => {
                                const newHeaders = [...form.headers];
                                newHeaders[index] = {
                                  ...newHeaders[index],
                                  value: e.target.value,
                                };
                                setForm({ ...form, headers: newHeaders });
                              }}
                              placeholder="Header Value"
                              type="password"
                              disabled={isLoading}
                              className="flex-1"
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                const newHeaders = form.headers.filter(
                                  (_, i) => i !== index
                                );
                                setForm({ ...form, headers: newHeaders });
                              }}
                              disabled={isLoading}
                            >
                              <TrashIcon className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Form Actions */}
                <SheetFooter className="flex-row gap-2 pt-6 border-t">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCancelEdit}
                    disabled={isLoading}
                  >
                    {t("btn_cancel", "Cancel")}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleTestConnection}
                    disabled={isLoading || testRawMutation.isPending}
                  >
                    {testRawMutation.isPending ? (
                      <>
                        <Spinner className="mr-2 h-4 w-4" />
                        {t("testing", "Testing...")}
                      </>
                    ) : (
                      t("btn_test_connection", "Test Connection")
                    )}
                  </Button>
                  <Button type="submit" disabled={isLoading}>
                    {isLoading
                      ? t("saving", "Saving...")
                      : t("btn_save_changes", "Save Changes")}
                  </Button>
                </SheetFooter>
              </form>
            )}

            {/* VIEW MODE */}
            {internalMode === "view" && config && (
              <div className="space-y-6">
                {/* Configuration Section */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-base">
                    {t("configuration", "Cấu hình")}
                  </h3>

                  <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">
                        {t("field_type", "Type")}
                      </p>
                      <p className="text-sm font-medium capitalize">
                        {config.type}
                      </p>
                    </div>

                    {config.type === "stdio" && (
                      <>
                        <Separator className="my-2" />
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">
                            {t("field_command", "Command")}
                          </p>
                          <p className="text-sm font-mono">
                            {config.command || "—"}
                          </p>
                        </div>

                        {config.args && config.args.length > 0 && (
                          <>
                            <Separator className="my-2" />
                            <div>
                              <p className="text-xs font-medium text-muted-foreground">
                                {t("field_args", "Arguments")}
                              </p>
                              <ul className="mt-2 space-y-1">
                                {config.args.map((arg, idx) => (
                                  <li
                                    key={idx}
                                    className="text-sm font-mono text-muted-foreground"
                                  >
                                    • {arg}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </>
                        )}

                        {config.env && Object.keys(config.env).length > 0 && (
                          <>
                            <Separator className="my-2" />
                            <div>
                              <p className="text-xs font-medium text-muted-foreground mb-2">
                                {t("field_env", "Environment Variables")}
                              </p>
                              <ul className="space-y-2">
                                {Object.entries(config.env).map(
                                  ([key, value]) => (
                                    <li key={key} className="text-xs">
                                      <span className="font-medium">{key}</span>
                                      <span className="text-muted-foreground">
                                        = {getDisplayValue(value as string)}
                                      </span>
                                    </li>
                                  )
                                )}
                              </ul>
                            </div>
                          </>
                        )}
                      </>
                    )}

                    {(config.type === "sse" || config.type === "http") && (
                      <>
                        <Separator className="my-2" />
                        <div>
                          <p className="text-xs font-medium text-muted-foreground">
                            {t("field_url", "URL")}
                          </p>
                          <p className="text-sm font-mono break-all text-muted-foreground">
                            {config.url || "—"}
                          </p>
                        </div>

                        {config.headers &&
                          Object.keys(config.headers).length > 0 && (
                            <>
                              <Separator className="my-2" />
                              <div>
                                <p className="text-xs font-medium text-muted-foreground mb-2">
                                  {t("field_headers", "HTTP Headers")}
                                </p>
                                <ul className="space-y-2">
                                  {Object.entries(config.headers).map(
                                    ([key, value]) => (
                                      <li key={key} className="text-xs">
                                        <span className="font-medium">
                                          {key}
                                        </span>
                                        <span className="text-muted-foreground">
                                          : {getDisplayValue(value as string)}
                                        </span>
                                      </li>
                                    )
                                  )}
                                </ul>
                              </div>
                            </>
                          )}
                      </>
                    )}
                  </div>

                  {/* Show Sensitive Data Toggle */}
                  {(config.env?.toString() || config.headers?.toString()) && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowSensitive(!showSensitive)}
                      className="w-full justify-start text-xs text-muted-foreground"
                    >
                      {showSensitive ? (
                        <>
                          <EyeOff className="mr-2 h-3.5 w-3.5" />
                          {t("hide_sensitive", "Hide sensitive data")}
                        </>
                      ) : (
                        <>
                          <Eye className="mr-2 h-3.5 w-3.5" />
                          {t("show_sensitive", "Show sensitive data")}
                        </>
                      )}
                    </Button>
                  )}
                </div>

                {/* Refresh Diff Display */}
                {refreshDiff && (
                  <Alert>
                    <AlertDescription>
                      <div className="space-y-2">
                        <p>
                          {t(
                            "refresh_complete",
                            "Tools refreshed successfully"
                          )}
                        </p>
                        <div className="flex gap-2 flex-wrap">
                          {refreshDiff.added &&
                            refreshDiff.added.length > 0 && (
                              <Badge variant="default" className="bg-green-500">
                                {refreshDiff.added.length} {t("added", "added")}
                              </Badge>
                            )}
                          {refreshDiff.removed &&
                            refreshDiff.removed.length > 0 && (
                              <Badge variant="destructive">
                                {refreshDiff.removed.length}{" "}
                                {t("removed", "removed")}
                              </Badge>
                            )}
                          {refreshDiff.updated &&
                            refreshDiff.updated.length > 0 && (
                              <Badge
                                variant="outline"
                                className="bg-blue-500 text-white"
                              >
                                {refreshDiff.updated.length}{" "}
                                {t("updated", "updated")}
                              </Badge>
                            )}
                        </div>
                      </div>
                    </AlertDescription>
                  </Alert>
                )}

                {/* Tools Section */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-sm">
                      {t("available_tools", "Available Tools")}
                    </h3>
                    <div className="flex items-center gap-2">
                      {config.tools_last_synced_at && (
                        <span className="text-xs text-muted-foreground">
                          {t("synced_at", "Synced")}{" "}
                          {new Date(
                            config.tools_last_synced_at
                          ).toLocaleString()}
                        </span>
                      )}
                      <Badge variant="outline">
                        {config.tools?.length || 0}
                      </Badge>
                    </div>
                  </div>

                  {/* Search */}
                  {config.tools && config.tools.length > 10 && (
                    <Input
                      placeholder={t("search_tools", "Search tools...")}
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-full"
                    />
                  )}

                  {tools.length > 0 ? (
                    <div className="max-h-[400px] space-y-2 overflow-y-auto rounded-lg border bg-muted/30 p-3">
                      {tools.map((tool) => {
                        const schema = tool.inputSchema || tool.input_schema;
                        return (
                          <div
                            key={tool.name}
                            className="space-y-1 border-b last:border-0 pb-2 last:pb-0"
                          >
                            <p className="text-sm font-medium">{tool.name}</p>
                            <p className="text-xs text-muted-foreground line-clamp-3">
                              {tool.description || "No description"}
                            </p>
                            {schema && (
                              <details className="text-xs text-muted-foreground">
                                <summary className="cursor-pointer hover:text-foreground">
                                  {t("input_schema", "Input schema")}
                                </summary>
                                <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 text-[10px]">
                                  {JSON.stringify(schema, null, 2)}
                                </pre>
                              </details>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <Alert>
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        {t(
                          "no_tools",
                          "No tools available from this configuration"
                        )}
                      </AlertDescription>
                    </Alert>
                  )}
                </div>

                {/* Action Buttons Row */}
                <div className="flex flex-row flex-wrap gap-2 border-t pt-4">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleRefreshTools}
                    disabled={refreshMutation.isPending}
                    className="flex-1 min-w-[120px]"
                  >
                    {refreshMutation.isPending ? (
                      <>
                        <Spinner className="mr-2 h-4 w-4" />
                        {t("refreshing", "Refreshing...")}
                      </>
                    ) : (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        {t("btn_refresh_tools", "Refresh Tools")}
                      </>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleEdit}
                    className="flex-1 min-w-[120px]"
                  >
                    <Edit className="mr-2 h-4 w-4" />
                    {t("btn_edit", "Edit")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleDelete}
                    className="flex-1 min-w-[120px] text-destructive hover:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    {t("btn_delete", "Delete")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("delete_confirmation", "Are you sure?")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("delete_warning", "This action cannot be undone")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("btn_cancel", "Cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive hover:bg-destructive/90"
            >
              {t("btn_delete", "Delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
