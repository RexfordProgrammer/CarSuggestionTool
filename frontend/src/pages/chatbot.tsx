import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "@/styles/style.css";

type Msg = { role: "user" | "bot" | "system"; text: string };

function MarkdownMessage({
  className,
  children,
}: {
  className?: string;
  children: string;
}) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

function App() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  // NEW → ref for chat window
  const chatWindowRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const token =
      localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");
    if (!token) {
      console.error("No auth token found");
      return;
    }

    const wsUrl = `wss://rnlcph5bha.execute-api.us-east-1.amazonaws.com/prodv1/?token=${encodeURIComponent(
      token
    )}`;
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      setMessages([{ role: "system", text: "Connected to Car Suggestion Tool" }]);
    };

    socket.onmessage = (event) => {
      const responseBody = JSON.parse(event.data);
      setMessages((prev) => [...prev, { role: "bot", text: responseBody.reply }]);
    };

    socket.onclose = () => {
      setConnected(false);
      setMessages((prev) => [...prev, { role: "system", text: "❌ Disconnected" }]);
    };

    socket.onerror = (err) => {
      setMessages((prev) => [...prev, { role: "system", text: "⚠️ WebSocket error" }]);
      console.error("WebSocket error:", err);
    };

    return () => socket.close();
  }, []);

  // NEW → Auto-scroll effect
  useEffect(() => {
    const chatDiv = chatWindowRef.current;
    if (chatDiv) {
      chatDiv.scrollTo({
        top: chatDiv.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const sendMessage = () => {
    if (socketRef.current && connected && input.trim() !== "") {
      const payload = JSON.stringify({ action: "sendMessage", text: input.trim() });
      socketRef.current.send(payload);
      setMessages((prev) => [...prev, { role: "user", text: input.trim() }]);
      setInput("");
    }
  };

  return (
    <>
      <div className="futuristic-bg" aria-hidden="true" />

      <section className="card futuristic-card max-w-[1200px] w-[90%] h-[90vh] flex flex-col">
        <h1 className="glow mb-3 text-center text-3xl">Car Suggestion Tool</h1>

        {/* ADD ref={chatWindowRef} */}
        <div
          ref={chatWindowRef}
          className="chat-window flex-1 border rounded p-4 overflow-y-auto bg-black/30 text-black text-lg space-y-3"
        >
          {messages.map((msg, i) => {
            const prefix =
              msg.role === "user" ? "**You:** " : msg.role === "bot" ? "**Bot:** " : "";
            return (
              <div
                key={i}
                className={
                  msg.role === "bot"
                    ? "text-black"
                    : msg.role === "user"
                    ? "text-gray-900"
                    : "text-gray-900 italic"
                }
              >
                <MarkdownMessage className="prose prose-invert max-w-none">
                  {`${prefix}${msg.text}`}
                </MarkdownMessage>
              </div>
            );
          })}
        </div>

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
