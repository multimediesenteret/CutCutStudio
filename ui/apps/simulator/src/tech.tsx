import { StudioContext } from "@cutcut/client";
import "@cutcut/design/tokens.css";
import "@cutcut/design/components.css";
import "@cutcut/tech/tech.css";
import { App } from "@cutcut/tech/App";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { simForScreen } from "./shared";

const root = document.getElementById("root");
void simForScreen().then(({ store, transport }) => {
  if (!root) return;
  createRoot(root).render(
    <StrictMode>
      <StudioContext value={{ store, transport }}>
        <App />
      </StudioContext>
    </StrictMode>,
  );
});
