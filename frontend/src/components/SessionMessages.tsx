"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { AgentMessage } from "@types";

const formatTime = (dateString: string) => {
  return new Date(dateString).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
};

interface SessionMessagesProps {
  agentId: string;
  sessionId: string;
  onLoadMore: (page: number) => void;
  hasMore: boolean;
  isLoading: boolean;
  messages: AgentMessage[];
}

export function SessionMessages({
  sessionId,
  onLoadMore,
  hasMore,
  isLoading,
  messages,
}: SessionMessagesProps) {
  const { t } = useTranslation("agents");
  const scrollViewportRef = useRef<HTMLDivElement>(null);
  const [messagePage, setMessagePage] = useState(1);
  const isLoadingMoreRef = useRef(false);

  // Reset page when session changes
  useEffect(() => {
    setMessagePage(1);
  }, [sessionId]);

  const previousMessagesLengthRef = useRef(messages.length);
  const scrollPositionRef = useRef<number | null>(null);

  // Scroll to bottom when messages first load
  useEffect(() => {
    if (messages.length > 0 && scrollViewportRef.current) {
      if (messagePage === 1) {
        // First page: scroll to bottom
        scrollViewportRef.current.scrollTop =
          scrollViewportRef.current.scrollHeight;
      } else if (previousMessagesLengthRef.current < messages.length) {
        // New messages loaded: restore scroll position
        if (scrollPositionRef.current !== null && scrollViewportRef.current) {
          const newScrollHeight = scrollViewportRef.current.scrollHeight;
          const scrollDiff = newScrollHeight - scrollPositionRef.current;
          scrollViewportRef.current.scrollTop = scrollDiff;
          scrollPositionRef.current = null;
        }
      }
      previousMessagesLengthRef.current = messages.length;
    }
  }, [messages.length, messagePage]);

  // Handle scroll to detect when reaching top
  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const target = e.currentTarget;
      const scrollTop = target.scrollTop;

      // Check if scrolled to top (within 50px threshold)
      if (
        scrollTop < 50 &&
        hasMore &&
        !isLoading &&
        !isLoadingMoreRef.current
      ) {
        isLoadingMoreRef.current = true;
        const nextPage = messagePage + 1;
        setMessagePage(nextPage);

        // Save current scroll height for position restoration
        scrollPositionRef.current = target.scrollHeight;

        // Load more messages
        onLoadMore(nextPage);

        // Reset loading flag after a delay
        setTimeout(() => {
          isLoadingMoreRef.current = false;
        }, 500);
      }
    },
    [hasMore, isLoading, messagePage, onLoadMore]
  );

  // Reverse messages to show newest at bottom (API returns desc, newest first)
  const reversedMessages = [...messages].reverse();

  return (
    <div className="h-full w-full overflow-hidden">
      <div
        ref={scrollViewportRef}
        className="h-full overflow-y-auto"
        onScroll={handleScroll}
      >
        <div className="flex flex-col space-y-4 p-6">
          {/* Loading indicator at top when loading more */}
          {isLoading && messagePage > 1 && (
            <div className="flex justify-center py-4">
              <Spinner className="h-5 w-5 text-muted-foreground" />
            </div>
          )}

          {/* Show message when no more to load - at top (oldest messages) */}
          {!hasMore && messages.length > 0 && (
            <div className="flex justify-center py-2">
              <div className="text-xs text-muted-foreground">
                {t("no_more_messages", "No more messages")}
              </div>
            </div>
          )}

          {/* Loading skeleton for initial load */}
          {isLoading && messagePage === 1 ? (
            <>
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex w-full",
                    i % 2 === 0 ? "justify-end" : "justify-start"
                  )}
                >
                  <Skeleton className="h-16 w-[60%] rounded-lg" />
                </div>
              ))}
            </>
          ) : (
            <>
              {reversedMessages.map((msg) => (
                <MessageItem key={msg.id} message={msg} />
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const MessageItem = ({ message }: { message: AgentMessage }) => {
  const isUser = message.chat_type === 1;

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-3 text-sm",
          isUser
            ? "bg-primary text-primary-foreground rounded-br-none"
            : "bg-muted text-foreground rounded-bl-none"
        )}
      >
        <div className="whitespace-pre-wrap break-words">{message.content}</div>
        <div
          className={cn(
            "text-[10px] mt-1 opacity-70",
            isUser ? "text-primary-foreground/80" : "text-muted-foreground"
          )}
        >
          {formatTime(message.created_at)}
        </div>
      </div>
    </div>
  );
};
