// Use CommonJS requires so Jest can load this setup file in a CJS environment
require('@testing-library/jest-dom')

// Optional: set up any global mocks or polyfills here

// Mock next/image to avoid DOM errors in Jest
jest.mock('next/image', () => ({
  __esModule: true,
  default: (props) => {
    // eslint-disable-next-line react/prop-types
    return require('react').createElement('img', props)
  }
}))
