import React from "react";
import ReactDOM from "react-dom/client";
import { EmbedPage } from "@/components/EmbedPage";
import "@/app/globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { TooltipProvider } from "@/components/ui/tooltip";

// Function to mount the React embed into any container
export function mountChatbotEmbed(containerId: string = "root") {
  const container = document.getElementById(containerId);
  if (!container) {
    console.warn(`[ReportIQ] Chatbot Embed container '${containerId}' not found. Cannot mount.`);
    return;
  }

  // Prevent multiple mountings in the same container
  if (container.dataset.reportiqMounted) {
    console.info(`[ReportIQ] Chatbot Embed already mounted in '${containerId}'. Skipping.`);
    return;
  }
  container.dataset.reportiqMounted = "true";

  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
        <TooltipProvider delayDuration={300}>
          <EmbedPage />
        </TooltipProvider>
      </ThemeProvider>
    </React.StrictMode>
  );
}

// Auto-mount for simple HTML usage or local dev if a root exists and we aren't in SPFx
if (typeof window !== "undefined") {
  (window as any).mountChatbotEmbed = mountChatbotEmbed;

  // Auto-mount only if there's a hardcoded #root and no SPFx property overrides it
  const hasRoot = !!document.getElementById("root");
  if (hasRoot && !(window as any).__BACKEND_API_URL__) {
    // Small delay to ensure DOM is ready
    setTimeout(() => {
      mountChatbotEmbed("root");
    }, 0);
  }
}
