import { QueryClient } from "@tanstack/react-query";

/**
 * Configure QueryClient for TanStack Query
 * Docs: https://tanstack.com/query/latest/docs/react/overview
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10, // 10 minutes (formerly cacheTime)
      retry: false, // Disable retry - only refetch on manual page reload
      refetchOnWindowFocus: false,
      refetchOnReconnect: false, // Don't auto-refetch when network reconnects
    },
    mutations: {
      retry: false, // Disable retry to prevent double submission
    },
  },
});
