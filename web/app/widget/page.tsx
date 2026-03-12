import { ChatbotWidget } from "@/components/ChatbotWidget";

export default function WidgetPage() {
  return (
    <div className="h-screen w-screen bg-background flex flex-col items-center justify-center">
      <h1 className="text-2xl font-bold mb-4">Chatbot Widget Preview</h1>
      <p className="text-muted-foreground mb-8">Click the bubble in the bottom right corner</p>
      <ChatbotWidget />
    </div>
  );
}
