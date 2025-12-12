import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  resolve: { alias: { "@": resolve(__dirname, "src") } },
  server: {
    port: 5173
  },
  build: {
    rollupOptions: {
      input: {
        home: resolve(__dirname, "index.html"),
        chatbot: resolve(__dirname, "Chatbot/index.html"),
      },
    },
  },
});
