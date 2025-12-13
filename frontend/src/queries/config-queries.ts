import apiClient from "@config/axios-instance";
import type { ConfigModulesType } from "@store";

/**
 * Query Keys for config queries
 */
export const configQueryKeys = {
  all: ["config"] as const,
  modules: () => [...configQueryKeys.all, "modules"] as const,
};

/**
 * API Service Functions using Axios
 * Based on CONFIG_ENDPOINT.md
 */
export const configAPI = {
  // GET /config/modules
  // Response: { LLM: [], VLLM: [], TTS: [], Memory: [], Intent: [], ASR: [], VAD: [] }
  getModules: async (): Promise<ConfigModulesType> => {
    const { data } = await apiClient.get("/config/modules");
    return data;
  },
};
