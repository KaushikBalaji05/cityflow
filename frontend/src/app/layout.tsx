import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'CityFlow — Bengaluru Multimodal Journey Planner',
  description: 'Fast, intelligent urban transit routing across Namma Metro, BMTC buses, and pedestrian networks.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
