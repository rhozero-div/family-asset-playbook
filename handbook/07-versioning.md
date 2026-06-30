# Versioning

**Version:** 0.1.0  
**Status:** draft

---

## 1. Overview

This chapter defines versioning conventions for:

- the methodology handbook
- the application behavior
- the generated playbook contract

Versioning matters because the methodology will evolve.
The system needs a way to distinguish:

- wording tweaks
- compatible feature additions
- real contract changes

## 2. Versioning Style

This project follows a SemVer-style pattern:

```text
MAJOR.MINOR.PATCH
```

Interpretation:

- `MAJOR`
  - incompatible methodology or schema change
- `MINOR`
  - new compatible rule, section, or feature
- `PATCH`
  - wording fixes, documentation cleanup, narrow default tuning, or bug-level clarification

## 3. What Can Trigger Each Level

### 3.1 PATCH

Use `PATCH` for changes such as:

- wording clarification
- documentation cleanup
- non-structural rendering fixes
- small assumption-default adjustment

### 3.2 MINOR

Use `MINOR` for changes such as:

- adding a new compatible event type
- adding a new optional input field
- adding a new explanatory section
- extending output structure without breaking current consumers

### 3.3 MAJOR

Use `MAJOR` for changes such as:

- incompatible schema changes
- removal or redefinition of core sections
- methodology logic that invalidates earlier profile interpretation

## 4. Schema Version and Methodology Version

In practice, a generated profile or playbook may carry methodology-related version references.
The purpose is to make it possible to answer:

- which methodology contract was this built under?
- is this profile still compatible with current behavior?

## 5. Runtime Reality

The current repo may contain:

- handbook version references
- schema version references
- asset-version references for frontend assets

These should not be conflated.
They solve different problems:

- methodology contract
- data compatibility
- static asset cache invalidation

## 6. When To Recalculate Old Playbooks

Old playbooks should be reconsidered when:

- a major methodology change occurs
- a meaningful minor rule changes interpretation materially
- the client profile facts themselves have changed

Not every patch-level wording change requires regeneration.

## 7. Documentation Responsibility

Whenever current code behavior changes materially, the matching handbook chapter should be updated so that:

- current output
- current documentation
- current tests

stay aligned.

## 8. Backward Compatibility Principle

Backward compatibility is preferred where practical, especially for:

- optional fields
- explanatory wording changes
- additive output sections

But compatibility should not be preserved at the cost of making the current methodology unclear.

## 9. Source of Truth Rule

When version references conflict, use this order:

1. current code behavior
2. current tests
3. current questionnaire output
4. current handbook

Then update whichever versioned document has drifted.
