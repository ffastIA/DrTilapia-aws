// hooks/useChat.ts
import { useState, useRef } from 'react';
import api from '@/lib/api';

export interface ChatSource {
  file: string;
  // Páginas discretas (0-indexed) realmente presentes nos trechos usados —
  // não mais um span min/max, que sugeria que todo o intervalo entre a
  // menor e a maior página tinha sido usado.
  pages: number[];
}

interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  isError?: boolean;
  sources?: ChatSource[];
}

interface ChatResponse {
  answer: string;
  sources: ChatSource[];
}

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatHistoryRef = useRef<[string, string][]>([]);

  const sendMessage = async (newMessage: string) => {
    if (!newMessage.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: newMessage,
      sender: 'user',
    };

    // Adiciona a mensagem do usuário imediatamente
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      console.log('Enviando mensagem para o backend...', {
        message: newMessage,
        history: chatHistoryRef.current,
      });

      const response = await api.post<ChatResponse>('/consultoria/chat', {
        message: newMessage,
        history: chatHistoryRef.current,
      });

      console.log('Resposta recebida do backend:', response.data);

      const aiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: response.data.answer,
        sender: 'ai',
        sources: response.data.sources,
      };

      // Adiciona a resposta da IA
      setMessages((prev) => [...prev, aiMessage]);

      // Atualiza o histórico para a próxima requisição
      chatHistoryRef.current = [
        ...chatHistoryRef.current,
        [newMessage, response.data.answer],
      ];
    } catch (err: any) {
      console.error('Erro ao enviar mensagem:', err);

      const errorMessage =
        err.response?.data?.detail ||
        err.message ||
        'Erro ao comunicar com a IA. Tente novamente.';

      setError(errorMessage);

      const errorAiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: `❌ Erro: ${errorMessage}`,
        sender: 'ai',
        isError: true,
      };

      setMessages((prev) => [...prev, errorAiMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    chatHistoryRef.current = [];
    setError(null);
  };

  return { messages, isLoading, error, sendMessage, clearChat };
};