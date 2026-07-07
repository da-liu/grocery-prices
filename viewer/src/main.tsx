import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "@/shared/styles/index.css";
import "@/shared/styles/utilities.css";
import App from "@/app/App";

function isInsideLightbox(target: EventTarget | null) {
  return target instanceof Element && Boolean(target.closest(".photo-lightbox-backdrop"));
}

function disablePinchZoom() {
  const block = (e: Event) => {
    if (isInsideLightbox(e.target)) return;
    e.preventDefault();
  };
  document.addEventListener("gesturestart", block, { passive: false });
  document.addEventListener("gesturechange", block, { passive: false });
  document.addEventListener("gestureend", block, { passive: false });
  document.addEventListener(
    "touchmove",
    (e) => {
      if (e.touches.length > 1 && !isInsideLightbox(e.target)) e.preventDefault();
    },
    { passive: false },
  );
}

disablePinchZoom();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
