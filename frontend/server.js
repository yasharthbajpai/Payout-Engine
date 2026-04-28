import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 5173;
const API_URL = process.env.VITE_API_URL || 'http://localhost:8000';

app.use('/api', createProxyMiddleware({
  target: API_URL,
  changeOrigin: true,
}));

app.use(express.static(path.join(__dirname, 'dist')));

app.get('*', (_req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend serving on port ${PORT}, proxying /api to ${API_URL}`);
});
