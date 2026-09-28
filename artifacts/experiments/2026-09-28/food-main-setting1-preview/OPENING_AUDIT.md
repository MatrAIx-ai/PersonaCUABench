# Food Setting 1 persona-opening audit

- Date: `2026-09-28`
- Scope: 24 previews (`4 personas × 6 tasks`)
- Model: Azure `gpt-5.6-terra`, temperature `1`
- Decision: **APPROVE 24/24 for formal execution**

## Gate

The persona prompt permits natural omission of expert-only sites, procedural
steps, fields, and tab instructions. Those omissions are the registered
communication treatment and are measured by rubric `communicated` coverage.
An opening is rejected only if it contradicts a fixed fact, changes a stated
quantity/budget/date, invents a material requirement, or leaks prompt/rubric
metadata.

No opening failed this gate. In particular, none changed the Boston `$500 per
person` ceiling or next-two-days window, the Minneapolis location, the UK
setting, or any fixed task item. No opening body mentions a persona, rubric,
benchmark, simulation, role-play, system prompt, or checklist.

## Persona separation

All four YAMLs validate against `dimensions.json`, use the same 36 dimensions,
and differ pairwise on 25–33 values. Mean opening lengths also separate:

| Persona | Mean words | Observed register |
| --- | ---: | --- |
| P1 Budget Novice | 72.8 | cheap, quick, easy, short |
| P3 Busy Host | 90.8 | action- and logistics-oriented |
| P2 Cautious Dietary Planner | 152.3 | reliable/dependable evidence and careful comparison |
| P4 Culinary Researcher | 146.7 | source detail, verification, and culinary vocabulary |

## Registered limitations

1. `persona.py` renders profile attributes but not the top-level YAML `note`.
   P3 should therefore be described from its rendered values—as a time-pressed
   operations manager and experienced home cook—not treated as directly
   prompted with the phrase “frequent household host.”
2. P2's schema value is only `Dietary restriction: Allergy`; no allergen is
   specified. It supports a generic dietary-caution interpretation, not an
   allergen-specific safety claim.
3. P4 is an intentionally synthetic expert upper bound. Master cooking and
   restaurant expertise is artificial for some basic-recipe tasks and must not
   be generalized to a population average.
4. Frugal personas still preserve expensive fixed task facts such as Le
   Creuset and the Boston business-dinner ceiling. These are task constraints,
   not evidence that the persona prefers the expense.
5. A few high-detail openings closely follow the canonical task order and page
   language. There is no literal metadata leak, but naturalistic speech is a
   limitation. Selectively regenerating only these high-coverage cells would
   bias communication coverage, so the complete batch is retained.

## Coverage observation

P1's meal-prep and UK Christmas openings and P3's BOTW opening omit the most
procedural detail. P2's UK Christmas opening and P4's Brussels/UK openings
preserve the most. This pattern is accepted as the treatment signal and will
be quantified by the unchanged rubric judge rather than manually corrected.
