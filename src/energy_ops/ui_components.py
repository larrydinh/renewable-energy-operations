"""Presentation helpers for the reference-inspired operations dashboard."""

from html import escape

import pandas as pd
import streamlit as st

PHASES = {
    "succeeded": ("Succeeded", "success"),
    "no_change": ("No change", "warning"),
    "failed": ("Failed", "danger"),
    "running": ("Running", "info"),
}

CSS = """
<style>
.stApp {background:#fff; color:#233347;}
.block-container {padding:5rem 2rem 2rem; max-width:1800px;}
header[data-testid="stHeader"] {height:0; background:transparent;}
.ops-topbar {position:fixed; top:0; left:0; right:0; height:52px; background:#073b70;
    color:white; z-index:100000; display:flex; align-items:center; gap:13px;
    padding:0 22px 0 244px; font-size:12px; font-weight:700; letter-spacing:.035em;}
.ops-topbar svg {width:25px; height:29px;}
.ops-environment {margin-left:auto; border:1px solid #54779a; border-radius:20px;
    padding:5px 12px; font-size:10px; letter-spacing:.08em;}
h1 {font-size:1.65rem!important; font-weight:700!important; letter-spacing:-.025em;
    color:#1d2938; padding-top:0!important;}
h2,h3 {font-size:1rem!important; font-weight:650!important; color:#34445a;}
[data-testid="stCaptionContainer"] {color:#738196;}
[data-testid="stSidebar"] {background:#fff; border-right:1px solid #e4e7eb;
    min-width:222px!important; max-width:222px!important;}
[data-testid="stSidebar"]::before {content:""; position:fixed; top:0; left:0;
    width:222px; height:52px; background:#073b70; z-index:99999;}
[data-testid="stSidebarUserContent"] {padding:4rem .65rem 1rem;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    padding:9px 10px; border-radius:6px; margin:3px 0; width:100%;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background:#073b70; color:#fff;}
[data-testid="stSidebar"] [data-testid="stRadio"] p {font-size:13px;}
[data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {display:none;}
[data-testid="stSidebar"] [data-testid="stExpander"] {border:0;}
[data-testid="stSidebarCollapsedControl"] {top:60px!important; z-index:100001;}
.ops-kicker {font-size:10px; font-weight:650; color:#94a1b3; letter-spacing:.07em;}
.ops-card {position:relative; border:1px solid #e7e9ed; border-radius:13px;
    padding:17px 19px; min-height:105px; margin-bottom:12px; background:#fff;
    box-shadow:0 1px 2px rgba(15,30,45,.045);}
.ops-card-label {font-size:10px; font-weight:700; letter-spacing:.045em;
    color:#8c9bb0; margin-bottom:5px; padding-right:42px;}
.ops-card-value {font-size:24px; line-height:1.2; font-weight:700; color:#263442;}
.ops-card-footnote {font-size:10px; color:#8b98a8; margin-top:7px; padding-right:25px;}
.ops-card-icon {position:absolute; right:17px; top:30px; width:34px; height:34px;
    display:flex; align-items:center; justify-content:center; border-radius:10px;
    font-size:19px; font-weight:700; color:#1d5be2; background:#eff5ff;}
.ops-card-icon.success {color:#13a454; background:#effbf4;}
.ops-card-icon.danger {color:#dc294c; background:#fff1f4;}
.ops-card-icon.warning {color:#d48b06; background:#fff8e9;}
.ops-online {color:#16a158; font-size:23px; font-weight:650;}
.ops-offline {color:#d93745; font-size:23px; font-weight:650;}
.ops-table-wrap {max-height:410px; overflow:auto; border:1px solid #e1e5eb; border-radius:3px;}
.ops-table {width:100%; border-collapse:collapse; font-size:12px;}
.ops-table th {background:#5d99d4; color:#fff; font-size:11px; font-weight:600;
    padding:12px 14px; position:sticky; top:0; z-index:1; text-align:left; white-space:nowrap;}
.ops-table td {padding:11px 14px; border-bottom:1px solid #dfe3e8; white-space:nowrap;}
.ops-table tbody tr:hover {background:#f7faff;}
.ops-table .empty {color:#8895a5; text-align:center; padding:24px;}
.ops-badge {font-size:10px; font-weight:600; color:#fff; border-radius:3px; padding:2px 6px;}
.ops-badge.success {background:#54ad63;}
.ops-badge.danger {background:#e94d4a;}
.ops-badge.warning {background:#e6a324;}
.ops-badge.info {background:#5d99d4;}
.ops-badge.neutral {background:#9da5af;}
.ops-small {font-size:11px; color:#8290a0;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:13px; border-color:#e7e9ed;}
div[data-testid="stMetric"] {border:1px solid #e7e9ed; border-radius:12px;
    padding:13px 16px; background:#fff;}
div[data-testid="stMetricValue"] {font-size:1.65rem;}
div[data-testid="stMetricLabel"] p {font-size:.8rem; white-space:normal;}
@media (max-width:900px) {.ops-topbar {padding-left:22px;}
    .block-container {padding-left:1rem; padding-right:1rem;}}
</style>
"""


def shell() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ops-topbar">
        <svg viewBox="0 0 32 36" fill="none" aria-hidden="true">
          <path d="M16 14L13 34h7L17 14M16 14L13 2l4-1 1 12M16 14L3 19l-1-4 12-3
                   M16 14l12 9 3-3-13-8" fill="white"/>
          <circle cx="16" cy="14" r="3" fill="white"/>
        </svg> ENERGY OPERATIONS <span class="ops-environment">LOCAL</span></div>
    """,
        unsafe_allow_html=True,
    )


def card(label: str, value: str, note: str, icon: str = "▦", tone: str = "info") -> None:
    st.markdown(
        f'<div class="ops-card"><div class="ops-card-label">{escape(label)}</div>'
        f'<div class="ops-card-value">{escape(value)}</div>'
        f'<div class="ops-card-footnote">{escape(note)}</div>'
        f'<span class="ops-card-icon {escape(tone)}">{escape(icon)}</span></div>',
        unsafe_allow_html=True,
    )


def service_card(label: str, online: bool, checked_at: str) -> None:
    css = "ops-online" if online else "ops-offline"
    icon, tone = ("✓", "success") if online else ("!", "danger")
    st.markdown(
        f'<div class="ops-card"><div class="ops-card-label">{escape(label)}</div>'
        f'<div class="{css}">{icon} {"Online" if online else "Unavailable"}</div>'
        f'<div class="ops-card-footnote">Checked: {escape(checked_at)}</div>'
        f'<span class="ops-card-icon {tone}">{icon}</span></div>',
        unsafe_allow_html=True,
    )


def html_table(frame: pd.DataFrame, *, phase_column: str | None = None) -> None:
    """Render escaped cells; status badge markup comes only from our own allowlist."""
    header = "".join(f"<th>{escape(str(column))}</th>" for column in frame.columns)
    rows = []
    for values in frame.itertuples(index=False, name=None):
        cells = []
        for column, value in zip(frame.columns, values, strict=True):
            if column == phase_column:
                label, tone = PHASES.get(str(value), (str(value), "neutral"))
                cells.append(f'<td><span class="ops-badge {tone}">{escape(label)}</span></td>')
            else:
                cells.append(f"<td>{escape(str(value))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    if not rows:
        rows.append(
            f'<tr><td class="empty" colspan="{len(frame.columns)}">No matching records</td></tr>'
        )
    st.markdown(
        f'<div class="ops-table-wrap"><table class="ops-table"><thead><tr>{header}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )
