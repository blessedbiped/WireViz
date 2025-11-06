# -*- coding: utf-8 -*-

from dataclasses import asdict
from itertools import groupby
from typing import Any, Dict, List, Optional, Tuple, Union, Set

from wireviz.DataClasses import AdditionalComponent, Cable, Color, Connector
from wireviz.wv_colors import translate_color
from wireviz.wv_gv_html import html_bgcolor_attr, html_line_breaks
from wireviz.wv_helper import clean_whitespace

BOM_COLUMNS_ALWAYS = ("id", "description", "qty", "unit", "designators")
BOM_COLUMNS_OPTIONAL = ("pn", "manufacturer", "mpn", "supplier", "spn")
BOM_COLUMNS_IN_KEY = ("description", "unit") + BOM_COLUMNS_OPTIONAL

HEADER_PN = "P/N"
HEADER_MPN = "MPN"
HEADER_SPN = "SPN"

BOMKey = Tuple[str, ...]
BOMColumn = str  # = Literal[*BOM_COLUMNS_ALWAYS, *BOM_COLUMNS_OPTIONAL]
BOMEntry = Dict[BOMColumn, Union[str, int, float, List[str], None]]


def optional_fields(part: Union[Connector, Cable, AdditionalComponent]) -> BOMEntry:
    """Return part field values for the optional BOM columns as a dict."""
    part = asdict(part)
    return {field: part.get(field) for field in BOM_COLUMNS_OPTIONAL}


def get_additional_component_table(
    harness: "Harness", component: Union[Connector, Cable]
) -> List[str]:
    """Return a list of diagram node table row strings with additional components.

    Special handling:
    - Parts with qty_multiplier == 'unpopulated' are included when there are cavities
      on the connector with no wires. The quantity shown is the number of such cavities
      the part applies to (honouring alias if present).
    """
    rows = []
    if component.additional_components:
        rows.append(["Additional components"])
        # Process each part, including 'unpopulated' parts when applicable
        for part in component.additional_components:
            # Determine the effective per-component count depending on qty_multiplier.
            qm = str(part.qty_multiplier).lower() if part.qty_multiplier else ""
            if qm == "unpopulated":
                # compute how many cavities this applies to (requires harness/connector context)
                count = _count_unwired_cavities(harness, component, part)
                if count <= 0:
                    continue
                # treat missing qty as 1
                try:
                    per_item = int(part.qty) if part.qty is not None else 1
                except Exception:
                    try:
                        per_item = float(part.qty)
                    except Exception:
                        per_item = 1
                qty = int(per_item * count)
                common_args = {
                    "qty": qty,
                    "unit": part.unit,
                    "bgcolor": part.bgcolor,
                }
            else:
                # fallback to existing behaviour for other multipliers (including 'populated')
                multiplier = component.get_qty_multiplier(part.qty_multiplier)
                if not multiplier:
                    continue
                # treat missing qty as 1 and coerce numeric values
                try:
                    per_item = int(part.qty) if part.qty is not None else 1
                except Exception:
                    try:
                        per_item = float(part.qty)
                    except Exception:
                        per_item = 1
                common_args = {
                    "qty": per_item * multiplier,
                    "unit": part.unit,
                    "bgcolor": part.bgcolor,
                }

            if harness.options.mini_bom_mode:
                id = get_bom_index(
                    harness.bom(),
                    bom_entry_key({**asdict(part), "description": part.description}),
                )
                rows.append(
                    component_table_entry(f"#{id} ({part.type.rstrip()})", **common_args)
                )
            else:
                rows.append(
                    component_table_entry(
                        part.description, **common_args, **optional_fields(part)
                    )
                )
    return rows


def get_additional_component_bom(harness: "Harness", component: Union[Connector, Cable]) -> List[BOMEntry]:
    """Return a list of BOM entries with additional components.

    Behaviour changes:
    - For parts with qty_multiplier == 'unpopulated' we add an entry for each unwired cavity
      (honouring alias matching if alias is present). This allows duplicates of the same alias
      token in contact definition to be counted separately.
    """
    bom_entries = []
    for part in component.additional_components:
        qm = str(part.qty_multiplier).lower() if part.qty_multiplier else ""
        if qm == "unpopulated":
            count = _count_unwired_cavities(harness, component, part)
            if count <= 0:
                continue
            per_pos = 1
            try:
                if part.qty is not None:
                    per_pos = int(part.qty)
            except Exception:
                try:
                    per_pos = float(part.qty)
                except Exception:
                    per_pos = 1
            bom_entries.append(
                {
                    "description": part.description,
                    "qty": int(count * per_pos),
                    "unit": part.unit,
                    "designators": component.name if component.show_name else None,
                    **optional_fields(part),
                }
            )
            continue

        # Ignore components that have qty 0 according to existing multiplier logic
        multiplier = component.get_qty_multiplier(part.qty_multiplier)
        if not multiplier:
            continue

        # safe per-item qty (default 1)
        per_item = 1
        try:
            if part.qty is not None:
                per_item = int(part.qty)
        except Exception:
            try:
                per_item = float(part.qty)
            except Exception:
                per_item = 1

        bom_entries.append(
            {
                "description": part.description,
                "qty": per_item * multiplier,
                "unit": part.unit,
                "designators": component.name if component.show_name else None,
                **optional_fields(part),
            }
        )
    return bom_entries


# --- helper utilities for detecting wired/unwired cavities ---

def _parse_positions(spec_list) -> Set[int]:
    """Parse connection spec like ['1-4','6','8,10-12'] -> zero-based indices."""
    out = set()
    if spec_list is None:
        return out
    # allow int, str or list
    if isinstance(spec_list, int):
        out.add(spec_list - 1)
        return out
    if isinstance(spec_list, str):
        items = [spec_list]
    else:
        items = list(spec_list)
    for item in items:
        if item is None:
            continue
        for part in str(item).split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                try:
                    a, b = part.split("-", 1)
                    a_i = int(a)
                    b_i = int(b)
                    out.update(range(a_i - 1, b_i))
                except ValueError:
                    continue
            else:
                try:
                    out.add(int(part) - 1)
                except ValueError:
                    continue
    return out


def _wired_positions_for_connector(harness: "Harness", connector: Connector) -> Set[int]:
    """Return a set of zero-based contact indices that have wires connected to this connector."""
    wired = set()
    # Attempt to inspect harness.connections which mirrors the input connections YAML.
    if not hasattr(harness, "connections"):
        return wired
    for group in getattr(harness, "connections") or []:
        # group is likely iterable of items; each item may be dict mapping node->positions
        for item in group:
            if not isinstance(item, dict):
                continue
            for key, val in item.items():
                # connector identifiers may be stored in connector.name or connector.id
                if key == connector.name or key == connector.id:
                    wired.update(_parse_positions(val))
    return wired


def _count_unwired_cavities(harness: "Harness", component: Union[Connector, Cable], part: AdditionalComponent) -> int:
    """Count how many cavities this 'unpopulated' part should apply to.

    Rules:
    - If the part has an alias, match against connector contact tokens (pinlabels / contact_definition).
      Each matching occurrence that is unwired counts separately.
    - If the part has no alias, it applies to all unwired cavities on the connector.
    """
    if not isinstance(component, Connector):
        # For cables / non-connector components, fall back to existing multiplier behaviour (none)
        return 0

    # Determine number of positions and tokens
    tokens = []
    # prefer explicit contact_definition if present, else pinlabels, else construct numeric tokens
    if getattr(component, "contact_definition", None):
        tokens = list(component.contact_definition)
    elif getattr(component, "pinlabels", None):
        tokens = list(component.pinlabels)
    else:
        # fallback to numeric positions using pincount if available
        pincount = getattr(component, "pincount", None) or getattr(component, "wirecount", None) or 0
        tokens = [str(i + 1) for i in range(int(pincount) if pincount else 0)]

    wired = _wired_positions_for_connector(harness, component)
    unwired_indices = [i for i in range(len(tokens)) if i not in wired]

    if part.alias is not None:
        alias_str = str(part.alias)
        count = 0
        for i in unwired_indices:
            token = tokens[i] if i < len(tokens) else None
            if token == alias_str:
                count += 1
        return count
    else:
        return len(unwired_indices)


def bom_entry_key(entry: BOMEntry) -> BOMKey:
    """Return a tuple of string values from the dict that must be equal to join BOM entries."""
    if "key" not in entry:
        entry["key"] = tuple(
            clean_whitespace(make_str(entry.get(c))) for c in BOM_COLUMNS_IN_KEY
        )
    return entry["key"]


def generate_bom(harness: "Harness") -> List[BOMEntry]:
    """Return a list of BOM entries generated from the harness."""
    from wireviz.Harness import Harness  # Local import to avoid circular imports

    bom_entries = []
    # connectors
    for connector in harness.connectors.values():
        if not connector.ignore_in_bom:
            description = (
                "Connector"
                + (f", {connector.type}" if connector.type else "")
                + (f", {connector.subtype}" if connector.subtype else "")
                + (f", {connector.pincount} pins" if connector.show_pincount else "")
                + (
                    f", {translate_color(connector.color, harness.options.color_mode)}"
                    if connector.color
                    else ""
                )
            )
            bom_entries.append(
                {
                    "description": description,
                    "designators": connector.name if connector.show_name else None,
                    **optional_fields(connector),
                }
            )

        # add connectors aditional components to bom
        bom_entries.extend(get_additional_component_bom(harness, connector))

    # cables
    # TODO: If category can have other non-empty values than 'bundle', maybe it should be part of description?
    for cable in harness.cables.values():
        if not cable.ignore_in_bom:
            if cable.category != "bundle":
                # process cable as a single entity
                description = (
                    "Cable"
                    + (f", {cable.type}" if cable.type else "")
                    + (f", {cable.wirecount}")
                    + (
                        f" x {cable.gauge} {cable.gauge_unit}"
                        if cable.gauge
                        else " wires"
                    )
                    + (" shielded" if cable.shield else "")
                    + (
                        f", {translate_color(cable.color, harness.options.color_mode)}"
                        if cable.color
                        else ""
                    )
                )
                bom_entries.append(
                    {
                        "description": description,
                        "qty": cable.length,
                        "unit": cable.length_unit,
                        "designators": cable.name if cable.show_name else None,
                        **optional_fields(cable),
                    }
                )
            else:
                # add each wire from the bundle to the bom
                for index, color in enumerate(cable.colors):
                    description = (
                        "Wire"
                        + (f", {cable.type}" if cable.type else "")
                        + (f", {cable.gauge} {cable.gauge_unit}" if cable.gauge else "")
                        + (
                            f", {translate_color(color, harness.options.color_mode)}"
                            if color
                            else ""
                        )
                    )
                    bom_entries.append(
                        {
                            "description": description,
                            "qty": cable.length,
                            "unit": cable.length_unit,
                            "designators": cable.name if cable.show_name else None,
                            **{
                                k: index_if_list(v, index)
                                for k, v in optional_fields(cable).items()
                            },
                        }
                    )

        # add cable/bundles aditional components to bom
        bom_entries.extend(get_additional_component_bom(harness, cable))

    # add harness aditional components to bom directly, as they both are List[BOMEntry]
    bom_entries.extend(harness.additional_bom_items)

    # remove line breaks if present and cleanup any resulting whitespace issues
    bom_entries = [
        {k: clean_whitespace(v) for k, v in entry.items()} for entry in bom_entries
    ]

    # deduplicate bom
    bom = []
    for _, group in groupby(sorted(bom_entries, key=bom_entry_key), key=bom_entry_key):
        group_entries = list(group)
        designators = sum(
            (make_list(entry.get("designators")) for entry in group_entries), []
        )
        total_qty = sum(entry.get("qty", 1) for entry in group_entries)
        bom.append(
            {
                **group_entries[0],
                "qty": int(total_qty)
                if float(total_qty).is_integer()
                else round(total_qty, 3),
                "designators": sorted(set(designators)),
            }
        )

    # add an incrementing id to each bom entry
    return [{**entry, "id": index} for index, entry in enumerate(bom, 1)]


def get_bom_index(bom: List[BOMEntry], target: BOMKey) -> int:
    """Return id of BOM entry or raise exception if not found."""
    for entry in bom:
        if bom_entry_key(entry) == target:
            return entry["id"]
    raise Exception("Internal error: No BOM entry found matching: " + "|".join(target))


def bom_list(bom: List[BOMEntry]) -> List[List[str]]:
    """Return list of BOM rows as lists of column strings with headings in top row."""
    keys = list(BOM_COLUMNS_ALWAYS)  # Always include this fixed set of BOM columns.
    for fieldname in BOM_COLUMNS_OPTIONAL:
        # Include only those optional BOM columns that are in use.
        if any(entry.get(fieldname) for entry in bom):
            keys.append(fieldname)
    # Custom mapping from internal name to BOM column headers.
    # Headers not specified here are generated by capitilising the internal name.
    bom_headings = {
        "pn": HEADER_PN,
        "mpn": HEADER_MPN,
        "spn": HEADER_SPN,
    }
    return [
        [bom_headings.get(k, k.capitalize()) for k in keys]
    ] + [  # Create header row with key names
        [make_str(entry.get(k)) for k in keys] for entry in bom
    ]  # Create string list for each entry row


def component_table_entry(
    type: str,
    qty: Union[int, float],
    unit: Optional[str] = None,
    bgcolor: Optional[Color] = None,
    pn: Optional[str] = None,
    manufacturer: Optional[str] = None,
    mpn: Optional[str] = None,
    supplier: Optional[str] = None,
    spn: Optional[str] = None,
) -> str:
    """Return a diagram node table row string with an additional component."""
    part_number_list = [
        pn_info_string(HEADER_PN, None, pn),
        pn_info_string(HEADER_MPN, manufacturer, mpn),
        pn_info_string(HEADER_SPN, supplier, spn),
    ]
    output = (
        f"{qty}"
        + (f" {unit}" if unit else "")
        + f" x {type}"
        + ("<br/>" if any(part_number_list) else "")
        + (", ".join([pn for pn in part_number_list if pn]))
    )
    # format the above output as left aligned text in a single visible cell
    # indent is set to two to match the indent in the generated html table
    return f"""<table border="0" cellspacing="0" cellpadding="3" cellborder="1"{html_bgcolor_attr(bgcolor)}><tr>
   <td align="left" balign="left">{html_line_breaks(output)}</td>
  </tr></table>"""


def pn_info_string(
    header: str, name: Optional[str], number: Optional[str]
) -> Optional[str]:
    """Return the company name and/or the part number in one single string or None otherwise."""
    number = str(number).strip() if number is not None else ""
    if name or number:
        return f'{name if name else header}{": " + number if number else ""}'
    else:
        return None


def index_if_list(value: Any, index: int) -> Any:
    """Return the value indexed if it is a list, or simply the value otherwise."""
    return value[index] if isinstance(value, list) else value


def make_list(value: Any) -> list:
    """Return value if a list, empty list if None, or single element list otherwise."""
    return value if isinstance(value, list) else [] if value is None else [value]


def make_str(value: Any) -> str:
    """Return comma separated elements if a list, empty string if None, or value as a string otherwise."""
    return ", ".join(str(element) for element in make_list(value))
