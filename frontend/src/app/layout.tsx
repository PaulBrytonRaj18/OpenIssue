import type { Metadata } from "next";
import "../styles/globals.css";
import { Providers } from "./providers";
import { Analytics } from "@vercel/analytics/next";

export const metadata: Metadata = {
  title: "IssueCompass — Find open source issues matched to your skills",
  description:
    "Stop searching. Start contributing. IssueCompass matches you to open-source issues you can actually solve based on your real GitHub activity.",
  keywords: ["open source", "github", "contributing", "developer", "issues"],
  openGraph: {
    title: "IssueCompass",
    description: "Find open source issues matched to your skills",
    type: "website",
  },
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
        <Analytics />
      </body>
    </html>
  );
}
