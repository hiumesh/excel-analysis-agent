"use client";

import { useState, useRef } from "react";
import { ChatContainer, type ChatContainerHandle } from "@/components/ChatContainer";
import { Button } from "@/components/ui/button";
import { Plus, Sparkles } from "lucide-react";

export function EmbedPage() {
  const [chatStatus, setChatStatus] = useState({ isStreaming: false, isEmpty: true });
  const chatRef = useRef<ChatContainerHandle>(null);

  const handleNewChat = () => {
    chatRef.current?.newChat();
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-background">
      {/* Header for Embed View */}
      <div className="h-14 shrink-0 border-b border-border/40 bg-background/50 backdrop-blur-sm px-4 flex items-center justify-between">
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

        {!chatStatus.isEmpty && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleNewChat}
            disabled={chatStatus.isStreaming}
            className="flex items-center gap-1.5 h-8 px-3 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
          >
            <Plus className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">New Chat</span>
          </Button>
        )}
      </div>

      <main className="flex-1 overflow-hidden">
        <ChatContainer 
          ref={chatRef}
          className="h-full w-full" 
          showNewChat={false} 
          onStatusChange={setChatStatus}
        />
      </main>
    </div>
  );
}
