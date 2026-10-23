/**
 * StockSense AI - Web Speech API Service
 * Handles speech-to-text (SpeechRecognition) and text-to-speech (SpeechSynthesis).
 */

// Declare browser SpeechRecognition types if missing in standard TS dom lib
declare global {
  interface Window {
    SpeechRecognition?: any;
    webkitSpeechRecognition?: any;
  }
}

export interface SpeechListenerCallbacks {
  onStart?: () => void;
  onInterim?: (interimText: string) => void;
  onResult: (finalText: string) => void;
  onError?: (errorMessage: string) => void;
  onEnd?: () => void;
}

class SpeechService {
  private recognition: any = null;
  private isListeningActive = false;
  private currentUtterance: SpeechSynthesisUtterance | null = null;

  constructor() {
    this.initRecognition();
  }

  private initRecognition() {
    const SpeechRecognitionClass =
      typeof window !== 'undefined'
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : null;

    if (SpeechRecognitionClass) {
      try {
        this.recognition = new SpeechRecognitionClass();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-IN'; // Default to Indian English for local grocery names & rupees
        this.recognition.maxAlternatives = 1;
      } catch (err) {
        console.warn('SpeechRecognition initialization error:', err);
      }
    }
  }

  public isRecognitionSupported(): boolean {
    return (
      typeof window !== 'undefined' &&
      (!!window.SpeechRecognition || !!window.webkitSpeechRecognition)
    );
  }

  public isSynthesisSupported(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window;
  }

  public startListening(callbacks: SpeechListenerCallbacks) {
    if (!this.isRecognitionSupported()) {
      callbacks.onError?.(
        'Speech recognition is not supported in this browser. You can type commands in the text box below.'
      );
      return;
    }

    // If already listening, stop first
    if (this.isListeningActive) {
      this.stopListening();
    }

    // Stop speaking if currently reading
    this.stopSpeaking();

    // Re-create instance to ensure fresh state
    this.initRecognition();
    if (!this.recognition) return;

    let finalTranscript = '';

    this.recognition.onstart = () => {
      this.isListeningActive = true;
      callbacks.onStart?.();
    };

    this.recognition.onresult = (event: any) => {
      let interimTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (interimTranscript) {
        callbacks.onInterim?.(interimTranscript);
      }

      if (finalTranscript) {
        callbacks.onResult(finalTranscript.trim());
      }
    };

    this.recognition.onerror = (event: any) => {
      this.isListeningActive = false;
      let msg = 'Voice recognition error';
      if (event.error === 'not-allowed' || event.error === 'permission-denied') {
        msg = 'Microphone permission was denied. Please allow microphone access in your browser address bar.';
      } else if (event.error === 'no-speech') {
        msg = 'No speech detected. Please press the microphone button and try speaking again.';
      } else if (event.error === 'network') {
        msg = 'Network issue during speech recognition. Please check your internet connection or type your command.';
      } else {
        msg = `Speech error: ${event.error}`;
      }
      callbacks.onError?.(msg);
    };

    this.recognition.onend = () => {
      this.isListeningActive = false;
      callbacks.onEnd?.();
    };

    try {
      this.recognition.start();
    } catch (err: any) {
      this.isListeningActive = false;
      callbacks.onError?.(err?.message || 'Could not start microphone listening.');
    }
  }

  public stopListening() {
    if (this.recognition && this.isListeningActive) {
      try {
        this.recognition.stop();
      } catch {
        // ignore
      }
      this.isListeningActive = false;
    }
  }

  public isListening(): boolean {
    return this.isListeningActive;
  }

  public speak(
    text: string,
    onStart?: () => void,
    onEnd?: () => void,
    onError?: (err: any) => void
  ) {
    if (!this.isSynthesisSupported()) return;

    this.stopSpeaking();

    // Clean text of markdown asterisks and backticks for clean audio speech
    const cleanSpeech = text
      .replace(/[*_#`~]/g, '')
      .replace(/₹/g, 'rupees ')
      .replace(/Rs\.?/gi, 'rupees ')
      .trim();

    if (!cleanSpeech) return;

    try {
      const utterance = new SpeechSynthesisUtterance(cleanSpeech);
      utterance.lang = 'en-IN';
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      // Select an Indian or clear English voice if available
      const voices = window.speechSynthesis.getVoices();
      const inVoice = voices.find(
        (v) => v.lang.includes('en-IN') || v.name.includes('India')
      );
      const enVoice = voices.find((v) => v.lang.startsWith('en'));
      if (inVoice) {
        utterance.voice = inVoice;
      } else if (enVoice) {
        utterance.voice = enVoice;
      }

      utterance.onstart = () => onStart?.();
      utterance.onend = () => {
        this.currentUtterance = null;
        onEnd?.();
      };
      utterance.onerror = (e) => {
        this.currentUtterance = null;
        onError?.(e);
      };

      this.currentUtterance = utterance;
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn('Speech synthesis error:', err);
      onError?.(err);
    }
  }

  public stopSpeaking() {
    if (this.isSynthesisSupported()) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore
      }
      this.currentUtterance = null;
    }
  }

  public isSpeaking(): boolean {
    return (
      typeof window !== 'undefined' &&
      'speechSynthesis' in window &&
      window.speechSynthesis.speaking
    );
  }
}

export const speechService = new SpeechService();
