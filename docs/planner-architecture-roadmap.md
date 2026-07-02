# Current Architecture Boundary

This document records the **current** product boundary for `family-asset-playbook`.

Chinese version: [planner-architecture-roadmap.zh.md](planner-architecture-roadmap.zh.md)

## Main Flow

The current primary flow is:

1. fill out the questionnaire
2. generate one unified YAML profile
3. run the engine
4. produce one final client-facing playbook

The playbook is the main deliverable.
It already includes:

- executive summary
- client overview
- asset projection
- allocation execution plan
- insurance structure suggestion

## Primary vs Secondary

### Primary path

The current product contract is:

- `questionnaire -> playbook`

After the playbook is rendered, the advisor may optionally continue into the insurance input loop from Plan A or Plan B, then regenerate the playbook with incremental insurance additions.

### Secondary modules

The repo still contains `asset_planner/` and `insurance_planner/`.
They may remain useful as internal or experimental modules, but they are not the main user path anymore.

## Current Boundary by Layer

### Questionnaire

The questionnaire is responsible for:

- collecting household facts
- storing default assumptions
- generating the unified YAML profile

### Playbook

The playbook is responsible for:

- client-readable explanation
- milestone funding logic
- asset-layer execution order
- insurance-structure suggestion

It is the main client-facing output.

## Insurance Suggestion Placement

Insurance suggestion is now embedded directly in the final playbook rather than treated as a required standalone destination.

The current insurance section includes:

- protection-gap summary
- Plan A
- Plan B
- member-level explanation
- related charts
- buttons that open the advisor-side insurance input page for Plan A or Plan B

## Source of Truth

If documentation and code disagree, use the following as the source of truth:

1. current questionnaire output
2. current engine behavior
3. current tests
4. the active `handbook/` contract
