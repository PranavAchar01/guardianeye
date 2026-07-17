import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GuardianEye Live — AI safety officer for stadiums",
  description:
    "Real-time crowd crush, collapse, and edge-fall detection from stadium video, with a Lyzr-powered AI safety officer that briefs operators.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
