import { useEffect } from "react";
import { useTranslation } from "react-i18next";

interface DocumentMetaOptions {
  title?: string;
  description?: string;
  translateTitle?: boolean;
  translateDescription?: boolean;
}

const DEFAULT_TITLE = "Home Bot";
const DEFAULT_DESCRIPTION = "Smart Home Assistant";

/**
 * Custom hook để quản lý document title và meta description
 *
 * @param options - Cấu hình meta tags
 * @param options.title - Title của page
 * @param options.description - Description của page
 * @param options.translateTitle - Có translate title không (default: false)
 * @param options.translateDescription - Có translate description không (default: false)
 *
 * @example
 * ```tsx
 * // Sử dụng với static text
 * useDocumentMeta({
 *   title: "Agents",
 *   description: "Manage your AI agents"
 * });
 *
 * // Sử dụng với i18n
 * useDocumentMeta({
 *   title: "agents:page.title",
 *   description: "agents:page.description",
 *   translateTitle: true,
 *   translateDescription: true
 * });
 * ```
 */
export const useDocumentMeta = ({
  title,
  description,
  translateTitle = false,
  translateDescription = false,
}: DocumentMetaOptions = {}) => {
  const { t } = useTranslation();

  useEffect(() => {
    // Update title
    const pageTitle = title
      ? translateTitle
        ? t(title)
        : title
      : DEFAULT_TITLE;
    document.title =
      pageTitle !== DEFAULT_TITLE
        ? `${pageTitle} | ${DEFAULT_TITLE}`
        : DEFAULT_TITLE;

    // Update meta description
    const pageDescription = description
      ? translateDescription
        ? t(description)
        : description
      : DEFAULT_DESCRIPTION;

    let metaDescription = document.querySelector('meta[name="description"]');
    if (!metaDescription) {
      metaDescription = document.createElement("meta");
      metaDescription.setAttribute("name", "description");
      document.head.appendChild(metaDescription);
    }
    metaDescription.setAttribute("content", pageDescription);

    // Cleanup function để reset về default khi component unmount
    return () => {
      document.title = DEFAULT_TITLE;
      const meta = document.querySelector('meta[name="description"]');
      if (meta) {
        meta.setAttribute("content", DEFAULT_DESCRIPTION);
      }
    };
  }, [title, description, translateTitle, translateDescription, t]);
};
