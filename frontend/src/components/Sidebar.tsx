/**
 * Sidebar Component Exports
 *
 * Re-exports shadcn/ui sidebar primitives for easy composition.
 * Supports collapsible navigation items, nested menus, and mobile responsiveness.
 *
 * Usage:
 *   import { Sidebar, SidebarMenu, SidebarMenuItem, SidebarMenuButton } from '@/components/Sidebar'
 */

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarInset,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";

/**
 * Navigation item interface for building dynamic menus
 */
export interface SidebarNavItem {
  id?: string;
  label: string;
  href?: string;
  icon?: React.ReactNode;
  badge?: string | number;
  subItems?: SidebarNavItem[];
  isCollapsible?: boolean;
  isActive?: boolean;
  onClick?: () => void;
}

/**
 * Helper to check if an item is active
 */
export const isItemActive = (href?: string, currentPath?: string): boolean => {
  if (!href || !currentPath) return false;
  return currentPath === href || currentPath.startsWith(href + "/");
};

/**
 * Helper to render navigation item with active state
 */
export const createNavItemClass = (
  isActive: boolean,
  baseClass?: string
): string => {
  const base = baseClass || "";
  const activeClass = isActive
    ? "bg-primary text-primary-foreground font-medium"
    : "hover:bg-accent text-foreground";

  return `transition-colors ${base} ${activeClass}`.trim();
};
