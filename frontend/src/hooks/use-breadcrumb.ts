import { useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  isActive: boolean;
}

interface BreadcrumbParams {
  agentName?: string;
  templateName?: string;
}

/**
 * Hook to generate breadcrumb items from current route
 * Maps route paths to user-friendly labels using i18n
 *
 * @param params - Optional params with agentName/templateName to display in breadcrumb
 */
export function useBreadcrumb(params?: BreadcrumbParams): BreadcrumbItem[] {
  const location = useLocation();
  const routeParams = useParams();
  const { t } = useTranslation("navigation");

  // Map route paths to i18n keys
  const routeLabels: Record<string, string> = {
    chat: "breadcrumb.chat",
    agents: "breadcrumb.agents",
    templates: "breadcrumb.templates",
    devices: "breadcrumb.devices",
    profile: "breadcrumb.profile",
    settings: "breadcrumb.settings",
  };

  // Split the path and filter empty segments
  const pathSegments = location.pathname
    .split("/")
    .filter((segment) => segment !== "");

  // Build breadcrumb items
  const breadcrumbs: BreadcrumbItem[] = [
    {
      label: t("breadcrumb.home"),
      href: "/",
      isActive: location.pathname === "/",
    },
  ];

  // Process each path segment
  pathSegments.forEach((segment, index) => {
    const isLast = index === pathSegments.length - 1;
    const href = `/${pathSegments.slice(0, index + 1).join("/")}`;

    // Handle agent IDs with parameter values
    if (segment === "agents" && routeParams.agentId) {
      breadcrumbs.push({
        label: t("breadcrumb.agents"),
        href: "/agents",
        isActive: false,
      });
      breadcrumbs.push({
        label: params?.agentName
          ? params.agentName
          : `Agent ${routeParams.agentId}`,
        isActive: true,
      });
    }
    // Handle template IDs with parameter values
    else if (segment === "templates" && routeParams.templateId) {
      breadcrumbs.push({
        label: t("breadcrumb.templates"),
        href: "/templates",
        isActive: false,
      });
      breadcrumbs.push({
        label: params?.templateName
          ? params.templateName
          : `Template ${routeParams.templateId}`,
        isActive: true,
      });
    } else if (routeLabels[segment]) {
      breadcrumbs.push({
        label: t(routeLabels[segment]),
        href: isLast ? undefined : href,
        isActive: isLast,
      });
    }
  });

  return breadcrumbs;
}
