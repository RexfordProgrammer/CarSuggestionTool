import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@/styles/style.css";

// --- Component ---
function App() {

  return (
    <>
      {/* Background layer (uses your existing CSS theme) */}
      <div className="futuristic-bg" aria-hidden="true" />

      <section>

      </section>

      <section className="card futuristic-card max-w-md mx-auto">
        <h1 className="glow">Car Suggestion Tool</h1>
        <div className="chat-window" >
</div>
          <input className="input w-full" type="text"></input>
          <button className="btn w-full" type="submit">
            {/* {submitting ? "Signing in…" : "Sign In"} */"Submit"}
          </button>
        <div className="divider" role="separator" aria-hidden="true" />
        
      </section>
    </>
  );
}

// Mount
createRoot(document.getElementById("app")!).render(<App />);

export default App;