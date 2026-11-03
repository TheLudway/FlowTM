import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Agent API (uv run uvicorn flowtm.api.app:app --port 8000)
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
