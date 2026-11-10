---
name: frontend-stack
description: Use when changing React, TypeScript, Vite, Tailwind, Zustand, renderer IPC contracts, or frontend tests in Gigma Work.
---

# Frontend stack

Use the existing React 19, TypeScript, Vite, Tailwind CSS, and Zustand architecture. Keep renderer code behind `src/platform/gigma-api.ts` and `src/platform/tauri.ts`. Do not call Tauri `invoke` directly from page components.

## Working sequence

1. Read the current component, store, API contract, and related i18n messages.
2. Keep state ownership explicit. Local view state belongs in the component. Cross-view state belongs in the existing Zustand store.
3. Add user-visible copy to the English and Russian message maps. Do not introduce a new language surface.
4. Preserve the existing design tokens and shared UI controls. Reuse `components/ui` instead of creating native lookalikes.
5. Run `npm run typecheck`, the focused script or test, and `npm run build:renderer` when the render path changes.

## TypeScript boundary

Define stable request and response shapes in `src/platform/gigma-api.ts` before wiring a new command. Keep nullable, error, loading, and cancellation states explicit. Prefer discriminated unions over stringly typed status objects.

## Sources

- Vite's official React TypeScript scaffold and supported templates https://github.com/vitejs/vite/tree/main/packages/create-vite
- React's TypeScript guidance https://github.com/reactjs/react.dev/blob/main/src/content/learn/typescript.md
- Tailwind's official Vite plugin guidance https://github.com/tailwindlabs/tailwindcss/tree/main/packages/%40tailwindcss-vite
- Tauri's React template family https://github.com/tauri-apps/create-tauri-app

These sources define the scaffold and type-boundary baseline. Project behavior remains governed by the existing Gigma Work components and tests.
