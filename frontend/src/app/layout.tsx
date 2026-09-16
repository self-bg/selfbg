import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "selfbg — self-hosted background remover",
  description:
    "A self-hosted replacement for remove.bg. Upload an image, get a PNG cutout back. Runs on your hardware, keeps your data on your network.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
