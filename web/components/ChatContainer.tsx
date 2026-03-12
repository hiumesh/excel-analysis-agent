"use client";

import { useState, useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/components/ChatMessage";
import { ArtifactsPanel } from "@/components/ArtifactsPanel";
import { StreamingIndicator } from "@/components/StreamingIndicator";
import { streamAnalysis, type Artifact, type StreamEvent } from "@/lib/api";
import { Send, X, Sparkles, Plus } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  nodeName?: string;
  isReasoning?: boolean;
  reasoningSteps?: string[];
}

interface ChatContainerProps {
  className?: string;
  showNewChat?: boolean;
  onNewChat?: () => void;
  onStatusChange?: (status: { isStreaming: boolean; isEmpty: boolean }) => void;
}

export interface ChatContainerHandle {
  newChat: () => void;
}

export const ChatContainer = forwardRef<ChatContainerHandle, ChatContainerProps>(
  ({ className = "", showNewChat = true, onNewChat, onStatusChange }, ref) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const [currentNode, setCurrentNode] = useState<string | null>(null);
    const [reasoningSteps, setReasoningSteps] = useState<string[]>([]);
    const [artifacts, setArtifacts] = useState<Artifact[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [threadId, setThreadId] = useState<string | null>(null);

    const scrollRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const abortRef = useRef<AbortController | null>(null);

    const isEmpty = messages.length === 0;

    // Notify parent of status changes
    useEffect(() => {
      if (onStatusChange) {
        onStatusChange({ isStreaming, isEmpty });
      }
    }, [isStreaming, isEmpty, onStatusChange]);

    /* auto-scroll */
    useEffect(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }, [messages, isStreaming, currentNode]);

    /* auto-resize textarea */
    useEffect(() => {
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
        inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
      }
    }, [input]);

    const handleSend = useCallback(async () => {
      const query = input.trim();
      if (!query || isStreaming) return;

      setInput("");
      setError(null);

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: query,
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsStreaming(true);
      setCurrentNode(null);
      setReasoningSteps([]);
      setArtifacts([]);

      const backendQuery = query;
      let latestNode = "";
      const currentReasoningSteps: string[] = [];

      const onEvent = (event: StreamEvent) => {
        if (event.status === "completed") return;
        if (event.error) {
          setError(event.error);
          return;
        }

        if (event.thread_id) setThreadId(event.thread_id);
        if (event.node) {
          latestNode = event.node;
          setCurrentNode(event.node);
        }

        /* messages from user-facing nodes */
        if (event.update?.messages) {
          if (
            ["chat", "followup_answer"].includes(latestNode) &&
            !event.is_subgraph
          ) {
            for (const msg of event.update.messages) {
              if (msg.content && msg.type !== "HumanMessage") {
                const assistantMsg: Message = {
                  id: `assistant-${Date.now()}-${Math.random()}`,
                  role: "assistant",
                  content: msg.content,
                  nodeName: latestNode,
                };
                setMessages((prev) => [...prev, assistantMsg]);
              }
            }
          }
        }

        /* final analysis */
        if (event.update?.final_analysis && !event.is_subgraph) {
          const finalMsg: Message = {
            id: `final-${Date.now()}`,
            role: "assistant",
            content: event.update.final_analysis as string,
            nodeName: "finalizer",
            reasoningSteps: [...currentReasoningSteps],
          };
          setMessages((prev) => {
            if (prev.some((m) => m.content === finalMsg.content)) return prev;
            return [...prev, finalMsg];
          });
        }

        /* artifacts - With Deduplication */
        if (event.update?.artifacts && Array.isArray(event.update.artifacts)) {
          const incoming = event.update.artifacts as Artifact[];
          setArtifacts((prev) => {
            const combined = [...prev, ...incoming];
            const uniqueMap = new Map<string, Artifact>();
            combined.forEach((a) => {
              const key = a.url || a.content;
              if (key) uniqueMap.set(key, a);
            });
            return Array.from(uniqueMap.values());
          });
        }
      };

      const onDone = () => {
        setIsStreaming(false);
        setCurrentNode(null);
        setReasoningSteps([]);
      };

      const onError = (errMsg: string) => {
        setError(errMsg);
        setIsStreaming(false);
        setCurrentNode(null);
        setReasoningSteps([]);
      };

      abortRef.current = await streamAnalysis(
        backendQuery,
        null,
        threadId,
        onEvent,
        onDone,
        onError,
      );
    }, [input, isStreaming, threadId]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    };

    const handleStop = () => {
      abortRef.current?.abort();
      setIsStreaming(false);
      setCurrentNode(null);
      setReasoningSteps([]);
    };

    const handleNewChatInternal = useCallback(() => {
      setMessages([]);
      setArtifacts([]);
      setError(null);
      setThreadId(null);
      setInput("");
      setCurrentNode(null);
      setReasoningSteps([]);
      if (onNewChat) onNewChat();
    }, [onNewChat]);

    useImperativeHandle(ref, () => ({
      newChat: handleNewChatInternal,
    }));

    return (
      <div className={`flex flex-col h-full overflow-hidden ${className}`}>
        {/* Chat area */}
        <div className="flex-1 overflow-y-auto p-4 scroll-smooth" ref={scrollRef}>
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center h-full px-4">
              <div className="flex flex-col items-center gap-4 max-w-[280px] text-center">
                <div className="relative">
                  <div className="flex items-center justify-center h-14 w-14 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 border border-primary/10">
                    <Sparkles className="h-7 w-7 text-primary/70" />
                  </div>
                  <div className="absolute -inset-3 rounded-3xl bg-primary/5 blur-xl -z-10" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">Report IQ</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Ask questions about your data. I&apos;ll generate insights, charts, and analysis.
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5 justify-center mt-1">
                  {["Summarize this data", "Show key statistics", "Find trends"].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => {
                        setInput(suggestion);
                        inputRef.current?.focus();
                      }}
                      className="text-[11px] px-2.5 py-1 rounded-full border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-all duration-200"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="py-2 space-y-4">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  nodeName={msg.nodeName}
                  isReasoning={msg.isReasoning}
                  reasoningSteps={msg.reasoningSteps}
                />
              ))}

              {isStreaming && (
                <StreamingIndicator currentNode={currentNode} reasoningSteps={reasoningSteps} />
              )}

              {error && (
                <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-xs text-destructive">
                  {error}
                </div>
              )}

              {!isStreaming && artifacts.length > 0 && <ArtifactsPanel artifacts={artifacts} />}
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="p-4 border-t border-border/40 bg-background/50 backdrop-blur-sm">
          <div className="flex items-end gap-2 max-w-4xl mx-auto">
            {showNewChat && !isEmpty && (
              <Button
                variant="outline"
                size="icon"
                onClick={handleNewChatInternal}
                disabled={isStreaming}
                className="shrink-0 h-[38px] w-[38px] rounded-lg border-border/50"
                title="New Chat"
              >
                <Plus className="h-4 w-4" />
              </Button>
            )}

            <div className="flex-1 relative flex">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your data..."
                rows={1}
                className="block w-full resize-none overflow-hidden rounded-lg border border-border/50 bg-muted/20 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/30 transition-all duration-200 min-h-[38px]"
                disabled={isStreaming}
              />
            </div>

            {isStreaming ? (
              <Button variant="destructive" size="icon" className="shrink-0 h-[38px] w-[38px] rounded-lg" onClick={handleStop}>
                <X className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                className="shrink-0 h-[38px] w-[38px] rounded-lg bg-primary hover:bg-primary/90 transition-colors"
                onClick={handleSend}
                disabled={!input.trim()}
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
          <p className="text-[9px] text-muted-foreground/40 text-center mt-2">
            AI-powered analysis may contain errors.
          </p>
        </div>
      </div>
    );
  }
);

ChatContainer.displayName = "ChatContainer";
