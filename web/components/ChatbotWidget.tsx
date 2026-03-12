"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { FileUpload } from "@/components/FileUpload";
import { uploadDefaultFile, type UploadResult } from "@/lib/api";
import {
  ChatContainer,
  type ChatContainerHandle,
} from "@/components/ChatContainer";
import {
  MessageCircle,
  X,
  Sparkles,
  Minus,
  Settings,
  CheckCircle2,
  Plus,
} from "lucide-react";

export function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadResult | null>(null);

  const [chatStatus, setChatStatus] = useState({
    isStreaming: false,
    isEmpty: true,
  });
  const chatRef = useRef<ChatContainerHandle>(null);

  const handleNewChat = () => {
    chatRef.current?.newChat();
  };

  return (
    <>
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

      {isOpen && (
        <div
          className="chatbot-modal-wrapper"
          style={{ pointerEvents: "auto" }}
        >
          <div className="chatbot-backdrop" onClick={() => setIsOpen(false)} />
          <div className="chatbot-modal overflow-hidden flex flex-col">
            <div className="chatbot-modal-header shrink-0">
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
                {!chatStatus.isEmpty && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleNewChat}
                    disabled={chatStatus.isStreaming}
                    className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
                    title="New Chat"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                )}
                {/* <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowSettings(!showSettings)}
                  className={`h-7 w-7 rounded-lg ${showSettings ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                  title="Settings"
                >
                  <Settings className="h-3.5 w-3.5" />
                </Button> */}
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

            {showSettings && (
              <div className="border-b border-border/40 bg-muted/10 p-4 shrink-0">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-xs font-medium text-foreground">
                    Global Default Dataset
                  </h3>
                </div>
                {uploadedFile ? (
                  <div className="flex flex-col items-center justify-center p-4 bg-muted/20 rounded-lg border border-border/50 text-center animate-in fade-in duration-300">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500 mb-2" />
                    <p className="text-[11px] text-muted-foreground mb-3">
                      <strong className="text-foreground">
                        {uploadedFile.filename}
                      </strong>{" "}
                      is now the default dataset.
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
                    className="p-4"
                  />
                )}
              </div>
            )}

            <div className="flex-1 overflow-hidden">
              <ChatContainer
                ref={chatRef}
                className="h-full"
                showNewChat={false}
                onStatusChange={setChatStatus}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
