import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { MemorySector } from "@/types";
import { Calendar, BookOpen, Cog, Heart, Lightbulb } from "lucide-react";

type SectorConfig = {
  label: string;
  labelVi: string;
  color: string;
  bgColor: string;
  icon: React.ElementType;
};

const SECTOR_CONFIG: Record<MemorySector, SectorConfig> = {
  episodic: {
    label: "Episodic",
    labelVi: "Sự kiện",
    color: "text-blue-700 dark:text-blue-300",
    bgColor:
      "bg-blue-100 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800",
    icon: Calendar,
  },
  semantic: {
    label: "Semantic",
    labelVi: "Kiến thức",
    color: "text-green-700 dark:text-green-300",
    bgColor:
      "bg-green-100 dark:bg-green-900/30 border-green-200 dark:border-green-800",
    icon: BookOpen,
  },
  procedural: {
    label: "Procedural",
    labelVi: "Quy trình",
    color: "text-purple-700 dark:text-purple-300",
    bgColor:
      "bg-purple-100 dark:bg-purple-900/30 border-purple-200 dark:border-purple-800",
    icon: Cog,
  },
  emotional: {
    label: "Emotional",
    labelVi: "Cảm xúc",
    color: "text-pink-700 dark:text-pink-300",
    bgColor:
      "bg-pink-100 dark:bg-pink-900/30 border-pink-200 dark:border-pink-800",
    icon: Heart,
  },
  reflective: {
    label: "Reflective",
    labelVi: "Suy nghĩ",
    color: "text-amber-700 dark:text-amber-300",
    bgColor:
      "bg-amber-100 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800",
    icon: Lightbulb,
  },
};

type KnowledgeSectorBadgeProps = {
  sector: MemorySector;
  showIcon?: boolean;
  onClick?: () => void;
  isActive?: boolean;
  locale?: "en" | "vi";
  className?: string;
};

export const KnowledgeSectorBadge = ({
  sector,
  showIcon = true,
  onClick,
  isActive = false,
  locale = "en",
  className,
}: KnowledgeSectorBadgeProps) => {
  const config = SECTOR_CONFIG[sector];
  const Icon = config.icon;
  const label = locale === "vi" ? config.labelVi : config.label;

  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 font-medium transition-all",
        config.bgColor,
        config.color,
        onClick && "cursor-pointer hover:opacity-80",
        isActive && "ring-2 ring-offset-1 ring-primary",
        className
      )}
      onClick={onClick}
    >
      {showIcon && <Icon className="h-3 w-3" />}
      {label}
    </Badge>
  );
};

export const getSectorConfig = (sector: MemorySector) => SECTOR_CONFIG[sector];
export const ALL_SECTORS: MemorySector[] = [
  "episodic",
  "semantic",
  "procedural",
  "emotional",
  "reflective",
];
