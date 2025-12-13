"use client";

import { useMemo } from "react";

import type { ProviderTypeSchema } from "@types";
import { useProviderSheetStore } from "@/store/provider-sheet.store";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";

interface ProviderTypeSelectorProps {
  category: string;
  schemaData?: Record<string, Record<string, unknown>>;
  disabled?: boolean;
}

/**
 * ProviderTypeSelector component
 * Badge selector for type within a category
 */
export function ProviderTypeSelector({
  category,
  schemaData,
  disabled = false,
}: ProviderTypeSelectorProps) {
  const { selectedType, selectType, mode } = useProviderSheetStore();

  // Get available types for selected category
  const availableTypes = useMemo(() => {
    if (!schemaData || !category) return [];
    const categoryData = schemaData[category];
    return categoryData ? Object.keys(categoryData) : [];
  }, [schemaData, category]);

  if (availableTypes.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <Label>Type</Label>
      <div className="flex flex-wrap gap-2">
        {availableTypes.map((type) => {
          const typeSchema = schemaData?.[category]?.[type] as
            | ProviderTypeSchema
            | undefined;
          return (
            <Badge
              key={type}
              variant={selectedType === type ? "default" : "outline"}
              className={`px-3 py-1 ${
                mode === "update" || disabled
                  ? "cursor-not-allowed opacity-60"
                  : "cursor-pointer"
              }`}
              onClick={() => mode === "create" && !disabled && selectType(type)}
              title={typeSchema?.description}
            >
              {typeSchema?.label || type}
            </Badge>
          );
        })}
      </div>
    </div>
  );
}
