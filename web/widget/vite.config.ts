import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import preserveDirectives from "rollup-plugin-preserve-directives";
import { resolve } from "path";

export default defineConfig(({ mode }) => {
  // Load env files from the widget/ directory
  const env = loadEnv(mode, __dirname, "VITE_");

  return {
    plugins: [react()],
    root: __dirname,
    base: "/widget/",
    define: {
      // Replace process.env.NEXT_PUBLIC_API_URL so the original api.ts works in the Vite build
      "process.env.NEXT_PUBLIC_API_URL": JSON.stringify(env.VITE_API_URL || ""),
    },
    resolve: {
      alias: {
        "@/components": resolve(__dirname, "../components"),
        "@/lib": resolve(__dirname, "../lib"),
      },
    },
    build: {
      outDir: resolve(__dirname, "../../static/widget"),
      emptyOutDir: true,
      rollupOptions: {
        preserveEntrySignatures: "exports-only",
        input: resolve(__dirname, "index.html"),
        output: {
          // Single JS + CSS file output
          entryFileNames: "chatbot-widget.js",
          chunkFileNames: "chatbot-widget.js",
          assetFileNames: (assetInfo) => {
            if (assetInfo.name && assetInfo.name.endsWith(".css")) {
              return "chatbot-widget.css";
            }
            return "assets/[name].[hash][extname]";
          },
        },
        plugins: [preserveDirectives()],
      },
    },
  };
});
