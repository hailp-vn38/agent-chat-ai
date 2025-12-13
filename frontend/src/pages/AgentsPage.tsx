import { memo, useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Zap, Plus } from "lucide-react";

import { useAgentList, useCreateAgent } from "@hooks/useAgent";
import type { Agent } from "@types";
import type { CreateAgentFormValues } from "@/components/AgentDialog";
import { AgentCard } from "@/components/AgentCard";
import { AgentDialog } from "@/components/AgentDialog";
import { PageHead } from "@/components/PageHead";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * AgentsPage Component
 *
 * Displays a responsive grid of agents. Features:
 * - Mobile-first responsive layout (1 col → 2 cols tablet → 3 cols desktop)
 * - Loading state with skeleton cards
 * - Error state with retry button
 * - Empty state using shadcn Empty component
 * - Integration with AgentCard component for each agent
 * - Create agent dialog with form
 * - Optimistic update: New agents appear immediately in UI while API request is in-flight
 *   - If API succeeds: Real agent data replaces optimistic data
 *   - If API fails: Cache is rolled back to previous state, user can retry
 */
const AgentsPageComponent = () => {
  const { t } = useTranslation(["agents", "common"]);
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useAgentList();
  const { mutate: createAgent, isPending: isCreating } = useCreateAgent();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleRetry = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleAgentCardClick = useCallback(
    (agent: Agent) => {
      navigate(`/agents/${agent.id}`);
    },
    [navigate]
  );

  const handleCreateAgent = useCallback(
    async (payload: CreateAgentFormValues) => {
      setCreateError(null);
      return new Promise<void>((resolve, reject) => {
        createAgent(
          {
            agent_name: payload.agent_name,
            description: payload.description,
            user_profile: payload.user_profile,
          },
          {
            onSuccess: () => {
              // Close dialog immediately with optimistic update
              // Data is already updated in cache (optimistic update)
              setIsDialogOpen(false);
              setCreateError(null);
              resolve();
            },
            onError: (err: unknown) => {
              const errorMessage =
                err instanceof Error
                  ? err.message
                  : t("agents:error_creating_agent");
              setCreateError(errorMessage);
              // Dialog stays open for user to retry or cancel
              reject(err);
            },
          }
        );
      });
    },
    [createAgent, t]
  );

  const agents = data?.data ?? [];
  const hasAgents = agents.length > 0;

  return (
    <>
      <PageHead
        title="agents:page.title"
        description="agents:page.description"
        translateTitle
        translateDescription
      />
      <div className="space-y-6 p-6">
        {/* Page Header with Create Button */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t("agents:agents")}
            </h1>
            <p className="text-muted-foreground mt-2">{t("common:common")}</p>
          </div>
          <Button
            onClick={() => setIsDialogOpen(true)}
            className="gap-2"
            disabled={isLoading}
          >
            <Plus className="h-4 w-4" />
            {t("agents:create_agent")}
          </Button>
        </div>

        {/* Loading State: Show skeleton cards */}
        {isLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton
                key={`skeleton-${index}`}
                className="h-80 w-full rounded-lg"
              />
            ))}
          </div>
        )}

        {/* Error State: Show error message with retry button */}
        {isError && !isLoading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h3 className="font-semibold text-destructive">
                  {t("agents:error_loading_agents")}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {error?.message || t("common:something_went_wrong")}
                </p>
              </div>
              <button
                onClick={handleRetry}
                className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 whitespace-nowrap"
              >
                {t("common:retry")}
              </button>
            </div>
          </div>
        )}

        {/* Empty State: Show when no agents exist */}
        {!isLoading && !isError && !hasAgents && (
          <Empty className="min-h-64">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Zap className="size-6" />
              </EmptyMedia>
              <EmptyTitle>{t("agents:no_agents")}</EmptyTitle>
              <EmptyDescription>{t("common:no_data")}</EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <button
                onClick={() => setIsDialogOpen(true)}
                className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                {t("agents:create_agent")}
              </button>
            </EmptyContent>
          </Empty>
        )}

        {/* Agents Grid: Display agents in responsive grid
         * Responsive breakpoints:
         * - Base (mobile): 1 column
         * - sm: (640px+): 2 columns
         * - lg: (1024px+): 3 columns
         */}
        {!isLoading && !isError && hasAgents && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onClick={handleAgentCardClick}
              />
            ))}
          </div>
        )}

        {/* Create Agent Dialog */}
        <AgentDialog
          open={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          mode="create"
          onSubmit={handleCreateAgent}
          isLoading={isCreating}
          error={createError}
          onErrorDismiss={() => setCreateError(null)}
        />
      </div>
    </>
  );
};

export const AgentsPage = memo(AgentsPageComponent);
