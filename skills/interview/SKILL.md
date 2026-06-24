---
name: interview
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a shared understanding.

## How you proceed

1. Analyze the plan / requirement silently first
2. Identify all open decisions and dependencies (decision tree)
3. Ask each question SEPARATELY as a poll - never several at once

## Question format (mandatory)

Every question MUST be asked as an `askQuestions` poll:
- **Copilot:** call `#tool:vscode_askQuestions`
- **Claude Code:** call the `AskUserQuestions` tool
- Use `options` with concrete answer choices
- Mark your recommendation with `recommended: true`
- Set `allowFreeformInput: true` for additions
- Use `multiSelect: true` when several options can be combined

## Conducting the interview

- Start with the most important dependencies (what determines everything else?)
- Follow the decision tree: answer A opens branch A, answer B opens branch B
- Briefly explain WHY you are asking this question (one sentence)
- Give your recommendation and justify it briefly
- If a question can be answered by analyzing the codebase -> analyze first, then ask or skip
- Never ask a question that has already been answered

## Closing

When all decision branches are resolved:
- Summarize the decisions
- Show the complete plan as a requirement list (REQ-XXXX format)
- Ask whether the plan should be implemented this way