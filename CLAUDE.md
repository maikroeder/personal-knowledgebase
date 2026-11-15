# personal-knowledgebase — working agreement for Claude

Installation instructions and example configuration for the personal knowledge base described in the *Personal
Knowledge Base* paper. Paper: `~/Writing/PersonalKnowledgeBasePaper`. Process record:
`~/Writing/Workspaces/personal-knowledgebase-paper/description.md`.

1. The README's installation instructions are what the paper's Procedure describes. Changing them changes the
   evidence: update the paper's Materials and Procedure in the same pass, so it never describes a version that no
   longer exists.
2. The paper describes what was actually run. Record what ran and what did not (README `## What has and has not
   been run`); never describe intended behaviour as achieved. As of scaffolding nothing here has been run on the
   Mac.
3. Commands come from the KiwiFS documentation and README. The installed version's `kiwifs --help` decides when
   they differ.
4. The knowledge base itself (`~/Knowledge/kiwi`) is private and lives outside this repository.
5. Python style, once Python is added: no list/dict comprehensions (explicit loops), one import per line.
6. Do not commit unless asked; never commit straight to `main`.
