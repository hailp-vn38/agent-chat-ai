import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { PageHead } from "@/components/PageHead";

export const NotFoundPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation("common");

  return (
    <>
      <PageHead
        title="404 - Page Not Found"
        description="The page you are looking for does not exist"
      />
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center space-y-6">
          <h1 className="text-5xl font-bold">404</h1>
          <p className="text-2xl font-semibold">{t("page_not_found")}</p>
          <p className="text-muted-foreground">{t("page_not_found_desc")}</p>
          <Button onClick={() => navigate("/")} variant="default">
            {t("go_home")}
          </Button>
        </div>
      </div>
    </>
  );
};

export default NotFoundPage;
