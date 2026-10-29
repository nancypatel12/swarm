import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Swarm",
  description: "What's still unsolved in your field: open problems from recent papers, in their authors' words, explained for you.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
