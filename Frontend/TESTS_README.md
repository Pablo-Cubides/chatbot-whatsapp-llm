Running frontend tests (Jest + React Testing Library)

Prerequisites
- Node 18+ and npm 9+
- From `Frontend/` run:

  npm install

Install (if not already present) dev dependencies for TypeScript + Jest support:

  npm install --save-dev jest @types/jest ts-jest @testing-library/react @testing-library/jest-dom jest-environment-jsdom identity-obj-proxy

Run tests:

  npm test

Run tests in watch mode:

  npm run test:watch

Notes
- The project includes a minimal `jest.config.js` and `jest.setup.js` to mock `next/image` and configure `@testing-library/jest-dom`.
- Tests live in `src/__tests__/` and use path aliases `@/` mapped to `src/` in the Jest config.
- If you prefer Vitest/Playwright for e2e, we can add Playwright-based E2E tests later.
