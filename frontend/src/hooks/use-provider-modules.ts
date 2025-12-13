import { useProviderConfigModules } from "@/queries";
import type { ProviderModulesResponse } from "@/queries/provider-queries";

/**
 * Custom hook to get provider modules grouped by category
 * Provides access to provider configuration modules from API
 *
 * @param includeDefaults - Whether to include default modules from config (default: false)
 * @returns { modules, isLoading, error }
 *
 * @example
 * const { modules, isLoading, error } = useProviderModules();
 * if (isLoading) return <Loading />;
 * if (error) return <Error message={error.message} />;
 * return <div>{modules?.LLM?.map(llm => <option>{llm.name}</option>)}</div>;
 */
export const useProviderModules = (includeDefaults = false) => {
  const { data, isLoading, error } = useProviderConfigModules(includeDefaults);

  return {
    modules: data as ProviderModulesResponse | undefined,
    isLoading,
    error: error instanceof Error ? error : undefined,
  };
};

export default useProviderModules;
