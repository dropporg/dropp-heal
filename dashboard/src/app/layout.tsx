import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";
import Link from "next/link";

import { Providers } from "@/components/Providers";
import "./globals.css";

// One superfamily in three roles: condensed for panel labels, sans for prose,
// mono for every measurement so columns of numbers line up.
const plexCondensed = IBM_Plex_Sans_Condensed({
  variable: "--font-plex-condensed",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});
const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Heal — network status",
  description: "Availability, latency and filtering detection for monitored targets.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${plexCondensed.variable} ${plexSans.variable} ${plexMono.variable} min-h-screen`}
      >
        <Providers>
          <header className="border-b border-rule bg-surface">
            <div className="mx-auto flex max-w-[1400px] items-baseline gap-6 px-6 py-4">
              <Link href="/" className="font-display text-xl font-bold tracking-tight">
                HEAL
              </Link>
              <p className="eyebrow hidden sm:block">Network reachability and filtering</p>
            </div>
          </header>
          <main className="mx-auto max-w-[1400px] px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
