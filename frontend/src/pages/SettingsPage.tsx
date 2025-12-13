import { PageHead } from "@/components/PageHead";

export const SettingsPage = () => {
  return (
    <>
      <PageHead
        title="Settings"
        description="Manage your account settings and preferences"
      />
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center space-y-4">
          <h1 className="text-3xl font-bold">Settings Page</h1>
          <p className="text-muted-foreground">
            This is a placeholder for the settings page.
          </p>
        </div>
      </div>
    </>
  );
};

export default SettingsPage;
