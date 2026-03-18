"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { User, Bot, Lightbulb, ChevronRight, ChevronDown } from "lucide-react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  nodeName?: string;
  isReasoning?: boolean;
  reasoningSteps?: string[];
  className?: string;
}

export function ChatMessage({
  role,
  content,
  nodeName,
  isReasoning,
  reasoningSteps,
  className,
}: ChatMessageProps) {
  const [showReasoning, setShowReasoning] = useState(false);
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "chat-message flex gap-3 px-4 py-3",
        isUser ? "flex-row-reverse" : "flex-row",
        className,
      )}
    >
      <Avatar
        className={cn(
          "h-8 w-8 shrink-0 border",
          isUser
            ? "bg-primary/10 border-primary/20"
            : isReasoning
              ? "bg-amber-500/10 border-amber-500/20"
              : "bg-muted border-border/50",
        )}
      >
        <AvatarFallback
          className={cn(
            "text-xs",
            isUser
              ? "bg-primary/10 text-primary"
              : isReasoning
                ? "bg-amber-500/10 text-amber-500"
                : "bg-muted text-muted-foreground",
          )}
        >
          {isUser ? (
            <User className="h-4 w-4" />
          ) : isReasoning ? (
            <Lightbulb className="h-4 w-4" />
          ) : (
            <Bot className="h-4 w-4" />
          )}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "flex flex-col gap-1 max-w-[85%] min-w-[50%]",
          isUser ? "items-end" : "items-start",
        )}
      >
        {nodeName && isReasoning && (
          <span className="text-xs text-muted-foreground flex items-center gap-1.5 ml-1 mb-1 font-medium capitalize">
            {nodeName} thinking...
          </span>
        )}

        {reasoningSteps && reasoningSteps.length > 0 && (
          <div className="mb-2 w-full rounded-xl border border-border/50 bg-muted/20 overflow-hidden">
            <button
              onClick={() => setShowReasoning(!showReasoning)}
              className="flex items-center gap-2 w-full px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-muted/40 transition-colors"
            >
              <Lightbulb className="h-3.5 w-3.5 text-amber-500/80" />
              <span>
                {showReasoning ? "Hide" : "Show"} internal reasoning (
                {reasoningSteps.length} steps)
              </span>
              {showReasoning ? (
                <ChevronDown className="h-3.5 w-3.5 ml-auto" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 ml-auto" />
              )}
            </button>
            {showReasoning && (
              <div className="px-4 py-3 border-t border-border/50 bg-muted/10 text-[13px] leading-relaxed text-muted-foreground/80 space-y-4 max-h-[400px] overflow-y-auto custom-scrollbar prose prose-sm dark:prose-invert prose-p:leading-relaxed prose-pre:bg-muted/30 prose-pre:border prose-pre:p-2 prose-pre:rounded-md max-w-none">
                {reasoningSteps.map((step, idx) => (
                  <ReactMarkdown key={idx} remarkPlugins={[remarkGfm]}>
                    {step}
                  </ReactMarkdown>
                ))}
              </div>
            )}
          </div>
        )}

        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed prose prose-sm dark:prose-invert",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : isReasoning
                ? "bg-amber-500/5 border border-amber-500/20 text-muted-foreground rounded-bl-md"
                : "bg-card border border-border/50 text-card-foreground rounded-bl-md",
            "prose-p:leading-relaxed prose-pre:bg-muted/50 prose-pre:border prose-pre:p-2 prose-pre:rounded-md",
            "prose-th:bg-muted/50 prose-td:border-t prose-table:border prose-table:rounded-md",
            isReasoning &&
              "text-sm prose-p:text-sm prose-headings:text-sm prose-li:text-sm",
          )}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap break-words">{content}</div>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children, ...props }) => (
                  <p className="mb-2 last:mb-0" {...props}>
                    {children}
                  </p>
                ),
                ul: ({ children, ...props }) => (
                  <ul className="mb-2 pl-4 list-disc" {...props}>
                    {children}
                  </ul>
                ),
                ol: ({ children, ...props }) => (
                  <ol className="mb-2 pl-4 list-decimal" {...props}>
                    {children}
                  </ol>
                ),
                table: ({ children, ...props }) => (
                  <div className="my-3 w-full overflow-x-auto rounded-md border border-border">
                    <table className="w-full text-left text-sm" {...props}>
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children, ...props }) => (
                  <th className="bg-muted px-4 py-2 font-medium" {...props}>
                    {children}
                  </th>
                ),
                td: ({ children, ...props }) => (
                  <td className="px-4 py-2 border-t" {...props}>
                    {children}
                  </td>
                ),
                pre: ({ children, ...props }) => (
                  <pre
                    className="my-2 overflow-x-auto rounded-md bg-muted/50 p-3"
                    {...props}
                  >
                    {children}
                  </pre>
                ),
                code: ({ className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || "");
                  return !match ? (
                    <code
                      className="rounded bg-muted/50 px-1 py-0.5 text-xs text-primary"
                      {...props}
                    >
                      {children}
                    </code>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
                img: ({ src, alt, ...props }) => {
                  let imgUrl = src as string | undefined;
                  // If running inside SPFx (__BACKEND_API_URL__ is set) and src is a relative string path
                  if (
                    typeof src === "string" &&
                    src.startsWith("/") &&
                    typeof window !== "undefined" &&
                    (window as any).__BACKEND_API_URL__
                  ) {
                    // Remove trailing slash from backend URL if present, and ensure src starts with slash
                    const baseUrl = (window as any).__BACKEND_API_URL__.replace(/\/$/, "");
                    imgUrl = `${baseUrl}${src}`;
                  }
                  return (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={imgUrl}
                      alt={alt || "Image"}
                      className="max-w-full h-auto rounded-lg object-contain my-2 border border-border/40 bg-black/5 dark:bg-black/20"
                      loading="lazy"
                      style={{ maxHeight: "60vh" }}
                      {...props}
                    />
                  );
                },
              }}
            >
              {content || ""}
            </ReactMarkdown>
          )}
        </div>
      </div>
    </div>
  );
}
