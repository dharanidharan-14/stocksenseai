/**
 * StockSense AI - Voice-Controlled Inventory Assistant Page
 * Modern, responsive interface with Web Speech STT, SpeechSynthesis TTS,
 * conversation history, live transcription, and confirmation gating for stock mutations.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  RotateCcw,
  AlertCircle,
  CheckCircle2,
  Package,
  Layers,
  TrendingUp,
  BrainCircuit,
  Calendar,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Loader2,
  Info,
  DollarSign,
} from 'lucide-react';
import { AssistantChatMessage, AssistantResponse, Product } from '../types';
import { api } from '../services/api';
import { speechService } from '../services/speech';

interface VoiceAssistantPageProps {
  products: Product[];
  onNavigateTab: (tab: any) => void;
  onDataChanged: () => void;
}

export const VoiceAssistantPage: React.FC<VoiceAssistantPageProps> = ({
  products,
  onNavigateTab,
  onDataChanged,
}) => {
  const [sessionId] = useState(() => 'stocksense_session_' + Math.random().toString(36).substring(2, 10));
  const [messages, setMessages] = useState<AssistantChatMessage[]>(() => {
    return [
      {
        id: 'welcome-1',
        sender: 'assistant',
        text: 'வணக்கம்! நான் உங்கள் StockSense AI Inventory Assistant. Ask me in English, தமிழ், or Tanglish about your stock, expiring batches, sales performance, or tell me to record sales and stock receipts.',
        speechText:
          'Hello! I am your StockSense AI Assistant. How can I help with your inventory today? Neengal Tamil alladhu Englishil kekkalaam.',
        timestamp: new Date(),
        suggestions: [
          'Tomato stock la evlo irukku?',
          'How much rice stock is left?',
          'Innaiku sales evlo?',
          'Which products expire tomorrow?',
          'Record a sale of 2 milk packets',
          '2000 rooba budget la enna vaanganum?',
        ],
      },
    ];
  });

  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [micError, setMicError] = useState<string | null>(null);
  const [autoSpeak, setAutoSpeak] = useState(true);

  // Active pending confirmation action
  const [pendingConfirmation, setPendingConfirmation] = useState<{
    messageId: string;
    payload: any;
    prompt: string;
  } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionSupported = speechService.isRecognitionSupported();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, liveTranscript, isLoading]);

  // Handle Voice Toggle
  const toggleListening = () => {
    if (isListening) {
      speechService.stopListening();
      setIsListening(false);
      setLiveTranscript('');
    } else {
      setMicError(null);
      setLiveTranscript('');
      speechService.startListening({
        onStart: () => {
          setIsListening(true);
          setMicError(null);
        },
        onInterim: (interim) => {
          setLiveTranscript(interim);
        },
        onResult: (finalText) => {
          setIsListening(false);
          setLiveTranscript('');
          handleSendCommand(finalText);
        },
        onError: (err) => {
          setIsListening(false);
          setMicError(err);
        },
        onEnd: () => {
          setIsListening(false);
        },
      });
    }
  };

  // Handle Stop Speaking
  const handleStopSpeaking = () => {
    speechService.stopSpeaking();
    setIsSpeaking(false);
  };

  // Speak a message
  const handleSpeakText = (text: string) => {
    speechService.stopSpeaking();
    speechService.speak(
      text,
      () => setIsSpeaking(true),
      () => setIsSpeaking(false),
      () => setIsSpeaking(false)
    );
  };

  // Process Command (typed or spoken)
  const handleSendCommand = async (command: string) => {
    const trimmed = command.trim();
    if (!trimmed || isLoading) return;

    // Add user message
    const userMsgId = 'user-' + Date.now();
    const userMsg: AssistantChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsLoading(true);
    setMicError(null);

    try {
      const response: AssistantResponse = await api.sendAssistantCommand(
        trimmed,
        false,
        undefined,
        sessionId
      );

      const assistantMsgId = 'asst-' + Date.now();
      const assistantMsg: AssistantChatMessage = {
        id: assistantMsgId,
        sender: 'assistant',
        text: response.display_text,
        speechText: response.speech_text,
        intent: response.intent,
        data: response.data,
        requiresConfirmation: response.requires_confirmation,
        actionPayload: response.action_payload,
        error: response.error,
        suggestions: response.suggestions,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // If response is a cancellation, clear any active confirmation card
      if (response.intent === 'CANCELLATION') {
        setPendingConfirmation(null);
      } else if (response.requires_confirmation && response.action_payload) {
        // If requires confirmation or was updated via correction
        setPendingConfirmation({
          messageId: assistantMsgId,
          payload: response.action_payload,
          prompt: response.speech_text,
        });
      } else if (response.intent === 'RECORD_SALE' || response.intent === 'RECEIVE_STOCK') {
        // Was confirmed via spoken turn ("Aama, confirm pannu")
        setPendingConfirmation(null);
        onDataChanged();
      }

      // Read aloud if enabled
      if (autoSpeak && response.speech_text) {
        handleSpeakText(response.speech_text);
      }
    } catch (err: any) {
      const errMsg: AssistantChatMessage = {
        id: 'err-' + Date.now(),
        sender: 'assistant',
        text: 'Sorry, I encountered an error communicating with the inventory backend.',
        speechText: 'An error occurred while retrieving inventory data.',
        error: err?.message,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // Confirm pending action (e.g. sale or stock receipt)
  const handleConfirmAction = async (confirmed: boolean) => {
    if (!pendingConfirmation) return;

    if (!confirmed) {
      // User cancelled via UI button
      setPendingConfirmation(null);
      try {
        await api.sendAssistantCommand('cancel', false, undefined, sessionId);
      } catch (e) {
        // ignore
      }
      const cancelMsg: AssistantChatMessage = {
        id: 'cancel-' + Date.now(),
        sender: 'assistant',
        text: 'Action cancelled. No changes were made to inventory or sales ledger.',
        speechText: 'Action cancelled.',
        timestamp: new Date(),
        suggestions: ['How much rice stock is left?', 'What should I reorder today?'],
      };
      setMessages((prev) => [...prev, cancelMsg]);
      if (autoSpeak) handleSpeakText('Action cancelled.');
      return;
    }

    // User confirmed!
    setIsLoading(true);
    try {
      const response = await api.sendAssistantCommand(
        'confirm',
        true,
        pendingConfirmation.payload,
        sessionId
      );

      const confirmedMsg: AssistantChatMessage = {
        id: 'conf-' + Date.now(),
        sender: 'assistant',
        text: response.display_text,
        speechText: response.speech_text,
        intent: response.intent,
        data: response.data,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, confirmedMsg]);
      setPendingConfirmation(null);

      // Trigger refresh in parent
      onDataChanged();

      if (autoSpeak && response.speech_text) {
        handleSpeakText(response.speech_text);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: 'err-' + Date.now(),
          sender: 'assistant',
          text: `Failed to execute action: ${err?.message}`,
          speechText: 'Failed to execute the transaction.',
          error: err?.message,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      {/* Header bar */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '12px 12px 0 0',
          border: '1px solid #e5e7eb',
          borderBottom: 'none',
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: '#0891b2',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 4px rgba(8, 145, 178, 0.25)',
            }}
          >
            <Sparkles size={22} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#111827', margin: 0 }}>
              Voice Inventory Assistant
            </h2>
            <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>
              Real-time conversational control backed by live PostgreSQL inventory & FEFO ledger
            </p>
          </div>
        </div>

        {/* Controls: Auto-speech toggle & Stop speaking button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isSpeaking && (
            <button
              onClick={handleStopSpeaking}
              className="btn btn-secondary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                background: '#fee2e2',
                color: '#b91c1c',
                borderColor: '#fca5a5',
                fontSize: '0.82rem',
                fontWeight: 600,
              }}
              title="Stop audio playback"
            >
              <VolumeX size={15} />
              <span>Stop Speaking</span>
            </button>
          )}

          <button
            onClick={() => setAutoSpeak(!autoSpeak)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #e5e7eb',
              background: autoSpeak ? '#f0fdfa' : '#f9fafb',
              color: autoSpeak ? '#0f766e' : '#6b7280',
              fontSize: '0.82rem',
              fontWeight: 500,
              cursor: 'pointer',
            }}
            title={autoSpeak ? 'Text-to-speech enabled' : 'Text-to-speech muted'}
          >
            {autoSpeak ? <Volume2 size={15} /> : <VolumeX size={15} />}
            <span>{autoSpeak ? 'Audio On' : 'Muted'}</span>
          </button>
        </div>
      </div>

      {/* Messages Stream Container */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          background: '#f9fafb',
          borderLeft: '1px solid #e5e7eb',
          borderRight: '1px solid #e5e7eb',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.sender === 'user' ? 'flex-end' : 'flex-start',
              width: '100%',
            }}
          >
            {/* Message Bubble */}
            <div
              style={{
                maxWidth: '82%',
                borderRadius: msg.sender === 'user' ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                padding: '14px 18px',
                background: msg.sender === 'user' ? '#0891b2' : '#ffffff',
                color: msg.sender === 'user' ? '#ffffff' : '#111827',
                border: msg.sender === 'user' ? 'none' : '1px solid #e5e7eb',
                boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                fontSize: '0.92rem',
                lineHeight: 1.5,
              }}
            >
              {/* Header badge if assistant */}
              {msg.sender === 'assistant' && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', borderBottom: '1px solid #f3f4f6', paddingBottom: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0891b2', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {msg.intent ? msg.intent.replace(/_/g, ' ') : 'StockSense AI'}
                    </span>
                  </div>
                  {msg.speechText && (
                    <button
                      onClick={() => handleSpeakText(msg.speechText!)}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#6b7280',
                        padding: '2px 4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                      }}
                      title="Read aloud"
                    >
                      <Volume2 size={13} />
                      <span>Speak</span>
                    </button>
                  )}
                </div>
              )}

              {/* Main text content with markdown-like formatting */}
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {msg.text}
              </div>

              {/* Structured Card: Single Product Stock Info */}
              {msg.data && msg.data.product_name && msg.data.usable_stock !== undefined && (
                <div
                  style={{
                    marginTop: '12px',
                    padding: '12px',
                    background: '#f8fafc',
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: '#1e293b' }}>
                      {msg.data.product_name}
                    </span>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '9999px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        background:
                          msg.data.status === 'In stock'
                            ? '#dcfce7'
                            : msg.data.status === 'Low stock'
                            ? '#fef3c7'
                            : '#fee2e2',
                        color:
                          msg.data.status === 'In stock'
                            ? '#15803d'
                            : msg.data.status === 'Low stock'
                            ? '#b45309'
                            : '#b91c1c',
                      }}
                    >
                      {msg.data.status}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginTop: '10px' }}>
                    <div style={{ background: '#ffffff', padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Usable Stock</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>
                        {msg.data.usable_stock} <span style={{ fontSize: '0.75rem' }}>{msg.data.unit}s</span>
                      </div>
                    </div>
                    <div style={{ background: '#ffffff', padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Total in Batches</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>
                        {msg.data.total_stock} <span style={{ fontSize: '0.75rem' }}>{msg.data.unit}s</span>
                      </div>
                    </div>
                    <div style={{ background: '#ffffff', padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Reorder Threshold</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>
                        {msg.data.reorder_threshold} <span style={{ fontSize: '0.75rem' }}>{msg.data.unit}s</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ marginTop: '8px', textAlign: 'right' }}>
                    <button
                      onClick={() => onNavigateTab('inventory')}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#0891b2',
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      View Batches in Ledger <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              )}

              {/* Structured Card: List of Batches (Expiring / Expired) */}
              {Array.isArray(msg.data) && msg.data.length > 0 && msg.data[0].batch_number && (
                <div style={{ marginTop: '12px', overflowX: 'auto' }}>
                  <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse', background: '#ffffff', borderRadius: '6px', overflow: 'hidden', border: '1px solid #e5e7eb' }}>
                    <thead style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
                      <tr>
                        <th style={{ padding: '8px 10px' }}>Product</th>
                        <th style={{ padding: '8px 10px' }}>Batch</th>
                        <th style={{ padding: '8px 10px' }}>Qty</th>
                        <th style={{ padding: '8px 10px' }}>Expiry</th>
                        <th style={{ padding: '8px 10px' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {msg.data.map((b: any, idx: number) => (
                        <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 10px', fontWeight: 600 }}>{b.product_name}</td>
                          <td style={{ padding: '8px 10px', color: '#64748b' }}><code>{b.batch_number}</code></td>
                          <td style={{ padding: '8px 10px', fontWeight: 600 }}>{b.quantity} {b.unit}</td>
                          <td style={{ padding: '8px 10px' }}>{b.expiry_date}</td>
                          <td style={{ padding: '8px 10px' }}>
                            <span style={{
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              background: b.status === 'Expired' ? '#fee2e2' : '#fef3c7',
                              color: b.status === 'Expired' ? '#b91c1c' : '#b45309',
                            }}>
                              {b.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Confirmation card if pending on this message */}
              {pendingConfirmation && pendingConfirmation.messageId === msg.id && (
                <div
                  style={{
                    marginTop: '14px',
                    padding: '16px',
                    background: '#fffbeb',
                    borderRadius: '8px',
                    border: '1px solid #fde68a',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#92400e', fontWeight: 700, fontSize: '0.9rem', marginBottom: '8px' }}>
                    <ShieldAlert size={18} />
                    <span>Inventory Action Requires Confirmation</span>
                  </div>
                  <p style={{ fontSize: '0.84rem', color: '#78350f', margin: '0 0 14px 0' }}>
                    Stock mutations and financial transactions are irreversible in the audit log. Do you want to proceed?
                  </p>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                      onClick={() => handleConfirmAction(true)}
                      className="btn"
                      style={{
                        background: '#0891b2',
                        color: '#ffffff',
                        border: 'none',
                        padding: '8px 16px',
                        borderRadius: '6px',
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <CheckCircle2 size={16} />
                      <span>Confirm & Execute</span>
                    </button>
                    <button
                      onClick={() => handleConfirmAction(false)}
                      className="btn btn-secondary"
                      style={{
                        padding: '8px 14px',
                        borderRadius: '6px',
                        fontSize: '0.85rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Suggestions Chips */}
            {msg.suggestions && msg.suggestions.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px', maxWidth: '85%' }}>
                {msg.suggestions.map((sug, i) => (
                  <button
                    key={i}
                    onClick={() => handleSendCommand(sug)}
                    style={{
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: '9999px',
                      padding: '4px 12px',
                      fontSize: '0.78rem',
                      color: '#0891b2',
                      cursor: 'pointer',
                      fontWeight: 500,
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = '#0891b2';
                      e.currentTarget.style.background = '#f0fdfa';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = '#cbd5e1';
                      e.currentTarget.style.background = '#ffffff';
                    }}
                  >
                    "{sug}"
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Live Speech Recognition Transcription Banner */}
        {isListening && (
          <div
            style={{
              padding: '12px 18px',
              borderRadius: '8px',
              background: '#ecfeff',
              border: '1px dashed #06b6d4',
              color: '#0e7490',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              animation: 'pulse 1.5s infinite',
            }}
          >
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: '#ef4444',
                boxShadow: '0 0 8px #ef4444',
              }}
            />
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Listening to your voice...
              </div>
              <div style={{ fontSize: '0.95rem', fontWeight: 500, color: '#164e63' }}>
                {liveTranscript || 'Speak clearly into your microphone...'}
              </div>
            </div>
          </div>
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#6b7280', fontSize: '0.85rem', padding: '8px 12px' }}>
            <Loader2 size={18} style={{ animation: 'spin 1s linear infinite', color: '#0891b2' }} />
            <span>Consulting PostgreSQL inventory database...</span>
          </div>
        )}

        {/* Microphone Error Warning */}
        {micError && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '8px',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#991b1b',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '0.82rem',
            }}
          >
            <AlertCircle size={16} />
            <span>{micError}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input controls container */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '0 0 12px 12px',
          border: '1px solid #e5e7eb',
          borderTop: 'none',
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        {/* Quick Suggestion Prompts */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
          <span style={{ fontSize: '0.72rem', color: '#6b7280', fontWeight: 600, whiteSpace: 'nowrap' }}>
            Try asking:
          </span>
          {[
            'How much rice stock is left?',
            'Which products expire tomorrow?',
            'Show products expiring in the next seven days',
            'Record a sale of 2 milk packets',
            'We received 20 biscuit packets',
            'What should I reorder today?',
            'Recommend purchases within my 2,000 rupee budget',
            'How much did I sell today?',
            'Which products are running low?',
          ].map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleSendCommand(prompt)}
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.75rem',
                color: '#334155',
                whiteSpace: 'nowrap',
                cursor: 'pointer',
              }}
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* Form with Mic and Text Input */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendCommand(inputText);
          }}
          style={{ display: 'flex', alignItems: 'center', gap: '10px' }}
        >
          {/* Large Microphone Button */}
          <button
            type="button"
            onClick={toggleListening}
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '50%',
              border: 'none',
              background: isListening ? '#ef4444' : '#0891b2',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: isListening
                ? '0 0 12px rgba(239, 68, 68, 0.5)'
                : '0 2px 4px rgba(8, 145, 178, 0.25)',
              transition: 'all 0.2s ease',
              flexShrink: 0,
            }}
            title={
              recognitionSupported
                ? isListening
                  ? 'Stop listening'
                  : 'Start voice input (Click and speak)'
                : 'Speech recognition not supported in this browser'
            }
          >
            {isListening ? <MicOff size={22} /> : <Mic size={22} />}
          </button>

          {/* Text Input */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={
              isListening
                ? 'Listening to your microphone...'
                : 'Ask a question or type a command (e.g. "How much rice stock is left?")...'
            }
            disabled={isListening || isLoading}
            style={{
              flex: 1,
              height: '46px',
              borderRadius: '8px',
              border: '1px solid #d1d5db',
              padding: '0 16px',
              fontSize: '0.92rem',
              outline: 'none',
              color: '#111827',
              background: '#ffffff',
            }}
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={!inputText.trim() || isLoading || isListening}
            className="btn"
            style={{
              height: '46px',
              padding: '0 18px',
              borderRadius: '8px',
              background: !inputText.trim() || isLoading ? '#9ca3af' : '#0891b2',
              color: '#ffffff',
              border: 'none',
              cursor: !inputText.trim() || isLoading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 600,
              fontSize: '0.88rem',
              flexShrink: 0,
            }}
          >
            <Send size={16} />
            <span>Send</span>
          </button>
        </form>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: '#9ca3af' }}>
          <span>
            {recognitionSupported
              ? 'Web Speech API active • Press microphone icon and speak clearly in English or Hinglish'
              : 'Web Speech API unavailable in this browser • Type commands in text box'}
          </span>
          <span>StockSense AI v1.0</span>
        </div>
      </div>
    </div>
  );
};
