import React from "react";
import ReactDOM from "react-dom/client";
import { ChatbotWidget } from "@/components/ChatbotWidget";
import "../app/globals.css";

// Mount the chatbot widget into a shadow-free container
const CONTAINER_ID = "reportiq-chatbot-root";

function mount() {
  // Avoid double-mounting
  if (document.getElementById(CONTAINER_ID)) return;

  const container = document.createElement("div");
  container.id = CONTAINER_ID;
  // Ensure the container doesn't interfere with the host page layout
  container.style.cssText =
    "position:fixed;inset:0;z-index:99999;pointer-events:none;";
  document.body.appendChild(container);

  const root = ReactDOM.createRoot(container);
  root.render(React.createElement(ChatbotWidget));
}

// Auto-mount when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}
