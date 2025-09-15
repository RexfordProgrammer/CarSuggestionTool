import "@/styles/style.css";
import { createRoot } from "react-dom/client";

function App() {
    return (
        <>
            <div className="futuristic-bg" aria-hidden="true" />
            <section className="card futuristic-card">
                <h1 className="glow">Rexford Dorchester</h1>
                <h2 className="subtitle">A Glimpse into My Work</h2>
                <p className="intro">
                    Explore my <a className="futuristic-link" href="/CAD/">CAD Gallery</a>{" "}
                    or browse my <a className="futuristic-link" href="/Code/">Code Samples</a>.<br />
                    <span className="tagline">Building tomorrow, today.</span>
                </p>
                <div className="links">
                    <a className="btn" href="/CAD/">CAD Gallery</a>
                    <a className="btn" href="/Code/">Code Samples</a>
                    <a className="btn" href="/Multiplication/">Multiplication Practice!</a>
                </div>
                <h4 className="subtitle">
                    Static hosting on AWS S3<br />
                    Delivered via CloudFront<br />
                    DNS by GoDaddy
                </h4>


            </section>
        </>
    );
}

createRoot(document.getElementById("app")!).render(<App />);
