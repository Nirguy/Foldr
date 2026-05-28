"use client";

import { useState, useRef, useEffect, useCallback } from "react";

type Message = { role: "user" | "assistant"; text: string };

type ChatSession = {
  id: string;
  title: string;
  messages: Message[];
  fileName?: string;
  createdAt: number;
};

const STORAGE_KEY = "foldr-chats";

function loadChats(): ChatSession[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : [];
}

function saveChats(chats: ChatSession[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
}

function generateId() {
  return Math.random().toString(36).substring(2, 10);
}

export default function Home() {
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [input, setInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load chats from localStorage on mount
  useEffect(() => {
    const saved = loadChats();
    setChats(saved);
    if (saved.length > 0) {
      setActiveChatId(saved[0].id);
    }
  }, []);

  // Persist chats whenever they change
  useEffect(() => {
    if (chats.length > 0) {
      saveChats(chats);
    }
  }, [chats]);

  const activeChat = chats.find((c) => c.id === activeChatId) || null;
  const messages = activeChat?.messages || [];

  const startNewChat = useCallback(() => {
    const newChat: ChatSession = {
      id: generateId(),
      title: "New Chat",
      messages: [],
      createdAt: Date.now(),
    };
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    setFile(null);
    setInput("");
  }, []);

  const deleteChat = (id: string) => {
    setChats((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      saveChats(updated);
      return updated;
    });
    if (activeChatId === id) {
      setActiveChatId(chats.length > 1 ? chats.find((c) => c.id !== id)?.id || null : null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type === "application/pdf") {
      setFile(dropped);
      // Update active chat with file name
      if (activeChatId) {
        setChats((prev) =>
          prev.map((c) =>
            c.id === activeChatId ? { ...c, fileName: dropped.name } : c
          )
        );
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      if (activeChatId) {
        setChats((prev) =>
          prev.map((c) =>
            c.id === activeChatId ? { ...c, fileName: selected.name } : c
          )
        );
      }
    }
  };

  const handleSend = () => {
    if (!input.trim()) return;

    // If no active chat, create one
    let chatId = activeChatId;
    if (!chatId) {
      const newChat: ChatSession = {
        id: generateId(),
        title: input.trim().slice(0, 40),
        messages: [],
        fileName: file?.name,
        createdAt: Date.now(),
      };
      setChats((prev) => [newChat, ...prev]);
      chatId = newChat.id;
      setActiveChatId(chatId);
    }

    const userMsg: Message = { role: "user", text: input };
    const assistantMsg: Message = {
      role: "assistant",
      text: "Analysis coming soon — backend not connected yet.",
    };

    setChats((prev) =>
      prev.map((c) => {
        if (c.id !== chatId) return c;
        const updated = {
          ...c,
          messages: [...c.messages, userMsg, assistantMsg],
          // Set title from first message if still default
          title: c.messages.length === 0 ? input.trim().slice(0, 40) : c.title,
        };
        return updated;
      })
    );
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? "w-64" : "w-0"
        } transition-all duration-200 bg-gray-900 border-r border-gray-800 flex flex-col overflow-hidden`}
      >
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
            Chats
          </h2>
          <button
            onClick={startNewChat}
            className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors"
            aria-label="New chat"
          >
            + New
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto p-2 space-y-1">
          {chats.map((chat) => (
            <div
              key={chat.id}
              className={`group flex items-center gap-2 rounded-lg px-3 py-2 cursor-pointer text-sm transition-colors ${
                chat.id === activeChatId
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-200"
              }`}
              onClick={() => setActiveChatId(chat.id)}
            >
              <span className="flex-1 truncate">{chat.title}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteChat(chat.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity"
                aria-label={`Delete chat: ${chat.title}`}
              >
                ✕
              </button>
            </div>
          ))}
          {chats.length === 0 && (
            <p className="text-gray-600 text-xs text-center mt-4">
              No chats yet. Start a new one!
            </p>
          )}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-gray-800">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-gray-400 hover:text-white transition-colors"
            aria-label="Toggle sidebar"
          >
            ☰
          </button>
          <h1 className="text-lg font-bold tracking-tight">Foldr</h1>
          {activeChat?.fileName && (
            <span className="text-xs text-gray-500 ml-auto">
              📄 {activeChat.fileName}
            </span>
          )}
        </header>

        {/* Chat area */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 gap-6 max-w-3xl mx-auto w-full overflow-y-auto">
          {!activeChat ? (
            <>
              <p className="text-gray-400 text-center">
                Upload an academic article and chat about it. We&apos;ll critique it for you.
              </p>
              <button
                onClick={startNewChat}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 font-medium transition-colors"
              >
                Start a new chat
              </button>
            </>
          ) : (
            <>
              {/* Upload Area */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`w-full border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                  isDragging
                    ? "border-blue-500 bg-blue-500/10"
                    : file || activeChat.fileName
                    ? "border-green-500 bg-green-500/10"
                    : "border-gray-700 hover:border-gray-500"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={handleFileSelect}
                  className="hidden"
                  aria-label="Upload PDF article"
                />
                {file || activeChat.fileName ? (
                  <p className="text-green-400 font-medium text-sm">
                    📄 {file?.name || activeChat.fileName}
                  </p>
                ) : (
                  <p className="text-gray-500 text-sm">
                    Drag &amp; drop a PDF here, or click to browse
                  </p>
                )}
              </div>

              {/* Chat Messages */}
              {messages.length > 0 && (
                <div className="w-full flex flex-col gap-3 max-h-96 overflow-y-auto rounded-lg bg-gray-900/50 p-4">
                  {messages.map((msg, i) => (
                    <div
                      key={i}
                      className={`rounded-lg px-4 py-2 max-w-[80%] ${
                        msg.role === "user"
                          ? "self-end bg-blue-600 text-white"
                          : "self-start bg-gray-800 text-gray-200"
                      }`}
                    >
                      {msg.text}
                    </div>
                  ))}
                </div>
              )}

              {/* Chat Input */}
              <div className="w-full flex gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask something about the article..."
                  rows={1}
                  className="flex-1 resize-none rounded-lg bg-gray-900 border border-gray-700 px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
                  aria-label="Chat message input"
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="px-5 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed font-medium transition-colors"
                >
                  Send
                </button>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
