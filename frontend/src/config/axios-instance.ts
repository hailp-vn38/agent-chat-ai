import axios from "axios";
import { saveAccessToken, removeAccessToken } from "@lib/token-storage";

// Để trống mặc định để sử dụng Proxy của Vite (relative path)
const API_URL = import.meta.env.VITE_API_URL || "";
const API_BASE_PATH = import.meta.env.VITE_API_BASE_PATH || "/api/v1";

/**
 * Create axios instance
 */
export const apiClient = axios.create({
  baseURL: `${API_URL}${API_BASE_PATH}`,
  withCredentials: true, // Include cookies in requests
});

/**
 * Callback refs to keep current setters accessible without re-setting up interceptors
 */
let callbackRefs = {
  getAccessToken: (() => null) as () => string | null,
  setAccessToken: ((_token: string | null) => {}) as (
    token: string | null
  ) => void,
  setAuthError: ((_error: string | null) => {}) as (
    error: string | null
  ) => void,
};

/**
 * Flag to prevent setting up interceptors multiple times
 */
let interceptorsSetup = false;

/**
 * Setup interceptors - can only be called inside React component
 * Call this in App.tsx or a main layout component
 * Only sets up interceptors ONCE to prevent duplicate handlers
 */
export const setupAxiosInterceptors = (
  getAccessToken: () => string | null,
  setAccessToken: (token: string | null) => void,
  setAuthError: (error: string | null) => void
) => {
  // Update callback refs (always updated even if interceptors already set up)
  callbackRefs.getAccessToken = getAccessToken;
  callbackRefs.setAccessToken = setAccessToken;
  callbackRefs.setAuthError = setAuthError;

  // Prevent setting up interceptors multiple times
  if (interceptorsSetup) {
    return;
  }
  interceptorsSetup = true;

  /**
   * Request interceptor - add access token to headers
   */
  apiClient.interceptors.request.use(
    (config) => {
      const token = callbackRefs.getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  /**
   * Response interceptor - handle 401 and refresh token
   */
  let isRefreshing = false;
  let failedQueue: Array<{
    resolve: (value: string) => void;
    reject: (reason?: any) => void;
  }> = [];

  const processQueue = (error: any, token: string | null = null) => {
    failedQueue.forEach((prom) => {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve(token!);
      }
    });
    failedQueue = [];
  };

  apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;

      // Handle 401 Unauthorized - try to refresh token
      if (error.response?.status === 401 && !originalRequest._retry) {
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          })
            .then((token) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              return apiClient(originalRequest);
            })
            .catch((err) => Promise.reject(err));
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          // Call refresh token endpoint
          const response = await axios.post(
            `${API_URL}${API_BASE_PATH}/auth/refresh`,
            {},
            { withCredentials: true }
          );

          const { access_token } = response.data;
          callbackRefs.setAccessToken(access_token);
          saveAccessToken(access_token);
          callbackRefs.setAuthError(null);

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          processQueue(null, access_token);

          return apiClient(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          callbackRefs.setAccessToken(null);
          removeAccessToken();
          callbackRefs.setAuthError("Session expired. Please login again.");
          // Redirect to login page
          window.location.href = "/login";
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }

      // Handle 403 Forbidden
      if (error.response?.status === 403) {
        callbackRefs.setAuthError(
          "You do not have permission to access this resource."
        );
      }

      // Handle 503 Service Unavailable for Knowledge Base
      if (error.response?.status === 503) {
        const detail = error.response?.data?.detail;
        if (detail?.includes("Knowledge Base feature is disabled")) {
          // Let the component handle this specific error
          error.isKnowledgeBaseDisabled = true;
        }
      }

      return Promise.reject(error);
    }
  );
};

export default apiClient;
