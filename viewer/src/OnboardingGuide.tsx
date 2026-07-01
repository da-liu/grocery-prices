import { useState } from "react";

interface OnboardingGuideProps {
  onStartUpload: () => void;
  onDismiss: () => void;
}

const STEPS = [
  {
    title: "Welcome to Grocery Prices",
    body: "Track shelf prices from your own photos. Each account has a private catalog.",
    image: null,
    imageAlt: null,
  },
  {
    title: "Take a shelf photo",
    body: "Photograph the product label and price tag together, like in the example below. GPS from the photo helps match the store.",
    image: "/onboarding-shelf-sample.jpg",
    imageAlt: "Grocery shelf with product labels and price tags visible",
  },
  {
    title: "Vision extraction",
    body: "We read product names and prices with a vision model. This usually takes 30-60 seconds.",
    image: null,
    imageAlt: null,
  },
  {
    title: "Browse your prices",
    body: "Your products appear on Browse. Compare the same item across stores over time on Compare.",
    image: null,
    imageAlt: null,
  },
];

export function OnboardingGuide({ onStartUpload, onDismiss }: OnboardingGuideProps) {
  const [step, setStep] = useState(0);
  const isLast = step === STEPS.length - 1;
  const current = STEPS[step];

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className="onboarding-card">
        <p className="onboarding-eyebrow">Getting started · {step + 1} / {STEPS.length}</p>
        <h2 id="onboarding-title">{current.title}</h2>
        {current.image && (
          <figure className="onboarding-sample">
            <img src={current.image} alt={current.imageAlt ?? ""} />
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
