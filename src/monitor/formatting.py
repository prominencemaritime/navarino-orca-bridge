# src/monitor/formatting.py
"""
Plain-text and HTML rendering for the vessel monitor.

The HTML follows the look of the approved-no-po alerts (same header colour,
table and badge styling) but is specific to vessel reporting status.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import List, Optional
from zoneinfo import ZoneInfo

from src.monitor.log_scanner import ScanResult, VesselStatus

COMPANY_NAME = "Prominence Maritime SA"

STATUS_BADGES = {
    "OK":      ("#e8f5e9", "#2e7d32", "#43a047"),
    "STALE":   ("#fff3e0", "#e65100", "#fb8c00"),
    "MISSING": ("#fde8e8", "#c0392b", "#e74c3c"),
    "PENDING": ("#eceff1", "#546e7a", "#90a4ae"),
}


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text: str
    html: str


# ----------------------------------------------------------------------
# Small formatters
# ----------------------------------------------------------------------

def format_dt(value: Optional[datetime], tz: str) -> str:
    if value is None:
        return "never"
    return value.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")


def format_duration(hours: Optional[float]) -> str:
    if hours is None:
        return "n/a"
    total_minutes = int(round(hours * 60))
    days, remainder = divmod(total_minutes, 24 * 60)
    hrs, mins = divmod(remainder, 60)
    parts = [f"{days}d"] if days else []
    if hrs:
        parts.append(f"{hrs}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts)


def _hours_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    if start is None or end is None:
        return None
    return max((end - start).total_seconds(), 0.0) / 3600


# ----------------------------------------------------------------------
# Plain-text status table (CLI and email text part)
# ----------------------------------------------------------------------

def render_status_text(result: ScanResult, tz: str = "UTC") -> str:
    lines = [
        f"Checked at: {format_dt(result.checked_at, tz)} {tz}"
        f" | outage threshold: {format_duration(result.threshold_hours)}"
        f" | basis: {result.basis}",
        f"Log files checked: {len(result.files)}"
        + (f" (earliest entry {format_dt(result.coverage_start, tz)} {tz})"
           if result.coverage_start else ""),
        "",
        f"{'VESSEL':<14} {'IMO':<9} {'STATUS':<9} "
        f"{'LAST POSITION (' + tz + ')':<22} {'LAST POST (' + tz + ')':<22} AGE",
        "-" * 88,
    ]
    for v in result.vessels:
        lines.append(
            f"{v.ref_code:<14} {v.imo:<9} {v.status:<9} "
            f"{format_dt(v.last_position_at, tz):<22} {format_dt(v.last_post_at, tz):<22} "
            f"{format_duration(v.age_hours)}"
        )
    return "\n".join(lines)


# ----------------------------------------------------------------------
# HTML building blocks
# ----------------------------------------------------------------------

def _badge(status: str) -> str:
    background, colour, border = STATUS_BADGES.get(status, STATUS_BADGES["PENDING"])
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:4px;'
        f'font-size:12px;font-weight:700;letter-spacing:0.4px;background-color:{background};'
        f'color:{colour};border:1px solid {border};">{escape(status)}</span>'
    )


def _status_table_html(vessels: List[VesselStatus], tz: str) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(v.ref_code)}</td>"
        f"<td>{escape(v.imo)}</td>"
        f"<td>{_badge(v.status)}</td>"
        f"<td>{escape(format_dt(v.last_position_at, tz))}</td>"
        f"<td>{escape(format_dt(v.last_post_at, tz))}</td>"
        f"<td>{escape(format_duration(v.age_hours))}</td>"
        "</tr>"
        for v in vessels
    )
    tz_label = escape(tz)
    return (
        '<div class="table-wrapper"><table><thead><tr>'
        "<th>Vessel</th><th>IMO</th><th>Status</th>"
        f"<th>Last Position ({tz_label})</th><th>Last ORCA POST ({tz_label})</th><th>Age</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def _key_value_table_html(rows: List[tuple]) -> str:
    body = "".join(
        f'<tr><td style="font-weight:600;color:#0B4877;padding:4px 0;width:220px;">'
        f"{escape(label)}:</td><td style=\"padding:4px 0;\">{value}</td></tr>"
        for label, value in rows
    )
    return (
        '<div class="metadata"><table role="presentation" '
        f'style="width:100%;border-collapse:collapse;">{body}</table></div>'
    )


def _intro_html(paragraphs: List[str]) -> str:
    inner = "".join(f'<p style="margin:0 0 10px 0;">{p}</p>' for p in paragraphs)
    return (
        '<div style="background-color:#fff;padding:20px;border-left:4px solid #2EA9DE;'
        f'margin-bottom:0;line-height:1.8;">{inner}</div>'
    )


def _page(title: str, subtitle: str, body_html: str, logo_cid: Optional[str]) -> str:
    logo_html = (
        f'<img src="cid:{escape(logo_cid)}" alt="Triton logo" style="max-height:50px;">'
        if logo_cid else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    body {{ font-family: Tahoma, Verdana, "Segoe UI", Roboto, Arial, sans-serif; font-size: 13px;
           background-color: #f9fafc; color: #333; line-height: 1.6; margin: 0; padding: 0; }}
    .container {{ max-width: 1000px; width: 95%; margin: 30px auto; background: #ffffff;
                 border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); overflow: hidden; }}
    .header {{ background-color: #0B4877; color: white; padding: 20px 30px; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
    .header p {{ margin: 5px 0 0 0; font-size: 14px; color: #d7e7f5; }}
    .content {{ padding: 30px; }}
    .metadata {{ background-color: #f5f8fb; margin: 10px 0; padding: 10px 15px; border-radius: 8px;
                border-left: 4px solid #2EA9DE; }}
    .table-wrapper {{ overflow-x: auto; margin: 20px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ background-color: #0B4877; color: white; text-align: left; padding: 10px 12px; font-weight: 600; }}
    td {{ padding: 9px 12px; border-bottom: 1px solid #e0e6ed; }}
    tr:nth-child(even) {{ background-color: #f5f8fb; }}
    .footer {{ font-size: 12px; color: #888; text-align: center; padding: 20px;
              border-top: 1px solid #eee; background-color: #f9fafc; }}
</style>
</head>
<body>
<div class="container">
    <div class="header" style="background-color:#0B4877;color:#ffffff;padding:20px 30px;">
        <table role="presentation" style="width:100%;border-collapse:collapse;">
            <tr>
                <td style="border:none;padding:0;vertical-align:middle;">{logo_html}</td>
                <td style="border:none;padding:0;text-align:right;vertical-align:middle;color:#ffffff;">
                    <h1 style="margin:0;font-size:22px;font-weight:600;color:#ffffff;">{escape(title)}</h1>
                    <p style="margin:5px 0 0 0;font-size:14px;color:#d7e7f5;">{escape(subtitle)}</p>
                </td>
            </tr>
        </table>
    </div>
    <div class="content">
{body_html}
    </div>
    <div class="footer">
        <p>This is an automated notification from the {escape(COMPANY_NAME)}.</p>
        <p>If you have questions, please contact your system administrator.</p>
    </div>
</div>
</body>
</html>
"""


def _subtitle(checked_at: datetime, tz: str) -> str:
    return checked_at.astimezone(ZoneInfo(tz)).strftime("%A, %d %B %Y \u2022 %H:%M %Z")


def _text_footer() -> str:
    return (
        "\n" + "=" * 70 + "\n"
        f"This is an automated notification from the {COMPANY_NAME}.\n"
        "If you have questions, please contact your system administrator.\n"
        + "=" * 70 + "\n"
    )


# ----------------------------------------------------------------------
# Emails
# ----------------------------------------------------------------------

def build_outage_email(
    result: ScanResult,
    repeat_hours: float,
    tz: str,
    logo_cid: Optional[str],
) -> EmailContent:
    """Digest listing every vessel, sent while at least one vessel is STALE/MISSING."""
    failing = result.failing
    names = ", ".join(v.ref_code for v in failing)
    subject = f'AlertDev | "{names}" Not Reporting Locations'
    threshold = format_duration(result.threshold_hours)
    repeat = format_duration(repeat_hours)

    intro = [
        f"The following vessel{'s have' if len(failing) != 1 else ' has'} not reported a "
        f"location to ORCA for more than <strong>{escape(threshold)}</strong>: "
        f"<strong>{escape(names)}</strong>.",
        f"This alert repeats every {escape(repeat)} while the condition persists. "
        "A separate email is sent when each vessel reports again.",
    ]
    notes = []
    if result.issues:
        notes.append(
            f"Note: {len(result.issues)} log read/parse issue(s) were found during this check, "
            "so the table below may be incomplete."
        )

    html_body = (
        _intro_html(intro + [escape(n) for n in notes])
        + _status_table_html(result.vessels, tz)
        + _key_value_table_html([
            ("Outage threshold", escape(threshold)),
            ("Judged on", escape("position timestamp" if result.basis == "position" else "POST time")),
            ("Log files checked", str(len(result.files))),
        ])
    )

    text = (
        "=" * 70 + "\nVessels Not Reporting Locations\n"
        + _subtitle(result.checked_at, tz) + "\n" + "=" * 70 + "\n\n"
        + f"Not reporting for more than {threshold}: {names}\n"
        + f"This alert repeats every {repeat} while the condition persists.\n"
        + "".join(f"{n}\n" for n in notes)
        + "\n" + render_status_text(result, tz) + "\n"
        + _text_footer()
    )

    html = _page("Vessels Not Reporting Locations", _subtitle(result.checked_at, tz), html_body, logo_cid)
    return EmailContent(subject=subject, text=text, html=html)


def build_recovery_email(
    vessel: VesselStatus,
    outage_declared_at: Optional[datetime],
    last_seen_before_outage: Optional[datetime],
    checked_at: datetime,
    tz: str,
    logo_cid: Optional[str],
) -> EmailContent:
    """Per-vessel email sent when a vessel in a declared outage reports again."""
    subject = f"AlertDev | {vessel.ref_code} API Online"
    downtime = format_duration(_hours_between(last_seen_before_outage, vessel.reference_at))

    rows = [
        ("Vessel", escape(vessel.ref_code)),
        ("IMO", escape(vessel.imo)),
        ("Last update before outage", escape(f"{format_dt(last_seen_before_outage, tz)} {tz}")),
        ("Outage alert first sent", escape(f"{format_dt(outage_declared_at, tz)} {tz}")),
        ("Reporting again since", escape(f"{format_dt(vessel.reference_at, tz)} {tz}")),
        ("Approximate downtime", escape(downtime)),
    ]

    html_body = _intro_html([
        f"<strong>{escape(vessel.ref_code)}</strong> (IMO {escape(vessel.imo)}) is reporting "
        "locations to ORCA again.",
    ]) + _key_value_table_html(rows)

    text = (
        "=" * 70 + f"\n{vessel.ref_code} API Online\n"
        + _subtitle(checked_at, tz) + "\n" + "=" * 70 + "\n\n"
        + f"{vessel.ref_code} (IMO {vessel.imo}) is reporting locations to ORCA again.\n\n"
        + "".join(f"  {label}: {value}\n" for label, value in [
            ("Last update before outage", f"{format_dt(last_seen_before_outage, tz)} {tz}"),
            ("Outage alert first sent", f"{format_dt(outage_declared_at, tz)} {tz}"),
            ("Reporting again since", f"{format_dt(vessel.reference_at, tz)} {tz}"),
            ("Approximate downtime", downtime),
        ])
        + _text_footer()
    )

    html = _page(f"{vessel.ref_code} API Online", _subtitle(checked_at, tz), html_body, logo_cid)
    return EmailContent(subject=subject, text=text, html=html)


def build_parse_issue_email(
    result: ScanResult,
    tz: str,
    logo_cid: Optional[str],
    max_issues: int = 50,
) -> EmailContent:
    """Technical email listing log read/parse issues found within the threshold window."""
    count = len(result.issues)
    subject = f"AlertDev | Vessel Monitor: {count} Log Parse Issue{'s' if count != 1 else ''}"
    shown = result.issues[:max_issues]
    more = count - len(shown)

    items = "".join(f"<li><code>{escape(i.describe())}</code></li>" for i in shown)
    if more:
        items += f"<li>... and {more} more (see the monitor log)</li>"

    html_body = _intro_html([
        f"The vessel monitor found <strong>{count}</strong> read/parse issue"
        f"{'s' if count != 1 else ''} in the bridge logs. Vessel statuses from this check "
        "may be incomplete.",
    ]) + f'<ul style="line-height:1.8;">{items}</ul>' + _status_table_html(result.vessels, tz)

    text = (
        "=" * 70 + "\nVessel Monitor Log Parse Issues\n"
        + _subtitle(result.checked_at, tz) + "\n" + "=" * 70 + "\n\n"
        + "".join(f"- {i.describe()}\n" for i in shown)
        + (f"- ... and {more} more (see the monitor log)\n" if more else "")
        + "\n" + render_status_text(result, tz) + "\n"
        + _text_footer()
    )

    html = _page("Vessel Monitor Log Parse Issues", _subtitle(result.checked_at, tz), html_body, logo_cid)
    return EmailContent(subject=subject, text=text, html=html)
