import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import preserveDirectives from "rollup-plugin-preserve-directives";
import { resolve } from "path";

export default defineConfig(({ mode }) => {
  // Load env from the project root (../) instead of this standalone directory
  const env = loadEnv(mode, resolve(__dirname, ".."), [
    "VITE_",
    "NEXT_PUBLIC_",
  ]);

  return {
    plugins: [react()],
    root: __dirname,
    base: "./", // Use relative paths for assets within each bundle
    define: {
      "process.env.NEXT_PUBLIC_API_URL": JSON.stringify(
        env.NEXT_PUBLIC_API_URL || env.VITE_API_URL || "http://localhost:8000",
      ),
    },
    resolve: {
      alias: {
        "@/components": resolve(__dirname, "../components"),
        "@/lib": resolve(__dirname, "../lib"),
        "@/app": resolve(__dirname, "../app"),
      },
    },
    build: {
      outDir: resolve(__dirname, "../../static/dist"),
      emptyOutDir: true,
      rollupOptions: {
        preserveEntrySignatures: "exports-only",
        input: {
          widget: resolve(__dirname, "widget/index.html"),
          embed: resolve(__dirname, "embed/index.html"),
        },
        output: {
          // Output into subdirectories to match URLs
          entryFileNames: "[name]/index.js",
          chunkFileNames: "assets/[name]-[hash].js",
          assetFileNames: (assetInfo) => {
            if (assetInfo.name && assetInfo.name.endsWith(".css")) {
              // Extract the parent directory name to group CSS
              return "[name]/index.css";
            }
            return "assets/[name].[hash][extname]";
          },
        },
        plugins: [preserveDirectives()],
      },
    },
  };
});
