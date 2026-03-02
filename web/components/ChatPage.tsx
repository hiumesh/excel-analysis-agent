"use client";

import Image from "next/image";
import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/components/ChatMessage";
// NOTE: File upload commented out — datasource is now static from backend
// import { FileUpload } from "@/components/FileUpload";
import { ArtifactsPanel } from "@/components/ArtifactsPanel";
import { StreamingIndicator } from "@/components/StreamingIndicator";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  streamAnalysis,
  // type UploadResult,
  type Artifact,
  type StreamEvent,
} from "@/lib/api";
import {
  Send,
  /* Paperclip, */ X,
  Sparkles,
  BarChart3,
  Plus,
} from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  nodeName?: string;
  isReasoning?: boolean;
  reasoningSteps?: string[];
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [reasoningSteps, setReasoningSteps] = useState<string[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  // NOTE: Upload state commented out — datasource is static from backend
  // const [uploadedFile, setUploadedFile] = useState<UploadResult | null>(null);
  // const [showFileUpload, setShowFileUpload] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current;
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, isStreaming, currentNode]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  const handleSend = useCallback(async () => {
    const query = input.trim();
    if (!query || isStreaming) return;

    setInput("");
    setError(null);
    // setShowFileUpload(false);

    // Add user message (display the clean query to the user)
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

    // NOTE: File context in query commented out — datasource is static from backend
    // const backendQuery = uploadedFile
    //   ? `[Uploaded file: ${uploadedFile.filename}]\n${query}`
    //   : query;
    const backendQuery = query;

    let latestNode = "";
    const currentReasoningSteps: string[] = [];

    // NOTE: Reasoning steps are commented out — not displayed in the current UI
    // const addReasoningStep = (text: string) => {
    //   if (!currentReasoningSteps.includes(text)) {
    //     currentReasoningSteps.push(text);
    //     setReasoningSteps([...currentReasoningSteps]);
    //   }
    // };

    const onEvent = (event: StreamEvent) => {
      if (event.status === "completed") return;
      if (event.error) {
        setError(event.error);
        return;
      }

      // Capture thread_id from the first event
      if (event.thread_id) {
        setThreadId(event.thread_id);
      }

      if (event.node) {
        latestNode = event.node;
        setCurrentNode(event.node);
      }

      // NOTE: Reasoning step collection is commented out — not displayed in current UI
      // if (event.update?.route_decision?.reasoning) {
      //   addReasoningStep(event.update.route_decision.reasoning);
      // }

      // if (event.update?.supervisor_decision?.reasoning) {
      //   addReasoningStep(event.update.supervisor_decision.reasoning);
      // }

      // if (event.update?.analysis_plan) {
      //   addReasoningStep(`**Analysis Plan:**\n${event.update.analysis_plan}`);
      // }

      // Process messages from the event
      if (event.update?.messages) {
        // Collect subgraph/coding agent internal reasoning
        // NOTE: Subgraph reasoning extraction is commented out — not displayed in current UI
        if (event.is_subgraph && latestNode === "coding_agent") {
          // for (const msg of event.update.messages) {
          //   if (msg.type === "AIMessage" && msg.content) {
          //     const thinkingMatch = msg.content.match(
          //       /Thinking:\s*([\s\S]*?)(?=\n\n|$)/i,
          //     );
          //     if (thinkingMatch && thinkingMatch[1].trim()) {
          //       const thought = thinkingMatch[1].trim();
          //       addReasoningStep(thought);
          //     }
          //   }
          //   if (msg.tool_calls) {
          //     for (const tc of msg.tool_calls) {
          //       const args = tc.args || {};
          //       const reasoning = args.reasoning || args.reflection;
          //       if (reasoning && typeof reasoning === "string") {
          //         const text = reasoning.trim();
          //         addReasoningStep(text);
          //       }
          //     }
          //   }
          // }
        }

        // Only show messages if they come from end-user facing nodes (not internal reasoning)
        if (
          ["chat", "followup_answer"].includes(latestNode) &&
          !event.is_subgraph
        ) {
          for (const msg of event.update.messages) {
            if (msg.content && msg.type !== "HumanMessage") {
              // Add as a new assistant message with node label
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

      // Collect final analysis
      if (event.update?.final_analysis && !event.is_subgraph) {
        const finalMsg: Message = {
          id: `final-${Date.now()}`,
          role: "assistant",
          content: event.update.final_analysis as string,
          nodeName: "finalizer",
          reasoningSteps: [...currentReasoningSteps],
        };
        // Check if we already have this exact message to be extra safe
        setMessages((prev) => {
          if (prev.some((m) => m.content === finalMsg.content)) return prev;
          return [...prev, finalMsg];
        });
      }

      // Collect artifacts
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
      null, // file_path — datasource is static from backend
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
    // setUploadedFile(null);
    // setShowFileUpload(false);
    setInput("");
    setCurrentNode(null);
    setReasoningSteps([]);
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto max-w-4xl flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center">
              <Image
                src="/isb_identity_colour_rgb_positive.svg"
                alt="ISB Logo"
                width={80}
                height={40}
              />
            </div>
            {/* <div>
              <h1 className="text-base font-semibold text-foreground tracking-tight">
                Excel Analysis Agent
              </h1>
              <p className="text-[11px] text-muted-foreground leading-none">
                Upload a spreadsheet and ask questions
              </p>
            </div> */}
          </div>
          <div className="flex items-center gap-2">
            {/* NOTE: Upload file badge commented out — datasource is static from backend */}
            {/* {uploadedFile && (
              <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="truncate max-w-[150px]">
                  {uploadedFile.filename}
                </span>
              </div>
            )} */}
            {!isEmpty && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleNewChat}
                disabled={isStreaming}
                className="gap-1.5 rounded-xl text-xs h-8 border-border/50 hover:bg-muted/50"
              >
                <Plus className="h-3.5 w-3.5" />
                New Chat
              </Button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Chat area */}
      <div className="flex-1 overflow-hidden">
        <div ref={scrollRef} className="h-full overflow-y-auto scroll-smooth">
          <div className="mx-auto max-w-4xl">
            {isEmpty ? (
              /* Empty state */
              <div className="flex flex-col items-center justify-center h-[calc(100vh-180px)] px-6">
                <div className="flex flex-col items-center gap-6 max-w-md text-center">
                  <div className="relative">
                    <div className="flex items-center justify-center h-20 w-20 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 border border-primary/10">
                      <Sparkles className="h-10 w-10 text-primary/70" />
                    </div>
                    <div className="absolute -inset-4 rounded-3xl bg-primary/5 blur-2xl -z-10" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-foreground mb-2">
                      Report IQ
                    </h2>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      Ask questions about your data. I&apos;ll generate
                      insights, charts, and statistical analysis.
                    </p>
                  </div>

                  {/* NOTE: File upload UI commented out — datasource is static from backend */}
                  <div className="flex flex-wrap gap-2 justify-center mt-2">
                    {[
                      "Summarize this data",
                      "Show key statistics",
                      "Find trends and patterns",
                    ].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => {
                          setInput(suggestion);
                          inputRef.current?.focus();
                        }}
                        className="text-xs px-3 py-1.5 rounded-full border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-all duration-200"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* Message list */
              <div className="py-6">
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
                  <div className="px-4 py-2">
                    <div className="rounded-xl bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
                      {error}
                    </div>
                  </div>
                )}

                {/* Artifacts panel */}
                {!isStreaming && artifacts.length > 0 && (
                  <ArtifactsPanel artifacts={artifacts} />
                )}

                {/* Bottom spacer */}
                <div className="h-4" />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* NOTE: File upload dropdown commented out — datasource is static from backend */}
      {/* {showFileUpload && !isEmpty && (
        <div className="mx-auto max-w-4xl w-full px-6">
          <div className="mb-2 animate-in fade-in slide-in-from-bottom-2 duration-200">
            <FileUpload
              onFileUploaded={(result) => {
                setUploadedFile(result);
                setShowFileUpload(false);
              }}
              onFileRemoved={() => setUploadedFile(null)}
              uploadedFile={uploadedFile}
              disabled={isStreaming}
            />
          </div>
        </div>
      )} */}

      {/* Input area */}
      <div className="sticky bottom-0 border-t border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto max-w-4xl px-6 py-3">
          {/* NOTE: Uploaded file chip commented out — datasource is static from backend */}
          {/* {uploadedFile && !isEmpty && (
            <div className="mb-2">
              <FileUpload
                onFileUploaded={setUploadedFile}
                onFileRemoved={() => setUploadedFile(null)}
                uploadedFile={uploadedFile}
                disabled={isStreaming}
              />
            </div>
          )} */}

          <div className="flex items-end gap-2">
            {/* NOTE: Attach button commented out — datasource is static from backend */}
            {/* <Button
              variant="ghost"
              size="icon"
              className="shrink-0 h-10 w-10 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/50"
              onClick={() => setShowFileUpload(!showFileUpload)}
              disabled={isStreaming}
            >
              <Paperclip className="h-5 w-5" />
            </Button> */}

            {/* Text input */}
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your data..."
                rows={1}
                className="w-full resize-none overflow-hidden rounded-xl border border-border/50 bg-muted/30 px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/30 transition-all duration-200"
                disabled={isStreaming}
              />
            </div>

            {/* Send / Stop button */}
            {isStreaming ? (
              <Button
                variant="destructive"
                size="icon"
                className="shrink-0 h-10 w-10 rounded-xl"
                onClick={handleStop}
              >
                <X className="h-5 w-5" />
              </Button>
            ) : (
              <Button
                size="icon"
                className="shrink-0 h-10 w-10 rounded-xl bg-primary hover:bg-primary/90 transition-colors"
                onClick={handleSend}
                disabled={!input.trim()}
              >
                <Send className="h-5 w-5" />
              </Button>
            )}
          </div>

          <p className="text-[10px] text-muted-foreground/50 text-center mt-2">
            AI-powered analysis may contain errors. Verify important results.
          </p>
        </div>
      </div>
    </div>
  );
}
