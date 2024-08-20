from typing import Any, Sequence


def join_args_with_quote(*args):
    args = [f'`{a}`' for a in args]
    args_str = ', '.join(args)
    return '(' + args_str + ')'


def format_properties(**kwargs):
    entries = []
    for k, v in kwargs.items():
        entry = f'"{k}" = "{v}",'
        entries.append(entry)
    result_str = '\n    '.join(entries)
    return '(\n    ' + result_str[:-1] + '\n)'


def ensure_sequence(value: Any) -> Sequence:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list|tuple):
        return value
    return [value]