export const metadata = {
  title: "Report IQ — Chatbot Widget",
  description: "Embeddable AI chatbot widget for data analysis.",
};

export default function EmbedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ background: "transparent", margin: 0, padding: 0 }}>
      {children}
    </div>
  );
}
