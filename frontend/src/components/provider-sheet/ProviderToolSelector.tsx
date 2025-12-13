"use client";

import { useTranslation } from "react-i18next";
import { ChevronsUpDown, XCircle, Check } from "lucide-react";

import { useProviderSheetStore } from "@/store/provider-sheet.store";
import { useToolOptions } from "@/queries";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { cn } from "@/lib/utils";

interface ProviderToolSelectorProps {
  disabled?: boolean;
}

/**
 * ProviderToolSelector component
 * Multi-select for tools when creating Intent providers with function_call type
 */
export function ProviderToolSelector({
  disabled = false,
}: ProviderToolSelectorProps) {
  const { t } = useTranslation(["common", "providers"]);
  const { selectedTools, toggleTool, setToolsPopoverOpen, isToolsPopoverOpen } =
    useProviderSheetStore();

  const { data: toolOptionsData, isLoading: isLoadingTools } =
    useToolOptions(true);

  const toolOptions = toolOptionsData?.data ?? [];

  return (
    <div className="space-y-2">
      <Label>
        {t("common:functions", "Functions")}
        <span className="ml-2 text-xs text-muted-foreground">
          ({selectedTools.length} {t("common:selected", "selected")})
        </span>
      </Label>

      <Popover open={isToolsPopoverOpen} onOpenChange={setToolsPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={isToolsPopoverOpen}
            className="w-full justify-between"
            disabled={disabled || isLoadingTools}
          >
            {isLoadingTools ? (
              <span className="text-muted-foreground">
                {t("common:loading", "Loading...")}
              </span>
            ) : selectedTools.length > 0 ? (
              <span className="truncate">
                {selectedTools.length}{" "}
                {t("common:tools_selected", "tools selected")}
              </span>
            ) : (
              <span className="text-muted-foreground">
                {t("common:select_tools", "Select tools...")}
              </span>
            )}
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="p-0"
          align="start"
          style={{ width: "var(--radix-popover-trigger-width)" }}
        >
          <Command>
            <CommandInput
              placeholder={t("common:search_tools", "Search tools...")}
            />
            <CommandList className="max-h-[200px]">
              <CommandEmpty>
                {t("common:no_tools_found", "No tools found")}
              </CommandEmpty>
              {toolOptions.length > 0 && (
                <CommandGroup>
                  {toolOptions.map((tool) => (
                    <CommandItem
                      key={tool.value}
                      value={tool.label}
                      keywords={[tool.value, tool.description ?? ""]}
                      onSelect={() => {
                        toggleTool(tool.value);
                      }}
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4 shrink-0",
                          selectedTools.includes(tool.value)
                            ? "opacity-100"
                            : "opacity-0"
                        )}
                      />
                      <div className="flex flex-col min-w-0">
                        <span className="font-medium truncate">
                          {tool.label}
                        </span>
                        {tool.description && (
                          <span className="text-xs text-muted-foreground whitespace-normal break-words">
                            {tool.description}
                          </span>
                        )}
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Show selected tools as badges */}
      {selectedTools.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {selectedTools.map((ref) => {
            const tool = toolOptions.find((t) => t.value === ref);
            return (
              <Badge
                key={ref}
                variant="secondary"
                className="cursor-pointer"
                onClick={() => !disabled && toggleTool(ref)}
              >
                {tool?.label ?? ref}
                <XCircle className="ml-1 h-3 w-3" />
              </Badge>
            );
          })}
        </div>
      )}
    </div>
  );
}
