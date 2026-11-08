import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "NoteForge — From ink to insight",
  description:
    "Your handwritten thinking, transformed into traceable knowledge.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-GB" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
