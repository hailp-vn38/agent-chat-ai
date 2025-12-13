import { atom } from "jotai";
import type { User } from "@/types";

/**
 * Token atoms - quản lý access token trong memory
 * Refresh token được lưu trong cookie (xử lý tự động)
 */

/**
 * Access token atom - lưu trong memory
 * Được set khi login, clear khi logout
 */
export const accessTokenAtom = atom<string | null>(null);

/**
 * User atom - lưu user info
 * Sync với React Query cache từ useMe() hook
 */
export const userAtom = atom<User | null>(null);

/**
 * Auth loading atom
 */
export const authLoadingAtom = atom(false);

/**
 * Auth error atom
 */
export const authErrorAtom = atom<string | null>(null);

/**
 * Is authenticated atom (derived)
 */
export const isAuthenticatedAtom = atom((get) => {
  const token = get(accessTokenAtom);
  return !!token;
});
