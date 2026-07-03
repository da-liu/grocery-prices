export type HeifImage = {
  get_width: () => number;
  get_height: () => number;
  display: (
    imageData: ImageData,
    callback: (data: ImageData | null) => void,
  ) => void;
};

export type LibheifModule = {
  HeifDecoder: new () => {
    decode: (buffer: ArrayBuffer) => HeifImage[];
  };
};

declare global {
  interface Window {
    libheif?: (opts: { wasmBinary: ArrayBuffer }) => LibheifModule;
  }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

let libheifPromise: Promise<LibheifModule> | null = null;

export function loadLibheif(): Promise<LibheifModule> {
  libheifPromise ??= (async () => {
    await loadScript("/libheif-official/libheif.js");
    if (!window.libheif) {
      throw new Error("libheif global not found after loading script");
    }
    const wasmRes = await fetch("/libheif-official/libheif.wasm");
    const wasmBinary = await wasmRes.arrayBuffer();
    return window.libheif({ wasmBinary });
  })();
  return libheifPromise;
}
