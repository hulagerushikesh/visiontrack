# VisionTrack design system

VisionTrack should feel like a precise, approachable research instrument: a
light-first canvas, clear indigo hierarchy, cyan/emerald data signals, hairline
boundaries, and compact monospace telemetry. Dark surfaces are reserved for
video, code, and live tracking stages where contrast carries meaning. The
product UI can be spacious; research tables can stay dense. Both should clearly
belong to the same system.

## Identity

- The tracking-reticle mark is the primary logo and favicon.
- `VisionTrack` is always written as one word with capital V and T.
- Indigo is the primary action and navigation color.
- Emerald represents a confirmed, actively tracked identity.
- Cyan distinguishes a second identity or comparison series; orange/red are
  reserved for warnings and negative findings.

## Interface rules

- Use warm white and pale slate for ordinary app surfaces; avoid site-wide dark
  mode. Use near-black graphite only for video, code, or telemetry stages.
- Gradients communicate hierarchy or data transition. Keep them within the
  indigo → cyan → emerald brand spectrum and never place body copy over a noisy
  gradient.
- Use rounded containers for product navigation and cards; use restrained
  radii and hairline rules for tables and research figures.
- Motion explains entry, hierarchy, or state. It must not delay access to
  content and must respect `prefers-reduced-motion`.
- Interactive targets retain visible keyboard focus and a minimum practical
  touch area of 40 pixels.
- Product copy leads with the outcome; implementation details follow.

## Migration boundary

React owns `/`, `/teaching`, and `/video`. Standalone experiences keep their
current structure until their behavior and progress-storage contracts have
equivalent React tests. Shared legacy tokens intentionally mirror the React
graphite/green palette during that transition.
