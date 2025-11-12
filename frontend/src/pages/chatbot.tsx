import React, {
  useEffect,
  useRef,
  useState,
  useMemo,
  useCallback,
} from "react";
import { createRoot } from "react-dom/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "@/styles/style.css";

type Msg = { role: "user" | "bot" | "system"; text: string };

type MarkdownMessageProps = {
  className?: string;
  children: string;
  remarkPlugins: any[];
  rehypePlugins: any[];
};

function MarkdownMessage({
  className,
  children,
  remarkPlugins,
  rehypePlugins,
}: MarkdownMessageProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
      >
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
  const chatWindowRef = useRef<HTMLDivElement | null>(null);

  const MAX_MESSAGES = 200;

  // Memoize markdown plugins so they aren't recreated on every render
  const remarkPlugins = useMemo(() => [remarkGfm], []);
  const rehypePlugins = useMemo(() => [rehypeHighlight], []);

  const appendMessage = useCallback((msg: Msg) => {
    setMessages((prev) => {
      const next = [...prev, msg];
      return next.length > MAX_MESSAGES
        ? next.slice(next.length - MAX_MESSAGES)
        : next;
    });
  }, []);

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
      appendMessage({
        role: "system",
        text: "Connected to Car Suggestion Tool",
      });
    };

    socket.onmessage = (event) => {
      // Some WS servers can send non-string data
      if (typeof event.data !== "string") {
        console.warn("Non-string WebSocket frame:", event.data);
        return;
      }

      let parsed: any;
      try {
        parsed = JSON.parse(event.data);
      } catch (err) {
        console.warn("Failed to parse WebSocket message as JSON:", event.data, err);
        return;
      }

      // Adjust this to match your backend payload shape
      // E.g. Emitter sends: { type: "bedrock_reply", reply: "..." }
      let text: string | null = null;

      if (typeof parsed?.reply === "string") {
        text = parsed.reply;
      } else if (typeof parsed?.message === "string") {
        text = parsed.message;
      }

      if (text) {
        appendMessage({ role: "bot", text });
      } else {
        console.warn("WebSocket JSON with no usable text field:", parsed);
      }
    };

    socket.onclose = () => {
      setConnected(false);
      appendMessage({ role: "system", text: "❌ Disconnected" });
    };

    socket.onerror = (err) => {
      appendMessage({
        role: "system",
        text: "⚠️ WebSocket error",
      });
      console.error("WebSocket error:", err);
    };

    return () => {
      try {
        socket.close();
      } catch (e) {
        // ignore
      }
    };
  }, [appendMessage]);

  // Auto-scroll chat window
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
    const text = input.trim();
    if (!socketRef.current || !connected || text === "") return;

    const payload = JSON.stringify({ action: "sendMessage", text });
    socketRef.current.send(payload);
    appendMessage({ role: "user", text });
    setInput("");
  };

  return (
    <>
      <div className="futuristic-bg" aria-hidden="true" />

      <section className="card futuristic-card max-w-[1200px] w-[90%] h-[90vh] flex flex-col">
        <h1 className="glow mb-3 text-center text-3xl">Car Suggestion Tool</h1>

        <div
          ref={chatWindowRef}
          className="chat-window flex-1 border rounded p-4 overflow-y-auto bg-black/30 text-black text-lg space-y-3"
        >
          {messages.map((msg, i) => {
            const prefix =
              msg.role === "user"
                ? "**You:** "
                : msg.role === "bot"
                ? "**Bot:** "
                : "";

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
                <MarkdownMessage
                  className="prose prose-invert max-w-none"
                  remarkPlugins={remarkPlugins}
                  rehypePlugins={rehypePlugins}
                >
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
