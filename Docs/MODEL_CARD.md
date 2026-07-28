# System model card

GL Guardian routes audit-investigation tasks across configurable LLM providers and deterministic
controls. Intended use is auditor-supervised prioritization and evidence synthesis. Out-of-scope
uses include autonomous fraud accusation, employee monitoring decisions, legal advice, credit or
insurance decisions, and automatic clearance of material unsupported transactions.

The system uses RAG, adversarial Challenger/Defender debate, adjudication, verification, confidence
gates, and human review. Provider/model selection is environment-dependent. Only the deterministic
rule baseline has a verified benchmark-v1 result; live LLM performance, subgroup fairness, and
human evidence-quality agreement are Not run. See the generated research report and Responsible AI
assessment before deployment.
