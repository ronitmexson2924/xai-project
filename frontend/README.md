# frontend/ (owner: Mit)

Adaptive learning Next.js web application for the **Psychometric Concept-Graph Explanation-Feedback Engine**.

## Stack
- Next.js (App Router, TypeScript)
- Tailwind CSS
- ESLint
- OpenAPI TypeScript client (`openapi-typescript`)

## Scripts
- `npm run dev`: start local Next.js dev server on http://localhost:3000
- `npm run build`: production build
- `npm run lint`: run ESLint
- `npm run gen:api`: regenerate `src/lib/api.d.ts` from backend `/openapi.json`
- `npm run test:unit`: unit tests for the learner-facing copy and the code highlighter (`node --test`)

## Design tokens and theme
Colours, radii and shadows are CSS variables in `src/app/globals.css` (light, dark, and a manual
`data-theme` override set from the account menu). Roles: indigo `primary` is the app, apricot
`accent` marks moments about the learner (at most one per screen), green is "correct", blue/orange
show a chart's direction only, red `danger` is for real errors only.

## ENGAGEMENT_UI
`NEXT_PUBLIC_ENGAGEMENT_UI=true` at build time turns on the warmer extras: greeting by name, the
"thinking about you" loading line, result moments (including "you beat the prediction"), the
animated mastery meter, the session strip and recap (every `NEXT_PUBLIC_RECAP_EVERY` answers,
default 5) and the second-person model panel. It is off by default so every study arm sees the
same app. With it off, the learner sees the same screens and copy as before apart from fixes that
apply to everyone (colours, the sticky Continue bar, the revealed correct option, clearer DiCE
wording for recency). It changes presentation only, never what the backend computes or records. See `src/lib/engagement.ts` and `src/lib/moments.ts`.
