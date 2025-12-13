import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ALL_SECTORS, KnowledgeSectorBadge } from "./KnowledgeSectorBadge";
import type { KnowledgeEntry, MemorySector } from "@/types";

const formSchema = z.object({
  content: z
    .string()
    .min(1, "Content is required")
    .max(50000, "Content must be less than 50000 characters"),
  sector: z.enum([
    "episodic",
    "semantic",
    "procedural",
    "emotional",
    "reflective",
  ]),
  tags: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

type KnowledgeEntryDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entry?: KnowledgeEntry | null;
  onSubmit: (data: {
    content: string;
    sector: MemorySector;
    tags: string[];
  }) => Promise<void>;
  isLoading?: boolean;
};

export const KnowledgeEntryDialog = ({
  open,
  onOpenChange,
  entry,
  onSubmit,
  isLoading = false,
}: KnowledgeEntryDialogProps) => {
  const { t, i18n } = useTranslation("agents");
  const [error, setError] = useState<string | null>(null);
  const isEditMode = Boolean(entry);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      content: "",
      sector: "semantic",
      tags: "",
    },
  });

  useEffect(() => {
    if (open) {
      if (entry) {
        form.reset({
          content: entry.content,
          sector: entry.primary_sector,
          tags: entry.tags.join(", "),
        });
      } else {
        form.reset({
          content: "",
          sector: "semantic",
          tags: "",
        });
      }
      setError(null);
    }
  }, [open, entry, form]);

  const handleSubmit = async (values: FormValues) => {
    setError(null);
    try {
      const tags = values.tags
        ? values.tags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean)
        : [];

      await onSubmit({
        content: values.content,
        sector: values.sector as MemorySector,
        tags,
      });

      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("error_saving_entry"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>
            {isEditMode ? t("edit_knowledge_entry") : t("add_knowledge_entry")}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? t("edit_knowledge_entry_desc")
              : t("add_knowledge_entry_desc")}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="content"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("content")}</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder={t("enter_knowledge_content")}
                      className="min-h-[150px] resize-y"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="sector"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("sector")}</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={t("select_sector")}>
                          {field.value && (
                            <KnowledgeSectorBadge
                              sector={field.value as MemorySector}
                              locale={i18n.language as "en" | "vi"}
                            />
                          )}
                        </SelectValue>
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {ALL_SECTORS.map((sector) => (
                        <SelectItem key={sector} value={sector}>
                          <KnowledgeSectorBadge
                            sector={sector}
                            locale={i18n.language as "en" | "vi"}
                          />
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="tags"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("tags_optional")}</FormLabel>
                  <FormControl>
                    <Input
                      placeholder={t("enter_tags_placeholder")}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {error && <p className="text-sm text-destructive">{error}</p>}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isLoading}
              >
                {t("cancel")}
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading
                  ? t("saving")
                  : isEditMode
                  ? t("save_changes")
                  : t("create")}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};
