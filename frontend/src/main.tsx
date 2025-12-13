import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { useAtom } from "jotai";
import { I18nextProvider } from "react-i18next";
import { Toaster } from "sonner";
import "./App.css";
import App from "./App.tsx";
import { QueryProvider, setupAxiosInterceptors, i18n } from "@config";
import { AuthProvider } from "@/contexts";
import { accessTokenAtom, authErrorAtom } from "@store";
import { languageAtom } from "@store/language-atom";
import {
  getAccessToken,
  saveAccessToken,
  removeAccessToken,
} from "@lib/token-storage";

function AppWrapper() {
  const [accessToken, setAccessToken] = useAtom(accessTokenAtom);
  const [, setAuthError] = useAtom(authErrorAtom);
  const [, setLanguage] = useAtom(languageAtom);
  const [isInitialized, setIsInitialized] = useState(false);

  // Restore token from localStorage on mount
  // This runs ONCE to hydrate auth state after page reload
  useEffect(() => {
    const storedToken = getAccessToken();
    if (storedToken) {
      setAccessToken(storedToken);
    }
    setIsInitialized(true);
  }, []);

  // Setup axios interceptors ONCE on mount
  // Interceptor will handle 401 refresh automatically
  useEffect(() => {
    setupAxiosInterceptors(() => accessToken, setAccessToken, setAuthError);
  }, [accessToken, setAccessToken, setAuthError]);

  // Persist access token changes (e.g., after refresh)
  useEffect(() => {
    if (!isInitialized) return;
    if (accessToken) {
      saveAccessToken(accessToken);
    } else {
      removeAccessToken();
    }
  }, [accessToken, isInitialized]);

  // Sync i18n language to Jotai atom and localStorage
  useEffect(() => {
    // Get current language from i18next and sync to atom
    const currentLng = i18n.language as "en" | "vi";
    setLanguage(currentLng);

    // Persist to localStorage (in case i18n didn't auto-save)
    localStorage.setItem("i18n", currentLng);

    // Listen to i18n language changes and sync to atom
    const handleLanguageChanged = (lng: string) => {
      const validLng = (lng === "vi" ? "vi" : "en") as "en" | "vi";
      setLanguage(validLng);
      localStorage.setItem("i18n", validLng);
    };

    i18n.on("languageChanged", handleLanguageChanged);

    return () => {
      i18n.off("languageChanged", handleLanguageChanged);
    };
  }, [setLanguage]);

  // Show loading spinner while initializing auth
  if (!isInitialized) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <>
      <App />
      <Toaster position="top-right" richColors />
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryProvider>
        <I18nextProvider i18n={i18n}>
          <AuthProvider>
            <AppWrapper />
          </AuthProvider>
        </I18nextProvider>
      </QueryProvider>
    </BrowserRouter>
  </StrictMode>
);
