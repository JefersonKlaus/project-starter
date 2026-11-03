import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { signOut } from "@/lib/auth/session";

/** Ends the Cognito session and sends the user to the login screen. */
export function useSignOut() {
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await signOut();
    } finally {
      await navigate({ to: "/login", replace: true });
    }
  }

  return { signingOut, signOut: handleSignOut };
}
