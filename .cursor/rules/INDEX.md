

# Cursor Rules Index – Gregor Zwanzig

This document lists and categorizes all `.cursor/rules/*.mdc` files to provide a clear overview.  
Each file has `alwaysApply: true` and should be considered active at all times.

---

## 00–09: Core Principles

- **00_role_and_alignment.mdc** → Roles (PO, Cursor as Dev), alignment rules.  
- **00_scoping.mdc** → Hard limits for step size, LoC, context (LLM-fit).  
- **01_basics.mdc** → General basics for working style.  
- **01_yolo_commands.mdc** → Allow-/deny-list for safe commands (uv-first).  
- **02_safety_henning_mode.mdc** → Henning safety rules (conservative execution).  
- **02_test_first.mdc** → Test-First Playbook (TDD).  
- **03_output_complete_artifacts.mdc** → Require full outputs, no truncation.  
- **03_thorough_testing.mdc** → Thorough Testing Rule (SMS length, token consistency, debug completeness).  
- **04_testing.mdc** → General testing discipline.  
- **04_system.mdc** → System behavior & discipline (refactor rules, code style).  
- **05_env_config.mdc** → Environment & config handling.  
- **05_auto_run_safe.mdc** → Auto-run only safe commands in `tests/` & `scripts/`.  
- **06_git_commits.mdc** → Git commit rules (small, Conventional Commits).  
- **06_provider_data_quality.mdc** → Rules for handling incomplete or faulty provider data.  
- **07_git_workflow.mdc** → Git workflow discipline.  
- **07_analysis_first.mdc** → Analysis-first rule (root cause before fix).  
- **08_definition_of_done.mdc** → Definition of Done.  
- **08_api_contract_guard.mdc** → API contract/schema drift guard.  

---

## Categories

### Scoping & Context
- 00_scoping.mdc  
- 07_analysis_first.mdc  

### Commands & Execution
- 01_yolo_commands.mdc  
- 05_auto_run_safe.mdc  

### Testing & Quality
- 02_test_first.mdc  
- 03_thorough_testing.mdc  
- 04_testing.mdc  
- 06_provider_data_quality.mdc  

### System Behavior & Style
- 04_system.mdc  
- 01_basics.mdc  
- 02_safety_henning_mode.mdc  

### Git Discipline
- 06_git_commits.mdc  
- 07_git_workflow.mdc  

### Contracts & Done
- 08_api_contract_guard.mdc  
- 08_definition_of_done.mdc  

### Meta
- 00_role_and_alignment.mdc  
- 03_output_complete_artifacts.mdc  
- 05_env_config.mdc  

---

## Notes
- Rules are intentionally small and focused to stay LLM-fit.  
- If conflicts arise between files, follow the stricter rule.  
- This index should be the entry point for understanding the rule landscape.
