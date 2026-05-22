import { useState } from "react";
import { LoginPage } from "./LoginPage";
import { SignupPage } from "./SignupPage";

/** Renders Login or Signup based on local UI state (no router in v1). */
export function AuthShell(): JSX.Element {
  const [mode, setMode] = useState<"login" | "signup">("login");
  return mode === "login" ? (
    <LoginPage onSwitchToSignup={() => setMode("signup")} />
  ) : (
    <SignupPage onSwitchToLogin={() => setMode("login")} />
  );
}
