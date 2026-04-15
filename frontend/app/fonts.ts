import localFont from "next/font/local";

export const dmSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-sans",
  display: "swap",
  weight: "100 900",
});

export const dmMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-mono",
  display: "swap",
  weight: "100 900",
});

export const dmSerif = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-serif",
  display: "swap",
  weight: "100 900",
});
