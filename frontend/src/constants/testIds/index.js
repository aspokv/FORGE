// constants/testIds/ — central registry of data-testid values.
// Structure: each feature lives in its own file and is re-exported from here.
//
// Adding a new feature:
//   1. Create constants/testIds/<feature>.js
//   2. Export named objects (e.g. `export const PROFILE = { ... }`)
//   3. Re-export here: `export * from './<feature>';`

export * from './auth';
export * from './home';
