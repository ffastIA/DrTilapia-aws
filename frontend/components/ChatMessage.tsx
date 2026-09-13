// components/ChatMessage.tsx
import React from 'react';
import type { ChatSource } from '@/hooks/useChat';

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  sources?: ChatSource[];
}

// Colapsa páginas discretas contíguas em intervalos só para leitura — o
// backend envia a lista exata (0-indexed), a apresentação decide como
// agrupar visualmente. Ex.: [2, 3, 4, 8] -> "3-5, 9" (convertido para 1-indexed).
function formatPageRanges(pages: number[]): string {
  if (pages.length === 0) return '';
  const sorted = [...pages].sort((a, b) => a - b);
  const ranges: string[] = [];
  let start = sorted[0];
  let prev = sorted[0];
  for (let i = 1; i <= sorted.length; i += 1) {
    const current = sorted[i];
    if (current === prev + 1) {
      prev = current;
      continue;
    }
    ranges.push(start === prev ? `${start + 1}` : `${start + 1}-${prev + 1}`);
    if (current !== undefined) {
      start = current;
      prev = current;
    }
  }
  return ranges.join(', ');
}

function formatSource(source: ChatSource): string {
  if (!source.pages || source.pages.length === 0) {
    return source.file;
  }
  return `${source.file} (p. ${formatPageRanges(source.pages)})`;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message, isUser, sources }) => {
  return (
    <div className={`flex mb-6 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-xs lg:max-w-md xl:max-w-lg px-4 py-3 ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-surface text-foreground border border-border'
        }`}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{message}</p>
        {!isUser && sources && sources.length > 0 && (
          <div className="mt-3 pt-2 border-t border-border text-xs text-muted-foreground">
            <span className="font-medium">Fontes: </span>
            {sources.map(formatSource).join(' · ')}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
