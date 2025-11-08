import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@/styles/style.css";

function App() {
  const [messages, setMessages] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token =
      localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
    if (!token) {
      console.error("No auth token found");
      return;
    }

    const wsUrl = `wss://rnlcph5bha.execute-api.us-east-1.amazonaws.com/prodv1?token=${encodeURIComponent(
      token
    )}`;
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      // ✅ Post connected notice, then bot greeting
      setMessages([
        "System: Connected",
      ]);
      console.log("WebSocket connected.");
    };

    socket.onmessage = (event) => {
      const responseBody = JSON.parse(event.data);
      setMessages((prev) => [...prev, "Bot: " + responseBody.reply]);
    };

    socket.onclose = () => {
      setConnected(false);
      setMessages((prev) => [...prev, "System: Disconnected"]);
    };

    socket.onerror = (err) => {
      setMessages((prev) => [...prev, "System: WebSocket error"]);
      console.error("WebSocket error:", err);
    };

    return () => {
      socket.close();
    };
  }, []);

  const sendMessage = () => {
    if (socketRef.current && connected && input.trim() !== "") {
      const payload = JSON.stringify({
        action: "sendMessage",
        text: input.trim(),
      });
      socketRef.current.send(payload);
      setMessages((prev) => [...prev, "User: " + input.trim()]);
      setInput("");
    }
  };

  return (
    <>
      {/* Background */}
      <div className="futuristic-bg" aria-hidden="true" />

      <section className="card futuristic-card max-w-[1200px] w-[90%] h-[90vh] flex flex-col">
        <h1 className="glow mb-3 text-center text-3xl">
          Car Suggestion Tool
        </h1>

        {/* Chat window */}
        <div className="chat-window flex-1 border rounded p-4 overflow-y-auto bg-black/30 text-black text-lg">
          {messages.map((msg, i) => (
            <div key={i} className="mb-2">
              {msg}
            </div>
          ))}
        </div>

        {/* Input + send button */}
        <div className="flex mt-3 gap-3">
          <input
            className="input flex-1 text-lg"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder={connected ? "Type your message…" : "Not connected"}
            disabled={!connected}
          />
          <button
            className="btn px-6 text-lg"
            type="button"
            onClick={sendMessage}
            disabled={!connected}
          >
            Send
          </button>
        </div>

        <div className="divider mt-2" role="separator" aria-hidden="true" />
      </section>
    </>
  );
}

createRoot(document.getElementById("app")!).render(<App />);

export default App;
