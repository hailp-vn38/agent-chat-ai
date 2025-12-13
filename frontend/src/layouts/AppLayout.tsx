import React from "react";
import type { ReactNode } from "react";
import { SidebarProvider, SidebarInset } from "@/components/Sidebar";

interface AppLayoutProps {
  children: ReactNode;
}

interface AppLayoutSubcomponents {
  Header: (props: { children: ReactNode }) => React.ReactElement;
  Content: (props: { children: ReactNode }) => React.ReactElement;
}

interface AppLayoutComponent
  extends React.FC<AppLayoutProps>,
    AppLayoutSubcomponents {}

const AppLayoutHeader = ({ children }: { children: ReactNode }) => (
  <header className="h-16 border-b bg-background flex items-center px-6 gap-4 flex-shrink-0">
    {children}
  </header>
);

const AppLayoutContent = ({ children }: { children: ReactNode }) => (
  <main className="flex-1 overflow-y-auto min-h-0">{children}</main>
);

const AppLayout = ({ children }: AppLayoutProps) => (
  <SidebarProvider>
    <div className="flex w-full h-screen">
      {/* Children should include AppSidebar */}
      {children}
    </div>
  </SidebarProvider>
);

// Compound component pattern with proper typing
const AppLayoutWithSubcomponents = AppLayout as AppLayoutComponent;
AppLayoutWithSubcomponents.Header = AppLayoutHeader;
AppLayoutWithSubcomponents.Content = AppLayoutContent;

export { SidebarInset };
export default AppLayoutWithSubcomponents;
