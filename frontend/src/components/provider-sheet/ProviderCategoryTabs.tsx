"use client";

import { useMemo } from "react";

import type { ProviderCategory, ProviderField } from "@types";
import { useProviderSheetStore } from "@/store/provider-sheet.store";
import { ProviderTypeSelector } from "./ProviderTypeSelector";
import { ProviderConfigForm } from "./ProviderConfigForm";
import { CATEGORY_LIST } from "./types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ProviderCategoryTabsProps {
  schemaData?: Record<string, Record<string, unknown>>;
  isFormDisabled?: boolean;
}

/**
 * ProviderCategoryTabs component
 * Category tabs with TabsContent for type selection and form
 */
export function ProviderCategoryTabs({
  schemaData,
  isFormDisabled = false,
}: ProviderCategoryTabsProps) {
  const { selectedCategory, selectedType, selectCategory, mode } =
    useProviderSheetStore();

  // Get filtered category list (only categories with schema data)
  const availableCategories = useMemo(() => {
    if (!schemaData) return [];
    return CATEGORY_LIST.filter((cat) => schemaData[cat]);
  }, [schemaData]);

  // Get fields for selected type
  const selectedFields = useMemo(() => {
    if (!schemaData || !selectedCategory || !selectedType) return [];
    const categoryData = schemaData[selectedCategory];
    if (!categoryData) return [];
    const typeSchema = categoryData[selectedType] as Record<string, unknown>;
    return (typeSchema?.fields ?? []) as ProviderField[];
  }, [schemaData, selectedCategory, selectedType]);

  const isUpdateMode = mode === "update";

  return (
    <Tabs
      value={selectedCategory ?? ""}
      onValueChange={(value) => {
        if (!isUpdateMode && !isFormDisabled) {
          const category = value as ProviderCategory;
          selectCategory(category);
        }
      }}
    >
      <TabsList className="flex w-full overflow-x-auto">
        {availableCategories.map((category) => (
          <TabsTrigger
            key={category}
            value={category}
            disabled={isUpdateMode || isFormDisabled}
            className="text-xs sm:text-sm flex-1 min-w-fit"
          >
            {category}
          </TabsTrigger>
        ))}
      </TabsList>

      {availableCategories.map((category) => (
        <TabsContent key={category} value={category} className="space-y-6">
          {/* Type Selector - Always show when category is selected */}
          <ProviderTypeSelector
            category={category}
            schemaData={schemaData}
            disabled={isFormDisabled}
          />

          {/* Config Form - Only show in update mode or if type is selected in create mode */}
          {(isUpdateMode || selectedType) && (
            <ProviderConfigForm
              selectedFields={selectedFields}
              isEditDisabled={isFormDisabled}
            />
          )}
        </TabsContent>
      ))}
    </Tabs>
  );
}
