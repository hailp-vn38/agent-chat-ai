import { memo, useState, useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import type { Agent, ChatHistoryConf } from "@types";
import { CHAT_HISTORY_CONF_LABELS } from "@types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

/**
 * Agent Dialog Form Schema
 */
const createAgentSchema = z.object({
  agent_name: z
    .string()
    .min(1, "Agent name is required")
    .min(3, "Agent name must be at least 3 characters")
    .max(100, "Agent name must not exceed 100 characters"),
  description: z
    .string()
    .max(500, "Description must not exceed 500 characters"),
  user_profile: z
    .string()
    .max(1000, "User profile must not exceed 1000 characters"),
  chat_history_conf: z.number().int().min(0).max(2),
});

const updateAgentSchema = createAgentSchema.extend({
  status: z.enum(["enabled", "disabled"]),
  chat_history_conf: z.number().int().min(0).max(2),
});

type CreateAgentFormValues = z.infer<typeof createAgentSchema>;
type UpdateAgentFormValues = z.infer<typeof updateAgentSchema>;
type AgentFormValues = CreateAgentFormValues | UpdateAgentFormValues;

export type { CreateAgentFormValues, UpdateAgentFormValues };

export interface AgentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "update";
  agent?: Agent | null;
  onSubmit: (data: AgentFormValues) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onErrorDismiss?: () => void;
}

const AgentDialogComponent = ({
  open,
  onOpenChange,
  mode,
  agent,
  onSubmit,
  isLoading = false,
  error = null,
  onErrorDismiss,
}: AgentDialogProps) => {
  const { t } = useTranslation(["agents", "common"]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [userProfileLength, setUserProfileLength] = useState(0);
  const isSubmittingRef = useRef(false);

  const schema = mode === "update" ? updateAgentSchema : createAgentSchema;

  const form = useForm<AgentFormValues>({
    resolver: zodResolver(schema),
    defaultValues:
      mode === "update" && agent
        ? {
            agent_name: agent.agent_name,
            description: agent.description || "",
            user_profile: agent.user_profile || "",
            chat_history_conf: (agent.chat_history_conf ??
              0) as ChatHistoryConf,
            ...(mode === "update" && { status: agent.status }),
          }
        : {
            agent_name: "",
            description: "",
            user_profile: "",
            chat_history_conf: 0,
            ...(mode === "update" && { status: "enabled" }),
          },
  });

  useEffect(() => {
    if (open) {
      setUserProfileLength(form.getValues("user_profile")?.length || 0);
    }
  }, [open, form]);

  const handleSubmit = async (data: AgentFormValues) => {
    setIsSubmitting(true);
    isSubmittingRef.current = true;
    try {
      await onSubmit(data);
      form.reset();
      onOpenChange(false);
    } finally {
      setIsSubmitting(false);
      isSubmittingRef.current = false;
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    onOpenChange(newOpen);
  };

  useEffect(() => {
    if (!open) {
      form.reset();
      isSubmittingRef.current = false;
      onErrorDismiss?.();
    }
  }, [open, form, onErrorDismiss]);

  useEffect(() => {
    if (!isLoading) {
      isSubmittingRef.current = false;
    }
  }, [isLoading]);

  const isDisabled = isSubmitting || isLoading;
  const isCreateMode = mode === "create";
  const title = isCreateMode
    ? t("agents:create_agent")
    : t("agents:update_agent");

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {isCreateMode
              ? t("agents:create_agent_description")
              : t("agents:update_agent_description")}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
          >
            {/* Error Message */}
            {error && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            {/* Agent Name Field */}
            <FormField
              control={form.control}
              name="agent_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("agents:agent_name")}</FormLabel>
                  <FormControl>
                    <Input
                      placeholder={t("agents:agent_name")}
                      disabled={isDisabled}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Description Field */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("agents:agent_description")}</FormLabel>
                  <FormControl>
                    <textarea
                      placeholder={t("agents:agent_description")}
                      disabled={isDisabled}
                      rows={3}
                      className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {field.value?.length || 0}/500
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* User Profile Field */}
            <FormField
              control={form.control}
              name="user_profile"
              render={({ field: { onChange, ...field } }) => (
                <FormItem>
                  <FormLabel>
                    {t("agents:user_profile") || "User Profile"}
                  </FormLabel>
                  <FormControl>
                    <textarea
                      placeholder={
                        t("agents:user_profile_placeholder") ||
                        "Enter user profile information..."
                      }
                      disabled={isDisabled}
                      rows={4}
                      maxLength={1000}
                      onChange={(e) => {
                        onChange(e.target.value);
                        setUserProfileLength(e.target.value.length);
                      }}
                      className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {userProfileLength}/1000
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Status Field (Update mode only) */}
            {!isCreateMode && (
              <FormField
                control={form.control}
                name="status"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("agents:status")}</FormLabel>
                    <FormControl>
                      <select
                        disabled={isDisabled}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        {...field}
                      >
                        <option value="enabled">{t("agents:enabled")}</option>
                        <option value="disabled">{t("agents:disabled")}</option>
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {/* Chat History Configuration Field */}
            <FormField
              control={form.control}
              name="chat_history_conf"
              render={({ field: { onChange, ...field } }) => (
                <FormItem>
                  <FormLabel>
                    {t("agents:chat_history_conf") || "Chat History"}
                  </FormLabel>
                  <FormControl>
                    <select
                      disabled={isDisabled}
                      onChange={(e) =>
                        onChange(parseInt(e.target.value) as ChatHistoryConf)
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      {...field}
                    >
                      <option value="0">{CHAT_HISTORY_CONF_LABELS[0]}</option>
                      <option value="1">{CHAT_HISTORY_CONF_LABELS[1]}</option>
                      <option value="2">{CHAT_HISTORY_CONF_LABELS[2]}</option>
                    </select>
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("agents:chat_history_conf_desc") ||
                      "Configure how to save chat history"}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={isDisabled}
              >
                {t("common:cancel")}
              </Button>
              <Button type="submit" disabled={isDisabled}>
                {isDisabled && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {isCreateMode
                  ? t("agents:create_agent")
                  : t("agents:update_agent")}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export const AgentDialog = memo(AgentDialogComponent);
