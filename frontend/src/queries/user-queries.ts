import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import type {
  User,
  UpdateUserInput,
  ChangePasswordInput,
  DeleteAccountResponse,
  UploadAvatarResponse,
} from "@types";
import { userAtom, accessTokenAtom } from "@store";
import apiClient from "@config/axios-instance";
import { USER_ENDPOINTS } from "@api";

/**
 * Query Keys for user queries
 */
export const userQueryKeys = {
  all: ["user"] as const,
  me: () => [...userQueryKeys.all, "me"] as const,
  devices: (filters?: Record<string, unknown>) =>
    [...userQueryKeys.all, "devices", filters] as const,
};

/**
 * API Service Functions using Axios
 * Based on docs/users.md
 */
const userAPI = {
  /**
   * GET /user/me - Fetch current user profile
   */
  getMe: async (): Promise<User> => {
    const { data } = await apiClient.get(USER_ENDPOINTS.ME);
    return data;
  },

  /**
   * PATCH /user/me - Update user profile
   * Supports partial updates
   */
  updateMe: async (input: UpdateUserInput): Promise<User> => {
    const { data } = await apiClient.patch(USER_ENDPOINTS.UPDATE_ME, input);
    return data;
  },

  /**
   * PUT /user/me/password - Change user password
   * Invalidates all tokens on success
   */
  changePassword: async (
    input: ChangePasswordInput
  ): Promise<{ message: string }> => {
    const { data } = await apiClient.put(USER_ENDPOINTS.CHANGE_PASSWORD, input);
    return data;
  },

  /**
   * POST /user/me/profile-image - Upload profile avatar
   * Accepts multipart/form-data with 'file' field
   */
  uploadAvatar: async (file: File): Promise<UploadAvatarResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    const { data } = await apiClient.post(
      USER_ENDPOINTS.UPLOAD_AVATAR,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return data;
  },

  /**
   * DELETE /user/me - Soft delete user account
   * Account can be restored within 30 days
   */
  deleteAccount: async (): Promise<DeleteAccountResponse> => {
    const { data } = await apiClient.delete(USER_ENDPOINTS.DELETE_ACCOUNT);
    return data;
  },
};

/**
 * Query Hooks
 */

/**
 * Hook thống nhất để lấy current user
 * - Dùng ở mọi nơi cần user data (ProfilePage, UserDropdownMenu, etc.)
 * - Tự động sync với userAtom khi fetch thành công
 * - Single source of truth từ React Query cache
 */
export const useMe = (enabled = true) => {
  const setUser = useSetAtom(userAtom);

  return useQuery({
    queryKey: userQueryKeys.me(),
    queryFn: async () => {
      const user = await userAPI.getMe();
      // Sync với Jotai atom
      setUser(user);
      return user;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1,
    enabled,
  });
};

/**
 * @deprecated Dùng useMe() thay thế
 * Fetch current user profile
 * Cache với staleTime 5 phút
 */
export const useUserProfile = () => {
  return useMe();
};

/**
 * Mutation Hooks
 */

/**
 * Update user profile (name, email)
 * Invalidates user cache và sync với userAtom
 */
export const useUpdateProfile = () => {
  const queryClient = useQueryClient();
  const setUser = useSetAtom(userAtom);

  return useMutation({
    mutationFn: userAPI.updateMe,
    onSuccess: (updatedUser) => {
      // Update React Query cache (single source of truth)
      queryClient.setQueryData(userQueryKeys.me(), updatedUser);

      // Sync với Jotai atom
      setUser(updatedUser);

      // Success feedback
      toast.success("Profile updated successfully");
    },
    onError: (error: any) => {
      // Handle specific error cases
      if (error.response?.status === 409) {
        toast.error("Email already in use");
      } else if (error.response?.status === 422) {
        toast.error("Invalid input data");
      } else {
        toast.error(error.response?.data?.detail || "Failed to update profile");
      }
    },
  });
};

/**
 * Change password mutation
 * Triggers logout sau khi success (tokens invalidated)
 */
export const useChangePassword = () => {
  const navigate = useNavigate();
  const setUser = useSetAtom(userAtom);
  const setAccessToken = useSetAtom(accessTokenAtom);

  return useMutation({
    mutationFn: userAPI.changePassword,
    onSuccess: () => {
      // Clear auth state
      setUser(null);
      setAccessToken(null);

      // Success feedback
      toast.success("Password changed successfully. Please login again.");

      // Redirect về login sau 2 seconds
      setTimeout(() => {
        navigate("/login", { replace: true });
      }, 2000);
    },
    onError: (error: any) => {
      if (error.response?.status === 401) {
        toast.error("Current password is incorrect");
      } else if (error.response?.status === 422) {
        toast.error("New password does not meet requirements");
      } else {
        toast.error(
          error.response?.data?.detail || "Failed to change password"
        );
      }
    },
  });
};

/**
 * Upload avatar mutation
 * Updates profile image URL trong cache
 */
export const useUploadAvatar = () => {
  const queryClient = useQueryClient();
  const setUser = useSetAtom(userAtom);

  return useMutation({
    mutationFn: userAPI.uploadAvatar,
    onSuccess: (response) => {
      // Update React Query cache (single source of truth)
      queryClient.setQueryData<User>(userQueryKeys.me(), (oldData) => {
        if (!oldData) return oldData;
        return {
          ...oldData,
          profile_image_base64: response.profile_image_base64,
        };
      });

      // Sync với Jotai atom
      setUser((prev) =>
        prev
          ? { ...prev, profile_image_base64: response.profile_image_base64 }
          : null
      );

      // Success feedback
      toast.success("Avatar updated successfully");

      // Invalidate để refetch fresh data
      queryClient.invalidateQueries({ queryKey: userQueryKeys.me() });
    },
    onError: (error: any) => {
      if (error.response?.status === 413) {
        toast.error("File size must be less than 5MB");
      } else if (error.response?.status === 422) {
        toast.error("Invalid file type. Only JPEG, PNG, and WebP are allowed");
      } else {
        toast.error(error.response?.data?.detail || "Failed to upload avatar");
      }
    },
  });
};

/**
 * Delete account mutation
 * Clears all auth state và redirects về login
 */
export const useDeleteAccount = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setUser = useSetAtom(userAtom);
  const setAccessToken = useSetAtom(accessTokenAtom);

  return useMutation({
    mutationFn: userAPI.deleteAccount,
    onSuccess: (response) => {
      // Clear all auth state
      setUser(null);
      setAccessToken(null);
      queryClient.clear();

      // Show final message với restore info
      const restoreDate = new Date(
        response.restore_deadline
      ).toLocaleDateString();
      toast.success(
        `Account deleted. You can restore it until ${restoreDate}.`,
        { duration: 5000 }
      );

      // Redirect về login sau 2 seconds
      setTimeout(() => {
        navigate("/login", { replace: true });
      }, 2000);
    },
    onError: (error: any) => {
      if (error.response?.status === 400) {
        toast.error("Account already deleted");
      } else {
        toast.error(error.response?.data?.detail || "Failed to delete account");
      }
    },
  });
};
