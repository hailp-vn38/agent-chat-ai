"use client";

import { useTranslation } from "react-i18next";
import { ChevronsUpDown, Check } from "lucide-react";
import { useState } from "react";

import { useProviderList } from "@/queries/provider-queries";
import { useProviderSheetStore } from "@/store/provider-sheet.store";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
import type { ProviderCategory, ProviderField } from "@types";

interface ProviderRefSelectorProps {
  field: ProviderField;
  providerCategory: ProviderCategory;
  disabled?: boolean;
}

/**
 * ProviderRefSelector component
 * Select a provider reference for Intent LLM type
 */
export function ProviderRefSelector({
  field,
  providerCategory,
  disabled = false,
}: ProviderRefSelectorProps) {
  const { t } = useTranslation(["common", "providers"]);
  const { formValues, setFieldValue, errors } = useProviderSheetStore();
  const [open, setOpen] = useState(false);

  const { data: providersData, isLoading } = useProviderList({
    category: providerCategory,
    source: "all",
  });

  const providers = providersData?.data ?? [];
  const selectedValue = formValues[field.name] as string | undefined;
  const selectedProvider = providers.find((p) => p.reference === selectedValue);
  const error = errors[field.name];

  return (
    <div className="space-y-2">
      <Label htmlFor={field.name}>
        {field.label}
        {field.required && <span className="ml-1 text-destructive">*</span>}
      </Label>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between"
            disabled={disabled || isLoading}
          >
            {isLoading ? (
              <span className="text-muted-foreground">
                {t("common:loading", "Loading...")}
              </span>
            ) : selectedProvider ? (
              <span className="truncate">{selectedProvider.name}</span>
            ) : (
              <span className="text-muted-foreground">
                {t("providers:select_provider", "Select provider...")}
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
              placeholder={t("providers:search_provider", "Search provider...")}
            />
            <CommandList className="max-h-[200px]">
              <CommandEmpty>
                {t("providers:no_providers_found", "No providers found")}
              </CommandEmpty>
              {providers.length > 0 && (
                <CommandGroup>
                  {providers.map((provider) => (
                    <CommandItem
                      key={provider.id}
                      value={provider.name}
                      keywords={[provider.reference ?? "", provider.type]}
                      onSelect={() => {
                        setFieldValue(field.name, provider.reference);
                        setOpen(false);
                      }}
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4 shrink-0",
                          selectedValue === provider.reference
                            ? "opacity-100"
                            : "opacity-0"
                        )}
                      />
                      <div className="flex flex-col min-w-0">
                        <span className="font-medium truncate">
                          {provider.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {provider.type}
                        </span>
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}

