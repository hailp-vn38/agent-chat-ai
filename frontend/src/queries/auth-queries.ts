import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { useNavigate } from "react-router-dom";
import { accessTokenAtom, userAtom, authErrorAtom } from "@store";
import apiClient from "@config/axios-instance";
import { AUTH_ENDPOINTS } from "@api";
import { saveAccessToken, removeAccessToken } from "@lib/token-storage";
import { userQueryKeys } from "./user-queries";

/**
 * Query Keys for auth queries
 * @deprecated Dùng userQueryKeys.me() từ user-queries.ts cho user data
 */
export const authQueryKeys = {
  all: ["auth"] as const,
  me: () => userQueryKeys.me(), // Redirect sang userQueryKeys để backward compatible
};

/**
 * API Service Functions using Axios
 * Based on AUTH_ENDPOINTS_V2.md
 */
const authAPI = {
  // POST /auth/login
  // Body: FormData { username, password }
  // Response: { access_token, token_type }
  login: async (
    username: string,
    password: string
  ): Promise<{ access_token: string; token_type: string }> => {
    const formData = new FormData();
    formData.append("username", username);
    formData.append("password", password);

    const { data } = await apiClient.post(AUTH_ENDPOINTS.LOGIN, formData, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });
    // Refresh token được tự động lưu trong cookie bởi server (httpOnly cookie)
    return data;
  },

  // POST /auth/register
  // Body: { name, email, password }
  // Response: { id, name, email, profile_image_url }
  register: async (
    name: string,
    email: string,
    password: string
  ): Promise<{
    id: string;
    name: string;
    email: string;
    profile_image_url?: string;
  }> => {
    const { data } = await apiClient.post(AUTH_ENDPOINTS.REGISTER, {
      name,
      email,
      password,
    });
    // Refresh token được tự động lưu trong cookie bởi server (httpOnly cookie)
    return data;
  },

  // POST /auth/logout
  // Headers: Authorization: Bearer <access_token>
  // Response: { message }
  logout: async (): Promise<void> => {
    await apiClient.post(AUTH_ENDPOINTS.LOGOUT);
    // Cookie refresh token sẽ bị xóa bởi server
  },
};

/**
 * Mutation Hooks
 */
export const useLogin = () => {
  const queryClient = useQueryClient();
  const setAccessToken = useSetAtom(accessTokenAtom);
  const setAuthError = useSetAtom(authErrorAtom);

  return useMutation({
    mutationFn: ({
      username,
      password,
    }: {
      username: string;
      password: string;
    }) => authAPI.login(username, password),
    onSuccess: (data) => {
      // Set access token to atom (from response: access_token)
      setAccessToken(data.access_token);
      // Save token to localStorage for persistence
      saveAccessToken(data.access_token);
      // Clear error
      setAuthError(null);
      // Invalidate queries to fetch current user (dùng userQueryKeys.me())
      queryClient.invalidateQueries({ queryKey: userQueryKeys.me() });
    },
    onError: (error: any) => {
      const message = error.response?.data?.message || "Login failed";
      setAuthError(message);
    },
  });
};

export const useRegister = () => {
  const setUser = useSetAtom(userAtom);
  const setAuthError = useSetAtom(authErrorAtom);

  return useMutation({
    mutationFn: ({
      name,
      email,
      password,
    }: {
      name: string;
      email: string;
      password: string;
    }) => authAPI.register(name, email, password),
    onSuccess: (data) => {
      // Set user to atom (register returns user data, not access token)
      // Need to login after register
      setUser({
        id: data.id,
        name: data.name,
        email: data.email,
        profile_image_base64: data.profile_image_url ?? null,
      });
      // Clear error
      setAuthError(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.message || "Registration failed";
      setAuthError(message);
    },
  });
};

export const useLogout = () => {
  const queryClient = useQueryClient();
  const setAccessToken = useSetAtom(accessTokenAtom);
  const setUser = useSetAtom(userAtom);
  const setAuthError = useSetAtom(authErrorAtom);
  const navigate = useNavigate();

  return useMutation({
    mutationFn: authAPI.logout,
    onSuccess: () => {
      // Clear access token
      setAccessToken(null);
      // Remove token from localStorage
      removeAccessToken();
      // Clear user
      setUser(null);
      // Clear error
      setAuthError(null);
      // Remove user queries
      queryClient.removeQueries({ queryKey: userQueryKeys.me() });
      // Redirect to login
      navigate("/login", { replace: true });
    },
    onError: (error: any) => {
      const message = error.response?.data?.message || "Logout failed";
      setAuthError(message);
    },
  });
};
