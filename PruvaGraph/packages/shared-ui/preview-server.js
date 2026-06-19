const http = require('http');
const { getWebviewShell } = require('./dist/webview-shell.js');

const PORT = process.env.PORT || 3000;

const previewContent = `
  <section class="section">
    <div class="surface">
      <h2>PRUVALEX PruvaGraph Preview</h2>
      <p class="muted">Explore the premium shared UI for a knowledge workspace built around privacy, deterministic graph routing, and token-efficient LLM workflows.</p>
    </div>
  </section>
  <section class="section column-grid">
    <div class="card">
      <h3>Premium Branding</h3>
      <p class="muted">A crisp circular emblem and elevated typography reflect the platform's professional identity.</p>
    </div>
    <div class="card">
      <h3>Nordic Minimalism</h3>
      <p class="muted">Balanced whitespace, soft tonal contrast, and accessible text create a refined workspace experience.</p>
    </div>
  </section>
`;

const server = http.createServer((req, res) => {
  if (req.url === '/favicon.ico') {
    res.writeHead(204);
    res.end();
    return;
  }

  const html = getWebviewShell('Shared UI Preview', previewContent);
  res.writeHead(200, {
    'Content-Type': 'text/html; charset=utf-8',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
  });
  res.end(html);
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Shared UI preview running at http://localhost:${PORT}/`);
});

server.on('error', (err) => {
  console.error('Preview server error:', err);
  process.exit(1);
});
