import { Store, StudioContext, WsTransport } from "@cutcut/client";
import "@cutcut/design/tokens.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const store = new Store();
const transport = new WsTransport("state,meters,decision,alert,health".split(","));
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
