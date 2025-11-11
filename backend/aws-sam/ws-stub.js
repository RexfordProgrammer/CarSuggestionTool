// ws-stub.js
import express from "express";
import http from "http";
import WebSocket, { WebSocketServer } from "ws";
import AWS from "aws-sdk";

const PORT = Number(process.env.WS_PORT || 8080);
const REGION = process.env.AWS_REGION || "us-east-1";
const LAMBDA_ENDPOINT = process.env.LAMBDA_ENDPOINT || "http://127.0.0.1:3001"; // SAM local

AWS.config.update({ region: REGION });
const lambda = new AWS.Lambda({ region: REGION, endpoint: LAMBDA_ENDPOINT });

// --- HTTP app + server (so WS and HTTP share the same port) ---
const app = express();
app.use(express.json());
const server = http.createServer(app);

// --- WebSocket server on the same HTTP server ---
const wss = new WebSocketServer({ server });
const clients = new Map(); // connectionId -> WebSocket

server.listen(PORT, () => {
  console.log(`✅ Local WebSocket proxy running on ws://localhost:${PORT}`);
  console.log(`🌐 HTTP relay active at http://localhost:${PORT}`);
});

wss.on("connection", (socket, req) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const forcedId = url.searchParams.get("connectionId");
  const token = url.searchParams.get("token") || undefined;

  const connectionId = forcedId || Math.random().toString(36).slice(2, 10);
  clients.set(connectionId, socket);
  console.log(`🔌 Client connected (${connectionId})${token ? `, token=${token}` : ""}`);

  // Simulate $connect
  invokeLambda("on_connect_v2", {
    requestContext: {
      routeKey: "$connect",
      connectionId,
      domainName: "localhost",
      stage: "local",
    },
    queryStringParameters: token ? { token } : undefined,
  }).catch((e) => console.error("on_connect_v2 failed:", e));

  // Ack back to client so UI can show id
  socket.send(JSON.stringify({ type: "connection_ack", connectionId }));

  // Messages → OnSendMessageFunctionV3
  socket.on("message", async (msgBuf) => {
    const msg = msgBuf.toString();
    console.log(`📨 Incoming message from ${connectionId}: ${msg}`);

    const payload = {
      requestContext: {
        routeKey: "sendMessage",
        connectionId,
        domainName: "localhost",
        stage: "local",
      },
      body: msg,
    };

    try {
      const response = await invokeLambda("on_send_message_v3", payload);
      if (response?.Payload) {
        try {
          // SAM returns Buffer/string; try to JSON parse
          const raw = typeof response.Payload === "string" ? response.Payload : response.Payload.toString();
          const parsed = JSON.parse(raw);
          if (parsed?.reply) {
            socket.send(JSON.stringify({ reply: parsed.reply }));
          }
        } catch {
          // non-JSON payload, ignore
        }
      }
    } catch (err) {
      console.error("on_send_message_v3 failed:", err);
    }
  });

  // Disconnect → on_disconnect_v2
  socket.on("close", () => {
    console.log(`❌ Client ${connectionId} disconnected.`);
    clients.delete(connectionId);
    invokeLambda("on_disconnect_v2", {
      requestContext: {
        routeKey: "$disconnect",
        connectionId,
        domainName: "localhost",
        stage: "local",
      },
    }).catch(() => {});
  });
});

// === HTTP route for Lambda Emitter local mode ===
// Lambda calls: POST http://localhost:8080/@connections/:id
app.post("/@connections/:id", (req, res) => {
  const { id } = req.params;
  const ws = clients.get(id);
  const body = req.body ?? {};

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(body));
    console.log(`➡️  Sent to ${id}:`, body);
    return res.sendStatus(200);
  } else {
    console.log(`⚠️  No active client for connection ID: ${id}. Known IDs:`, [...clients.keys()]);
    return res.sendStatus(404);
  }
});

// (Optional) health check & debug endpoints
app.get("/healthz", (_req, res) => res.json({ ok: true }));
app.get("/clients", (_req, res) => res.json({ clients: [...clients.keys()] }));

async function invokeLambda(FunctionName, payload) {
  const params = {
    FunctionName,
    InvocationType: "RequestResponse",
    Payload: JSON.stringify(payload),
  };
  return lambda.invoke(params).promise();
}
