# Skill Layer – Deterministic Macro Expansion

Skills are local to the Spine.

They expand into ordered ICL primitives.

---

Example: prep_workspace

Sequence:
1. home
2. move_cartesian to safe pose
3. io_set tool off
4. wait until motion complete
5. park

---

Design Rules

- Skills are deterministic
- Skills may branch only on validated sensor state
- LLM may suggest skills, but Spine executes them deterministically
