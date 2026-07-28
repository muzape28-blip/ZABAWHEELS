"""
ZMUX Core — Code Syntax & Structure Checker
Pre-execution validation to prevent EOFError and common syntax issues.
"""



def strip_comments_and_strings(code: str) -> tuple[str, list[str]]:
    """
    Strips comments and string literals from Python code,
    returning the clean structure and a list of structural string errors.
    """
    issues = []
    out = []
    i = 0
    n = len(code)
    state = "normal"  # normal, sq, dq, tsq, tdq, comment

    while i < n:
        if state == "normal":
            if code[i:i+3] == '"""':
                state = "tdq"
                i += 3
            elif code[i:i+3] == "'''":
                state = "tsq"
                i += 3
            elif code[i] == '"':
                state = "dq"
                i += 1
            elif code[i] == "'":
                state = "sq"
                i += 1
            elif code[i] == '#':
                state = "comment"
                i += 1
            else:
                out.append(code[i])
                i += 1
        elif state == "comment":
            if code[i] == '\n':
                state = "normal"
                out.append('\n')
            i += 1
        elif state == "dq":
            if code[i] == '\\':
                i += 2  # skip escaped character
            elif code[i] == '"':
                state = "normal"
                i += 1
            elif code[i] == '\n':
                issues.append("Unterminated double-quoted string")
                state = "normal"
                i += 1
            else:
                i += 1
        elif state == "sq":
            if code[i] == '\\':
                i += 2  # skip escaped character
            elif code[i] == "'":
                state = "normal"
                i += 1
            elif code[i] == '\n':
                issues.append("Unterminated single-quoted string")
                state = "normal"
                i += 1
            else:
                i += 1
        elif state == "tdq":
            if code[i:i+3] == '"""':
                state = "normal"
                i += 3
            elif code[i] == '\\':
                i += 2
            else:
                i += 1
        elif state == "tsq":
            if code[i:i+3] == "'''":
                state = "normal"
                i += 3
            elif code[i] == '\\':
                i += 2
            else:
                i += 1

    if state in ["dq", "tdq"]:
        issues.append("Unterminated double quotes (\")")
    elif state in ["sq", "tsq"]:
        issues.append("Unterminated single quotes (')")

    return "".join(out), issues


def check_code(code: str) -> dict:
    """
    Validate Python code structure before execution.
    
    Returns dict with: ok, valid, issues, hint
    """
    # Normalise line endings/BOM only. normalize_code() also injects the
    # SAFE_INPUT_PATCH prelude, which shifted every reported line number by
    # PRELUDE_LINE_COUNT and made "Line 11" point at the user's line 2.
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    if code.startswith("\ufeff"):
        code = code[1:]
    code = "\n".join(line.rstrip() for line in code.split("\n"))

    # Strip comments and string literals to prevent bracket/quote imbalances inside them
    clean_code, string_issues = strip_comments_and_strings(code)
    issues = list(string_issues)

    # Check balanced parentheses
    paren_open = clean_code.count('(')
    paren_close = clean_code.count(')')
    if paren_open != paren_close:
        issues.append(f"Parenthesis () imbalance: {paren_open} '(' vs {paren_close} ')'")

    # Check balanced brackets
    bracket_open = clean_code.count('[')
    bracket_close = clean_code.count(']')
    if bracket_open != bracket_close:
        issues.append(f"Brackets [] imbalance: {bracket_open} '[' vs {bracket_close} ']'")

    # Check balanced braces
    brace_open = clean_code.count('{')
    brace_close = clean_code.count('}')
    if brace_open != brace_close:
        issues.append(f"Braces {{}} imbalance: {brace_open} '{{' vs {brace_close} '}}'")

    # Check for missing indentation after a colon (likely IndentationError)
    lines = code.split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip()
        if stripped.endswith(':') and i < len(lines):
            next_line = lines[i]
            ns = next_line.strip()
            if ns and not next_line.startswith(' ') and not next_line.startswith('\t'):
                if not ns.startswith('#') and not ns.startswith('"""') and not ns.startswith("'''"):
                    issues.append(f"Line {i+1}: missing indentation after ':' on line {i}")

    return {
        "ok": True,
        "valid": len(issues) == 0,
        "issues": issues,
        "hint": "Fix all issues above before running code" if issues else None
    }
