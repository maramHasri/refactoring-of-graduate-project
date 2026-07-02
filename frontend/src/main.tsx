import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MonitoringDebugPage } from "@/pages/MonitoringDebugPage";
import "@/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MonitoringDebugPage />
  </StrictMode>,
);
