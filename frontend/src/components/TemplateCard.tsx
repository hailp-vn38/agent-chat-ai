"use client";

import { memo } from "react";
import { LayoutTemplate, Pencil, Trash2, Globe } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import type { Template } from "@types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const truncateText = (text: string, maxLength: number = 150) => {
  if (!text) return "N/A";
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
};

export interface TemplateCardProps {
  template: Template;
  className?: string;
  onEdit?: () => void;
  onDelete?: () => void;
  onClick?: () => void;
}

const TemplateCardComponent = ({
  template,
  className,
  onEdit,
  onDelete,
  onClick,
}: TemplateCardProps) => {
  const { t } = useTranslation("templates");
  const navigate = useNavigate();

  const modelsList = [
    { label: "ASR", value: template.ASR?.name },
    { label: "LLM", value: template.LLM?.name },
    { label: "TTS", value: template.TTS?.name },
  ].filter((item) => item.value);

  const handleCardClick = () => {
    if (onClick) {
      onClick();
    } else {
      navigate(`/templates/${template.id}`);
    }
  };

  return (
    <Card
      className={cn(
        "group relative cursor-pointer hover:shadow-md transition-shadow",
        className
      )}
      onClick={handleCardClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-lg flex items-center gap-2 truncate">
              <LayoutTemplate className="h-5 w-5 text-primary flex-shrink-0" />
              <span className="truncate">{template.name}</span>
            </CardTitle>
            <CardDescription className="text-xs mt-1 line-clamp-2">
              {truncateText(template.prompt, 100)}
            </CardDescription>
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {onEdit && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit();
                }}
              >
                <Pencil className="h-4 w-4" />
              </Button>
            )}
            {onDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-destructive hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        {/* Models */}
        {modelsList.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {modelsList.map((model) => (
              <Badge key={model.label} variant="secondary" className="text-xs">
                {model.label}: {model.value}
              </Badge>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
          <div className="flex items-center gap-2">
            {template.is_public && (
              <Badge variant="outline" className="gap-1">
                <Globe className="h-3 w-3" />
                {t("public")}
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export const TemplateCard = memo(TemplateCardComponent);
