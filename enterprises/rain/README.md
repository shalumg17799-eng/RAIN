# Enterprise: rain

Rain-specific assets: `skills/` holds overrides of shared skills (same skill name and version, `enterprise: rain` in the
SKILL.md frontmatter, at least the shared skill's `validation` contract) and `config/` holds Rain configuration such as
the business taxonomy. The registry layers `enterprises/*/skills` on top of `skills/` and `skills-factory/` and returns
an override only for runs started with `enterprise="rain"`; other tenants never see it. Overrides should import the
shared implementation rather than copy it. Do not commit customer data, credentials, API keys or real DDL extracts here;
`config/taxonomy.yaml` is a placeholder until the agreed Rain taxonomy lands.
