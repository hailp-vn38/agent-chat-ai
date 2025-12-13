import { useState, useEffect, useMemo, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowLeft,
  MessageSquare,
  Trash2,
  Clock,
  MoreVertical,
} from "lucide-react";

import {
  useChatSessions,
  useSessionMessages,
  useDeleteAgentMessages,
} from "@/queries/agent-queries";
import { PageHead } from "@/components/PageHead";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionMessages } from "@/components/SessionMessages";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from "@/components/ui/pagination";
import { cn } from "@/lib/utils";
import type { AgentMessage } from "@types";

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatTime = (dateString: string) => {
  return new Date(dateString).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const DEFAULT_PAGE_SIZE = 10;

export const AgentHistoryPage = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useTranslation("agents");

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null
  );
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [messagePage, setMessagePage] = useState(1);
  const [accumulatedMessages, setAccumulatedMessages] = useState<
    AgentMessage[]
  >([]);

  // Get page from URL params
  const page = useMemo(() => {
    const p = searchParams.get("page");
    return p ? parseInt(p, 10) : 1;
  }, [searchParams]);

  // Queries
  const {
    data: sessionsData,
    isLoading: isLoadingSessions,
    refetch: refetchSessions,
  } = useChatSessions(agentId || "", {
    page,
    page_size: DEFAULT_PAGE_SIZE,
  });

  const totalPages = sessionsData?.total_pages || 1;
  const hasPrevious = page > 1;
  const hasNext = page < totalPages;

  const { data: messagesData, isLoading: isLoadingMessages } =
    useSessionMessages(
      agentId || "",
      selectedSessionId || "",
      { page: messagePage, page_size: 20 },
      !!selectedSessionId
    );

  // Reset accumulated messages when session changes
  useEffect(() => {
    if (selectedSessionId) {
      setMessagePage(1);
      setAccumulatedMessages([]);
    }
  }, [selectedSessionId]);

  // Accumulate messages when new data arrives
  // API returns desc (newest first), so we append older messages to the end
  useEffect(() => {
    if (messagesData?.data) {
      if (messagePage === 1) {
        // First page: replace all messages (newest messages)
        setAccumulatedMessages(messagesData.data);
      } else {
        // Subsequent pages: append older messages to the end (maintains desc order)
        setAccumulatedMessages((prev) => [...prev, ...messagesData.data]);
      }
    }
  }, [messagesData?.data, messagePage]);

  const hasMoreMessages =
    messagesData?.total_pages && messagePage < messagesData.total_pages;

  const handleLoadMore = useCallback((page: number) => {
    setMessagePage(page);
  }, []);

  const { mutateAsync: deleteMessages } = useDeleteAgentMessages(agentId || "");

  // Select first session by default if available and none selected
  useEffect(() => {
    if (
      !selectedSessionId &&
      sessionsData?.data &&
      sessionsData.data.length > 0
    ) {
      setSelectedSessionId(sessionsData.data[0].session_id);
    }
  }, [sessionsData, selectedSessionId]);

  // Pagination handlers
  const handlePreviousPage = useCallback(() => {
    if (page > 1) {
      setSelectedSessionId(null);
      setSearchParams({ page: String(page - 1) });
    }
  }, [page, setSearchParams]);

  const handleNextPage = useCallback(() => {
    if (page < totalPages) {
      setSelectedSessionId(null);
      setSearchParams({ page: String(page + 1) });
    }
  }, [page, totalPages, setSearchParams]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      setSelectedSessionId(null);
      setSearchParams({ page: String(newPage) });
    },
    [setSearchParams]
  );

  const handleDeleteSession = (sessionId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setSessionToDelete(sessionId);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!agentId || !sessionToDelete) return;

    try {
      await deleteMessages(sessionToDelete);

      // If we deleted the currently selected session, clear selection
      if (selectedSessionId === sessionToDelete) {
        setSelectedSessionId(null);
      }

      setDeleteConfirmOpen(false);
      setSessionToDelete(null);
      refetchSessions();
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  const handleDeleteAll = () => {
    setSessionToDelete("ALL");
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDeleteAll = async () => {
    if (!agentId) return;

    try {
      await deleteMessages(undefined); // undefined means delete all
      setSelectedSessionId(null);
      setDeleteConfirmOpen(false);
      setSessionToDelete(null);
      refetchSessions();
    } catch (error) {
      console.error("Failed to delete all messages:", error);
    }
  };

  if (!agentId) return null;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <PageHead
        title={t("history_title", "Chat History")}
        description={t("history_description", "View and manage chat history")}
      />

      <div className="flex-1 flex overflow-hidden border-t min-h-0">
        {/* Sidebar - Session List */}
        <div className="w-80 border-r flex flex-col bg-muted/10 overflow-hidden">
          <div className="p-4 border-b space-y-4">
            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                size="sm"
                className="gap-2 -ml-2"
                onClick={() => navigate(`/agents/${agentId}`)}
              >
                <ArrowLeft className="h-4 w-4" />
                {t("back_to_agent", "Back")}
              </Button>

              {sessionsData?.data && sessionsData.data.length > 0 && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={handleDeleteAll}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      {t("delete_all_history", "Delete All History")}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>

          <ScrollArea className="flex-1 min-h-0">
            {isLoadingSessions ? (
              <div className="p-4 space-y-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ))}
              </div>
            ) : sessionsData?.data?.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">
                  {t("no_history", "No chat history found")}
                </p>
              </div>
            ) : (
              <div className="flex flex-col">
                {sessionsData?.data.map((session) => (
                  <button
                    key={session.session_id}
                    onClick={() => setSelectedSessionId(session.session_id)}
                    className={cn(
                      "flex flex-col items-start gap-1 p-4 text-left transition-colors hover:bg-muted/50 border-b last:border-0",
                      selectedSessionId === session.session_id &&
                        "bg-muted border-l-4 border-l-primary pl-[13px]"
                    )}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="font-medium text-sm truncate">
                        {formatDate(session.first_message_at)}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) =>
                          handleDeleteSession(session.session_id, e)
                        }
                      >
                        <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                      </Button>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <MessageSquare className="h-3 w-3" />
                        {session.message_count}
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatTime(session.last_message_at)}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </ScrollArea>

          {/* Pagination */}
          {!isLoadingSessions && totalPages > 1 && (
            <div className="p-4 border-t flex-shrink-0">
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        handlePreviousPage();
                      }}
                      className={
                        !hasPrevious
                          ? "pointer-events-none opacity-50"
                          : "cursor-pointer"
                      }
                    />
                  </PaginationItem>

                  {/* First page */}
                  {page > 2 && (
                    <PaginationItem>
                      <PaginationLink
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          handlePageChange(1);
                        }}
                      >
                        1
                      </PaginationLink>
                    </PaginationItem>
                  )}

                  {/* Ellipsis before current */}
                  {page > 3 && (
                    <PaginationItem>
                      <PaginationEllipsis />
                    </PaginationItem>
                  )}

                  {/* Previous page */}
                  {page > 1 && (
                    <PaginationItem>
                      <PaginationLink
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          handlePageChange(page - 1);
                        }}
                      >
                        {page - 1}
                      </PaginationLink>
                    </PaginationItem>
                  )}

                  {/* Current page */}
                  <PaginationItem>
                    <PaginationLink href="#" isActive>
                      {page}
                    </PaginationLink>
                  </PaginationItem>

                  {/* Next page */}
                  {page < totalPages && (
                    <PaginationItem>
                      <PaginationLink
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          handlePageChange(page + 1);
                        }}
                      >
                        {page + 1}
                      </PaginationLink>
                    </PaginationItem>
                  )}

                  {/* Ellipsis after current */}
                  {page < totalPages - 2 && (
                    <PaginationItem>
                      <PaginationEllipsis />
                    </PaginationItem>
                  )}

                  {/* Last page */}
                  {page < totalPages - 1 && (
                    <PaginationItem>
                      <PaginationLink
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          handlePageChange(totalPages);
                        }}
                      >
                        {totalPages}
                      </PaginationLink>
                    </PaginationItem>
                  )}

                  <PaginationItem>
                    <PaginationNext
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        handleNextPage();
                      }}
                      className={
                        !hasNext
                          ? "pointer-events-none opacity-50"
                          : "cursor-pointer"
                      }
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </div>

        {/* Main Content - Messages */}
        <div className="flex-1 flex flex-col bg-background overflow-hidden">
          {selectedSessionId ? (
            <>
              <div className="h-14 border-b flex items-center justify-between px-6 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">
                    {t("session_detail", "Session Detail")}
                  </h2>
                  <Badge variant="outline" className="font-normal">
                    {selectedSessionId.slice(0, 8)}...
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                  onClick={() => handleDeleteSession(selectedSessionId)}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  {t("delete_session", "Delete Session")}
                </Button>
              </div>

              <div className="flex-1 overflow-hidden">
                <SessionMessages
                  agentId={agentId || ""}
                  sessionId={selectedSessionId || ""}
                  onLoadMore={handleLoadMore}
                  hasMore={hasMoreMessages || false}
                  isLoading={isLoadingMessages}
                  messages={accumulatedMessages}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-20" />
                <p>
                  {t("select_session", "Select a session to view messages")}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {sessionToDelete === "ALL"
                ? t("delete_all_confirm_title", "Delete all history?")
                : t("delete_session_confirm_title", "Delete this session?")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {sessionToDelete === "ALL"
                ? t(
                    "delete_all_confirm_desc",
                    "This action cannot be undone. All chat history for this agent will be permanently deleted."
                  )
                : t(
                    "delete_session_confirm_desc",
                    "This action cannot be undone. This chat session will be permanently deleted."
                  )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex justify-end gap-2">
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={
                sessionToDelete === "ALL"
                  ? handleConfirmDeleteAll
                  : handleConfirmDelete
              }
              className="bg-destructive hover:bg-destructive/90"
            >
              {t("delete")}
            </AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
