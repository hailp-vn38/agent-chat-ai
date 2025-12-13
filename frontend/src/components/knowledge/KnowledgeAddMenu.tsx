import { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  Plus,
  FileText,
  Link,
  PenLine,
  ChevronDown,
  Upload,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ALL_SECTORS, KnowledgeSectorBadge } from "./KnowledgeSectorBadge";
import type {
  MemorySector,
  IngestFilePayload,
  IngestUrlPayload,
} from "@/types";

type KnowledgeAddMenuProps = {
  onAddManual: () => void;
  onIngestFile: (payload: IngestFilePayload) => Promise<void>;
  onIngestUrl: (payload: IngestUrlPayload) => Promise<void>;
  isLoading?: boolean;
};

const SUPPORTED_FILE_TYPES = {
  "application/pdf": "pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
    "docx",
  "text/plain": "txt",
  "text/markdown": "md",
} as const;

const ACCEPTED_EXTENSIONS = ".pdf,.docx,.txt,.md";

export function KnowledgeAddMenu({
  onAddManual,
  onIngestFile,
  onIngestUrl,
  isLoading = false,
}: KnowledgeAddMenuProps) {
  const { t, i18n } = useTranslation("agents");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Dialog states
  const [isUrlDialogOpen, setIsUrlDialogOpen] = useState(false);
  const [isFileDialogOpen, setIsFileDialogOpen] = useState(false);

  // Form states
  const [url, setUrl] = useState("");
  const [urlSector, setUrlSector] = useState<MemorySector>("semantic");
  const [urlTags, setUrlTags] = useState("");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileSector, setFileSector] = useState<MemorySector>("semantic");
  const [fileTags, setFileTags] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);

  const resetUrlForm = () => {
    setUrl("");
    setUrlSector("semantic");
    setUrlTags("");
  };

  const resetFileForm = () => {
    setSelectedFile(null);
    setFileSector("semantic");
    setFileTags("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setIsFileDialogOpen(true);
    }
  };

  const handleFileButtonClick = () => {
    fileInputRef.current?.click();
  };

  const getFileContentType = (
    file: File
  ): IngestFilePayload["content_type"] | null => {
    const mimeType = file.type as keyof typeof SUPPORTED_FILE_TYPES;
    if (SUPPORTED_FILE_TYPES[mimeType]) {
      return SUPPORTED_FILE_TYPES[
        mimeType
      ] as IngestFilePayload["content_type"];
    }
    // Fallback to extension
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext && ["pdf", "docx", "txt", "md"].includes(ext)) {
      return ext as IngestFilePayload["content_type"];
    }
    return null;
  };

  const parseTags = (tagsString: string): string[] => {
    return tagsString
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
  };

  const handleUrlSubmit = async () => {
    if (!url.trim()) return;

    setIsSubmitting(true);
    try {
      await onIngestUrl({
        url: url.trim(),
        sector: urlSector,
        tags: parseTags(urlTags),
      });
      setIsUrlDialogOpen(false);
      resetUrlForm();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileSubmit = async () => {
    if (!selectedFile) return;

    const contentType = getFileContentType(selectedFile);
    if (!contentType) {
      return;
    }

    setIsSubmitting(true);
    try {
      // Convert file to base64
      const reader = new FileReader();
      const base64Data = await new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const result = reader.result as string;
          // Remove data URL prefix (e.g., "data:application/pdf;base64,")
          const base64 = result.split(",")[1] || result;
          resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(selectedFile);
      });

      await onIngestFile({
        content_type: contentType,
        data: base64Data,
        filename: selectedFile.name,
        sector: fileSector,
        tags: parseTags(fileTags),
      });
      setIsFileDialogOpen(false);
      resetFileForm();
    } finally {
      setIsSubmitting(false);
    }
  };

  const locale = i18n.language as "en" | "vi";

  return (
    <>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS}
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Add Menu Button */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button disabled={isLoading} className="gap-2">
            <Plus className="h-4 w-4" />
            {t("add_knowledge")}
            <ChevronDown className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem onClick={onAddManual}>
            <PenLine className="h-4 w-4 mr-2" />
            {t("add_manual_entry")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleFileButtonClick}>
            <FileText className="h-4 w-4 mr-2" />
            {t("import_from_file")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setIsUrlDialogOpen(true)}>
            <Link className="h-4 w-4 mr-2" />
            {t("import_from_url")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* URL Dialog */}
      <Dialog open={isUrlDialogOpen} onOpenChange={setIsUrlDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("import_from_url")}</DialogTitle>
            <DialogDescription>{t("import_url_description")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="url">{t("url")}</Label>
              <Input
                id="url"
                type="url"
                placeholder="https://example.com/article"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("sector")}</Label>
              <Select
                value={urlSector}
                onValueChange={(v) => setUrlSector(v as MemorySector)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_SECTORS.map((sector) => (
                    <SelectItem key={sector} value={sector}>
                      <KnowledgeSectorBadge sector={sector} locale={locale} />
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="url-tags">{t("tags_optional")}</Label>
              <Input
                id="url-tags"
                placeholder={t("tags_placeholder")}
                value={urlTags}
                onChange={(e) => setUrlTags(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsUrlDialogOpen(false);
                resetUrlForm();
              }}
            >
              {t("cancel")}
            </Button>
            <Button
              onClick={handleUrlSubmit}
              disabled={!url.trim() || isSubmitting}
            >
              {isSubmitting && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {t("import")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* File Dialog */}
      <Dialog
        open={isFileDialogOpen}
        onOpenChange={(open) => {
          setIsFileDialogOpen(open);
          if (!open) resetFileForm();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("import_from_file")}</DialogTitle>
            <DialogDescription>
              {t("import_file_description")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {/* Selected file display */}
            {selectedFile && (
              <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
                <Upload className="h-5 w-5 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleFileButtonClick}
                >
                  {t("change")}
                </Button>
              </div>
            )}
            <div className="space-y-2">
              <Label>{t("sector")}</Label>
              <Select
                value={fileSector}
                onValueChange={(v) => setFileSector(v as MemorySector)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_SECTORS.map((sector) => (
                    <SelectItem key={sector} value={sector}>
                      <KnowledgeSectorBadge sector={sector} locale={locale} />
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="file-tags">{t("tags_optional")}</Label>
              <Input
                id="file-tags"
                placeholder={t("tags_placeholder")}
                value={fileTags}
                onChange={(e) => setFileTags(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsFileDialogOpen(false);
                resetFileForm();
              }}
            >
              {t("cancel")}
            </Button>
            <Button
              onClick={handleFileSubmit}
              disabled={!selectedFile || isSubmitting}
            >
              {isSubmitting && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {t("import")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
