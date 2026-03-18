"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  BarChart3,
  Table2,
  FileText,
  ChevronDown,
  ChevronUp,
  Image as ImageIcon,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Artifact } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ArtifactsPanelProps {
  artifacts: Artifact[];
  className?: string;
}

function getArtifactIcon(type: string) {
  switch (type) {
    case "plot":
      return <BarChart3 className="h-3.5 w-3.5" />;
    case "table":
      return <Table2 className="h-3.5 w-3.5" />;
    case "image":
      return <ImageIcon className="h-3.5 w-3.5" />;
    default:
      return <FileText className="h-3.5 w-3.5" />;
  }
}

function getArtifactColor(type: string, isActive: boolean) {
  if (isActive) {
    return "bg-primary text-primary-foreground border-primary";
  }
  switch (type) {
    case "plot":
      return "text-blue-400 bg-blue-500/10 border-blue-500/20 hover:bg-blue-500/20";
    case "table":
      return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/20";
    case "image":
      return "text-purple-400 bg-purple-500/10 border-purple-500/20 hover:bg-purple-500/20";
    default:
      return "text-amber-400 bg-amber-500/10 border-amber-500/20 hover:bg-amber-500/20";
  }
}

export function ArtifactsPanel({ artifacts, className }: ArtifactsPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  // Only show plot artifacts
  const plotArtifacts = artifacts.filter((a) => a.type === "plot");

  if (!plotArtifacts.length) return null;

  const activeArtifact = plotArtifacts[activeIndex] || plotArtifacts[0];

  return (
    <div className={cn("w-full px-4 mb-4", className)}>
      <div className="ml-11">
        {/* Expand Button Aligned Left */}
        <div className="flex justify-start py-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsOpen(!isOpen)}
            className="gap-2 rounded-full px-4 border-border/50 bg-card/50 hover:bg-card backdrop-blur-sm transition-all duration-300"
          >
            <BarChart3 className="h-4 w-4 text-primary/70" />
            <span className="text-sm">Artifacts</span>
            <Badge
              variant="secondary"
              className="h-5 min-w-5 rounded-full px-1.5 text-[10px] bg-primary/15 text-primary font-semibold"
            >
              {plotArtifacts.length}
            </Badge>
            {isOpen ? (
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            ) : (
              <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </Button>
        </div>

        {isOpen && (
          <div className="mt-2 flex flex-col gap-3">
            {/* Top Section: Tags */}
            <div className="flex flex-wrap gap-2">
              {plotArtifacts.map((artifact, index) => {
                const isActive = index === activeIndex;
                const title = artifact.title || artifact.type;
                const isTruncated = title.length > 25;
                const displayTitle = isTruncated
                  ? `${title.slice(0, 25)}...`
                  : title;

                return (
                  <Tooltip key={index} delayDuration={300}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => setActiveIndex(index)}
                        className={cn(
                          "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors",
                          getArtifactColor(artifact.type, isActive),
                        )}
                      >
                        {getArtifactIcon(artifact.type)}
                        <span>{displayTitle}</span>
                      </button>
                    </TooltipTrigger>
                    {isTruncated && (
                      <TooltipContent
                        side="bottom"
                        className="max-w-[300px] break-words"
                      >
                        <p>{title}</p>
                      </TooltipContent>
                    )}
                  </Tooltip>
                );
              })}
            </div>
            <div className="bg-transparent mt-2">
              {activeArtifact.type === "plot" && activeArtifact.url ? (
                (() => {
                  let imgUrl = activeArtifact.url;
                  // If running inside SPFx (__BACKEND_API_URL__ is set) and src is relative
                  if (
                    imgUrl &&
                    imgUrl.startsWith("/") &&
                    typeof window !== "undefined" &&
                    (window as any).__BACKEND_API_URL__
                  ) {
                    const baseUrl = (window as any).__BACKEND_API_URL__.replace(/\/$/, "");
                    imgUrl = `${baseUrl}${imgUrl}`;
                  }
                  return (
                    <div className="rounded-xl overflow-hidden bg-black/5 dark:bg-black/20 p-2 border border-border/40 inline-block">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={imgUrl}
                        alt={activeArtifact.title || "Plot"}
                        className="max-w-full h-auto rounded-lg object-contain"
                        loading="lazy"
                        style={{ maxHeight: "60vh" }}
                      />
                    </div>
                  );
                })()
              ) : (
                <ScrollArea className="max-h-[600px] w-full rounded-xl bg-muted/10 border border-border/40 p-4">
                  <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-muted/30 prose-pre:border prose-pre:p-2 prose-pre:rounded-md prose-table:border-collapse prose-th:bg-muted/50 prose-th:px-4 prose-th:py-2 prose-td:border-t prose-td:px-4 prose-td:py-2">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {activeArtifact.content}
                    </ReactMarkdown>
                  </div>
                </ScrollArea>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
