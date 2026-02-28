"use client";

import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useEffect,
  useState,
  useMemo,
  createContext,
  useContext,
  useRef,
  useId,
  useCallback,
} from "react";
import type { Components } from "react-markdown";

interface StreamingIndicatorProps {
  currentNode: string | null;
  reasoningSteps?: string[];
  className?: string;
}

const nodeLabels: Record<string, { label: string; icon: string }> = {
  router: { label: "Routing query", icon: "🔀" },
  planner: { label: "Planning analysis", icon: "📋" },
  data_loader: { label: "Loading data", icon: "📁" },
  coding_agent: { label: "Writing analysis code", icon: "💻" },
  execute_tools: { label: "Executing tools", icon: "⚙️" },
  code_executor: { label: "Executing code", icon: "⚡" },
  synthesizer: { label: "Synthesizing results", icon: "✨" },
  finalizer: { label: "Finalizing response", icon: "📊" },
};

const DelayContext = createContext<{
  register: (id: string, count: number) => number;
} | null>(null);

function AnimatedText({ text }: { text: string }) {
  const [visibleWords, setVisibleWords] = useState<number>(0);
  const words = useMemo(() => text.split(/(\s+)/), [text]);
  const id = useId();
  const context = useContext(DelayContext);

  const startIndex = useMemo(() => {
    return context ? context.register(id, words.length) : 0;
  }, [context, id, words.length]);

  useEffect(() => {
    if (!text) return;

    // Reset visible words if text changes, but inside a timeout to avoid sync update warning
    const resetTimeout = setTimeout(() => {
      setVisibleWords(0);
    }, 0);

    // Reveal one token (word or space) at a time
    const revealTimeout = setTimeout(
      () => {
        const animationInterval = setInterval(() => {
          setVisibleWords((prev) => {
            if (prev >= words.length) {
              clearInterval(animationInterval);
              return prev;
            }
            return prev + 1;
          });
        }, 30); // Adjust speed here (ms per token)

        return () => clearInterval(animationInterval);
      },
      startIndex * 30 + 5,
    );

    return () => {
      clearTimeout(resetTimeout);
      clearTimeout(revealTimeout);
    };
  }, [text, words.length, startIndex]);

  return (
    <>
      {words.map((word, i) => (
        <span
          key={i}
          className={cn(
            "transition-opacity duration-300",
            i < visibleWords ? "opacity-100" : "opacity-0",
          )}
        >
          {word}
        </span>
      ))}
    </>
  );
}

function AnimatedListItem({
  children,
  ...props
}: React.LiHTMLAttributes<HTMLLIElement>) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  const context = useContext(DelayContext);

  const startIndex = useMemo(() => {
    return context ? context.register(id, 0) : 0;
  }, [context, id]);

  useEffect(() => {
    const revealTimeout = setTimeout(
      () => {
        setVisible(true);
      },
      startIndex * 30 + 5,
    );
    return () => clearTimeout(revealTimeout);
  }, [startIndex]);

  return (
    <li
      className={cn(
        "my-0.5 transition-opacity duration-300",
        visible
          ? "opacity-100 marker:text-muted-foreground/40"
          : "opacity-0 marker:text-transparent",
      )}
      {...props}
    >
      {children}
    </li>
  );
}

const markdownComponents: Components = {
  p: ({ children, ...props }) => (
    <p className="mb-2 last:mb-0" {...props}>
      {typeof children === "string" ? (
        <AnimatedText text={children} />
      ) : Array.isArray(children) ? (
        children.map((child, i) =>
          typeof child === "string" ? (
            <AnimatedText key={i} text={child} />
          ) : (
            child
          ),
        )
      ) : (
        children
      )}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul
      className="mb-2 pl-4 list-disc marker:text-muted-foreground/40"
      {...props}
    >
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol
      className="mb-2 pl-4 list-decimal marker:text-muted-foreground/40"
      {...props}
    >
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <AnimatedListItem {...props}>
      {typeof children === "string" ? (
        <AnimatedText text={children} />
      ) : Array.isArray(children) ? (
        children.map((child, i) =>
          typeof child === "string" ? (
            <AnimatedText key={i} text={child} />
          ) : (
            child
          ),
        )
      ) : (
        children
      )}
    </AnimatedListItem>
  ),
};

export function StreamingIndicator({
  currentNode,
  reasoningSteps = [],
  className,
}: StreamingIndicatorProps) {
  const nodeInfo = currentNode ? nodeLabels[currentNode] : null;
  const label = nodeInfo?.label || currentNode || "Processing";
  const icon = nodeInfo?.icon || "🔄";

  return (
    <div className={cn("flex flex-col gap-3 px-4 py-1", className)}>
      <div className="flex flex-col gap-3 w-full ml-11">
        {reasoningSteps.map((step, idx) => (
          <ReasoningStepBox key={idx} step={step} />
        ))}
      </div>
      <div className="flex items-center gap-2 px-1 py-1 text-muted-foreground/70 ml-10">
        <span className="text-sm">{icon}</span>
        <span className="text-[13px] font-medium tracking-tight">{label}</span>
        <div className="flex items-center gap-1 ml-1">
          <span
            className="streaming-dot h-1 w-1 rounded-full bg-muted-foreground/50"
            style={{ animationDelay: "0ms" }}
          />
          <span
            className="streaming-dot h-1 w-1 rounded-full bg-muted-foreground/50"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="streaming-dot h-1 w-1 rounded-full bg-muted-foreground/50"
            style={{ animationDelay: "300ms" }}
          />
        </div>
      </div>
    </div>
  );
}

function ReasoningStepBox({ step }: { step: string }) {
  const registryRef = useRef<Map<string, number>>(new Map());
  const counterRef = useRef(0);

  const register = useCallback((id: string, count: number) => {
    if (registryRef.current.has(id)) {
      return registryRef.current.get(id)!;
    }
    const start = counterRef.current;
    registryRef.current.set(id, start);
    counterRef.current += count;
    return start;
  }, []);

  return (
    <DelayContext.Provider value={{ register }}>
      <div className="text-[13px] leading-relaxed text-muted-foreground/60 prose prose-sm dark:prose-invert prose-p:leading-relaxed prose-pre:bg-muted/30 prose-pre:border prose-pre:p-2 prose-pre:rounded-md max-w-[85%]">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents}
        >
          {step}
        </ReactMarkdown>
      </div>
    </DelayContext.Provider>
  );
}
