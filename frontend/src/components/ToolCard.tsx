import { memo } from "react";
import { useTranslation } from "react-i18next";
import { Info, Wrench } from "lucide-react";

import type { ToolSchema, ToolCategory } from "@types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * Category color mapping
 */
const CATEGORY_CONFIG: Record<
  ToolCategory,
  { color: string; bgColor: string }
> = {
  weather: { color: "text-sky-600", bgColor: "bg-sky-100" },
  music: { color: "text-purple-600", bgColor: "bg-purple-100" },
  reminder: { color: "text-amber-600", bgColor: "bg-amber-100" },
  news: { color: "text-blue-600", bgColor: "bg-blue-100" },
  agent: { color: "text-green-600", bgColor: "bg-green-100" },
  calendar: { color: "text-red-600", bgColor: "bg-red-100" },
  iot: { color: "text-cyan-600", bgColor: "bg-cyan-100" },
  other: { color: "text-gray-600", bgColor: "bg-gray-100" },
};

/**
 * Props for ToolCard displaying a system tool schema
 */
export interface ToolCardProps {
  tool: ToolSchema;
  onViewDetails?: (tool: ToolSchema) => void;
}

/**
 * ToolCard - Display available system tool (v2.0 - read only)
 */
const ToolCardComponent = ({ tool, onViewDetails }: ToolCardProps) => {
  const { t } = useTranslation(["tools", "common"]);
  const categoryConfig =
    CATEGORY_CONFIG[tool.category] || CATEGORY_CONFIG.other;

  return (
    <Card className="group relative transition-all hover:shadow-md">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Category Badge */}
            <Badge
              variant="secondary"
              className={`${categoryConfig.bgColor} ${categoryConfig.color} border-0`}
            >
              {tool.category}
            </Badge>
          </div>

          {/* View Details Button */}
          {onViewDetails && (
            <Button
              variant="ghost"
              size="sm"
              className="opacity-0 transition-opacity group-hover:opacity-100"
              onClick={() => onViewDetails(tool)}
            >
              <Info className="mr-1 h-4 w-4" />
              {t("common:details")}
            </Button>
          )}
        </div>

        <CardTitle className="mt-2 text-lg flex items-center gap-2">
          <Wrench className="h-4 w-4 text-muted-foreground" />
          {tool.name}
        </CardTitle>
      </CardHeader>

      <CardContent>
        <div className="space-y-2 text-sm">
          {/* Description */}
          <p className="text-muted-foreground line-clamp-2">
            {tool.description}
          </p>

          {/* Tool Name */}
          <div className="flex items-center justify-between pt-2 border-t">
            <span className="text-muted-foreground">
              {t("tools:tool_name")}
            </span>
            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
              {tool.name}
            </code>
          </div>

          {/* Parameters Count */}
          {tool.parameters?.properties && (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">
                {t("tools:parameters")}
              </span>
              <span className="text-xs">
                {Object.keys(tool.parameters.properties).length}{" "}
                {t("tools:params")}
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export const ToolCard = memo(ToolCardComponent);
