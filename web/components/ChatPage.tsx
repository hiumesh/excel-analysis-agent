"use client";

import Image from "next/image";
import { useState, useRef } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ChatContainer, type ChatContainerHandle } from "@/components/ChatContainer";
import { Plus, Settings } from "lucide-react";

export function ChatPage() {
  const [chatStatus, setChatStatus] = useState({ isStreaming: false, isEmpty: true });
  const chatRef = useRef<ChatContainerHandle>(null);

  const handleNewChat = () => {
    chatRef.current?.newChat();
  };

  return (
    <div className="flex flex-col h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl shrink-0">
        <div className="mx-auto max-w-4xl flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center">
              <Image
                src="/isb_identity_colour_rgb_positive.svg"
                alt="ISB Logo"
                width={80}
                height={40}
                priority
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/upload" passHref>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 rounded-xl text-xs h-8 border-border/50 hover:bg-muted/50 mr-2"
              >
                <Settings className="h-3.5 w-3.5" />
                Settings
              </Button>
            </Link>
            {!chatStatus.isEmpty && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleNewChat}
                disabled={chatStatus.isStreaming}
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

      {/* Main Chat Interface */}
      <main className="flex-1 overflow-hidden">
        <ChatContainer 
          ref={chatRef}
          className="h-full w-full max-w-4xl mx-auto" 
          showNewChat={false}
          onStatusChange={setChatStatus}
        />
      </main>
    </div>
  );
}
