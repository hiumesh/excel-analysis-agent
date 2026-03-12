import React from "react";
import ReactDOM from "react-dom/client";
import { EmbedPage } from "@/components/EmbedPage";
import "@/app/globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <EmbedPage />
    </ThemeProvider>
  </React.StrictMode>,
);
