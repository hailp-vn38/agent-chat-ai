import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Search, X, Filter } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { ALL_SECTORS, KnowledgeSectorBadge } from "./KnowledgeSectorBadge";
import type { MemorySector } from "@/types";

type KnowledgeSearchBarProps = {
  onSearch: (query: string) => void;
  onFilterChange: (sector: MemorySector | null) => void;
  selectedSector: MemorySector | null;
  isSearching?: boolean;
};

export const KnowledgeSearchBar = ({
  onSearch,
  onFilterChange,
  selectedSector,
  isSearching = false,
}: KnowledgeSearchBarProps) => {
  const { t, i18n } = useTranslation("agents");
  const [query, setQuery] = useState("");

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setQuery(e.target.value);
    },
    []
  );

  const handleSearch = useCallback(() => {
    onSearch(query);
  }, [onSearch, query]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        handleSearch();
      }
    },
    [handleSearch]
  );

  const handleClear = useCallback(() => {
    setQuery("");
    onSearch("");
  }, [onSearch]);

  const handleSectorSelect = useCallback(
    (sector: MemorySector) => {
      onFilterChange(selectedSector === sector ? null : sector);
    },
    [selectedSector, onFilterChange]
  );

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex-1">
        <Input
          placeholder={t("search_knowledge")}
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          className="pr-9"
        />
        {query && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2"
            onClick={handleClear}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      <Button onClick={handleSearch} disabled={isSearching} className="gap-2">
        <Search className="h-4 w-4" />
        {t("search")}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className={selectedSector ? "border-primary" : ""}
          >
            <Filter className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          {ALL_SECTORS.map((sector) => (
            <DropdownMenuCheckboxItem
              key={sector}
              checked={selectedSector === sector}
              onCheckedChange={() => handleSectorSelect(sector)}
            >
              <KnowledgeSectorBadge
                sector={sector}
                locale={i18n.language as "en" | "vi"}
              />
            </DropdownMenuCheckboxItem>
          ))}
          {selectedSector && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuCheckboxItem
                checked={false}
                onCheckedChange={() => onFilterChange(null)}
              >
                {t("clear_filter")}
              </DropdownMenuCheckboxItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};
