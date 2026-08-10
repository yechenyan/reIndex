import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        tableQuery: resolve(import.meta.dirname, "v1/tables/query/index.html"),
      },
    },
  },
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
      "/v1": "http://127.0.0.1:8000",
    },
  },
});
