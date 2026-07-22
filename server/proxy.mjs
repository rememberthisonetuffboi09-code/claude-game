/* =====================================================================
 *  LOCAL CLAUDE PROXY  (only needed for PRANK.engine = "live")
 * ---------------------------------------------------------------------
 *  Keeps your Anthropic API key on your machine — it never reaches the
 *  browser (or your friend). The game POSTs a Messages request here and
 *  this forwards it to the Anthropic API with your key attached.
 *
 *  Run it:
 *      export ANTHROPIC_API_KEY=sk-ant-...
 *      node server/proxy.mjs
 *
 *  Needs Node 18+ (uses built-in fetch). No npm install required.
 * ===================================================================== */

import http from "node:http";

const PORT = process.env.PORT || 8787;
const KEY = process.env.ANTHROPIC_API_KEY;

if (!KEY) {
  console.error("✗ Set ANTHROPIC_API_KEY first:  export ANTHROPIC_API_KEY=sk-ant-...");
  process.exit(1);
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

http.createServer((req, res) => {
  if (req.method === "OPTIONS") { res.writeHead(204, CORS); return res.end(); }
  if (req.method !== "POST" || !req.url.startsWith("/claude")) {
    res.writeHead(404, CORS); return res.end("not found");
  }

  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", async () => {
    try {
      const upstream = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": KEY,
          "anthropic-version": "2023-06-01",
        },
        body,
      });
      const text = await upstream.text();
      res.writeHead(upstream.status, { ...CORS, "Content-Type": "application/json" });
      res.end(text);
    } catch (err) {
      res.writeHead(502, { ...CORS, "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: String(err) }));
    }
  });
}).listen(PORT, () => {
  console.log(`✓ Claude proxy on http://localhost:${PORT}/claude`);
  console.log("  Leave this running, then open index.html with PRANK.engine = \"live\".");
});
