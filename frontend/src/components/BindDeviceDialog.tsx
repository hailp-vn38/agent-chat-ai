import { memo, useState } from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

/**
 * Bind Device Form Schema
 */
const BindDeviceSchema = z.object({
  code: z
    .string()
    .min(1, "Device code is required")
    .min(6, "Device code must be at least 6 characters")
    .max(50, "Device code must not exceed 50 characters"),
});

type BindDeviceFormValues = z.infer<typeof BindDeviceSchema>;

export type { BindDeviceFormValues };

export interface BindDeviceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: BindDeviceFormValues) => Promise<void>;
  isLoading?: boolean;
}

const BindDeviceDialogComponent = ({
  open,
  onOpenChange,
  onSubmit,
  isLoading = false,
}: BindDeviceDialogProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { t } = useTranslation("agents");

  const form = useForm<BindDeviceFormValues>({
    resolver: zodResolver(BindDeviceSchema),
    defaultValues: {
      code: "",
    },
  });

  const handleSubmit = async (data: BindDeviceFormValues) => {
    setIsSubmitting(true);
    try {
      await onSubmit(data);
      form.reset();
      onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDisabled = isSubmitting || isLoading;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("add_device_title")}</DialogTitle>
          <DialogDescription>{t("add_device_desc")}</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
          >
            {/* Device Code Field */}
            <FormField
              control={form.control}
              name="code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("device_code")}</FormLabel>
                  <FormControl>
                    <Input
                      placeholder={t("enter_device_code")}
                      disabled={isDisabled}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isDisabled}
              >
                {t("cancel")}
              </Button>
              <Button type="submit" disabled={isDisabled}>
                {isDisabled && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {t("bind_device_btn")}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export const BindDeviceDialog = memo(BindDeviceDialogComponent);
