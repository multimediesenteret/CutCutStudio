import { Store, StudioContext, WsTransport } from "@cutcut/client";
import "@cutcut/design/tokens.css";
import "@cutcut/design/components.css";
import "./touch.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const store = new Store();
const transport = new WsTransport(["state", "meters", "touch", "session", "alert"]);
transport.start(store);

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <StudioContext value={{ store, transport }}>
        <App />
      </StudioContext>
    </StrictMode>,
  );
}
