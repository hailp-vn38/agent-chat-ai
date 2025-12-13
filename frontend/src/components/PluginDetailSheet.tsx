import { useTranslation } from "react-i18next";
import { Loader2, AlertCircle } from "lucide-react";

import type { Plugin } from "@types";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";

export interface PluginDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plugin: Plugin | null;
  isLoading?: boolean;
}

export const PluginDetailSheet = ({
  open,
  onOpenChange,
  plugin,
  isLoading = false,
}: PluginDetailSheetProps) => {
  const { t } = useTranslation(["tools", "common"]);

  if (!plugin) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="max-w-md space-y-6 overflow-y-auto">
        <SheetHeader className="space-y-2">
          <SheetTitle className="flex items-center justify-between gap-2">
            <span className="flex-1 truncate">{plugin.name}</span>
            <Badge variant={plugin.enabled ? "success" : "secondary"}>
              {plugin.enabled
                ? t("status_enabled", "Enabled")
                : t("status_disabled", "Disabled")}
            </Badge>
          </SheetTitle>
          <SheetDescription>{plugin.name}</SheetDescription>
        </SheetHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Plugin Info */}
            <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
              <div>
                <p className="text-xs font-medium text-muted-foreground">
                  {t("field_version", "Version")}
                </p>
                <p className="text-sm font-medium">{plugin.version}</p>
              </div>

              <Separator />

              <div>
                <p className="text-xs font-medium text-muted-foreground">
                  {t("field_category", "Category")}
                </p>
                <Badge variant="outline" className="mt-2">
                  {plugin.category}
                </Badge>
              </div>

              <Separator />

              <div>
                <p className="text-xs font-medium text-muted-foreground">
                  {t("field_description", "Description")}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {plugin.description || "—"}
                </p>
              </div>
            </div>

            {/* Tools Section */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm">{t("tools", "Tools")}</h3>
                <Badge variant="outline">{plugin.tools_count}</Badge>
              </div>

              {plugin.tools && plugin.tools.length > 0 ? (
                <div className="max-h-[300px] space-y-2 overflow-y-auto rounded-lg border bg-muted/30 p-3">
                  {plugin.tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="space-y-1 border-b last:border-0 pb-2 last:pb-0"
                    >
                      <p className="text-sm font-medium">{tool.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {tool.description || "No description"}
                      </p>
                      {tool.input_schema && (
                        <details className="text-xs text-muted-foreground cursor-pointer">
                          <summary>{t("schema", "Schema")}</summary>
                          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words bg-black/10 rounded p-2 text-xs">
                            {JSON.stringify(tool.input_schema, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    {t("no_tools", "No tools available")}
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};
