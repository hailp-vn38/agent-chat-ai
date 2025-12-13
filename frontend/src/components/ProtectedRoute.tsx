import type { ReactNode } from "react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks";

interface ProtectedRouteProps {
  children: ReactNode;
}

/**
 * ProtectedRoute Component
 * Wraps routes to protect them from unauthorized access
 * - Checks if user is authenticated via useAuth hook
 * - AuthContext tự động fetch user qua useMe() khi authenticated
 * - Shows loading spinner while checking auth
 * - Redirects to /login if not authenticated
 * - Renders children if authenticated
 */
export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate("/login", { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  // Show loading spinner while checking auth or fetching user
  if (isLoading || (isAuthenticated && !user)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    );
  }

  // Redirect in progress, don't render anything
  if (!isAuthenticated) {
    return null;
  }

  return children;
};

export default ProtectedRoute;
