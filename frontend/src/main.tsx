import "@atlaskit/css-reset";
import { setGlobalTheme } from "@atlaskit/tokens/set-global-theme";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Atlassian Design System themes: colour follows the OS light/dark setting;
// spacing, typography and shape tokens come from the same theme set.
setGlobalTheme({
  colorMode: "auto",
  light: "light",
  dark: "dark",
  spacing: "spacing",
  typography: "typography",
  shape: "shape",
}).finally(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
