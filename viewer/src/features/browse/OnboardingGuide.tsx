import { useEffect, useState } from "react";
import "./OnboardingGuide.css";

interface OnboardingGuideProps {
  onStartUpload: () => void;
  onDismiss: () => void;
}

interface OnboardingStep {
  title: string;
  body: string;
  images: string[] | null;
  imageAlt: string | null;
}

const STEPS: OnboardingStep[] = [
  {
    title: "Welcome to Grocery Prices",
    body: "Snap photos of store shelves to track prices, remember what things cost at different stores, and easily compare trends over time.",
    images: null,
    imageAlt: null,
  },
  {
    title: "Take a shelf photo",
    body: "Photograph the product and price tag together, like in the example above. GPS from the photo helps match the store.",
    images: [
      "/onboarding-shelf-sample.jpg",
      "/onboarding-shelf-sample-2.jpg",
    ],
    imageAlt: "Grocery shelf with product labels and price tags visible",
  },
  {
    title: "Vision extraction",
    body: "We read product names and prices with a vision model. This usually takes a few seconds.",
    images: ["/onboarding-vision-extraction.jpg"],
    imageAlt: null,
  },
  {
    title: "Your catalog",
    body: "Your products appear in Catalog. Search, filter, and sort to find what you need.",
    images: null,
    imageAlt: null,
  },
];

const CROSSFADE_HOLD_MS = 2000;

export function OnboardingGuide({ onStartUpload, onDismiss }: OnboardingGuideProps) {
  const [step, setStep] = useState(0);
  const [activeImage, setActiveImage] = useState(0);
  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];
  const images = current.images;

  useEffect(() => {
    setActiveImage(0);
    if (!images || images.length < 2) return;

    const id = window.setTimeout(() => {
      setActiveImage(1);
    }, CROSSFADE_HOLD_MS);

    return () => window.clearTimeout(id);
  }, [step, images]);

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className="onboarding-card">
        <p className="onboarding-eyebrow">Getting started · {step + 1} / {STEPS.length}</p>
        <h2 id="onboarding-title">{current.title}</h2>
        {images && images.length > 0 && (
          <figure className="onboarding-sample">
            <div className="onboarding-sample-stack">
              {images.map((src, idx) => (
                <img
                  key={src}
                  src={src}
                  alt={idx === activeImage ? (current.imageAlt ?? "") : ""}
                  className={idx === activeImage ? "is-active" : undefined}
                />
              ))}
            </div>
            <figcaption>Include the product name and shelf price tag in frame.</figcaption>
          </figure>
        )}
        <p className="onboarding-body">{current.body}</p>

        <div className="onboarding-dots" aria-hidden="true">
          {STEPS.map((_, idx) => (
            <span key={idx} className={idx === step ? "active" : undefined} />
          ))}
        </div>

        <div className="onboarding-actions">
          <button type="button" className="ghost" onClick={onDismiss}>
            Skip
          </button>
          {!isLast ? (
            <button type="button" onClick={() => setStep((s) => s + 1)}>
              Next
            </button>
          ) : (
            <button type="button" onClick={onStartUpload}>
              Upload first photo
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
