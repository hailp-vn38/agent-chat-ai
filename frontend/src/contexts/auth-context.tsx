import { createContext, useCallback, useMemo } from "react";
import type { ReactNode } from "react";
import { useAtomValue } from "jotai";
import type { User } from "@/types";
import { authErrorAtom, isAuthenticatedAtom } from "@/store/auth-atom";
import { useLogout } from "@/queries/auth-queries";
import { useMe } from "@/queries/user-queries";

/**
 * Auth Context Type Definition
 * Contains authentication state and functions
 */
export interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  error: string | null;
  logout: () => void;
}

/**
 * Create Auth Context
 * Default value will be checked at runtime in useAuth hook
 */
export const AuthContext = createContext<AuthContextType | undefined>(
  undefined
);

/**
 * Auth Provider Component
 * - Dùng useMe() để lấy user từ React Query (single source of truth)
 * - useMe() tự động sync với userAtom
 * Provides useAuth hook for components
 */
export const AuthProvider = ({ children }: { children: ReactNode }) => {
  // Read atoms
  const isAuthenticated = useAtomValue(isAuthenticatedAtom);
  const error = useAtomValue(authErrorAtom);

  // Get user from React Query (single source of truth)
  // Chỉ fetch khi đã authenticated
  const { data: user = null, isLoading: isUserLoading } =
    useMe(isAuthenticated);

  // Get logout mutation
  const { mutate: logoutMutate, isPending: isLogoutPending } = useLogout();

  // Memoized logout function
  const logout = useCallback(() => {
    logoutMutate();
  }, [logoutMutate]);

  // Memoize context value to prevent unnecessary re-renders
  const contextValue = useMemo<AuthContextType>(
    () => ({
      isAuthenticated,
      isLoading: isLogoutPending || isUserLoading,
      user,
      error,
      logout,
    }),
    [isAuthenticated, isLogoutPending, isUserLoading, user, error, logout]
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
};

export default AuthProvider;
