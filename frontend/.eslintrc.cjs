module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react-refresh"],
  ignorePatterns: ["dist", "node_modules", "*.cjs"],
  rules: {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "react-refresh/only-export-components": "off",
  },
  overrides: [
    {
      files: ["mock/**/*.mjs"],
      parserOptions: { ecmaVersion: "latest", sourceType: "module" },
      rules: { "@typescript-eslint/no-unused-vars": "off" },
    },
  ],
};
