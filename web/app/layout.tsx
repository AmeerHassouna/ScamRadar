import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AnimatedNavFramer } from "@/components/ui/scroll-navigation-menu";
import { Providers } from "@/components/ui/providers";
import { ScrollToTop } from "@/components/ui/scroll-to-top";
import { ErrorBoundary } from "@/components/ui/error-boundary";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ScamRadar+ — AI-Powered Scam Detection",
  description: "Detect scam messages instantly with machine learning, vector proximity search, and real-time URL scanning.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-background">
        <Providers>
          <ErrorBoundary>
            <ScrollToTop />
            <AnimatedNavFramer />
            {children}
          </ErrorBoundary>
        </Providers>
      </body>
    </html>
  );
}
