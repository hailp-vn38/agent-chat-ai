/**
 * Knowledge Base Type Definitions
 * Based on knowledge-base.md API documentation
 */

/**
 * Memory Sectors - Phân loại tri thức
 */
export const MEMORY_SECTORS = {
  EPISODIC: "episodic",
  SEMANTIC: "semantic",
  PROCEDURAL: "procedural",
  EMOTIONAL: "emotional",
  REFLECTIVE: "reflective",
} as const;

export type MemorySector = (typeof MEMORY_SECTORS)[keyof typeof MEMORY_SECTORS];

/**
 * Sector Info - Thông tin về một sector
 */
export type SectorInfo = {
  name: MemorySector;
  description: string;
};

/**
 * Knowledge Entry - Một mục tri thức
 */
export type KnowledgeEntry = {
  id: string;
  content: string;
  sectors: MemorySector[];
  primary_sector: MemorySector;
  tags: string[];
  metadata: Record<string, unknown>;
  salience: number;
  last_seen_at: number | null;
  created_at: string;
};

/**
 * Search Match Result - Kết quả tìm kiếm
 */
export type KnowledgeSearchMatch = {
  id: string;
  content: string;
  score: number;
  sectors: MemorySector[];
  primary_sector: MemorySector;
  path: string[];
  salience: number;
  last_seen_at: number | null;
};

/**
 * API Response Types
 */
export type KnowledgeBaseHealthResponse = {
  success: boolean;
  message: string;
  data: {
    status: string;
    version: string;
    message: string;
  };
};

export type KnowledgeBaseSectorsResponse = {
  success: boolean;
  message: string;
  data: {
    sectors: SectorInfo[];
  };
};

export type KnowledgeEntryResponse = {
  success: boolean;
  message: string;
  data: KnowledgeEntry;
};

export type KnowledgeEntryListResponse = {
  success: boolean;
  message: string;
  data: {
    items: KnowledgeEntry[];
    total: number;
    limit: number;
    offset: number;
  };
};

export type KnowledgeSearchResponse = {
  success: boolean;
  message: string;
  data: {
    query: string;
    matches: KnowledgeSearchMatch[];
    total: number;
  };
};

export type KnowledgeDeleteResponse = {
  success: boolean;
  message: string;
  data: {
    id: string;
    deleted: boolean;
  };
};

export type KnowledgeIngestResponse = {
  success: boolean;
  message: string;
  data: {
    success: boolean;
    message: string;
    items_created: number;
  };
};

/**
 * Request Payload Types
 */
export type CreateKnowledgeEntryPayload = {
  content: string;
  sector?: MemorySector;
  tags?: string[];
  metadata?: Record<string, unknown>;
};

export type UpdateKnowledgeEntryPayload = {
  content?: string;
  tags?: string[];
};

export type KnowledgeSearchPayload = {
  query: string;
  k?: number;
  min_score?: number;
  sector?: MemorySector;
};

export type IngestFilePayload = {
  content_type: "pdf" | "docx" | "txt" | "md";
  data: string;
  filename: string;
  sector?: MemorySector;
  tags?: string[];
};

export type IngestUrlPayload = {
  url: string;
  sector?: MemorySector;
  tags?: string[];
};

/**
 * Query Parameters
 */
export type KnowledgeListParams = {
  limit?: number;
  offset?: number;
  sector?: MemorySector;
};
