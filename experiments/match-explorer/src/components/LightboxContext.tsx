import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { PhotoLightbox } from "@/components/PhotoLightbox";

interface LightboxState {
  src: string;
  alt: string;
}

interface LightboxContextValue {
  openLightbox: (src: string, alt: string) => void;
  closeLightbox: () => void;
}

const LightboxContext = createContext<LightboxContextValue | null>(null);

export function LightboxProvider({ children }: { children: ReactNode }) {
  const [lightbox, setLightbox] = useState<LightboxState | null>(null);

  const openLightbox = useCallback((src: string, alt: string) => {
    setLightbox({ src, alt });
  }, []);

  const closeLightbox = useCallback(() => {
    setLightbox(null);
  }, []);

  const value = useMemo(
    () => ({ openLightbox, closeLightbox }),
    [openLightbox, closeLightbox],
  );

  return (
    <LightboxContext.Provider value={value}>
      {children}
      {lightbox && (
        <PhotoLightbox src={lightbox.src} alt={lightbox.alt} onClose={closeLightbox} />
      )}
    </LightboxContext.Provider>
  );
}

export function useLightbox(): LightboxContextValue {
  const ctx = useContext(LightboxContext);
  if (!ctx) {
    throw new Error("useLightbox must be used within LightboxProvider");
  }
  return ctx;
}
