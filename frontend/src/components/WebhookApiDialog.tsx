"use client";

import { useState } from "react";
import { Copy, Eye, EyeOff, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  useGetWebhookConfig,
  useCreateWebhookConfig,
  useDeleteWebhookConfig,
} from "@/queries/agent-queries";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

type WebhookApiDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentId: string;
  agentName: string;
};

export function WebhookApiDialog({
  open,
  onOpenChange,
  agentId,
  agentName,
}: WebhookApiDialogProps) {
  const { t } = useTranslation(["agents", "common"]);
  const [showKey, setShowKey] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: webhookConfig, isLoading: isLoadingConfig } =
    useGetWebhookConfig(agentId, open);
  const { mutateAsync: createWebhookConfig, isPending: isCreatingConfig } =
    useCreateWebhookConfig(agentId);
  const { mutateAsync: deleteWebhookConfig, isPending: isDeletingConfig } =
    useDeleteWebhookConfig(agentId);

  const apiKey = webhookConfig?.data?.api_key;

  const handleCreateKey = async () => {
    try {
      await createWebhookConfig();
      setShowKey(true);
    } catch (error) {
      console.error("Failed to create webhook config:", error);
    }
  };

  const handleDeleteKey = async () => {
    try {
      await deleteWebhookConfig();
      setShowKey(false);
      setDeleteConfirmOpen(false);
    } catch (error) {
      console.error("Failed to delete webhook config:", error);
    }
  };

  const handleCopyKey = async () => {
    if (!apiKey) return;
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error("Failed to copy:", error);
    }
  };

  const maskKey = (key: string): string => {
    if (key.length <= 8) return key;
    return key.slice(0, 4) + "•".repeat(key.length - 8) + key.slice(-4);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("webhook_api_key", "Webhook API Key")}</DialogTitle>
            <DialogDescription>
              {t(
                "webhook_api_description",
                "Quản lý API key để kích hoạt agent thông qua webhook"
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Agent Info */}
            <div className="rounded-lg bg-muted p-3">
              <p className="text-xs text-muted-foreground mb-1">
                {t("common:agent", "Agent")}
              </p>
              <p className="font-medium text-sm">{agentName}</p>
            </div>

            {/* API Key Section */}
            {isLoadingConfig ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : apiKey ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="secondary">
                    {t("key_active", "Key đã kích hoạt")}
                  </Badge>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">
                    {t("api_key", "API Key")}
                  </label>
                  <div className="flex gap-2">
                    <Input
                      type={showKey ? "text" : "password"}
                      value={showKey ? apiKey : maskKey(apiKey)}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <Button
                      size="icon"
                      variant="outline"
                      onClick={() => setShowKey(!showKey)}
                      title={showKey ? t("hide", "Ẩn") : t("show", "Hiện")}
                    >
                      {showKey ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      size="icon"
                      variant="outline"
                      onClick={handleCopyKey}
                      title={t("copy", "Sao chép")}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                  {copied && (
                    <p className="text-xs text-green-600">
                      {t("copied", "Đã sao chép vào clipboard")}
                    </p>
                  )}
                </div>

                {/* Webhook URL Info */}
                <div className="space-y-2 rounded-lg bg-muted p-3">
                  <p className="text-xs font-medium text-muted-foreground">
                    {t("webhook_url", "Webhook URL")}
                  </p>
                  <p className="text-xs font-mono text-foreground break-all">
                    POST /api/v1/agents/{agentId}/webhook?token=YOUR_API_KEY
                  </p>
                </div>

                {/* Usage Info */}
                <div className="text-xs text-muted-foreground space-y-1">
                  <p className="font-medium mb-2">
                    {t("usage_instructions", "Hướng dẫn sử dụng")}
                  </p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>
                      {t(
                        "pass_token_param",
                        "Truyền token qua query parameter hoặc header X-Agent-Token"
                      )}
                    </li>
                    <li>
                      {t(
                        "keep_key_secure",
                        "Giữ API key an toàn và không chia sẻ công khai"
                      )}
                    </li>
                    <li>
                      {t(
                        "rotate_key_regularly",
                        "Xoá và tạo key mới định kỳ để bảo mật"
                      )}
                    </li>
                  </ul>
                </div>

                <Button
                  variant="destructive"
                  onClick={() => setDeleteConfirmOpen(true)}
                  disabled={isDeletingConfig}
                  className="w-full"
                >
                  {isDeletingConfig
                    ? t("deleting", "Đang xoá...")
                    : t("delete_key", "Xoá API Key")}
                </Button>
              </div>
            ) : (
              <div className="space-y-4 py-4">
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
                  <p className="text-xs text-amber-800">
                    {t(
                      "no_webhook_key",
                      "Agent này chưa có API key. Tạo một key để bắt đầu sử dụng webhook."
                    )}
                  </p>
                </div>

                <Button
                  onClick={handleCreateKey}
                  disabled={isCreatingConfig}
                  className="w-full"
                >
                  {isCreatingConfig
                    ? t("creating", "Đang tạo...")
                    : t("create_api_key", "Tạo API Key")}
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("delete_api_key_confirm", "Xoá API Key?")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "delete_api_key_warning",
                "Webhook không còn hoạt động sau khi xoá. Hành động này không thể hoàn tác."
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex justify-end gap-2">
            <AlertDialogCancel>{t("common:cancel", "Hủy")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteKey}
              disabled={isDeletingConfig}
              className="bg-destructive hover:bg-destructive/90"
            >
              {isDeletingConfig
                ? t("deleting", "Đang xoá...")
                : t("delete", "Xoá")}
            </AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
