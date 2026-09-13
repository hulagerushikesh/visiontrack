# VisionTrack design system

VisionTrack should feel like a precise tracking instrument: quiet graphite
surfaces, signal-green identity marks, hairline boundaries, and compact
monospace telemetry. The product UI can be spacious; research tables can stay
dense. Both should clearly belong to the same system.

## Identity

- The tracking-reticle mark is the primary logo and favicon.
- `VisionTrack` is always written as one word with capital V and T.
- Signal green represents a confirmed, actively tracked identity.
- Cyan may distinguish a second identity or comparison series; orange/red are
  reserved for warnings and negative findings.

## Interface rules

- Use near-black graphite rather than pure black for app surfaces.
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
