"use client";

import { useTranslation } from "react-i18next";
import type { ReactNode } from "react";
import Markdown from "react-markdown";
import type { ChatMessage } from "@/types/chat";

type ChatMessagesProps = {
  messages: ChatMessage[];
  isConnected: boolean;
};

const markdownComponents = {
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-2 last:mb-0">{children}</p>
  ),
  code: ({ children }: { children?: ReactNode }) => (
    <code className="px-1 py-0.5 rounded text-xs font-mono bg-black/20">
      {children}
    </code>
  ),
  pre: ({ children }: { children?: ReactNode }) => (
    <pre className="p-2 rounded-md bg-black/30 overflow-auto mb-2">
      {children}
    </pre>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="text-sm">{children}</li>
  ),
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="font-bold">{children}</strong>
  ),
  em: ({ children }: { children?: ReactNode }) => (
    <em className="italic">{children}</em>
  ),
  a: ({ children, href }: { children?: ReactNode; href?: string }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline hover:opacity-80"
    >
      {children}
    </a>
  ),
} as const;

export function ChatMessages(props: ChatMessagesProps) {
  const { t } = useTranslation("chat");
  const { messages, isConnected } = props;

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center text-muted-foreground h-full">
        <div className="text-center">
          <p className="text-lg font-medium mb-2">{t("no_messages")}</p>
          <p className="text-sm">
            {isConnected
              ? t("start_conversation")
              : t("connect_to_server_first")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {(() => {
        console.log(
          `[UI] Rendering ${messages.length} messages:`,
          messages.map((m) => `${m.type}:"${m.text.substring(0, 30)}"`)
        );
        return messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${
              msg.type === "user" || msg.type === "stt"
                ? "justify-end"
                : "justify-start"
            }`}
          >
            <div
              className={`max-w-xs rounded-lg px-4 py-2 ${
                msg.type === "user" || msg.type === "stt"
                  ? "bg-blue-500 text-white"
                  : msg.type === "tts"
                  ? "bg-purple-200 text-purple-900 italic"
                  : "bg-gray-200 text-gray-900"
              }`}
            >
              {(msg.type === "stt" || msg.type === "tts") && (
                <span className="opacity-75 text-xs block mb-1">
                  {msg.type === "stt" && "🎤 Recognized:"}
                  {msg.type === "tts" && "🔊 Playing:"}
                </span>
              )}
              <div className="text-sm break-words prose prose-sm max-w-none dark:prose-invert">
                <Markdown components={markdownComponents}>{msg.text}</Markdown>
              </div>
            </div>
          </div>
        ));
      })()}
    </div>
  );
}
