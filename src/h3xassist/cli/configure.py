import os
from typing import TYPE_CHECKING, Any, get_args, get_origin

import typer
from pydantic import BaseModel
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text
from rich.tree import Tree

from h3xassist.logging import setup_logging
from h3xassist.settings import AppSettings, save_settings, settings
from h3xassist.ui import console

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic.fields import FieldInfo


def _is_secret_field(field_name: str) -> bool:
    name = field_name.lower()
    return any(tok in name for tok in ("token", "password", "secret", "key"))


def _format_breadcrumb(parts: list[str]) -> str:
    # Display-only breadcrumb using Title Case for readability
    return " > ".join(p.replace("_", " ").title() for p in parts) if parts else ""


def _label_for(field_name: str, field_info: "FieldInfo") -> str:
    return field_info.title or field_name.replace("_", " ").title()


def _desc_for(field_info: "FieldInfo") -> str | None:
    return field_info.description or None


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is None:
        return False
    args = tuple(get_args(annotation))
    return type(None) in args


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    args = tuple(get_args(annotation))
    non_none = [a for a in args if a is not type(None)]
    return non_none[0] if non_none else annotation


def _format_value_for_display(key_path: str, key_name: str, value: Any) -> str:
    path_l = key_path.lower()
    is_secret = _is_secret_field(key_name) or any(
        tok in path_l for tok in ("token", "password", "secret", "key")
    )
    if is_secret:
        return "[muted]<set>[/muted]" if value else "[muted]<not set>[/muted]"
    if value is None:
        return "[muted]None[/muted]"
    if isinstance(value, bool):
        return "[ok]True[/ok]" if value else "[warn]False[/warn]"
    if isinstance(value, int | float):
        return f"[cyan]{value}[/cyan]"
    if isinstance(value, str):
        return f'[text]"{value}"[/text]'
    return f"[text]{value}[/text]"


def _ask_value(
    field_name: str, field_info: "FieldInfo", current_value: Any, *, breadcrumb: list[str]
) -> Any:
    label = _label_for(field_name, field_info)
    desc = _desc_for(field_info)
    # Show full path to the setting for better orientation
    path_str = _format_breadcrumb([*breadcrumb, label])
    if path_str:
        console.print(f"[muted]{path_str}[/muted]")
    if desc:
        console.print(f"[muted]{desc}[/muted]")
    # Show environment variable hint
    env_key = "H3XASSIST_" + (
        "__".join([*(p.upper() for p in breadcrumb), field_name.upper()])
        if breadcrumb
        else field_name.upper()
    )
    console.print(f"[muted]ENV: {env_key}[/muted]")

    annotation = field_info.annotation
    base_type = _unwrap_optional(annotation)

    # Booleans via Confirm
    if base_type is bool:
        return bool(Confirm.ask(label, default=bool(current_value)))

    # Integers
    if base_type is int:

        def _valid_int(s: str) -> bool:
            s = s.strip()
            if s == "":
                return _is_optional(annotation)
            return s.isdigit() or (s.startswith("-") and s[1:].isdigit())

        raw = _ask_text(
            f"{label} [dim](int{' optional' if _is_optional(annotation) else ''})[/dim]",
            default=(str(current_value) if current_value is not None else None),
            validate=_valid_int,
        )
        if raw.strip() == "" and _is_optional(annotation):
            return None
        return int(raw)

    # Floats
    if base_type is float:

        def _valid_float(s: str) -> bool:
            s = s.strip()
            if s == "":
                return _is_optional(annotation)
            try:
                float(s)
                return True
            except ValueError:
                return False

        raw = _ask_text(
            f"{label} [dim](float{' optional' if _is_optional(annotation) else ''})[/dim]",
            default=(str(current_value) if current_value is not None else None),
            validate=_valid_float,
        )
        if raw.strip() == "" and _is_optional(annotation):
            return None
        return float(raw)

    # Strings (password mode for secrets)
    if base_type is str:
        is_secret = _is_secret_field(field_name)
        raw = _ask_text(
            f"{label} [dim](str{' optional' if _is_optional(annotation) else ''})[/dim]",
            default=(current_value if current_value is not None else None),
            password=is_secret,
        )
        if raw.strip() == "" and _is_optional(annotation):
            return None
        return raw

    # Unsupported primitive - return current as is
    return current_value


def _ask_text(
    label: str,
    default: str | None = None,
    *,
    password: bool = False,
    validate: "Callable[[str], bool] | None" = None,
) -> str:
    while True:
        value = Prompt.ask(
            label, default=default if default is not None else None, password=password
        )
        value = "" if value is None else str(value)
        value = value.strip()
        if validate is None or validate(value):
            return value
        console.print("[error]Invalid value[/error]. Please try again.")


def _edit_model_section(
    model: BaseModel, *, section_title: str, breadcrumb: list[str]
) -> dict[str, Any]:
    console.print()
    console.print(
        Panel(Text(_format_breadcrumb(breadcrumb), style="title"), style="cyan", expand=False)
    )

    model_cls = model.__class__
    result: dict[str, Any] = model.model_dump(mode="python")

    # Preview current section: description + current values tree
    section_field_info = None
    # Try to find this section's FieldInfo on parent model by matching last breadcrumb key
    if breadcrumb:
        # Root section keys align with AppSettings.model_fields
        try:
            from h3xassist.settings import AppSettings as _AppSettings

            section_field_info = _AppSettings.model_fields.get(breadcrumb[0])
        except Exception:
            section_field_info = None
    if section_field_info and section_field_info.description:
        console.print(f"[muted]{section_field_info.description}[/muted]")
    # Render mini-tree of current values in this section
    tree_label = (breadcrumb[-1].replace("_", " ").title()) if breadcrumb else section_title
    tree = Tree(tree_label, guide_style="muted")

    def _add_tree_nodes(parent: Tree, data: Any, *, prefix: str = "") -> None:
        if isinstance(data, dict):
            for k, v in data.items():
                next_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    node = parent.add(f"[bold]{k}[/bold]")
                    _add_tree_nodes(node, v, prefix=next_prefix)
                else:
                    parent.add(f"[bold]{k}[/bold]: {_format_value_for_display(next_prefix, k, v)}")
        else:
            parent.add(
                _format_value_for_display(prefix, prefix.split(".")[-1] if prefix else "", data)
            )

    _add_tree_nodes(tree, result)
    console.print(tree)

    # Ask whether to configure this section now
    if not Confirm.ask("Configure this section now?", default=False):
        return result

    for field_name, field_info in model_cls.model_fields.items():
        # Nested BaseModel fields
        inner_ann = _unwrap_optional(field_info.annotation)
        if isinstance(inner_ann, type) and issubclass(inner_ann, BaseModel):
            # Optional nested section toggle
            enabled = True
            if _is_optional(field_info.annotation):
                enabled = Confirm.ask(
                    f"Enable {field_info.title or field_name}?",
                    default=result.get(field_name) is not None,
                )
            if not enabled:
                result[field_name] = None
                continue

            current_dict = result.get(field_name) or {}
            nested_title = field_info.title or inner_ann.__name__
            # If we already have values, try instantiate; otherwise ask by schema
            if current_dict:
                try:
                    nested_model = inner_ann(**current_dict)
                    result[field_name] = _edit_model_section(
                        nested_model,
                        section_title=nested_title,
                        breadcrumb=[*breadcrumb, field_name],
                    )
                except Exception:
                    result[field_name] = _edit_model_section_from_schema(
                        inner_ann,
                        current_dict,
                        section_title=nested_title,
                        breadcrumb=[*breadcrumb, field_name],
                    )
            else:
                result[field_name] = _edit_model_section_from_schema(
                    inner_ann,
                    current_dict,
                    section_title=nested_title,
                    breadcrumb=[*breadcrumb, field_name],
                )
            continue

        # Primitive fields
        current_value = result.get(field_name)
        new_value = _ask_value(field_name, field_info, current_value, breadcrumb=breadcrumb)
        result[field_name] = new_value

    return result


def _edit_model_section_from_schema(
    model_cls: type[BaseModel],
    current_values: dict[str, Any],
    *,
    section_title: str,
    breadcrumb: list[str],
) -> dict[str, Any]:
    console.print()
    console.print(
        Panel(Text(_format_breadcrumb(breadcrumb), style="title"), style="cyan", expand=False)
    )

    result: dict[str, Any] = dict(current_values)

    # Preview values tree (description shown for root via AppSettings metadata)
    section_field_info = None
    if breadcrumb:
        try:
            from h3xassist.settings import AppSettings as _AppSettings

            section_field_info = _AppSettings.model_fields.get(breadcrumb[0])
        except Exception:
            section_field_info = None
    if section_field_info and section_field_info.description and len(breadcrumb) == 1:
        console.print(f"[muted]{section_field_info.description}[/muted]")
    tree_label = (breadcrumb[-1].replace("_", " ").title()) if breadcrumb else section_title
    tree = Tree(tree_label, guide_style="muted")

    def _add_tree_nodes(parent: Tree, data: Any, *, prefix: str = "") -> None:
        if isinstance(data, dict):
            for k, v in data.items():
                next_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    node = parent.add(f"[bold]{k}[/bold]")
                    _add_tree_nodes(node, v, prefix=next_prefix)
                else:
                    parent.add(f"[bold]{k}[/bold]: {_format_value_for_display(next_prefix, k, v)}")
        else:
            parent.add(
                _format_value_for_display(prefix, prefix.split(".")[-1] if prefix else "", data)
            )

    _add_tree_nodes(tree, result)
    console.print(tree)

    if not Confirm.ask("Configure this section now?", default=True):
        return result

    for field_name, field_info in model_cls.model_fields.items():
        inner_ann = _unwrap_optional(field_info.annotation)
        if isinstance(inner_ann, type) and issubclass(inner_ann, BaseModel):
            enabled = True
            if _is_optional(field_info.annotation):
                enabled = Confirm.ask(
                    f"Enable {field_info.title or field_name}?",
                    default=result.get(field_name) is not None,
                )
            if not enabled:
                result[field_name] = None
                continue
            nested_title = field_info.title or inner_ann.__name__
            inner_current = result.get(field_name) or {}
            if inner_current:
                try:
                    nested_model = inner_ann(**inner_current)
                    result[field_name] = _edit_model_section(
                        nested_model,
                        section_title=nested_title,
                        breadcrumb=[*breadcrumb, field_name],
                    )
                except Exception:
                    result[field_name] = _edit_model_section_from_schema(
                        inner_ann,
                        inner_current,
                        section_title=nested_title,
                        breadcrumb=[*breadcrumb, field_name],
                    )
            else:
                result[field_name] = _edit_model_section_from_schema(
                    inner_ann,
                    inner_current,
                    section_title=nested_title,
                    breadcrumb=[*breadcrumb, field_name],
                )
            continue

        current_value = result.get(field_name)
        result[field_name] = _ask_value(
            field_name, field_info, current_value, breadcrumb=breadcrumb
        )

    return result


def _flatten(prefix: str, value: Any, rows: list[tuple[str, Any]]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}.{k}" if prefix else k
            _flatten(key, v, rows)
    else:
        rows.append((prefix, value))


def run_setup_wizard() -> None:
    console.print(Panel(Text("H3XAssist Setup", justify="center", style="title"), expand=False))
    # Capture current state into a typed model to inherit defaults
    current = settings.model_dump(mode="python")
    typed = AppSettings(**current)

    updated: dict[str, Any] = {}

    # Iterate top-level sections using Pydantic metadata
    for section_name, field_info in AppSettings.model_fields.items():
        section_ann = _unwrap_optional(field_info.annotation)
        if isinstance(section_ann, type) and issubclass(section_ann, BaseModel):
            # Section header panel is handled inside _edit_model_section
            section_model = getattr(typed, section_name)
            section_title = field_info.title or section_ann.__name__
            updated[section_name] = _edit_model_section(
                section_model, section_title=section_title, breadcrumb=[section_name]
            )
        else:
            # Primitive at root (not expected, but supported)
            current_value = getattr(typed, section_name)
            updated[section_name] = _ask_value(
                section_name, field_info, current_value, breadcrumb=[section_name]
            )

    # Summary
    console.print()

    def _mask_if_secret(key: str, val: Any) -> Any:
        if _is_secret_field(key):
            return "<set>" if val else "<not set>"
        return val

    def _add_tree_nodes(parent: Tree, data: Any, *, prefix: str = "") -> None:
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    node = parent.add(k)
                    _add_tree_nodes(node, v, prefix=f"{prefix}.{k}" if prefix else k)
                else:
                    parent.add(f"{k}: {_mask_if_secret((prefix + '.' + k) if prefix else k, v)}")
        else:
            parent.add(str(data))

    tree = Tree("Settings", guide_style="muted")
    _add_tree_nodes(tree, updated)
    console.print(tree)

    if not Confirm.ask("Save these settings?", default=True):
        console.print("[warn]Aborted. No changes were saved.[/warn]")
        return

    save_settings(AppSettings(**updated))
    console.print("[ok]Configuration updated successfully.[/ok]")

    # Suggest standalone login command
    if updated.get("integrations", {}).get("outlook"):
        console.print(
            "[muted]Tip: run 'h3xassist setup outlook' to complete Outlook authorization now.[/muted]"
        )


def main(_args: Any) -> None:
    setup_logging(os.environ.get("H3XASSIST_LOG", "INFO"))
    run_setup_wizard()


# Typer sub-app
app = typer.Typer(help="Interactive configuration wizard")


@app.callback(invoke_without_command=True)
def cli_config(ctx: typer.Context) -> None:
    """Interactive configuration wizard."""
    if ctx.invoked_subcommand is None:
        run_setup_wizard()
