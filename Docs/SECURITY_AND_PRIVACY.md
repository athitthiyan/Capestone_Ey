# Security and privacy

Commit only `.env.example`; store API keys, database credentials, signing secrets, and deployment
keys in an approved secret manager or GitHub encrypted secrets. Rotate any exposed credential and
rewrite history through an approved incident process. Research outputs must exclude raw prompts,
chain-of-thought, access tokens, personal data, and confidential evidence.

Use least privilege, TLS, authenticated endpoints, provider retention controls, dependency and
secret scanning, source allowlists, prompt-injection defenses, audit-log access controls, and tested
retention/deletion procedures. Synthetic benchmark identifiers are fictional. See `Docs/SECURITY.md`
and incident-response documentation for operational controls.
