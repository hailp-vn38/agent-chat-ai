import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

// Import translation resources
import authEn from "@/locales/en/auth.json";
import authVi from "@/locales/vi/auth.json";
import chatEn from "@/locales/en/chat.json";
import chatVi from "@/locales/vi/chat.json";
import navigationEn from "@/locales/en/navigation.json";
import navigationVi from "@/locales/vi/navigation.json";
import commonEn from "@/locales/en/common.json";
import commonVi from "@/locales/vi/common.json";
import agentsEn from "@/locales/en/agents.json";
import agentsVi from "@/locales/vi/agents.json";
import templatesEn from "@/locales/en/templates.json";
import templatesVi from "@/locales/vi/templates.json";
import devicesEn from "@/locales/en/devices.json";
import devicesVi from "@/locales/vi/devices.json";
import providersEn from "@/locales/en/providers.json";
import providersVi from "@/locales/vi/providers.json";
import toolsEn from "@/locales/en/tools.json";
import toolsVi from "@/locales/vi/tools.json";
import mcpConfigsEn from "@/locales/en/mcp-configs.json";
import mcpConfigsVi from "@/locales/vi/mcp-configs.json";
import profileEn from "@/locales/en/profile.json";
import profileVi from "@/locales/vi/profile.json";

const resources = {
  en: {
    auth: authEn,
    chat: chatEn,
    navigation: navigationEn,
    common: commonEn,
    agents: agentsEn,
    templates: templatesEn,
    devices: devicesEn,
    providers: providersEn,
    tools: toolsEn,
    "mcp-configs": mcpConfigsEn,
    profile: profileEn,
  },
  vi: {
    auth: authVi,
    chat: chatVi,
    navigation: navigationVi,
    common: commonVi,
    agents: agentsVi,
    templates: templatesVi,
    devices: devicesVi,
    providers: providersVi,
    tools: toolsVi,
    "mcp-configs": mcpConfigsVi,
    profile: profileVi,
  },
};

i18next
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "en",
    ns: ["common"],
    defaultNS: "common",
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

export default i18next;
