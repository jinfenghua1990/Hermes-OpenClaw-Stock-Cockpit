import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';

const PROJECT_ROOT = '/Users/gino/project_ai_trading';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'local-data',
      configureServer(server) {
        server.middlewares.use('/data/', (req, res) => {
          const safePath = path.normalize(req.url.replace(/\.\./g, '')).slice(1);
          const filePath = path.join(PROJECT_ROOT, safePath);
          try {
            const content = fs.readFileSync(filePath);
            const ext = path.extname(filePath);
            const mime = ext === '.json' ? 'application/json' : 'text/plain';
            res.setHeader('Content-Type', mime);
            res.end(content);
          } catch {
            res.statusCode = 404;
            res.end('Not found');
          }
        });
      }
    }
  ],
  server: {
    port: 3000,
    host: true
  }
});
