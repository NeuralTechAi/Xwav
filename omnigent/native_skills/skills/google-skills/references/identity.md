# identity

Read only the best matching entry, not every skill listed here. Prefer an already installed matching user/project skill.

## dpop-adoption
Implement and debug OAuth 2.0 DPoP (RFC 9449) refresh token sender-constraining for WebCrypto, Node.js ES6, and browser runtimes integrating with Google's OAuth platform. Use when configuring non-extractable asymmetric key pairs (P-256), generating DPoP Proof JWTs for authorization code exchange and token refresh, or handling 400 use_dpop_nonce challenge retry loops at oauth2.googleapis.com/token. Don't use for unconstrained OAuth 2.0 flows (where refresh tokens are not bound to a client key pair), or for Google Cloud IAM / service account authentication.

Read: `library/identity/dpop-adoption/INSTRUCTIONS.md`

## sign-in-with-google-web
Implement, configure, and secure Sign In With Google (SiwG) using Google Identity Services (GIS / `https://accounts.google.com/gsi/client`) across web architectures. Use when creating Google sign-in buttons, implementing Google One Tap with FedCM, integrating GIS in React/Next.js/Angular/HTML, verifying ID tokens on backend runtimes (Python/Node.js/Go/Java), enforcing Google Workspace domain restrictions (`hd`), securing client-side ID tokens via WebCrypto nonces or encrypted IndexedDB, embedding in cross-origin iframes via the Intermediate Iframe API (`https://accounts.google.com/gsi/intermediate`), configuring Content Security Policy (CSP), COOP, and Permissions Policy (`identity-credentials-get`) headers, or handling sign-out and revocation. Don't use for legacy Google Sign-In (`gapi.auth2`), Google Cloud IAM service accounts, or Android/iOS native Credential Manager.

Read: `library/identity/sign-in-with-google-web/INSTRUCTIONS.md`
