import { useQuery } from "@tanstack/react-query";
import apiClient from "@config/axios-instance";
import { DEVICE_ENDPOINTS } from "@lib/api";
import type { Device, PaginatedResponse } from "@types";

/**
 * Request payload definitions
 */
export interface DeviceListParams {
  page?: number;
  page_size?: number;
}

export type DeviceListResponse = PaginatedResponse<Device>;

/**
 * Query Keys for device queries
 */
export const deviceQueryKeys = {
  all: ["devices"] as const,
  lists: () => [...deviceQueryKeys.all, "list"] as const,
  list: (params?: DeviceListParams) =>
    [...deviceQueryKeys.lists(), params ?? {}] as const,
  details: () => [...deviceQueryKeys.all, "detail"] as const,
  detail: (deviceId: string) =>
    [...deviceQueryKeys.details(), deviceId] as const,
};

/**
 * API Service Functions using Axios
 */
const deviceAPI = {
  fetchDevices: async (
    params?: DeviceListParams
  ): Promise<DeviceListResponse> => {
    const { data } = await apiClient.get<DeviceListResponse>(
      DEVICE_ENDPOINTS.LIST,
      { params }
    );
    return data;
  },

  fetchDeviceDetail: async (deviceId: string): Promise<Device> => {
    const { data } = await apiClient.get<Device>(
      DEVICE_ENDPOINTS.DETAIL(deviceId)
    );
    return data;
  },
};

/**
 * Query Hooks
 */
export const useDeviceList = (params?: DeviceListParams) => {
  return useQuery({
    queryKey: deviceQueryKeys.list(params),
    queryFn: () => deviceAPI.fetchDevices(params),
  });
};

export const useDeviceDetail = (deviceId: string, enabled = true) => {
  return useQuery({
    queryKey: deviceQueryKeys.detail(deviceId),
    queryFn: () => deviceAPI.fetchDeviceDetail(deviceId),
    enabled: Boolean(deviceId) && enabled,
  });
};
