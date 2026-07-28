"""
ZMUX Plugins — High-Performance & DRY Plugin Implementations
Includes:
1. AutoImportOptimizer
2. DuplicateLineDetector
3. SmartCommentGenerator
4. CodeBeautifierPro
5. VariableTypeHintGenerator
6. Centralized PluginExecutor
"""

import ast


class AutoImportOptimizer:
    """Finds and comments/removes unused imports in Python code using AST parsing."""

    @staticmethod
    def analyze_imports(code: str):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"ok": False, "error": f"SyntaxError: {str(e)}", "unused": []}

        imported_names = {}  # name -> (node, line_num, end_line_num, full_imported_name)
        used_names = set()

        class ImportVisitor(ast.NodeVisitor):
            def visit_Import(self, node):
                for alias in node.names:
                    name = alias.asname or alias.name
                    root_name = name.split('.')[0]
                    end = getattr(node, "end_lineno", node.lineno)
                    imported_names[root_name] = (node, node.lineno, end, name)
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                for alias in node.names:
                    name = alias.asname or alias.name
                    end = getattr(node, "end_lineno", node.lineno)
                    imported_names[name] = (node, node.lineno, end, name)
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)
                self.generic_visit(node)

        visitor = ImportVisitor()
        visitor.visit(tree)

        unused = []
        for name, (node, lineno, end_lineno, full_name) in imported_names.items():
            if name not in used_names:
                unused.append((lineno, end_lineno, full_name))

        # Sort unused imports by line number
        unused.sort()
        return {"ok": True, "unused": unused}

    @staticmethod
    def optimize(code: str) -> tuple[str, list[str]]:
        analysis = AutoImportOptimizer.analyze_imports(code)
        if not analysis.get("ok"):
            return code, [analysis.get("error", "Syntax error in code.")]

        unused = analysis.get("unused", [])
        if not unused:
            return code, ["No unused imports found."]

        lines = code.split('\n')
        # Build a set of line numbers to comment, covering full multi-line import spans
        unused_lines = set()
        line_to_names = {}
        for start, end, name in unused:
            for ln in range(start, end + 1):
                unused_lines.add(ln)
            line_to_names.setdefault(start, []).append(name)
        report = []
        new_lines = []
        for i, line in enumerate(lines, 1):
            if i in unused_lines:
                if i in line_to_names:
                    names_on_line = line_to_names[i]
                    report.append(f"Line {i}: Unused import {', '.join(names_on_line)}")
                new_lines.append(f"# {line}  # Optimized: unused import")
            else:
                new_lines.append(line)

        return '\n'.join(new_lines), report


class DuplicateLineDetector:
    """Detects duplicate significant lines and injects warnings."""

    @staticmethod
    def detect(code: str) -> tuple[str, list[str]]:
        lines = code.split('\n')
        seen = {}  # cleaned_line -> list of 1-based line numbers
        report = []

        for i, line in enumerate(lines, 1):
            cleaned = line.strip()
            # Ignore comments, empty lines, and very short lines
            if not cleaned or cleaned.startswith('#') or len(cleaned) < 5:
                continue
            if cleaned in seen:
                seen[cleaned].append(i)
            else:
                seen[cleaned] = [i]

        duplicates = []
        for content, occurrences in seen.items():
            if len(occurrences) > 1:
                duplicates.append({
                    "content": content,
                    "lines": occurrences
                })

        if not duplicates:
            return code, ["No significant duplicate lines found."]

        report.append("📊 [Duplicate Line Detector Report]")
        report_lines = []
        for dup in duplicates:
            occ_str = ", ".join(f"Line {ln}" for ln in dup["lines"])
            report.append(f"- '{dup['content']}' duplicated on: {occ_str}")
            report_lines.append(f"# WARNING: Duplicate line '{dup['content']}' found on: {occ_str}")

        if report_lines:
            updated_code = "\n".join(report_lines) + "\n\n" + code
        else:
            updated_code = code

        return updated_code, report


class SmartCommentGenerator:
    """Generates Python function docstrings dynamically based on parameters and returns."""

    @staticmethod
    def generate(code: str) -> tuple[str, list[str]]:
        report = []
        current = code
        # Process one function at a time, re-parsing after each insertion so line
        # numbers stay accurate. Inserting at a function shifts every line below
        # it, which corrupts offsets captured from a single up-front parse.
        while True:
            try:
                tree = ast.parse(current)
            except SyntaxError as e:
                return current, [f"SyntaxError: {str(e)}"] + report

            target = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and ast.get_docstring(node) is None:
                    target = node
                    break
            if target is None:
                break

            lines = current.split('\n')
            body_start_line_idx = target.body[0].lineno - 1
            first_body_line = lines[body_start_line_idx]
            indent = len(first_body_line) - len(first_body_line.lstrip())
            indent_str = " " * indent

            params = [arg.arg for arg in target.args.args if arg.arg != 'self']
            param_lines = [f"{indent_str}    {p}: Type description." for p in params]
            param_block = f"\n{indent_str}Args:\n" + "\n".join(param_lines) if params else ""

            doc = f'{indent_str}"""Docstring for {target.name}.\n{param_block}\n{indent_str}Returns:\n{indent_str}    Type: Description.\n{indent_str}"""'

            lines.insert(body_start_line_idx, doc)
            report.append(f"Generated docstring for function '{target.name}' at line {target.lineno}")
            current = '\n'.join(lines)

        if not report:
            return current, ["No functions missing docstrings found."]
        return current, report


# Operators the beautifier pads with spaces, ordered longest-first so that a
# prefix never wins over the full token (`//=` before `//` before `/`).
# Anything missing here gets chopped into single characters and re-spaced,
# which silently produces code that no longer parses.
_OPERATORS: tuple[str, ...] = (
    # 3 chars
    '//=', '**=', '>>=', '<<=', '...',
    # 2 chars
    '==', '!=', '<=', '>=', '->', ':=',
    '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '@=',
    '//', '**', '<<', '>>',
    # 1 char
    '=', '+', '-', '*', '/',
)


class CodeBeautifierPro:
    """Formats Python code into standard PEP-8 spacing, omitting strings and comments."""

    @staticmethod
    def beautify(code: str) -> tuple[str, list[str]]:
        lines = code.split('\n')
        beautified_lines = []
        consecutive_empty = 0
        report = []

        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            if not stripped:
                consecutive_empty += 1
                if consecutive_empty <= 2:
                    beautified_lines.append("")
                continue

            consecutive_empty = 0

            new_line_chars = []
            in_string = False
            string_char = None
            in_comment = False

            j = 0
            n = len(stripped)
            while j < n:
                ch = stripped[j]

                if not in_string and ch == '#':
                    in_comment = True

                if in_comment:
                    new_line_chars.append(ch)
                    j += 1
                    continue

                if (ch == '"' or ch == "'") and (j == 0 or stripped[j-1] != '\\'):
                    if in_string:
                        if ch == string_char:
                            in_string = False
                            string_char = None
                    else:
                        in_string = True
                        string_char = ch
                    new_line_chars.append(ch)
                    j += 1
                    continue

                if in_string:
                    new_line_chars.append(ch)
                    j += 1
                    continue

                # Format commas
                if ch == ',':
                    new_line_chars.append(',')
                    k = j + 1
                    while k < n and stripped[k] in ' \t':
                        k += 1
                    if k < n and stripped[k] != '#':
                        new_line_chars.append(' ')
                    j = k
                    continue

                # Format operators.
                #
                # Longest match first, otherwise a multi-character operator is
                # split into pieces that are then spaced individually and no
                # longer parse: `->` became `- >` (breaking every annotated
                # function), `//=` became `// =`, `>>=` became `> >=`.
                matched_op = None
                for candidate in _OPERATORS:
                    if stripped.startswith(candidate, j):
                        matched_op = candidate
                        break

                if matched_op:
                    while new_line_chars and new_line_chars[-1] == ' ':
                        new_line_chars.pop()
                    new_line_chars.append(' ')
                    new_line_chars.append(matched_op)
                    new_line_chars.append(' ')
                    k = j + len(matched_op)
                    while k < n and stripped[k] in ' \t':
                        k += 1
                    j = k
                    continue

                new_line_chars.append(ch)
                j += 1

            beautified_lines.append("".join(new_line_chars))

        beautified_code = "\n".join(beautified_lines)
        if beautified_code != code:
            report.append("⚡ Code beautified successfully (PEP8 formatting).")
        else:
            report.append("Code is already well-formatted.")

        return beautified_code, report


class VariableTypeHintGenerator:
    """Adds type hint annotations to Python functions, importing typing package if necessary."""

    @staticmethod
    def infer_type_by_default(default_node) -> str:
        if isinstance(default_node, ast.Constant):
            val = default_node.value
            if isinstance(val, bool):
                return "bool"
            if isinstance(val, int):
                return "int"
            if isinstance(val, float):
                return "float"
            if isinstance(val, str):
                return "str"
            if val is None:
                return "Optional[Any]"
        elif isinstance(default_node, ast.List):
            return "list"
        elif isinstance(default_node, ast.Dict):
            return "dict"
        return "Any"

    @staticmethod
    def generate(code: str) -> tuple[str, list[str]]:
        report = []
        current = code
        has_any_imports = "from typing import Any" in code or "import typing" in code

        # Process one function per pass, re-parsing so line offsets stay valid
        # after each edit, and never overwrite an existing return annotation.
        skipped = set()
        while True:
            try:
                tree = ast.parse(current)
            except SyntaxError as e:
                return current, [f"SyntaxError: {str(e)}"] + report

            target = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name not in skipped:
                    target = node
                    break
            if target is None:
                break

            args = target.args.args
            defaults = target.args.defaults

            defaults_map = {}
            for idx, default in enumerate(reversed(defaults)):
                arg_idx = len(args) - 1 - idx
                if arg_idx >= 0:
                    defaults_map[args[arg_idx].arg] = default

            needs_annotation = any(
                arg.arg != 'self' and arg.annotation is None for arg in args
            )
            if not needs_annotation and target.returns is not None:
                skipped.add(target.name)
                continue

            lines = current.split('\n')
            sig_start_idx = target.lineno - 1
            sig_end_idx = target.body[0].lineno - 1

            def_line = lines[sig_start_idx]
            indent = len(def_line) - len(def_line.lstrip())
            indent_str = " " * indent

            arg_strs = []
            for arg in args:
                if arg.arg == 'self':
                    arg_strs.append('self')
                    continue
                arg_repr = arg.arg
                if arg.annotation is None:
                    inferred = "Any"
                    if arg.arg in defaults_map:
                        inferred = VariableTypeHintGenerator.infer_type_by_default(defaults_map[arg.arg])
                    arg_repr += f": {inferred}"

                if arg.arg in defaults_map:
                    default_node = defaults_map[arg.arg]
                    if isinstance(default_node, ast.Constant):
                        val_repr = repr(default_node.value)
                    elif isinstance(default_node, ast.List):
                        val_repr = "[]"
                    elif isinstance(default_node, ast.Dict):
                        val_repr = "{}"
                    else:
                        val_repr = "None"
                    arg_repr += f" = {val_repr}"
                arg_strs.append(arg_repr)

            # Preserve an existing return annotation instead of forcing -> Any:
            if target.returns is None:
                return_part = " -> Any:"
            else:
                return_part = ":"

            new_sig = f"{indent_str}def {target.name}({', '.join(arg_strs)}){return_part}"

            del lines[sig_start_idx:sig_end_idx]
            lines.insert(sig_start_idx, new_sig)
            report.append(f"Injected variable type hints into function '{target.name}' signature.")
            current = '\n'.join(lines)
            skipped.add(target.name)

        if report and not has_any_imports:
            current = "from typing import Any, Optional\n" + current

        if not report:
            return current, ["No functions found to add type hints."]
        return current, report


class PluginExecutor:
    """Central registry and executor for transform plugins."""

    @staticmethod
    def execute_plugin(plugin_id: str, code: str) -> dict:
        if plugin_id == "auto_import_optimizer":
            new_code, report = AutoImportOptimizer.optimize(code)
            return {"ok": True, "code": new_code, "report": "\n".join(report)}
        elif plugin_id == "duplicate_line_detector":
            new_code, report = DuplicateLineDetector.detect(code)
            return {"ok": True, "code": new_code, "report": "\n".join(report)}
        elif plugin_id == "smart_comment_generator":
            new_code, report = SmartCommentGenerator.generate(code)
            return {"ok": True, "code": new_code, "report": "\n".join(report)}
        elif plugin_id == "code_beautifier_pro":
            new_code, report = CodeBeautifierPro.beautify(code)
            return {"ok": True, "code": new_code, "report": "\n".join(report)}
        elif plugin_id == "variable_type_hint_generator":
            new_code, report = VariableTypeHintGenerator.generate(code)
            return {"ok": True, "code": new_code, "report": "\n".join(report)}
        else:
            return {"ok": False, "message": f"Plugin '{plugin_id}' is not supported on backend."}
