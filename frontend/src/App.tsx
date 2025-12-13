import { Routes, Route, Outlet } from "react-router-dom";
import {
  LoginPage,
  ChatPage,
  RegisterPage,
  ProfilePage,
  SettingsPage,
  NotFoundPage,
  AgentsPage,
  AgentDetailPage,
  AgentKnowledgePage,
  AgentHistoryPage,
  DevicesPage,
  ProvidersPage,
  ToolsPage,
  TemplatesPage,
  TemplateDetailPage,
  McpConfigsPage,
} from "@/pages";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppLayout, AppHeader, AppSidebar, SidebarInset } from "@/layouts";

// Layout for protected routes
const ProtectedLayout = () => (
  <AppLayout>
    <AppSidebar />
    <SidebarInset>
      <AppLayout.Header>
        <AppHeader />
      </AppLayout.Header>
      <AppLayout.Content>
        <Outlet />
      </AppLayout.Content>
    </SidebarInset>
  </AppLayout>
);

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected routes */}
      <Route
        element={
          <ProtectedRoute>
            <ProtectedLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<AgentsPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:agentId" element={<AgentDetailPage />} />
        <Route
          path="/agents/:agentId/knowledge"
          element={<AgentKnowledgePage />}
        />
        <Route path="/agents/:agentId/history" element={<AgentHistoryPage />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/providers" element={<ProvidersPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/mcp-configs" element={<McpConfigsPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/templates/:templateId" element={<TemplateDetailPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      {/* 404 fallback */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default App;
