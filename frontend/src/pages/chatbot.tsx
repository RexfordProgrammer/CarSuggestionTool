import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@/styles/style.css";

function App() {
  const [messages, setMessages] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
useEffect(() => {
  const token = localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
  if (!token) {
    console.error("No auth token found");
    return;
  }

  // Attach token as query param
  const wsUrl = `wss://rnlcph5bha.execute-api.us-east-1.amazonaws.com/prodv1?token=${encodeURIComponent(token)}`;
  const socket = new WebSocket(wsUrl);
  socketRef.current = socket;

  socket.onopen = () => {
    setConnected(true);
    setMessages((prev) => [...prev, "Connected"]);
  };

  socket.onmessage = (event) => {
    //     payload = {"type": "bedrock_reply", "reply": bedrock_reply}
    const reponsebody = JSON.parse(event.data)
    setMessages((prev) => [...prev, "Bot: " + reponsebody.reply]);
  };

  socket.onclose = () => {
    setConnected(false);
    setMessages((prev) => [...prev, "....Disconnected"]);
  };

  socket.onerror = (err) => {
    setMessages((prev) => [...prev, "...WebSocket error"]);
    console.error("WebSocket error:", err);
  };

  return () => {
    socket.close();
  };
}, []);


  // --- Send message handler ---
  const sendMessage = () => {
    console.log("sending message");
    if (socketRef.current && connected && input.trim() !== "") {
          console.log("stringifying payload");
      const payload = JSON.stringify({
        action: "sendMessage",
        text: input.trim(),
      });
      console.log(payload);
      socketRef.current.send(payload);

      setMessages((prev) => [...prev, "User: " + input.trim()]);
      setInput("");
    }
  };

  return (
    <>
      {/* Background */}
      <div className="futuristic-bg" aria-hidden="true" />

      <section className="card futuristic-card max-w-md mx-auto">
        <h1 className="glow">Car Suggestion Tool</h1>

        {/* Chat window */}
        <div className="chat-window border rounded p-2 h-64 overflow-y-auto text-left bg-black/30 text-black">
          {messages.map((msg, i) => (
            <div key={i} className="mb-1">
              {msg}
            </div>
          ))}
        </div>

        {/* Input + send button */}
        <div className="flex mt-2 gap-2">
          <input
            className="input flex-1"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder={connected ? "Type your message…" : "Not connected"}
            disabled={!connected}
          />
          <button
            className="btn"
            type="button"
            onClick={sendMessage}
            disabled={!connected}
          >
            Send
          </button>
        </div>

        <div className="divider" role="separator" aria-hidden="true" />
      </section>
    </>
  );
}

// Mount
createRoot(document.getElementById("app")!).render(<App />);

export default App;
