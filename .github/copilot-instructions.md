# GitHub Copilot Instructions for `phantom-shell`

This repository is extremely small at the moment.  Most of the "code" lives implicitly in the
`openai.yaml` configuration, so an AI agent needs to treat the YAML as the primary
source of truth when reasoning about desired behaviour.

## Big Picture

- **Purpose**: *Phantom‑Shell* is an autonomous orchestrator for an Operator laptop that
  provides a local AI command centre with shared memory, conflict detection and
  verified execution loops.
- **Core file**: `openai.yaml` contains the model instructions, operating mode
  (Jarrett Prime Protocol), tool definitions and high‑level description.  Every change to
  the system’s behaviour must correspond to updates in this YAML.
- **Architecture**:  There is no defined service boundary or language stack yet.  When code
  is added it will likely be vanilla Python (see `requirements.txt`); expect a single
  package or script for the orchestrator and possibly helper modules for memory,
  verification and conflict‑resolution.

## Developer workflows

1. **Bootstrapping**
   - Clone repository, create a Python virtualenv, install packages from
     `requirements.txt` (currently empty).
   - There are no build scripts; new functionality is just added as Python
     modules and regulated by tests you add.

2. **Testing / evidence**
   - There is no test framework yet, but the pull‑request template enforces an
     "evidence pair".  Every PR must run `make verify-revoke-smoke` and include a
     block with two UTC timestamps in the required format.  This is the only
     automated check today.
   - Add unit or integration tests alongside new code.  Choose a lightweight
     framework (e.g. `pytest`) and add it to `requirements.txt`.

3. **Pull requests**
   - Follow the template from `.github/pull_request_template.md` exactly.
   - Branch names often include `evidence-gate` followed by a timestamp (see
     current branch).  This is just a convention to remind reviewers of the
     evidence requirement.
   - Descriptions should be concise and include pointers to `openai.yaml` when
     behaviour is modified.

4. **Debugging**
   - There are no container, makefile or CI configurations in the repo.  Run
     Python scripts directly (`python -m package.module`) or execute code from a
     REPL.  Use standard tooling (`pdb`, `print`, etc.).
   - To change the agent’s reasoning rules, update `openai.yaml` and verify the
     instructions with the model in an interactive session (via `gh` CLI or the
     platform you use for development).

## Conventions & patterns

- **Jarrett Prime Protocol**: always obey the five numbered rules in `openai.yaml`.
  When you write new code that interprets instructions, encode those priorities
  (accuracy > conflict detection > verification > speed).  New agents or helpers
  must expose the verification checkpoint as a function named `verify()`.

- **Evidence‑gate**: many temporary branches and filenames use the phrase
  "evidence".  Use the existing `make verify-revoke-smoke` target as a template
  when adding new make targets or scripts.

- **Minimalism**: keep dependencies tight and the workspace clean.  The entire
  project currently fits in a couple of files; avoid scaffolding large frameworks
  until they are actually needed.

- **File locations**:
  - `.github/` holds GitHub‑specific configuration (templates, issue/PR rules).
  - `openai.yaml` is the heart of the project.
  - `requirements.txt` lists runtime dependencies; start it with lines like
    `# keep sorted` when you add packages.

- **Future structure**: when adding more code, consider a layout such as:

  ```text
  phantom_shell/          # python package
  ├── __init__.py         # version, metadata
  ├── orchestrator.py     # entry point
  ├── memory.py           # shared memory management
  └── verify.py           # verification logic
  tests/                  # pytest modules mirroring package structure
  ```

## Agent guidance

- Before modifying anything, read `openai.yaml` fully and treat the project’s
  description there as the design document.  Ask the user if you are uncertain
  about the behaviour of any tool or module; the repo contains almost nothing,
  so dialogue is expected.

- When generating code, include concrete examples from the repo (e.g. reference
  `make verify-revoke-smoke`, the evidence template, the Jarrett Prime Protocol
  rules).  Avoid generic advice such as "write tests" unless you describe how
  they should fit into the existing minimal structure.

- To propose changes to the repository structure, always justify them in terms
  of the current goal: turning the Operator laptop into an AI command centre.
  Do not add extraneous subdirectories or complex CI patterns unless the user
  explicitly requests them.

- Maintain the response formatting rules specified in `openai.yaml`.  Use
  standalone code blocks for transposable artifacts and keep text succinct.


---

*If any of the above points are unclear or missing critical information, please
let me know so I can iterate.*