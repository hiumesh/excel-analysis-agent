"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/components/ChatMessage";
import { ArtifactsPanel } from "@/components/ArtifactsPanel";
import { StreamingIndicator } from "@/components/StreamingIndicator";
import { FileUpload } from "@/components/FileUpload";
import { streamAnalysis, uploadDefaultFile, type UploadResult, type Artifact, type StreamEvent } from "@/lib/api";
import { MessageCircle, Send, X, Sparkles, Plus, Minus, Settings, CheckCircle2 } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  nodeName?: string;
  isReasoning?: boolean;
  reasoningSteps?: string[];
}

/* ------------------------------------------------------------------ */
/*  ChatbotWidget                                                      */
/* ------------------------------------------------------------------ */
export function ChatbotWidget() {
  /* ---- modal open / close ---- */
  const [isOpen, setIsOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadResult | null>(null);

  /* ---- chat state (mirrors ChatPage) ---- */
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

  /* focus input when modal opens */
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen]);

  /* ---- handlers ---- */
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

      /* artifacts */
      if (event.update?.artifacts && Array.isArray(event.update.artifacts)) {
        setArtifacts((prev) => [
          ...prev,
          ...(event.update!.artifacts as Artifact[]),
        ]);
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

  const handleNewChat = () => {
    setMessages([]);
    setArtifacts([]);
    setError(null);
    setThreadId(null);
    setInput("");
    setCurrentNode(null);
    setReasoningSteps([]);
  };

  const isEmpty = messages.length === 0;

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */
  return (
    <>
      {/* ==================== FLOATING ACTION BUTTON ==================== */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        aria-label={isOpen ? "Close chat" : "Open chat"}
        className="chatbot-fab"
        style={{ pointerEvents: "auto" }}
      >
        <span
          className={`chatbot-fab-icon ${isOpen ? "chatbot-fab-icon--hidden" : ""}`}
        >
          <MessageCircle className="h-6 w-6" />
        </span>
        <span
          className={`chatbot-fab-icon ${!isOpen ? "chatbot-fab-icon--hidden" : ""}`}
        >
          <Minus className="h-6 w-6" />
        </span>
      </button>

      {/* ==================== MODAL OVERLAY ==================== */}
      {isOpen && (
        <div
          className="chatbot-modal-wrapper"
          style={{ pointerEvents: "auto" }}
        >
          {/* backdrop — click to close */}
          <div className="chatbot-backdrop" onClick={() => setIsOpen(false)} />

          {/* modal container */}
          <div className="chatbot-modal">
            {/* ---- header ---- */}
            <div className="chatbot-modal-header">
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/10">
                  <Sparkles className="h-4 w-4 text-primary/80" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-foreground leading-none">
                    Report IQ
                  </h2>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    AI-powered data analysis
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {!isEmpty && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleNewChat}
                    disabled={isStreaming}
                    className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                    title="New Chat"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowSettings(!showSettings)}
                  disabled={isStreaming}
                  className={`h-7 w-7 rounded-lg ${showSettings ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                  title="Settings"
                >
                  <Settings className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsOpen(false)}
                  className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* ---- settings area ---- */}
            {showSettings && (
              <div className="border-b border-border/40 bg-muted/10 p-4 relative">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-xs font-medium text-foreground">Global Default Dataset</h3>
                </div>
                {uploadedFile ? (
                   <div className="flex flex-col items-center justify-center p-4 bg-muted/20 rounded-lg border border-border/50 text-center animate-in fade-in duration-300">
                     <CheckCircle2 className="h-6 w-6 text-emerald-500 mb-2" />
                     <p className="text-[11px] text-muted-foreground mb-3">
                       <strong className="text-foreground">{uploadedFile.filename}</strong> is now the default dataset.
                     </p>
                     <Button 
                       variant="outline"
                       size="sm"
                       className="h-7 text-[10px]"
                       onClick={() => setUploadedFile(null)}
                     >
                       Upload Another
                     </Button>
                   </div>
                ) : (
                  <FileUpload
                    onFileUploaded={(result) => setUploadedFile(result)}
                    onFileRemoved={() => setUploadedFile(null)}
                    uploadedFile={uploadedFile}
                    uploadAction={uploadDefaultFile}
                    disabled={isStreaming}
                    className="p-4"
                  />
                )}
              </div>
            )}

            {/* ---- chat area ---- */}
            <div className="chatbot-modal-body" ref={scrollRef}>
              {isEmpty ? (
                /* empty state */
                <div className="flex flex-col items-center justify-center h-full px-4">
                  <div className="flex flex-col items-center gap-4 max-w-[260px] text-center">
                    <div className="relative">
                      <div className="flex items-center justify-center h-14 w-14 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 border border-primary/10">
                        <Sparkles className="h-7 w-7 text-primary/70" />
                      </div>
                      <div className="absolute -inset-3 rounded-3xl bg-primary/5 blur-xl -z-10" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-foreground mb-1">
                        Report IQ
                      </h3>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Ask questions about your data. I&apos;ll generate
                        insights, charts, and analysis.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1.5 justify-center mt-1">
                      {[
                        "Summarize this data",
                        "Show key statistics",
                        "Find trends",
                      ].map((suggestion) => (
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
                /* message list */
                <div className="py-3">
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
                    <StreamingIndicator
                      currentNode={currentNode}
                      reasoningSteps={reasoningSteps}
                    />
                  )}

                  {error && (
                    <div className="px-3 py-2">
                      <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-xs text-destructive">
                        {error}
                      </div>
                    </div>
                  )}

                  {!isStreaming && artifacts.length > 0 && (
                    <ArtifactsPanel artifacts={artifacts} />
                  )}

                  <div className="h-2" />
                </div>
              )}
            </div>

            {/* ---- input area ---- */}
            <div className="chatbot-modal-footer">
              <div className="flex items-end gap-1.5">
                <div className="flex-1 relative flex">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about your data..."
                    rows={1}
                    className="block w-full resize-none overflow-hidden rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/30 transition-all duration-200 md:min-h-[38px]"
                    disabled={isStreaming}
                  />
                </div>

                {isStreaming ? (
                  <Button
                    variant="destructive"
                    size="icon"
                    className="shrink-0 h-[38px] w-[38px] rounded-lg"
                    onClick={handleStop}
                  >
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
              <p className="text-[9px] text-muted-foreground/40 text-center mt-1.5">
                AI-powered analysis may contain errors.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
