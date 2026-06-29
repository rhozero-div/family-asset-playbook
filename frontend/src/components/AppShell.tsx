import Link from "next/link";
import type { ReactNode } from "react";

export default function AppShell({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: ReactNode;
}) {
  return (
    <div className="shell">
      <header className="site-frame">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <Link href="/" className="brand">
            Family Asset Playbook Demo
          </Link>
        </div>
        <nav className="topnav">
          <Link href="/">Overview</Link>
          <Link href="/questionnaire">Questionnaire</Link>
          <Link href="/playbook">Playbook</Link>
        </nav>
      </header>
      <main className="site-frame">
        <section className="hero-head">
          <h1>{title}</h1>
        </section>
        {children}
      </main>
    </div>
  );
}
