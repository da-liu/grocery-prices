## Model Price Comparison

All prices are in USD per 1M tokens unless noted otherwise.

| Model | Pricing Scope | Input | Output | Cache / Context Price | Cache Storage | Notes |
| :---- | :------------ | :---- | :----- | :-------------------- | :------------ | :---- |
| `qwen3.7-plus` | Input <= 256k | $0.40 | $1.60 | Implicit hit: $0.08; explicit cache creation: $0.50; explicit cache hit: $0.04 | Not listed in source note | Tiered pricing based on input size |
| `qwen3.7-plus` | 256k < Input <= 1m | $1.20 | $4.80 | Implicit hit: $0.24; explicit cache creation: $1.50; explicit cache hit: $0.12 | Not listed in source note | Much more expensive for long-context requests |
| `gemini-3.1-flash-lite` | Text / image / video | $0.25 | $1.50 | $0.025 | $1.00 / 1,000,000 tokens per hour | Cheapest input of the three for multimodal non-audio usage |
| `glm-4.6v` | Vision | $0.30 | $0.90 | Cached input: $0.05 | Limited-time Free | Cheapest output of the three |
