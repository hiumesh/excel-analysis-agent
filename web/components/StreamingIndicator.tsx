"use client";

import { cn } from "@/lib/utils";
// NOTE: Commented out — not needed while ReasoningStepBox is disabled
// import ReactMarkdown from "react-markdown";
// import remarkGfm from "remark-gfm";
import {
  useEffect,
  useState,
  useMemo,
  createContext,
  useContext,
  // useRef,
  useId,
  // useCallback,
} from "react";
// import type { Components } from "react-markdown";

interface StreamingIndicatorProps {
  currentNode: string | null;
  reasoningSteps?: string[];
  className?: string;
}

const nodeLabels: Record<string, { label: string; icon: string }> = {
  router: { label: "Understanding your question", icon: "🧠" },
  planner: { label: "Preparing analysis plan", icon: "📋" },
  data_loader: { label: "Reading your data", icon: "�" },
  coding_agent: { label: "Crunching the numbers", icon: "�" },
  execute_tools: { label: "Running analysis", icon: "⚙️" },
  code_executor: { label: "Processing results", icon: "⚡" },
  synthesizer: { label: "Summarizing findings", icon: "✍️" },
  finalizer: { label: "Preparing your report", icon: "�" },
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

// NOTE: Commented out — not needed while ReasoningStepBox is disabled
// const markdownComponents: Components = {
//   p: ({ children, ...props }) => (...),
//   ul: ({ children, ...props }) => (...),
//   ol: ({ children, ...props }) => (...),
//   li: ({ children, ...props }) => (...),
// };

export function StreamingIndicator({
  currentNode,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  reasoningSteps = [],
  className,
}: StreamingIndicatorProps) {
  // NOTE: Reasoning steps remain commented out.
  // Showing per-node progress labels instead of static "Analyzing" text.

  const nodeInfo = currentNode ? nodeLabels[currentNode] : null;
  const displayIcon = nodeInfo?.icon || "✨";
  const displayLabel = nodeInfo?.label || "Analyzing";

  return (
    <div className={cn("flex items-center gap-3 px-4 py-3", className)}>
      <div className="flex items-center gap-2.5 text-muted-foreground/70">
        <span className="text-sm">{displayIcon}</span>
        <span className="text-[13px] font-medium tracking-tight">
          {displayLabel}
        </span>
        <div className="flex items-center gap-1 ml-0.5">
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

// --- Commented out: ReasoningStepBox (thinking steps display) ---
// function ReasoningStepBox({ step }: { step: string }) {
//   const registryRef = useRef<Map<string, number>>(new Map());
//   const counterRef = useRef(0);
//
//   const register = useCallback((id: string, count: number) => {
//     if (registryRef.current.has(id)) {
//       return registryRef.current.get(id)!;
//     }
//     const start = counterRef.current;
//     registryRef.current.set(id, start);
//     counterRef.current += count;
//     return start;
//   }, []);
//
//   return (
//     <DelayContext.Provider value={{ register }}>
//       <div className="text-[13px] leading-relaxed text-muted-foreground/60 prose prose-sm dark:prose-invert prose-p:leading-relaxed prose-pre:bg-muted/30 prose-pre:border prose-pre:p-2 prose-pre:rounded-md max-w-[85%]">
//         <ReactMarkdown
//           remarkPlugins={[remarkGfm]}
//           components={markdownComponents}
//         >
//           {step}
//         </ReactMarkdown>
//       </div>
//     </DelayContext.Provider>
//   );
// }
