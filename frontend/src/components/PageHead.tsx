import { usePageHead } from "@/hooks/usePageHead";

interface PageHeadProps {
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

/**
 * PageHead Component
 *
 * Component to manage document metadata using React 19 native Document Metadata API
 * Supports SEO, Open Graph, Twitter Card, and i18n
 *
 * Example usage:
 * - Basic: <PageHead title="Agents" description="Manage your AI agents" />
 * - With i18n: <PageHead title="agents:page.title" translateTitle />
 * - With OG: <PageHead title="Agents" ogImage="/images/agents-preview.png" />
 */
export const PageHead = ({
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
}: PageHeadProps) => {
  usePageHead({
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
  });

  return null;
};
