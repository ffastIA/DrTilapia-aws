// types/chat.ts
export interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  isError?: boolean;
}

export interface ChatRequest {
  message: string;
  history: [string, string][];
}

export interface ChatResponse {
  answer: string;
  sources: string[];
}