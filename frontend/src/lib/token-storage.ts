/**
 * Token Storage Utility
 * Manages access token persistence in localStorage
 */

const TOKEN_KEY = "access_token";

/**
 * Save access token to localStorage
 */
export const saveAccessToken = (token: string): void => {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch (error) {
    console.error("Failed to save access token to localStorage:", error);
  }
};

/**
 * Get access token from localStorage
 */
export const getAccessToken = (): string | null => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch (error) {
    console.error("Failed to get access token from localStorage:", error);
    return null;
  }
};

/**
 * Remove access token from localStorage
 */
export const removeAccessToken = (): void => {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch (error) {
    console.error("Failed to remove access token from localStorage:", error);
  }
};

/**
 * Check if token exists in localStorage
 */
export const hasAccessToken = (): boolean => {
  return getAccessToken() !== null;
};
