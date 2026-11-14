# ADR-004: Project licensing and AI-assisted development transparency

**Status**: Accepted
**Date**: 2026-04-07
**Deciders**: Project owner (human reviewer)

## Context

This project (a Home Assistant add-on / MCP server, originally for Tandoor Recipes, now for Grocy) has significant portions of code developed with assistance from AI tools. As the project approaches its first alpha release, it needs a license and a clear stance on how AI-assisted development is disclosed.

Two distinct questions must be answered:

1. **Which open-source license?** The project needs a standard OSS license that is compatible with the Home Assistant ecosystem, protects contributors, and accounts for the AI-assisted development model.

2. **How to disclose AI involvement?** The US Copyright Office and the EU position hold that purely AI-generated works cannot be copyrighted. However, this project involves substantial human creative input: architecture design, prompt engineering, code review, editing, and integration decisions. This human involvement establishes copyrightability for the overall work. The project should be transparent about AI tool usage without undermining the validity of its copyright claims.

## Decision Drivers

- License compatibility with the Home Assistant ecosystem (HA itself is Apache 2.0)
- Patent protection for contributors and users
- Mechanism for structured notices about development practices
- Ecosystem familiarity and tooling support (license scanners, dependency auditors)
- Honest disclosure of AI-assisted development without unnecessary legal risk

## Options Considered

### Option 1: MIT License

The most popular permissive license by adoption count.

**Pros:**
- Extremely simple and well-understood
- Compatible with virtually all other licenses
- Minimal compliance burden for downstream users

**Cons:**
- No explicit patent grant -- users rely on an implied license, which is legally weaker
- No NOTICE file mechanism -- no standard place to document AI-assisted development
- Does not match the Home Assistant project's own license choice (Apache 2.0)

### Option 2: Apache License 2.0

A permissive license with explicit patent grant and NOTICE file mechanism.

**Pros:**
- Explicit patent grant protects users and contributors from patent claims
- NOTICE file mechanism provides a standard, license-sanctioned place to document the AI-assisted development disclosure
- Matches Home Assistant's own license, ensuring full ecosystem compatibility
- Well-understood by enterprises and OSS projects alike
- Compatible with GPLv3 (one-way: Apache 2.0 code can be included in GPLv3 projects)

**Cons:**
- Slightly more complex than MIT (attribution requirements, NOTICE file propagation)
- Requires downstream redistributors to preserve the NOTICE file (this is a feature for our transparency goal, but adds a minor compliance step)

### Option 3: CC0 / Unlicense (public domain dedication)

Waive all rights and place the work in the public domain.

**Pros:**
- Maximum freedom for downstream users
- Sidesteps the AI-copyrightability question entirely

**Cons:**
- Gives up all rights unnecessarily -- the project has substantial human creative input that establishes copyrightability
- No ability to enforce license terms (e.g., attribution)
- No patent protection
- No NOTICE file mechanism
- Not recognized as valid in all jurisdictions (some legal systems do not allow full copyright waiver)

### Option 4: Custom license with AI-specific clauses

Draft a bespoke license that addresses AI-generated code specifically.

**Pros:**
- Could precisely address the project's unique circumstances

**Cons:**
- Custom licenses create confusion for downstream users and contributors
- Incompatible with automated license scanners and compliance tooling
- Not OSI-approved, so the project could not claim to be "open source" in the formal sense
- Legal review cost is disproportionate for a project of this scale
- Ecosystem incompatibility with Home Assistant and other Apache 2.0 projects

## Decision

**Apache License 2.0** with a transparency notice in the NOTICE file.

### License

The project will be licensed under the Apache License, Version 2.0. A standard `LICENSE` file will be placed in the repository root.

### Transparency notice

A `NOTICE` file will be placed in the repository root, as provided for by Section 4(d) of the Apache License 2.0. The NOTICE file will state that portions of the codebase were developed with assistance from AI tools, and that the project owner reviewed, directed, and edited all contributions.

The NOTICE file will follow these guidelines:

- **General, not specific**: Do not name specific AI tools or vendors. Multiple AI tools were used; the disclosure covers all of them.
- **No commit-level attribution**: Do not reference Co-Authored-By lines in commit messages or any per-file AI attribution. The NOTICE file is the single disclosure point.
- **Affirm human creative control**: State that a human directed the architecture, reviewed all code, and made all acceptance decisions. This supports the copyrightability of the work.
- **Keep it brief**: The NOTICE file is a legal document, not a blog post. A few sentences suffice.

## Consequences

**If accepted:**

- A `LICENSE` file (Apache 2.0 full text) will be added to the repository root.
- A `NOTICE` file will be added to the repository root with the transparency disclosure.
- The README should reference the license (standard practice).
- Downstream redistributors must preserve the NOTICE file per Apache 2.0 Section 4(d), ensuring the AI-assisted development disclosure propagates.
- The project aligns with the Home Assistant ecosystem's license choice.

**If rejected:**

- The project remains unlicensed, which is legally equivalent to "all rights reserved" -- no one has permission to use, modify, or distribute the code. This blocks the alpha release goal.
