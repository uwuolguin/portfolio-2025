import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: ["**/libs/**", "**/*.min.js"],
  },
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        DOMPurify: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "error",
      "no-useless-escape": "warn",
      "no-useless-catch": "warn",
    },
  },
];