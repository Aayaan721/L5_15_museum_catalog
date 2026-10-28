# Lab 5: Static Code Analysis — Reflection

> **Notice on Provenance:**  
> The official lab handout (`Lab_5_Static_Code_Analysis_Student_handout (1).pdf`) lists *"Answers to reflection questions provided in the lab"* under Deliverables but terminates on page 3 without printing explicit question text. Similarly, the repository `README.md` references *"the four reflection questions from the handout"*.  
> To fulfill this deliverable rigorously and prepare for a comprehensive lab evaluation/viva, the following **four supplementary, AI-generated reflection questions** were formulated. They directly address the core technical dimensions of static analysis, database security, credential management, and software quality assurance encountered in `museum_catalog.py`.

---

### Question 1 (Static Analysis and Dynamic Testing)
**Explain the fundamental difference between static analysis and dynamic testing. Using `museum_catalog.py` as the case study, identify what Pylint, Bandit, and Flake8 can detect, what they cannot prove, and which runtime tests remain necessary.**

**Answer:**  
Static code analysis examines source code artifacts—lexical tokens, Abstract Syntax Trees (AST), and structural control flow—without executing the software. In contrast, dynamic testing evaluates compiled or interpreted software during runtime by executing test vectors and observing state transitions, return values, and side effects.

In our analysis of `museum_catalog.py`, static tools detected lexical and structural flaws: Flake8 identified PEP 8 formatting defects (such as lines exceeding 79 characters and missing operator whitespace), Pylint flagged dead code (`import datetime`), unreferenced parameters (`curator`), and naming non-conformities (`addArtifact`), while Bandit detected dangerous AST patterns including raw string concatenation in SQL execution (`B608`) and shell invocation via `subprocess.call` (`B602`).

However, static analyzers cannot verify functional correctness, semantic intent, or runtime stability. They cannot prove that `total_value("Chola")` returns the accurate mathematical sum (`135000`), nor can they guarantee that SQLite transactions commit successfully under concurrent access, or that database queries handle non-existent artifact IDs safely. In the original `displayStatus`, a missing ID made `fetchone()` return `None`, so `row[0]` raised `TypeError: 'NoneType' object is not subscriptable` (observed when that logic was run against an empty table); none of the three tools reported this crash path. The corrected `display_status` checks `if row and row[0] == 1` and returns `"in storage"` for a missing ID (observed in a smoke test), so a boundary test is still needed to confirm and preserve that behavior.

Consequently, dynamic automated tests remain indispensable:
1. **Unit tests:** Asserting correct calculations and return values across known fixtures.
2. **Boundary tests:** Passing invalid identifiers or negative values into `display_status()` and `add_artifact()`.
3. **Integration tests:** Validating SQLite database constraints, in-memory rollbacks, and schema migrations under actual execution.

---

### Question 2 (SQL Injection and Parameterized Queries)
**Explain how constructing SQL with string concatenation can create a SQL injection vulnerability. Explain how parameterized queries reduce this risk, why placeholders must be used correctly, and what additional database security measures are appropriate.**

**Answer:**  
In the original `museum_catalog.py` implementation (line 11), SQL statements were constructed dynamically using Python string concatenation:
```python
conn.execute("INSERT INTO artifacts ... VALUES ('" + title + "', '" + era + "', ...")
```
When SQL statements are assembled as raw strings, user-controlled input becomes part of the SQL text, so the database parses it as syntax rather than as data. A quote character in `title` or `era` can therefore close the string literal and change the logic of the single statement being built (CWE-89). Bandit flagged this as `B608` (Medium).

It is important to state accurately what was and was not observed. Python's `sqlite3` `execute()` accepts only one SQL statement per call. When the original concatenated `INSERT` was built with a stacked payload (`x', 'Chola', 1, 0); DROP TABLE artifacts; --`), `execute()` raised `sqlite3.ProgrammingError: You can only execute one statement at a time`, and the table was **not** dropped. So a stacked `DROP TABLE` did **not** execute through `execute()` in this test. The vulnerability was nevertheless real: with the same concatenation pattern, a single-statement payload (`a', 'b', 1, 1), ('injected`) made one `execute()` call insert two rows instead of one, which shows that crafted input altered the statement's meaning. The damage that is possible depends on the query structure and on the database driver; other drivers or APIs such as `executescript()` may allow multiple statements, but that was not tested here. These checks used an in-memory database and the original query pattern, not the repository's own database or files.

Parameterized queries eliminate this vulnerability by decoupling the SQL query structure from data values. In the corrected implementation:
```python
conn.execute(
    "INSERT INTO artifacts (title, era, value, on_display) VALUES (?, ?, ?, ?)",
    (title, era, value, on_display),
)
```
The database engine pre-compiles the query template with positional placeholders (`?`). The supplied tuple is transmitted separately and bound exclusively as literal values. Even if a parameter contains quotation marks or SQL syntax, the engine treats it purely as data, which prevents injection through the values. In a smoke test of the corrected `add_artifact`, the stacked payload above was stored verbatim as a `title` value: exactly one new row was added (3 rows became 4) and the `artifacts` table remained intact.

Placeholders must be used correctly: they can only bind literal values, never table names, column identifiers, or SQL operators. Additional defense-in-depth measures include enforcing the Principle of Least Privilege on database user accounts, establishing schema-level check constraints (e.g., `CHECK (value >= 0)`), and validating input types at domain boundaries.

---

### Question 3 (Security Trade-offs and Environment Variables)
**Explain why replacing a hardcoded password with an environment variable improves credential management. Analyze the security implications of using `os.environ.get("CURATOR_PASSWORD", "")` when the variable is missing. Discuss safe failure behavior, secret storage, access control, and why environment variables alone do not guarantee security.**

**Answer:**  
Hardcoding credentials directly in source code (`CURATOR_PASSWORD = "m4seum!"`) represents a critical security risk (CWE-259). Static literals are permanently recorded in Git version history, replicated across distributed developer workstations, and exposed whenever source repositories are made public or shared. Externalizing secrets via `os.environ.get()` separates code from configuration, enabling environment-specific credentials without modifying source files.

However, the specific implementation `os.environ.get("CURATOR_PASSWORD", "")` introduces significant security implications. Defaulting to an empty string (`""`) when the variable is undefined creates an insecure fallback. If a downstream authentication check evaluates `if input_password == CURATOR_PASSWORD:`, an attacker could gain administrative curator access by submitting an empty password, or unauthenticated operations might execute silently without administrative oversight.

Secure failure behavior requires adhering to "fail-safe defaults": the application should fail closed. If a vital security credential is missing, the system should halt during initialization by raising an explicit configuration error (e.g., `raise KeyError("CURATOR_PASSWORD environment variable required")`), preventing execution in an unauthenticated or degraded state.

Furthermore, environment variables alone do not ensure complete security. They can be exposed through `/proc` directory inspection on Linux, inherited inadvertently by unprivileged child processes, printed in system crash dumps, or leaked in debugging logs. Production-grade architectures require dedicated Secret Management Services (such as HashiCorp Vault or AWS Secrets Manager) providing fine-grained Role-Based Access Control (RBAC), automatic secret rotation, and encrypted transit.

---

### Question 4 (Interpreting Tool Findings and Maintaining Quality)
**Explain how Pylint, Bandit, and Flake8 overlap and differ. Discuss why suppressing warnings to obtain a high score is not equivalent to fixing defects. Explain how baseline and final reports, a structured issue table, regression testing, and meaningful Git commits provide evidence that improvements are real.**

**Answer:**  
Pylint, Bandit, and Flake8 serve complementary yet fundamentally distinct functions within a continuous code quality pipeline:
- **Flake8** acts as a fast, syntactic style and PEP 8 enforcer, flagging line lengths (`E501`), spacing anomalies (`E225`), and basic syntactic defects.
- **Pylint** acts as an in-depth code reviewer, inspecting AST semantics, dead code (`W0611`), unreferenced arguments (`W0613`), refactoring patterns (`R1705`), and maintainability metrics.
- **Bandit** operates strictly as an application security scanner, hunting for Common Weakness Enumerations (CWEs) such as SQL injection (`B608`) and unsafe shell subprocessing (`B602`).

While overlaps occur—both Pylint and Flake8 detected the unused `import datetime` and long lines—their priorities diverge sharply. Code can achieve flawless PEP 8 compliance under Flake8 while harboring critical Bandit security flaws.

Suppressing warnings (e.g., using `# pylint: disable=...`, `# nosec`, or broad configuration silencers) merely conceals linter diagnostics without mitigating root defects. Silencing Bandit on unparameterized SQL leaves the database vulnerable to exploitation, creating a deceptive appearance of quality.

Genuine software engineering improvements are substantiated through verifiable empirical evidence:
1. **Preserved Baseline Reports (`*_before.txt`):** Establish the objective pre-fix baseline (Pylint 4.85/10, 5 Bandit findings, 8 Flake8 violations).
2. **Structured Issue Table:** Documents each defect's root cause, CWE/rule code, original line number, and architectural fix.
3. **Verified Final Reports:** Demonstrate quantifiable progress through tool execution (Pylint reaching 10.00/10, Bandit reporting 0 issues, Flake8 reporting 0 violations).
4. **Regression Testing:** Verifies that operational behavior and program outputs remain intact.
5. **Atomic Git Commits:** Provide a clear, auditable timeline isolating quality, security, and styling improvements.
