import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

interface UsePageHeadProps {
  title?: string;
  description?: string;
  keywords?: string;
  ogTitle?: string;
  ogDescription?: string;
  ogImage?: string;
  ogUrl?: string;
  translateTitle?: boolean;
  translateDescription?: boolean;
  translateKeywords?: boolean;
}

export type { UsePageHeadProps };

const DEFAULT_TITLE = "Home Bot";
const DEFAULT_DESCRIPTION = "Smart Home Assistant";
const DEFAULT_OG_IMAGE = "/og-image.png";

/**
 * Hook to manage document metadata using React 19 native Document Metadata API
 * Supports SEO, Open Graph, Twitter Card, and i18n
 *
 * Example:
 * usePageHead({
 *   title: 'Agents',
 *   description: 'Manage your AI agents',
 *   translateTitle: true,
 *   translateDescription: true,
 * });
 */
export function usePageHead({
  title,
  description,
  keywords,
  ogTitle,
  ogDescription,
  ogImage,
  ogUrl,
  translateTitle = false,
  translateDescription = false,
  translateKeywords = false,
}: UsePageHeadProps): void {
  const { t, ready } = useTranslation();
  const metaRefs = useRef<Map<string, HTMLMetaElement | HTMLTitleElement>>(
    new Map()
  );

  useEffect(() => {
    // Process title
    const pageTitle = title
      ? translateTitle && ready
        ? t(title)
        : title
      : DEFAULT_TITLE;

    const fullTitle =
      pageTitle !== DEFAULT_TITLE
        ? `${pageTitle} | ${DEFAULT_TITLE}`
        : DEFAULT_TITLE;

    // Process description
    const pageDescription = description
      ? translateDescription && ready
        ? t(description)
        : description
      : DEFAULT_DESCRIPTION;

    // Process keywords
    const pageKeywords = keywords
      ? translateKeywords && ready
        ? t(keywords)
        : keywords
      : undefined;

    // Open Graph defaults
    const finalOgTitle = ogTitle || fullTitle;
    const finalOgDescription = ogDescription || pageDescription;
    const finalOgImage = ogImage || DEFAULT_OG_IMAGE;
    const finalOgUrl = ogUrl || window.location.href;

    // Update title
    document.title = fullTitle;
    const titleElement = document.querySelector("title");
    if (titleElement) {
      metaRefs.current.set("title", titleElement);
    }

    // Helper to create or update meta tag
    const updateMetaTag = (
      name: string,
      property: string | null,
      content: string
    ) => {
      let element = metaRefs.current.get(name);

      if (!element) {
        element = document.createElement("meta");
        if (property) {
          element.setAttribute("property", property);
        } else {
          element.setAttribute("name", name);
        }
        document.head.appendChild(element);
        metaRefs.current.set(name, element);
      }

      element.setAttribute("content", content);
    };

    // Update meta tags
    updateMetaTag("description", null, pageDescription);

    if (pageKeywords) {
      updateMetaTag("keywords", null, pageKeywords);
    }

    // Open Graph
    updateMetaTag("og:type", "og:type", "website");
    updateMetaTag("og:title", "og:title", finalOgTitle);
    updateMetaTag("og:description", "og:description", finalOgDescription);
    updateMetaTag("og:image", "og:image", finalOgImage);
    updateMetaTag("og:url", "og:url", finalOgUrl);

    // Twitter Card
    updateMetaTag("twitter:card", null, "summary_large_image");
    updateMetaTag("twitter:title", null, finalOgTitle);
    updateMetaTag("twitter:description", null, finalOgDescription);
    updateMetaTag("twitter:image", null, finalOgImage);

    // Cleanup function to remove meta tags when component unmounts (optional)
    // For now, we keep them so they persist when navigating
  }, [
    title,
    description,
    keywords,
    ogTitle,
    ogDescription,
    ogImage,
    ogUrl,
    translateTitle,
    translateDescription,
    translateKeywords,
    ready,
    t,
  ]);
}
