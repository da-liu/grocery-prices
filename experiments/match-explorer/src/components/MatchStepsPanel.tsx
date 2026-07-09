import type { MatchDetail, ProductRecord } from "@/lib/types";
import { formatScore, tierLabel } from "@/lib/matching";

export function MatchStepsPanel({
  detail,
  source,
  target,
}: {
  detail: MatchDetail;
  source?: ProductRecord;
  target?: ProductRecord;
}) {
  return (
    <div className="match-steps">
      <div className="match-steps-header">
        <div>
          <strong>Final score:</strong> {formatScore(detail.final_score)}
        </div>
        <div>
          <strong>Path:</strong> {tierLabel(detail.tier)}
        </div>
        {detail.skip_reason && (
          <div>
            <strong>Skip reason:</strong> {detail.skip_reason}
          </div>
        )}
      </div>
      {(source || target) && (
        <div className="match-pair-labels">
          {source && (
            <div>
              <span className="label">Source</span> {source.product_name} ({source.image_id})
            </div>
          )}
          {target && (
            <div>
              <span className="label">Target</span> {target.product_name} ({target.image_id})
            </div>
          )}
        </div>
      )}
      <ol className="steps-list">
        {detail.steps.map((step) => (
          <li key={step.id}>
            <span className="step-label">{step.label}</span>
            <span className="step-value">{formatStepValue(step.value)}</span>
            {step.note && <span className="step-note">{step.note}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

function formatStepValue(value: string | number | boolean | null): string {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return value.toFixed(4).replace(/\.?0+$/, "");
  return value;
}
