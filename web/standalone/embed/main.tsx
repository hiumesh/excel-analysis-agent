import React from "react";
import ReactDOM from "react-dom/client";
import { EmbedPage } from "@/components/EmbedPage";
import "@/app/globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { TooltipProvider } from "@/components/ui/tooltip";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <TooltipProvider delayDuration={300}>
        <EmbedPage />
      </TooltipProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
