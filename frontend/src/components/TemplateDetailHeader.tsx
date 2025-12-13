"use client";

import { memo, useCallback } from "react";
import { MoreVertical, Globe, Lock } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

export interface TemplateDetailHeaderProps {
  templateId: string;
  templateName: string;
  isPublic?: boolean;
  onEdit?: () => void;
  onDelete?: () => void;
  isDeleting?: boolean;
}

const TemplateDetailHeaderComponent = ({
  templateName,
  isPublic = false,
  onEdit,
  onDelete,
  isDeleting = false,
}: TemplateDetailHeaderProps) => {
  const { t } = useTranslation("templates");

  const handleDelete = useCallback(() => {
    onDelete?.();
  }, [onDelete]);

  const handleEdit = useCallback(() => {
    onEdit?.();
  }, [onEdit]);

  return (
    <div className="flex items-center justify-between gap-4 mb-6">
      <div className="flex-1 min-w-0">
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground truncate">
          {templateName}
        </h1>
        <div className="mt-2 flex items-center gap-2">
          <Badge variant={isPublic ? "default" : "secondary"} className="gap-1">
            {isPublic ? (
              <>
                <Globe className="h-3 w-3" />
                {t("public")}
              </>
            ) : (
              <>
                <Lock className="h-3 w-3" />
                {t("private")}
              </>
            )}
          </Badge>
        </div>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            disabled={isDeleting}
            className="h-9 w-9"
          >
            <MoreVertical className="h-5 w-5" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onClick={handleEdit} disabled={isDeleting}>
            {t("edit")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={handleDelete}
            disabled={isDeleting}
            className="text-destructive focus:bg-destructive/10 focus:text-destructive"
          >
            {isDeleting ? t("deleting") : t("delete")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

export const TemplateDetailHeader = memo(TemplateDetailHeaderComponent);
