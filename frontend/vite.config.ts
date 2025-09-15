import { defineConfig } from "vite";
import { resolve } from "node:path";

// https://vite.dev/config/
export default defineConfig({
  resolve: { alias: { "@": resolve(__dirname, "src") } },
  server: {
    port: 5173
  },
  build: {
    rollupOptions: {
      input: {
        home: resolve(__dirname, "index.html"),
        code: resolve(__dirname, "Code/index.html"),
        cad: resolve(__dirname, "CAD/index.html"),
        multiplicaiton: resolve(__dirname, "Multiplication/index.html"),
      },
    },
  },
});
