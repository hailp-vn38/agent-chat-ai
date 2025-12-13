import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Brain, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type KnowledgePreviewCardProps = {
  agentId: string;
};

export const KnowledgePreviewCard = ({
  agentId,
}: KnowledgePreviewCardProps) => {
  const navigate = useNavigate();
  const { t } = useTranslation("agents");

  const handleManageClick = () => {
    navigate(`/agents/${agentId}/knowledge`);
  };

  return (
    <Card
      className="h-full cursor-pointer transition-all hover:shadow-md"
      onClick={handleManageClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Brain className="h-4 w-4 text-primary" />
            {t("knowledge_base")}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              handleManageClick();
            }}
            className="gap-1 text-xs"
          >
            {t("view")}
            <ChevronRight className="h-3 w-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-start justify-start py-2 text-left">
          <Brain className="h-8 w-8 text-muted-foreground/50 mb-2" />
          <p className="text-sm text-muted-foreground">
            {t("knowledge_base_description")}
          </p>
        </div>
      </CardContent>
    </Card>
  );
};
