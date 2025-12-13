"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RecordingTimer } from "@/components/RecordingTimer";

type ChatInputAreaProps = {
  isConnected: boolean;
  isRecording: boolean;
  onSendMessage: (message: string) => void;
  onToggleRecording: () => void;
};

export function ChatInputArea(props: ChatInputAreaProps) {
  const { t } = useTranslation("chat");
  const [messageInput, setMessageInput] = useState("");

  const handleSendMessage = () => {
    if (messageInput.trim() && props.isConnected) {
      props.onSendMessage(messageInput);
      setMessageInput("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex items-end gap-3">
      <textarea
        value={messageInput}
        onChange={(e) => setMessageInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          props.isConnected
            ? t("message_placeholder_connected")
            : t("message_placeholder_disconnected")
        }
        disabled={!props.isConnected || props.isRecording}
        rows={2}
        className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 min-h-[75px] max-h-40"
      />
      <div className="flex flex-col gap-2">
        <Button
          onClick={handleSendMessage}
          disabled={
            !props.isConnected || !messageInput.trim() || props.isRecording
          }
          size="sm"
          className="w-full"
        >
          <Send className="w-4 h-4" />
        </Button>
        <RecordingTimer
          isRecording={props.isRecording}
          isConnected={props.isConnected}
          onToggleRecording={props.onToggleRecording}
        />
      </div>
    </div>
  );
}
