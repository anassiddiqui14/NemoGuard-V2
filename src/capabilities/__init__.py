"""
Governed Capability Gateway — Phase 1 of the enterprise-scale build
(see docs/nemoguard_real_world_support_engineer_build_spec.md §12 and
docs/IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md Part 1).

This package is the ONLY path through which agents, workflows, and the API
can resolve an abstract "do this" intent into a real, typed, executed,
verified action. It replaces:
  - free-text `tool_name` strings in action_step (no formal executable
    binding)
  - the two hardcoded if/else branches in write_tools.execute_simulated_action
  - the hardcoded "PASSED" verification_result rows in
    orchestrator.execute_plan

Modules:
  - registry.py         Capability registration (the "connector catalog")
  - plan_compiler.py     ActionIntent -> CompiledAction, with plan hashing
  - policy.py             Deterministic risk -> approval-requirement mapping
  - execution_engine.py   Generic precondition -> dry-run -> execute -> verify
"""
