import { useEffect, useState } from "react";

type NavItem = { label: string; href: string; external?: boolean };

export function Navbar({
    brand = "Rexford Dorchester",
    items = [
        { label: "Home", href: "/" },
        { label: "CAD Gallery", href: "/CAD/" },
        { label: "Code Samples", href: "/Code/" },
        { label: "MultiTester", href: "/Multiplication/" },
    ],
}: {
    brand?: string;
    items?: NavItem[];
}) {
    const [open, setOpen] = useState(false);
    const [scrolled, setScrolled] = useState(false);

    // highlight current route
    const path =
        typeof window !== "undefined" ? window.location.pathname.toLowerCase() : "/";

    // add a subtle shadow once you scroll past the top
    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 2);
        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    return (
        <header className={`topbar${scrolled ? " scrolled" : ""}`} role="banner">
            <a className="brand glow" href="/">{brand}</a>

            <button
                className="nav-toggle"
                aria-label="Toggle navigation"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
            >
                <span className="bar" />
                <span className="bar" />
                <span className="bar" />
            </button>

            <nav className={`topnav${open ? " open" : ""}`} aria-label="Primary">
                {items.map(({ label, href, external }) => {
                    const current = path === href.toLowerCase();
                    return external ? (
                        <a
                            key={href}
                            className={`topnav-link${current ? " active" : ""}`}
                            href={href}
                            target="_blank"
                            rel="noopener"
                            aria-current={current ? "page" : undefined}
                        >
                            {label}
                        </a>
                    ) : (
                        <a
                            key={href}
                            className={`topnav-link${current ? " active" : ""}`}
                            href={href}
                            aria-current={current ? "page" : undefined}
                        >
                            {label}
                        </a>
                    );
                })}
            </nav>
        </header>
    );
}
