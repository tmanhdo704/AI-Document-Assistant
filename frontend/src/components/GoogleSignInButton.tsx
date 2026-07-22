import { useEffect, useRef } from "react";

const GOOGLE_SCRIPT_SRC = "https://accounts.google.com/gsi/client";

type GoogleCredentialResponse = {
  credential?: string;
};

type GoogleIdApi = {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    use_fedcm_for_prompt?: boolean;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: {
      type: "standard";
      theme: "outline";
      size: "large";
      text: "continue_with";
      shape: "rectangular";
      width: number;
    },
  ): void;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: GoogleIdApi;
      };
    };
  }
}

let googleScriptPromise: Promise<void> | null = null;

function loadGoogleIdentityScript(): Promise<void> {
  if (window.google?.accounts.id) {
    return Promise.resolve();
  }

  if (googleScriptPromise) {
    return googleScriptPromise;
  }

  googleScriptPromise = new Promise((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      `script[src="${GOOGLE_SCRIPT_SRC}"]`,
    );
    const script = existingScript ?? document.createElement("script");

    const handleLoad = () => resolve();
    const handleError = () => {
      googleScriptPromise = null;
      reject(new Error("Google Identity Services failed to load."));
    };

    script.addEventListener("load", handleLoad, { once: true });
    script.addEventListener("error", handleError, { once: true });

    if (!existingScript) {
      script.src = GOOGLE_SCRIPT_SRC;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  });

  return googleScriptPromise;
}

type GoogleSignInButtonProps = {
  disabled?: boolean;
  onCredential: (credential: string) => void;
  onError: (message: string) => void;
};

export default function GoogleSignInButton({
  disabled = false,
  onCredential,
  onError,
}: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const credentialHandlerRef = useRef(onCredential);
  const errorHandlerRef = useRef(onError);

  credentialHandlerRef.current = onCredential;
  errorHandlerRef.current = onError;

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    let cancelled = false;

    if (!clientId) {
      errorHandlerRef.current("Google Login chưa được cấu hình.");
      return;
    }

    loadGoogleIdentityScript()
      .then(() => {
        const googleId = window.google?.accounts.id;
        const container = containerRef.current;

        if (cancelled || !googleId || !container) return;

        googleId.initialize({
          client_id: clientId,
          callback: (response) => {
            if (response.credential) {
              credentialHandlerRef.current(response.credential);
            } else {
              errorHandlerRef.current(
                "Google không trả về thông tin đăng nhập.",
              );
            }
          },
          use_fedcm_for_prompt: true,
        });

        container.replaceChildren();
        googleId.renderButton(container, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "rectangular",
          width: Math.max(200, Math.floor(container.clientWidth)),
        });
      })
      .catch(() => {
        if (!cancelled) {
          errorHandlerRef.current(
            "Không thể tải Google Login. Vui lòng thử lại.",
          );
        }
      });

    return () => {
      cancelled = true;
      containerRef.current?.replaceChildren();
    };
  }, []);

  return (
    <div
      className={disabled ? "pointer-events-none opacity-60" : undefined}
      aria-busy={disabled}
    >
      <div ref={containerRef} className="min-h-10 w-full" />
    </div>
  );
}
