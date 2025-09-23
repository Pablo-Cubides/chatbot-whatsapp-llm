module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    "^.+\\.(css|less|scss|sass)$": "identity-obj-proxy"
  },
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', { tsconfig: '<rootDir>/tsconfig.jest.json' }]
  },
  // By default node_modules is ignored by transformers. If some packages ship ESM or
  // need transformation, add them to transformIgnorePatterns or list exceptions.
  transformIgnorePatterns: ['/node_modules/(?!(some-esm-package)/)'],
  testPathIgnorePatterns: ['/node_modules/', '/.next/']
}
