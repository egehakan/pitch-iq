import type { Metadata } from "next";
import { Archivo, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/providers/QueryProvider";

const display = Archivo({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
});
const sans = Inter({ variable: "--font-sans", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Pitch IQ — World Cup companion",
  description:
    "An agentic companion for the World Cup: grounded live match Q&A, critic-tested predictions, briefings, and a bracket you can lock.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable} h-full`}>
      <body className="min-h-full antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
