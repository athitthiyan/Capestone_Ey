# Responsible AI and audit safety

GL Guardian is decision support for investigation prioritization. It does not replace a qualified
auditor and must not autonomously accuse, discipline, deny payment, clear material transactions,
or make legal conclusions.

False positives can create reputational harm and investigative burden; false negatives and unsafe
automatic clearance can conceal control failures. Material, borderline, low-confidence,
conflicting, ungrounded, and provider-failure cases require human review. Reviewers can override
outputs, and the audit trail must retain evidence, model/config version, confidence, override, and
reason without private chain-of-thought.

Risks include automation bias, synthetic-data bias, model explanation bias, privacy and retention,
provider data handling, prompt injection, retrieval poisoning, citation hallucination, model drift,
and denial-of-service/cost attacks. Mitigations include least-data prompts, contractual provider
review, retention limits, role-based access, source allowlists, content sanitization, provenance,
immutable events, confidence gates, independent citation review, monitoring, and incident response.
Suspected harm or evidence poisoning must pause automation, preserve logs, notify security/audit
owners, assess affected decisions, and remediate or roll back the corpus/model/config.
