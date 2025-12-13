import { useAtom } from "jotai";
import { configModulesAtom, configLoadingAtom, configErrorAtom } from "@store";

/**
 * Custom hook to manage config modules
 * Provides access to config state and query
 *
 * Note: Only fetches once on app load, data is cached forever
 * Use atom directly for minimal re-renders
 *
 * @example
 * const { modules, loading, error } = useConfig();
 * if (loading) return <Loading />;
 * if (error) return <Error message={error} />;
 * return <div>{modules?.LLM.map(llm => <option>{llm}</option>)}</div>;
 */
export const useConfig = () => {
  const [configModules] = useAtom(configModulesAtom);
  const [configLoading] = useAtom(configLoadingAtom);
  const [configError] = useAtom(configErrorAtom);

  return {
    modules: configModules,
    loading: configLoading,
    error: configError,
  };
};

export default useConfig;
