# JIRA Integration

Source-of-truth strategy: **JIRA is where issues live**. GitHub Issues stays as a thin public intake for OSS contributors who don't have an Atlassian account; tickets mirror into JIRA via Atlassian's official "GitHub for Jira" app for real planning. Close in JIRA, GitHub closes via smart-commit syntax.

This doc walks through the setup. No custom code is required for the mirror; Atlassian's app handles it.

## One-time setup

### 1. Create the JIRA project

In your Atlassian site:

1. Top-right **Projects** → **Create project**.
2. Template: **Scrum**, **Kanban**, or **Bug tracking** depending on how you plan to work it. Kanban is the lowest-ceremony.
3. Project key: short, all-caps, memorable. Suggestion: `VND` (Voice Notes Desktop).
4. Workflow: default is fine for v1 (To Do → In Progress → Done). Customize later.

Repeat per repo you want to track. Voice Notes Desktop, AgeniusDesk, future tools, etc.

### 2. Install Atlassian's "GitHub for Jira" app

This is the official, free integration. It mirrors GitHub Issues into JIRA and lets you close JIRA tickets from PR descriptions.

1. In JIRA → top-right **gear icon** → **Apps**.
2. Search "GitHub for Jira" (publisher: Atlassian).
3. Click **Get app** → **Get it now**.
4. After install, **Configure** → **Connect GitHub organization**.
5. Authenticate as a GitHub admin and pick the **Agenius-AI-Labs** org.
6. Choose which repos to sync. Start with `voice-notes-desktop`.

After the app finishes its initial scan (a few minutes for a young repo), branches, commits, and PRs that mention a JIRA key (`VND-123`) show up in the corresponding JIRA ticket's development panel.

### 3. Smart commits / smart PR descriptions

Once the app is connected, mentioning a ticket key in your commit message or PR description links them. Recognized verbs:

| Phrase | Effect |
|---|---|
| `VND-123` | Links the commit / PR to the ticket. |
| `VND-123 #close` | Transitions the ticket to its "Done" state on merge. |
| `VND-123 #in-progress` | Transitions to In Progress. |
| `VND-123 #comment a note` | Posts a comment on the ticket. |
| `VND-123 #time 2h` | Logs 2 hours. |

Example PR description:

> Fix the mic button hover state on dark theme. VND-42 #close

When the PR merges, VND-42 closes automatically.

### 4. Update the PR template (optional)

Add a "Linked JIRA" line to `.github/PULL_REQUEST_TEMPLATE.md` so contributors are reminded:

```markdown
## Linked JIRA / Issue

VND-... or Closes #...
```

## Filing tickets from this repo

Public OSS contributors file on GitHub Issues. They don't need Atlassian accounts. The app mirrors their issues into the corresponding JIRA project as new tickets, and updates flow both directions.

Internal-only tickets (roadmap, design, infra) go straight into JIRA. They don't appear on GitHub.

## Credentials

The JIRA API key + org ID live in Infisical:
- `agenius/JIRA_MASTER_API_KEY`
- `agenius/JIRA_ORG_ID`

These are for ad-hoc scripts and future automation (filing tickets from agent runs, etc.), not for the GitHub-for-Jira mirror — that app handles its own auth via OAuth.

## Future: `/file-jira` skill

A Claude Code skill that lets the agent file a JIRA ticket mid-session ("file a JIRA for this bug we just hit") is on the roadmap. Implementation plan when we build it:

1. Helper module that reads the API key from the Infisical CLI: `infisical run --env=prod -- bash -c 'echo $JIRA_MASTER_API_KEY'`.
2. Wraps the REST API:
   - `POST /rest/api/3/issue` to create
   - `POST /rest/api/3/issue/{key}/comment` to comment
3. Skill takes a summary + description + project key, returns the ticket URL.

## Status

- [x] Strategy decided: JIRA source of truth, GitHub Issues as OSS intake.
- [x] Credentials in Infisical.
- [ ] JIRA projects created.
- [ ] "GitHub for Jira" app installed on Agenius-AI-Labs org.
- [ ] Smart-commit convention used in this repo's PR template.
- [ ] `/file-jira` skill (deferred until the mirror is in place and used).
