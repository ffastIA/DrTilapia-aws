// CAMINHO: frontend/app/main/consultoria/page.tsx

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useChat, ChatSource } from '@/hooks/useChat';
import ChatMessage from '@/components/ChatMessage';
import LoadingSpinner from '@/components/LoadingSpinner';
import Button from '@/components/Button';
import PageHeader from '@/components/ui/PageHeader';
import BackButton from '@/components/ui/BackButton';
import { SendIcon, Trash2Icon, MessageSquareTextIcon } from 'lucide-react';

interface Message {
  id: string;
  text: string;
  sender: string;
  sources?: ChatSource[];
}

export default function Consultoria() {
  const { messages, isLoading, error, sendMessage, clearChat } = useChat() as {
    messages: Message[];
    isLoading: boolean;
    error: string | null;
    sendMessage: (message: string) => void;
    clearChat: () => void;
  };

  const [input, setInput] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      sendMessage(input);
      setInput('');
    }
  };

  const handleClear = () => {
    clearChat();
    setInput('');
  };

  return (
    <div className="flex flex-col">
      <PageHeader
        kicker="Assistente de IA"
        title="Consultoria de IA"
        description="Faça perguntas sobre piscicultura e tilápias"
        actions={<BackButton />}
      />

      <div className="border border-border bg-card flex flex-col">
        <div className="max-h-[55vh] overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="p-4 bg-destructive/10 border border-destructive/30 text-destructive text-sm">
              Erro: {error}
            </div>
          )}

          {messages.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center justify-center text-center py-16">
              <MessageSquareTextIcon className="w-16 h-16 text-muted-foreground mb-6 opacity-60" />
              <h2 className="font-heading font-semibold text-xl uppercase mb-3">
                Bem-vindo à Consultoria de IA
              </h2>
              <p className="text-muted-foreground max-w-md leading-relaxed">
                Digite sua pergunta sobre criação de tilápias, manejo de tanques, alimentação ou qualquer dúvida em piscicultura.
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg.text}
                isUser={msg.sender === 'user'}
                sources={msg.sources}
              />
            ))
          )}

          {isLoading && (
            <div className="flex justify-end p-4">
              <LoadingSpinner />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="p-4 border-t border-border">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Digite sua pergunta sobre tilápias..."
              className="flex-1 px-4 py-3 border border-border bg-surface text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
              disabled={isLoading}
            />
            <Button
              type="submit"
              variant="primary"
              isLoading={isLoading}
              disabled={!input.trim() || isLoading}
              className="min-w-[44px] p-3"
            >
              <SendIcon className="w-5 h-5" />
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={handleClear}
              disabled={isLoading || messages.length === 0}
              className="min-w-[44px] p-3"
            >
              <Trash2Icon className="w-5 h-5" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
