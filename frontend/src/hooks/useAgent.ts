export {
  useAgentList,
  useAgentDetail,
  useCreateAgent,
  useUpdateAgent,
  useDeleteAgent,
  useBindAgentDevice,
  useDeleteAgentDevice,
  useActivateAgentTemplate,
  agentQueryKeys,
} from "@/queries/agent-queries";

// Re-export template queries for convenience
export {
  useTemplateList,
  useTemplateDetail,
  useTemplateAgents,
  useCreateTemplate,
  useUpdateTemplate,
  useDeleteTemplate,
  useAssignTemplate,
  useUnassignTemplate,
  useCreateAndAssignTemplate,
  templateQueryKeys,
} from "@/queries/template-queries";
