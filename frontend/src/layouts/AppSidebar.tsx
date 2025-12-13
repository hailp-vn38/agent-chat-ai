"use client";

import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  MessageCircle,
  Bot,
  Smartphone,
  Sparkles,
  Blocks,
  Wrench,
  FileText,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  type SidebarNavItem,
  useSidebar,
} from "@/components/Sidebar";
import { useIsMobile } from "@/hooks/use-mobile";

/**
 * Navigation items configuration for AppSidebar
 * Labels will be populated from i18n translations
 */
const MAIN_ITEMS_CONFIG = [
  {
    id: "agents",
    labelKey: "navigation:sidebar.agents",
    href: "/agents",
    icon: <Bot className="h-4 w-4" />,
  },
  {
    id: "providers",
    labelKey: "navigation:sidebar.providers",
    href: "/providers",
    icon: <Blocks className="h-4 w-4" />,
  },
  {
    id: "tools",
    labelKey: "navigation:sidebar.tools",
    href: "/tools",
    icon: <Wrench className="h-4 w-4" />,
  },
  {
    id: "mcp-configs",
    labelKey: "navigation:sidebar.mcp_configs",
    href: "/mcp-configs",
    icon: <Blocks className="h-4 w-4" />,
  },
  {
    id: "templates",
    labelKey: "navigation:sidebar.templates",
    href: "/templates",
    icon: <FileText className="h-4 w-4" />,
  },
  {
    id: "devices",
    labelKey: "navigation:sidebar.devices",
    href: "/devices",
    icon: <Smartphone className="h-4 w-4" />,
  },
  {
    id: "chat",
    labelKey: "navigation:sidebar.chat",
    href: "/chat",
    icon: <MessageCircle className="h-4 w-4" />,
  },
];

interface NavItemProps {
  item: SidebarNavItem;
  isActive: boolean;
}

const SidebarLogo = () => (
  <div className="flex items-center gap-3">
    <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary transition-all duration-200 group-data-[collapsible=icon]:h-11 group-data-[collapsible=icon]:w-11">
      <span className="absolute inset-0 rounded-2xl border border-primary/30" />
      <Sparkles className="h-5 w-5" />
    </span>
    <span className="text-lg font-semibold leading-tight group-data-[collapsible=icon]:hidden">
      Home Agent
    </span>
  </div>
);

/**
 * Simple navigation item renderer for the sidebar menu
 */
const NavItemComponent = ({ item, isActive }: NavItemProps) => {
  if (!item.href) {
    return null;
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={isActive}
        tooltip={item.label}
        className="group-data-[collapsible=icon]:!h-16 group-data-[collapsible=icon]:!w-full group-data-[collapsible=icon]:!justify-center group-data-[collapsible=icon]:!px-0"
      >
        <Link
          to={item.href}
          onClick={item.onClick}
          className="flex w-full items-center gap-3 group-data-[collapsible=icon]:justify-center"
        >
          {item.icon && (
            <span className="flex h-6 w-6 items-center justify-center">
              {item.icon}
            </span>
          )}
          <span className="text-sm font-medium group-data-[collapsible=icon]:hidden">
            {item.label}
          </span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
};

const useSidebarDimensions = (
  collapsedWidth: string,
  expandedWidth?: string
) => {
  useEffect(() => {
    if (typeof document === "undefined") return;

    const wrapper = document.querySelector<HTMLElement>(
      "[data-slot='sidebar-wrapper']"
    );
    if (!wrapper) return;

    const previousCollapsed =
      wrapper.style.getPropertyValue("--sidebar-width-icon") ||
      getComputedStyle(wrapper).getPropertyValue("--sidebar-width-icon");
    const trimmedPreviousCollapsed = previousCollapsed.trim();

    const previousExpanded = expandedWidth
      ? (
          wrapper.style.getPropertyValue("--sidebar-width") ||
          getComputedStyle(wrapper).getPropertyValue("--sidebar-width")
        ).trim()
      : "";

    wrapper.style.setProperty("--sidebar-width-icon", collapsedWidth);
    if (expandedWidth) {
      wrapper.style.setProperty("--sidebar-width", expandedWidth);
    }

    return () => {
      if (trimmedPreviousCollapsed) {
        wrapper.style.setProperty(
          "--sidebar-width-icon",
          trimmedPreviousCollapsed
        );
      } else {
        wrapper.style.removeProperty("--sidebar-width-icon");
      }

      if (expandedWidth) {
        if (previousExpanded) {
          wrapper.style.setProperty("--sidebar-width", previousExpanded);
        } else {
          wrapper.style.removeProperty("--sidebar-width");
        }
      }
    };
  }, [collapsedWidth, expandedWidth]);
};

/**
 * AppSidebarContent Component
 *
 * Content wrapper for the AppSidebar
 */
const AppSidebarContent = ({
  collapsedWidth,
  expandedWidth,
}: {
  collapsedWidth: string;
  expandedWidth?: string;
}) => {
  const { t } = useTranslation();
  const location = useLocation();
  const currentPath = location.pathname;
  const isMobile = useIsMobile();
  const { setOpenMobile } = useSidebar();

  useSidebarDimensions(collapsedWidth, expandedWidth);

  // Transform config items with translated labels
  const mainItems: SidebarNavItem[] = MAIN_ITEMS_CONFIG.map((item) => ({
    id: item.id,
    label: t(item.labelKey),
    href: item.href,
    icon: item.icon,
    onClick: () => {
      // Tự động đóng sidebar trên mobile khi click item
      if (isMobile) {
        setOpenMobile(false);
      }
    },
  }));

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-16 flex items-center px-4 group-data-[collapsible=icon]:px-2">
        <SidebarLogo />
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent className="px-0">
        <div className="flex flex-1 flex-col px-4 py-6">
          <SidebarMenu className="gap-4">
            {mainItems.map((item) => (
              <NavItemComponent
                key={item.id || item.label}
                item={item}
                isActive={item.href === currentPath}
              />
            ))}
          </SidebarMenu>
        </div>
      </SidebarContent>
    </Sidebar>
  );
};

/**
 * AppSidebar Component
 *
 * Main application sidebar using shadcn/ui Sidebar primitives.
 * Features:
 * - Responsive mobile/desktop layout
 * - Collapsible navigation groups
 * - Icon-only mode when collapsed
 * - Active route highlighting
 * - Icon support with lucide-react
 * - Mobile-first styling with Tailwind CSS
 */
interface AppSidebarProps {
  collapsedWidth?: number | string;
  expandedWidth?: number | string;
}

const formatWidthValue = (width: number | string): string =>
  typeof width === "number" ? `${width}px` : width;

export const AppSidebar = ({
  collapsedWidth = 90,
  expandedWidth = "12rem",
}: AppSidebarProps) => {
  const resolvedCollapsedWidth = formatWidthValue(collapsedWidth);
  const resolvedExpandedWidth =
    typeof expandedWidth === "undefined"
      ? undefined
      : formatWidthValue(expandedWidth);

  return (
    <AppSidebarContent
      collapsedWidth={resolvedCollapsedWidth}
      expandedWidth={resolvedExpandedWidth}
    />
  );
};
