"use client";

import { useState, useEffect } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import type { ChatServiceError } from "@/types/chat";

type ChatErrorAlertProps = {
  error?: ChatServiceError | null;
  onDismiss: () => void;
};

export function ChatErrorAlert(props: ChatErrorAlertProps) {
  const { error, onDismiss } = props;
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (error) {
      setOpen(true);
    }
  }, [error]);

  const handleDismiss = () => {
    setOpen(false);
    onDismiss();
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Error</AlertDialogTitle>
          <AlertDialogDescription>
            <div>
              <p className="font-medium text-foreground">{error?.message}</p>
              {error?.code && (
                <p className="text-xs mt-2 opacity-75">Code: {error.code}</p>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogAction onClick={handleDismiss}>Dismiss</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
