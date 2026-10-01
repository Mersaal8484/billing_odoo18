"""Convert the Odoo 16 XML view syntax in this repository to Odoo 18.

This migration helper is deliberately conservative: it supports the legacy
domain operators used by the Utility ERP views and fails on unsupported
expressions instead of leaving a partially migrated view behind.
"""

from __future__ import annotations

import ast
import html
import re
from pathlib import Path


MODULES = ("utility_core", "utility_inventory", "utility_operations", "utility_billing")
SUPPORTED_ATTRIBUTES = {"invisible", "readonly", "required", "column_invisible"}
OPERATORS = {
    "=": "==",
    "==": "==",
    "!=": "!=",
    ">": ">",
    ">=": ">=",
    "<": "<",
    "<=": "<=",
    "in": "in",
    "not in": "not in",
}


def _value(value):
    return repr(value)


def _leaf_to_expression(leaf):
    field, operator, value = leaf
    if operator == "=?":
        return f"(not {_value(value)} or {field} == {_value(value)})"
    if operator not in OPERATORS:
        raise ValueError(f"Unsupported legacy domain operator: {operator!r}")
    return f"{field} {OPERATORS[operator]} {_value(value)}"


def domain_to_expression(domain):
    if isinstance(domain, bool):
        return repr(domain)
    if not isinstance(domain, list):
        raise ValueError(f"Expected a domain list, got {domain!r}")
    if not domain:
        return "True"

    def parse(index):
        token = domain[index]
        if token == "!":
            child, end = parse(index + 1)
            return f"not ({child})", end
        if token in ("|", "&"):
            left, end = parse(index + 1)
            right, end = parse(end)
            joiner = "or" if token == "|" else "and"
            return f"({left}) {joiner} ({right})", end
        if not isinstance(token, (tuple, list)) or len(token) != 3:
            raise ValueError(f"Unsupported domain token: {token!r}")
        return _leaf_to_expression(token), index + 1

    expressions = []
    index = 0
    while index < len(domain):
        expression, index = parse(index)
        expressions.append(f"({expression})")
    return " and ".join(expressions)


def _xml_escape(expression):
    return expression.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _combine(existing, value):
    if not existing:
        return value
    return f"({existing}) or ({value})"


def migrate_attributes(text, path):
    pattern = re.compile(r'\battrs="([^"]*)"')
    offset = 0
    while match := pattern.search(text, offset):
        before = text
        raw = html.unescape(match.group(1))
        attributes = ast.literal_eval(raw)
        unknown = set(attributes) - SUPPORTED_ATTRIBUTES
        if unknown:
            raise ValueError(f"{path}: unsupported attrs keys {sorted(unknown)}")
        tag_start = text.rfind("<", 0, match.start())
        tag_end = text.find(">", match.end()) + 1
        tag = text[tag_start:tag_end]
        replacements = []
        for name, domain in attributes.items():
            expression = _xml_escape(domain_to_expression(domain))
            if name == "column_invisible" and "meter_line_type" in expression:
                name = "invisible"
            replacements.append((name, expression))
        for name, expression in replacements:
            existing = re.search(rf'\b{name}="([^"]*)"', tag)
            if existing:
                joined = _combine(html.unescape(existing.group(1)), expression)
                tag = tag[:existing.start(1)] + joined + tag[existing.end(1):]
            else:
                self_closing = tag.rstrip().endswith("/>")
                tag = tag.rstrip()
                if self_closing:
                    tag = tag[:-2].rstrip() + f' {name}="{expression}"/>'
                else:
                    tag += f' {name}="{expression}"'
        tag = re.sub(r'\s+attrs="[^"]*"', "", tag, count=1)
        text = text[:tag_start] + tag + text[tag_end:]
        offset = tag_start + len(tag)
        if text == before:
            raise ValueError(f"{path}: failed to convert attrs attribute")
    return text


def migrate_states(text, path):
    pattern = re.compile(r'\bstates="([^"]+)"')
    while match := pattern.search(text):
        states = tuple(part.strip() for part in match.group(1).split(",") if part.strip())
        if not states:
            raise ValueError(f"{path}: empty states attribute")
        values = ", ".join(repr(state) for state in states)
        invisible = f"state not in ({values})"
        tag_start = text.rfind("<", 0, match.start())
        tag_end = text.find(">", match.end()) + 1
        tag = text[tag_start:tag_end]
        existing = re.search(r'\binvisible="([^"]*)"', tag)
        if existing:
            invisible = f"({html.unescape(existing.group(1))}) or ({invisible})"
            tag = tag[:existing.start(1)] + _xml_escape(invisible) + tag[existing.end(1):]
            tag = re.sub(r'\s+states="[^"]*"', "", tag, count=1)
        else:
            self_closing = tag.rstrip().endswith("/>")
            tag = tag.rstrip()
            if self_closing:
                tag = tag[:-2].rstrip() + f' invisible="{_xml_escape(invisible)}"/>'
            else:
                tag += f' invisible="{_xml_escape(invisible)}"'
            tag = re.sub(r'\s+states="[^"]*"', "", tag, count=1)
        text = text[:tag_start] + tag + text[tag_end:]
    return text


def migrate_file(path):
    text = path.read_text(encoding="utf-8")
    original = text
    # Repair self-closing tags from files migrated by an earlier script version.
    text = re.sub(
        r'/((?:\s+(?:invisible|readonly|required|column_invisible)="[^"]*")+)\s*>',
        r'\1/>',
        text,
    )
    text = migrate_attributes(text, path)
    text = migrate_states(text, path)
    text = re.sub(r"<tree(?=[\s>])", "<list", text)
    text = text.replace("</tree>", "</list>")
    text = re.sub(
        r'(<field\s+name="view_mode">)([^<]*)(</field>)',
        lambda match: match.group(1) + re.sub(r"\btree\b", "list", match.group(2)) + match.group(3),
        text,
    )
    text = re.sub(
        r"(view_mode\s*['\"]?\s*:\s*['\"])([^'\"]*)(['\"])",
        lambda match: match.group(1) + re.sub(r"\btree\b", "list", match.group(2)) + match.group(3),
        text,
    )
    if text != original:
        path.write_text(text, encoding="utf-8", newline="")


def main():
    for module in MODULES:
        for path in Path(module).rglob("*"):
            if path.suffix in (".xml", ".py"):
                migrate_file(path)


if __name__ == "__main__":
    main()
