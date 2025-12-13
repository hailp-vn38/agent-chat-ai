"use client";

import { useBreadcrumb } from "@/hooks";
import { SidebarTrigger } from "@/components/Sidebar";
import { UserDropdownMenu } from "@/components/UserDropdownMenu";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

export const AppHeader = () => {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  // Try to get agent/template name from sessionStorage if viewing detail page
  let agentName: string | undefined;
  let templateName: string | undefined;
  if (pathname.includes("/agents/")) {
    agentName = sessionStorage.getItem("currentAgentName") || undefined;
  }
  if (pathname.includes("/templates/")) {
    templateName = sessionStorage.getItem("currentTemplateName") || undefined;
  }

  const breadcrumbs = useBreadcrumb({ agentName, templateName });

  return (
    <div className="flex items-center justify-between w-full">
      <div className="flex items-center gap-4 flex-1">
        <SidebarTrigger className="-ml-1" />

        <Breadcrumb>
          <BreadcrumbList>
            {breadcrumbs.map((breadcrumb, index) => (
              <div
                key={`${breadcrumb.label}-${index}`}
                className="flex items-center gap-1.5"
              >
                {breadcrumb.isActive ? (
                  <BreadcrumbPage>{breadcrumb.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink
                    onClick={() => breadcrumb.href && navigate(breadcrumb.href)}
                    className="cursor-pointer"
                  >
                    {breadcrumb.label}
                  </BreadcrumbLink>
                )}
                {index < breadcrumbs.length - 1 && <BreadcrumbSeparator />}
              </div>
            ))}
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      <div className="flex items-center flex-shrink-0">
        <UserDropdownMenu />
      </div>
    </div>
  );
};
