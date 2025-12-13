import { useContext } from "react";
import { AuthContext } from "@/contexts";

/**
 * Custom hook to use Auth Context
 * Must be used within AuthProvider
 * @throws Error if used outside AuthProvider
 * @returns AuthContextType with auth state and functions
 */
export const useAuth = () => {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
};

export default useAuth;
