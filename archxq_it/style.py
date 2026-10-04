"""ArchXQ look: one stylesheet for every piece (hub, submenu, left strip,
view bar), plus the band used when a piece sits in a host toolbar."""
from __future__ import annotations

BLUE = "#2f6fb3"
PLAN = "#f07d14"     # the plan view switch: orange, never mistaken for blue

CSS = f"""
QFrame#axq_hub {{ background: transparent; }}
QFrame#axq_row, QFrame#axq_sub, QFrame#axq_strip, QFrame#axq_viewbar {{
    background: rgba(32, 35, 40, 225); border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 22); }}
QLabel {{ background: transparent; border: none; }}
QToolButton#axq_power {{
    background: rgba(70, 75, 82, 230); color: #d6d9dd;
    border-radius: 5px; padding: 5px 12px; font-weight: bold; }}
QToolButton#axq_power:hover {{ background: rgba(90, 96, 104, 240); }}
QToolButton#axq_power:checked {{ background: {BLUE}; color: white; }}
QPushButton#axq_plan {{
    background: rgba(32, 35, 40, 235); color: #f3f4f6; text-align: left;
    border: 2px solid {PLAN}; border-radius: 7px; padding: 6px 14px;
    font-weight: bold; }}
QPushButton#axq_plan:hover {{ background: rgba(60, 64, 70, 240); }}
QPushButton#axq_plan:checked {{ background: {PLAN}; color: white;
    border: 2px solid #ffc27a; }}
QLabel#axq_sep {{ color: #6b7280; padding: 0 1px; }}
QLabel#axq_caption {{ color: #9aa5b1; padding: 0 4px 0 10px; }}
QLabel#axq_title {{ color: #e8eaed; font-weight: bold; padding: 2px 8px 4px 8px; }}
QComboBox#axq_floor {{ min-width: 110px; }}
QToolButton#axq_swap, QToolButton#axq_gear {{
    color: #9aa5b1; background: transparent; border-radius: 4px;
    padding: 0px 7px; margin-left: 4px; font-size: 17px; }}
QToolButton#axq_swap {{ margin-left: 8px; }}
QToolButton#axq_swap:checked {{
    background: rgba(240,125,20,150); }}
QToolButton#axq_swap:hover, QToolButton#axq_gear:hover {{
    color: white; background: rgba(255,255,255,30); }}
QPushButton[axq="phase"] {{
    color: #e8eaed; background: transparent;
    border-radius: 5px; padding: 5px 11px; }}
QPushButton[axq="phase"]:hover {{ background: rgba(255,255,255,30); }}
QPushButton[axq="phase"][state="current"] {{
    background: {BLUE}; color: white; font-weight: bold; }}
QPushButton[axq="phase"][state="done"] {{ color: #7ce0a3; }}
QPushButton[axq="phase"][state="locked"] {{ color: #6b7280; }}
QPushButton[axq="item"] {{
    color: #cfd6de; background: transparent; text-align: left;
    border-radius: 4px; padding: 4px 12px; }}
QPushButton[axq="item"]:hover {{ background: rgba(255,255,255,30); }}
QPushButton[axq="item"]:checked {{ background: rgba(47,111,179,170); color: white; }}
QPushButton[axq="chip"] {{
    color: #cfd6de; background: rgba(255,255,255,12); border-radius: 4px;
    padding: 3px 9px; }}
QPushButton[axq="chip"]:hover {{ background: rgba(255,255,255,34); }}
QPushButton[axq="chip"]:checked {{ background: {BLUE}; color: white; }}
QPushButton[axq="chip"]::menu-indicator {{ image: none; width: 0px; }}
QMenu#axq_menu {{ background: rgb(36, 39, 44); color: #e8eaed;
    border: 1px solid rgba(255, 255, 255, 40); border-radius: 6px;
    padding: 4px; }}
QMenu#axq_menu::item {{ padding: 5px 22px 5px 22px; border-radius: 4px; }}
QMenu#axq_menu::item:selected {{ background: rgba(47, 111, 179, 170);
    color: white; }}
QMenu#axq_menu::indicator {{ width: 10px; height: 10px; left: 6px; }}
QFrame#axq_vsep {{ background: rgba(255,255,255,30); border: none;
    min-width: 1px; max-width: 1px; margin: 3px 6px; }}
QFrame#axq_levels {{
    background: rgba(32, 35, 40, 225); border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 22); }}
QScrollArea#axq_levels_scroll, QWidget#axq_levels_body {{
    background: transparent; border: none; }}
QFrame[axq="level"] {{ background: transparent; border-radius: 4px;
    border-left: 3px solid transparent; }}
QFrame[axq="level"]:hover {{ background: rgba(255,255,255,22); }}
QFrame[axq="level"][current="true"] {{
    background: rgba(47,111,179,110); border-left: 3px solid #5aa0ff; }}
QFrame[axq="level"][kind="terrain"] {{
    border-top: 1px solid rgba(255,255,255,30); border-radius: 0; }}
QLabel[axq="lvname"] {{ color: #e8eaed; padding: 0 2px; }}
QFrame[axq="level"][current="true"] QLabel[axq="lvname"] {{
    color: white; font-weight: bold; }}
QFrame[axq="level"][kind="terrain"] QLabel[axq="lvname"] {{ color: #b9c7a3; }}
QLabel[axq="lvelev"] {{ color: #9aa5b1; padding: 0 4px; }}
QLabel[axq="lvhidden"] {{ color: #6b7280; }}
QToolButton[axq="eye"] {{ background: transparent; border: none;
    border-radius: 4px; padding: 2px; }}
QToolButton[axq="eye"]:hover {{ background: rgba(255,255,255,34); }}
QToolButton#axq_lvadd {{ color: #9aa5b1; background: transparent;
    border-radius: 4px; padding: 0 6px; font-size: 15px; }}
QToolButton#axq_lvadd:hover {{ color: white; background: rgba(255,255,255,30); }}
QLineEdit[axq="lvedit"] {{ background: #2c3238; color: white;
    border: 1px solid {BLUE}; border-radius: 3px; padding: 1px 4px; }}
"""

#: A piece sitting in a host toolbar: a soft band with a thin blue rule,
#: the pill inside a little lighter — serious, but not flat.
BAR_CSS = f"""
QToolBar[axq="bar"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2c3037, stop:1 #24272c);
    border: none; padding: 5px 8px; spacing: 0; }}
QToolBar[axq="bar"][area="top"] {{
    border-bottom: 1px solid rgba(47, 111, 179, 150); }}
QToolBar[axq="bar"][area="bottom"] {{
    border-top: 1px solid rgba(47, 111, 179, 150); }}
QToolBar[axq="bar"][area="left"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #2c3037, stop:1 #24272c);
    border-right: 1px solid rgba(47, 111, 179, 150); }}
QToolBar[axq="bar"][area="right"] {{
    background: qlineargradient(x1:1, y1:0, x2:0, y2:0,
                                stop:0 #2c3037, stop:1 #24272c);
    border-left: 1px solid rgba(47, 111, 179, 150); }}
QToolBar[axq="bar"] QFrame#axq_row, QToolBar[axq="bar"] QFrame#axq_strip,
QToolBar[axq="bar"] QFrame#axq_viewbar,
QToolBar[axq="bar"] QFrame#axq_levels {{ background: rgba(255, 255, 255, 10); }}
QToolBar[axq="bar"] QPushButton[axq="phase"] {{ padding: 6px 13px; }}
QToolBar[axq="bar"] QToolButton#axq_power {{ padding: 6px 14px; }}
"""
