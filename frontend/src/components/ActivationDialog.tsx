"use client";

import { useEffect, useState } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import type { ActivationData } from "@/types/chat";

type ActivationDialogProps = {
  activation?: ActivationData | null;
  onDismiss: () => void;
};

export function ActivationDialog(props: ActivationDialogProps) {
  const { activation, onDismiss } = props;
  const [open, setOpen] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);

  useEffect(() => {
    if (activation) {
      setOpen(true);
      setTimeLeft(activation.timeout_ms / 1000); // Convert to seconds
    }
  }, [activation]);

  // Countdown timer
  useEffect(() => {
    if (!open || timeLeft <= 0) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        const newTime = prev - 1;
        if (newTime <= 0) {
          setOpen(false);
          onDismiss();
          return 0;
        }
        return newTime;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [open, timeLeft, onDismiss]);

  const handleDismiss = () => {
    setOpen(false);
    onDismiss();
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>🔐 Activation Code</AlertDialogTitle>
          <AlertDialogDescription>
            <div className="space-y-3">
              <p className="text-sm text-foreground">{activation?.message}</p>
              <div className="bg-primary/10 rounded-lg p-4 text-center">
                <p className="text-xs text-muted-foreground mb-2">Code</p>
                <p className="text-3xl font-bold text-primary tracking-widest">
                  {activation?.code}
                </p>
              </div>
              <p className="text-xs text-muted-foreground text-center">
                Expires in{" "}
                <span className="font-semibold text-foreground">
                  {Math.max(0, timeLeft)}s
                </span>
              </p>
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
