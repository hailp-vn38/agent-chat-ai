import { memo } from "react";
import { useTranslation } from "react-i18next";

import type { Provider, ProviderCategory } from "@types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * Category icon and color mapping
 */
const CATEGORY_CONFIG: Record<
  ProviderCategory,
  { color: string; bgColor: string }
> = {
  LLM: { color: "text-blue-600", bgColor: "bg-blue-100" },
  VLLM: { color: "text-indigo-600", bgColor: "bg-indigo-100" },
  TTS: { color: "text-green-600", bgColor: "bg-green-100" },
  ASR: { color: "text-purple-600", bgColor: "bg-purple-100" },
  VAD: { color: "text-orange-600", bgColor: "bg-orange-100" },
  Memory: { color: "text-pink-600", bgColor: "bg-pink-100" },
  Intent: { color: "text-cyan-600", bgColor: "bg-cyan-100" },
};

export interface ProviderCardProps {
  provider: Provider;
  onView?: (provider: Provider) => void;
  onEdit?: (provider: Provider) => void;
  onDelete?: (provider: Provider) => void;
  onToggleActive?: (provider: Provider) => void;
  onClick?: (provider: Provider) => void;
}

const ProviderCardComponent = ({
  provider,
  onView,
  onClick,
}: ProviderCardProps) => {
  const { t } = useTranslation(["providers", "common"]);
  const categoryConfig = CATEGORY_CONFIG[provider.category] || {
    color: "text-gray-600",
    bgColor: "bg-gray-100",
  };

  const isDefaultProvider = provider.source === "default";

  const handleCardClick = () => {
    if (onClick) {
      onClick(provider);
    } else if (onView) {
      onView(provider);
    }
  };

  return (
    <Card
      className="group relative transition-all hover:shadow-md cursor-pointer"
      onClick={handleCardClick}
    >
      <CardHeader className="pb-2 sm:pb-3">
        <div className="flex flex-col gap-2 sm:gap-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
              {/* Category Badge */}
              <Badge
                variant="secondary"
                className={`${categoryConfig.bgColor} ${categoryConfig.color} border-0 text-xs sm:text-sm`}
              >
                {provider.category}
              </Badge>
              {/* Source Badge */}
              {provider.source && (
                <Badge
                  variant={isDefaultProvider ? "secondary" : "outline"}
                  className={`text-xs sm:text-sm ${
                    isDefaultProvider
                      ? "bg-amber-100 text-amber-700 border-0"
                      : ""
                  }`}
                >
                  {isDefaultProvider
                    ? t("providers:default")
                    : t("providers:custom")}
                </Badge>
              )}
              {/* Status Badge */}
              <Badge
                variant={provider.is_active ? "default" : "outline"}
                className="text-xs sm:text-sm"
              >
                {provider.is_active ? t("common:active") : t("common:inactive")}
              </Badge>
            </div>
          </div>

          <CardTitle className="text-lg sm:text-xl line-clamp-2">
            {provider.name}
          </CardTitle>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-2 text-xs sm:text-sm">
          {/* Provider Type */}
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">{t("providers:type")}</span>
            <span className="font-medium text-right truncate ml-2">
              {provider.type}
            </span>
          </div>

          {/* Model/Config Summary */}
          {typeof provider.config.model_name === "string" && (
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground">
                {t("providers:model")}
              </span>
              <span className="font-mono text-xs truncate text-right">
                {provider.config.model_name}
              </span>
            </div>
          )}

          {/* Created Date */}
          {provider.created_at && (
            <div className="flex items-center justify-between pt-2 border-t">
              <span className="text-muted-foreground text-xs">
                {t("common:created")}
              </span>
              <span className="text-xs">
                {new Date(provider.created_at).toLocaleDateString("vi-VN")}
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export const ProviderCard = memo(ProviderCardComponent);
