import { atom } from "jotai";

/**
 * Config modules type definition
 */
export type ConfigModulesType = {
  LLM: string[];
  VLLM: string[];
  TTS: string[];
  Memory: string[];
  Intent: string[];
  ASR: string[];
  VAD: string[];
};

/**
 * Config modules atom - lưu danh sách modules từ backend
 */
export const configModulesAtom = atom<ConfigModulesType | null>(null);

/**
 * Config loading atom
 */
export const configLoadingAtom = atom(false);

/**
 * Config error atom
 */
export const configErrorAtom = atom<string | null>(null);
