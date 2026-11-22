"""ui.py — All UI: theme, editors, file explorer, workflow, command palette,
welcome screen, examples gallery, and all supporting widgets."""
import os
import re
import json
import time
import tempfile
import subprocess
import platform
import webbrowser
from datetime import datetime
from typing import Optional, List, Dict
import glob as globmod
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QFileDialog,
    QTextEdit, QPlainTextEdit, QLineEdit, QTabWidget, QStatusBar,
    QMessageBox, QSplitter, QCheckBox, QGroupBox, QFormLayout,
    QToolBar, QMenu, QListWidget, QListWidgetItem, QTreeWidget,
    QTreeWidgetItem, QStackedWidget, QHeaderView, QAbstractItemView,
    QInputDialog, QFrame, QApplication, QGraphicsDropShadowEffect,
    QDialog, QScrollArea, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QObject, QSettings, QTimer, QUrl, QSize, QRect, Signal, Slot, QEvent,
    QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QColor, QFont, QPainter, QTextCursor, QTextCharFormat, QTextFormat,
    QSyntaxHighlighter, QPixmap, QKeyEvent, QKeySequence, QShortcut
)
from engine import (
    PromptGenerator, PromptConfig, ScriptValidator, ValidationResult,
    ScriptExecutor, FileSystemScanWorker, TTSPreviewWorker,
    ExportPresentationWorker, WorkflowHistory, WorkflowRun,
    ErrorRecovery, CancellationToken, WorkerThread,
    TemplateLibrary, PromptTemplate, RecentProjects, AutoSaveManager,
    SnippetManager, Snippet, EmmetExpander, InlineAIEditor,
    SpellChecker, SEOAnalyzer, AnsiParser, ProjectSearchIndex,
    log_info, log_success, log_warning, log_error
)
from examples import ExampleLibrary, ExampleProject

# =============================================================================
#   THEME SYSTEM
# =============================================================================
class Themes:
    DARK = {
        "bg_base": "#1e1e1e", "bg_elevated": "#252526", "bg_surface": "#2d2d30",
        "bg_hover": "#3e3e42", "bg_active": "#094771", "bg_highlight": "#264f78",
        "text_primary": "#d4d4d4", "text_secondary": "#858585",
        "text_disabled": "#5a5a5a", "text_inverse": "#1e1e1e",
        "accent_primary": "#007acc", "accent_success": "#4ec9b0",
        "accent_warning": "#dcdcaa", "accent_error": "#f48771",
        "accent_info": "#75beff",
        "syn_keyword": "#569cd6", "syn_string": "#ce9178",
        "syn_number": "#b5cea8", "syn_comment": "#6a9955",
        "syn_function": "#dcdcaa", "syn_type": "#4ec9b0",
        "syn_variable": "#9cdcfe", "syn_tag": "#569cd6",
        "syn_attribute": "#9cdcfe",
        "border": "#3e3e42", "scrollbar": "#424242", "divider": "#2d2d30",
    }
    LIGHT = {
        "bg_base": "#ffffff", "bg_elevated": "#f3f3f3", "bg_surface": "#ececec",
        "bg_hover": "#e0e0e0", "bg_active": "#c4dfe8", "bg_highlight": "#f5f5f5",
        "text_primary": "#1e1e1e", "text_secondary": "#616161",
        "text_disabled": "#a0a0a0", "text_inverse": "#ffffff",
        "accent_primary": "#0066cc", "accent_success": "#16825d",
        "accent_warning": "#795e26", "accent_error": "#cd3131",
        "accent_info": "#007acc",
        "syn_keyword": "#0000ff", "syn_string": "#a31515",
        "syn_number": "#098658", "syn_comment": "#008000",
        "syn_function": "#795e26", "syn_type": "#267f99",
        "syn_variable": "#001080", "syn_tag": "#800000",
        "syn_attribute": "#ff0000",
        "border": "#c8c8c8", "scrollbar": "#c1c1c1", "divider": "#e0e0e0",
    }

class ThemeManager(QObject):
    theme_changed = Signal(str)
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = "dark"
        self.settings = QSettings("VideoGen", "PresentationStudio")
        self._current = self.settings.value("theme", "dark")

    @classmethod
    def instance(cls):
        if cls._instance is None: cls._instance = cls()
        return cls._instance

    @property
    def current(self) -> str: return self._current

    @property
    def colors(self) -> Dict:
        return Themes.DARK if self._current == "dark" else Themes.LIGHT

    def toggle(self):
        self._current = "light" if self._current == "dark" else "dark"
        self.settings.setValue("theme", self._current)
        self.theme_changed.emit(self._current)

def C(name: str) -> str:
    return ThemeManager.instance().colors.get(name, "#000000")

class F:
    ui = "Inter, -apple-system, Segoe UI, Roboto, sans-serif"
    mono = "JetBrains Mono, Fira Code, Consolas, Monaco, monospace"
    title = 18; heading = 14; body = 12; small = 11; tiny = 10; editor = 13

def build_stylesheet() -> str:
    c = ThemeManager.instance().colors
    return f"""
QMainWindow, QWidget {{ background: {c['bg_base']}; color: {c['text_primary']};
  font-family: '{F.ui}'; font-size: {F.body}pt; }}
QTabWidget::pane {{ border: 1px solid {c['border']}; background: {c['bg_base']}; border-top: none; }}
QTabBar {{ background: {c['bg_elevated']}; border-bottom: 1px solid {c['border']}; }}
QTabBar::tab {{ background: transparent; color: {c['text_secondary']}; padding: 10px 18px;
  border: none; border-bottom: 2px solid transparent; margin-right: 2px;
  font-weight: 500; font-size: {F.body}pt; }}
QTabBar::tab:hover {{ color: {c['text_primary']}; background: {c['bg_hover']}; }}
QTabBar::tab:selected {{ color: {c['text_primary']}; border-bottom: 2px solid {c['accent_primary']}; }}
QGroupBox {{ background: {c['bg_elevated']}; border: 1px solid {c['border']};
  border-radius: 6px; margin-top: 14px; padding: 16px 12px 12px 12px;
  font-weight: 600; font-size: {F.heading}pt; color: {c['text_primary']}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 8px;
  color: {c['accent_primary']}; background: {c['bg_elevated']}; }}
QLineEdit, QSpinBox, QComboBox {{
  background: {c['bg_surface']}; border: 1px solid {c['border']};
  border-radius: 4px; color: {c['text_primary']}; padding: 6px 10px;
  font-size: {F.body}pt; selection-background-color: {c['bg_active']}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {c['accent_primary']}; }}
QPushButton {{ background: {c['bg_surface']}; color: {c['text_primary']};
  border: 1px solid {c['border']}; border-radius: 4px; padding: 7px 14px;
  font-weight: 500; font-size: {F.body}pt; min-height: 18px; }}
QPushButton:hover {{ background: {c['bg_hover']}; border-color: {c['accent_primary']}; }}
QPushButton:pressed {{ background: {c['bg_active']}; }}
QPushButton:disabled {{ background: {c['bg_elevated']}; color: {c['text_disabled']}; }}
QPushButton[accent="true"] {{ background: {c['accent_primary']}; color: white;
  border: none; font-weight: 600; }}
QPushButton[danger="true"] {{ background: transparent; color: {c['accent_error']};
  border: 1px solid {c['accent_error']}; }}
QPushButton[danger="true"]:hover {{ background: {c['accent_error']}; color: white; }}
QPushButton[success="true"] {{ background: {c['accent_success']}; color: {c['text_inverse']};
  border: none; font-weight: 600; }}
QTextEdit, QPlainTextEdit {{ background: {c['bg_base']}; color: {c['text_primary']};
  border: 1px solid {c['border']}; border-radius: 4px; padding: 8px;
  font-family: '{F.mono}'; font-size: {F.editor}pt;
  selection-background-color: {c['bg_active']}; }}
QProgressBar {{ background: {c['bg_surface']}; border: 1px solid {c['border']};
  border-radius: 4px; text-align: center; color: {c['text_primary']};
  font-size: {F.small}pt; min-height: 20px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
  stop:0 {c['accent_primary']}, stop:1 {c['accent_info']}); border-radius: 3px; }}
QListWidget, QTreeWidget {{ background: {c['bg_elevated']};
  border: 1px solid {c['border']}; color: {c['text_primary']};
  font-size: {F.body}pt; outline: none; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {c['bg_hover']}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {c['bg_active']}; }}
QScrollBar:vertical {{ background: {c['bg_base']}; width: 12px; margin: 0; border: none; }}
QScrollBar::handle:vertical {{ background: {c['scrollbar']}; min-height: 30px;
  border-radius: 6px; margin: 2px; }}
QSplitter::handle {{ background: {c['divider']}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:hover {{ background: {c['accent_primary']}; }}
QCheckBox {{ color: {c['text_primary']}; spacing: 8px; font-size: {F.body}pt; }}
QStatusBar {{ background: {c['accent_primary']}; color: white; border: none;
  font-size: {F.small}pt; padding: 2px 10px; }}
QLabel {{ color: {c['text_primary']}; background: transparent; }}
"""

# =============================================================================
#   SYNTAX HIGHLIGHTERS
# =============================================================================
class BaseHighlighter(QSyntaxHighlighter):
    def __init__(self, doc, rules):
        super().__init__(doc)
        self.rules = []
        for pattern, color_key, bold in rules:
            fmt = QTextCharFormat()
            color = C(color_key) if color_key.startswith("syn_") else color_key
            fmt.setForeground(QColor(color))
            if bold: fmt.setFontWeight(QFont.Bold)
            try: self.rules.append((re.compile(pattern), fmt))
            except: pass

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

class HtmlHighlighter(BaseHighlighter):
    def __init__(self, doc):
        rules = [
            (r"<!--[\s\S]*?-->", "syn_comment", False),
            (r"<!DOCTYPE[^>]*>", "syn_keyword", True),
            (r"</?[a-zA-Z][a-zA-Z0-9]*", "syn_tag", False),
            (r"/?>", "syn_tag", False),
            (r"\b[a-zA-Z-]+(?==)", "syn_attribute", False),
            (r'"[^"]*"', "syn_string", False),
            (r"'[^']*'", "syn_string", False),
            (r"\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|pt)?\b", "syn_number", False),
        ]
        super().__init__(doc, rules)

class BashHighlighter(BaseHighlighter):
    def __init__(self, doc):
        rules = [
            (r"#[^\n]*", "syn_comment", False),
            (r'"(?:\\.|[^"\\])*"', "syn_string", False),
            (r"'[^']*'", "syn_string", False),
            (r"\b(if|then|else|elif|fi|for|in|do|done|while|until|case|esac|function|return|exit|select)\b",
             "syn_keyword", True),
            (r"\b(echo|printf|cd|export|set|unset|source|read|shift|local|readonly)\b",
             "syn_function", False),
            (r"\b(cat|mkdir|rm|cp|mv|ls|pwd|chmod|grep|sed|awk|find|curl|wget|tar)\b",
             "syn_type", False),
            (r"\$\{?[a-zA-Z_][a-zA-Z0-9_]*\}?", "syn_variable", False),
            (r"\b\d+\b", "syn_number", False),
            (r"<<-?\s*['\"]?\w+['\"]?", "syn_function", True),
        ]
        super().__init__(doc, rules)

class ScriptHighlighter(BaseHighlighter):
    def __init__(self, doc):
        rules = [
            (r"\[PAUSE[^\]]*\]", "#dcdcaa", True),
            (r"\[EMPHASIS[^\]]*\]", "#007acc", True),
            (r"\[TONE:[^\]]*\]", "#4ec9b0", False),
            (r"\[MUSIC:[^\]]*\]", "#6a9955", False),
            (r"\[B-ROLL:[^\]]*\]", "#6a9955", False),
            (r"\[[A-Z][^\]]*\]", "#858585", False),
            (r"^SLIDE \d+[^\n]*$", "#007acc", True),
            (r'"[^"]*"', "syn_string", False),
            (r"\b\d+(?:\.\d+)?\b", "syn_number", False),
        ]
        super().__init__(doc, rules)

# =============================================================================
#   CODE EDITOR
# =============================================================================
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)

class CodeEditor(QPlainTextEdit):
    content_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_font_size = F.editor
        self._zoom_level = 0
        font = QFont(F.mono, self._base_font_size)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance("    "))
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_ln_width)
        self.updateRequest.connect(self._update_ln_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_ln_width(0)
        self._highlight_current_line()
        
        self._change_timer = QTimer()
        self._change_timer.setSingleShot(True)
        self._change_timer.setInterval(300)
        self._change_timer.timeout.connect(self.content_changed.emit)
        self.textChanged.connect(lambda: self._change_timer.start())
        
        self.line_numbers_visible = True
        self.highlight_current_line_enabled = True
        self.tab_width = 4
        self.word_wrap_enabled = False

    def zoom_in(self):
        self._zoom_level = min(self._zoom_level + 1, 10)
        self._apply_zoom()

    def zoom_out(self):
        self._zoom_level = max(self._zoom_level - 1, -5)
        self._apply_zoom()

    def zoom_reset(self):
        self._zoom_level = 0
        self._apply_zoom()

    def _apply_zoom(self):
        font = self.font()
        font.setPointSize(max(8, self._base_font_size + self._zoom_level))
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" " * self.tab_width))
        self._update_ln_width(0)

    def toggle_word_wrap(self):
        self.word_wrap_enabled = not self.word_wrap_enabled
        if self.word_wrap_enabled:
            self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        else:
            self.setLineWrapMode(QPlainTextEdit.NoWrap)

    def line_number_area_width(self):
        if not self.line_numbers_visible: return 0
        digits = max(1, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * (digits + 1)

    def _update_ln_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_ln_area(self, rect, dy):
        if dy: self.line_number_area.scroll(0, dy)
        else: self.line_number_area.update(0, rect.y(),
                                           self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_ln_width(0)

    def paint_line_numbers(self, event):
        if not self.line_numbers_visible: return
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(C('bg_elevated')))
        block = self.firstVisibleBlock()
        bn = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if bn == self.textCursor().blockNumber():
                    painter.setPen(QColor(C('accent_primary')))
                    painter.setFont(QFont(self.font().family(),
                                          self.font().pointSize(), QFont.Bold))
                else:
                    painter.setPen(QColor(C('text_secondary')))
                    painter.setFont(QFont(self.font().family(),
                                          self.font().pointSize() - 1))
                painter.drawText(0, top, self.line_number_area.width() - 8,
                                 self.fontMetrics().height(), Qt.AlignRight, str(bn + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            bn += 1
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                                self.line_number_area_width(), cr.height()))

    def _highlight_current_line(self):
        extra = []
        if self.highlight_current_line_enabled and not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(C('bg_highlight')))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)

    def keyPressEvent(self, event):
        key = event.key()
        mod = event.modifiers()
        if key in (Qt.Key_Plus, Qt.Key_Equal) and mod == Qt.ControlModifier:
            self.zoom_in(); return
        if key == Qt.Key_Minus and mod == Qt.ControlModifier:
            self.zoom_out(); return
        if key == Qt.Key_0 and mod == Qt.ControlModifier:
            self.zoom_reset(); return
        if key == Qt.Key_Tab and not mod:
            cursor = self.textCursor()
            if cursor.hasSelection(): self._indent_selection(True)
            else: cursor.insertText(" " * self.tab_width)
            return
        if key == Qt.Key_Backtab:
            cursor = self.textCursor()
            if cursor.hasSelection(): self._indent_selection(False)
            else: self._unindent_line()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._auto_indent(); return
        if key == Qt.Key_D and mod == Qt.ControlModifier:
            self._duplicate_line(); return
        if key == Qt.Key_Slash and mod == Qt.ControlModifier:
            self._toggle_comment(); return
        if key == Qt.Key_K and mod == (Qt.ControlModifier | Qt.ShiftModifier):
            self._delete_line(); return
        super().keyPressEvent(event)

    def _auto_indent(self):
        cursor = self.textCursor()
        text = cursor.block().text()
        indent = ""
        for ch in text:
            if ch in " \t": indent += ch
            else: break
        if text.rstrip().endswith(("{", ":", "[", "(")):
            indent += " " * self.tab_width
        cursor.insertText("\n" + indent)
        self.setTextCursor(cursor)

    def _indent_selection(self, indent=True):
        cursor = self.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.setPosition(start)
        cursor.beginEditBlock()
        while cursor.position() <= end:
            cursor.movePosition(QTextCursor.StartOfBlock)
            if indent:
                cursor.insertText(" " * self.tab_width)
                end += self.tab_width
            else:
                for _ in range(self.tab_width):
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
                    if cursor.selectedText() == " ":
                        cursor.removeSelectedText()
                        end -= 1
                    else:
                        cursor.movePosition(QTextCursor.Left)
                        break
            if not cursor.movePosition(QTextCursor.Down): break
        cursor.endEditBlock()

    def _unindent_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.beginEditBlock()
        for _ in range(self.tab_width):
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
            if cursor.selectedText() == " ":
                cursor.removeSelectedText()
            else:
                cursor.movePosition(QTextCursor.Left)
                break
        cursor.endEditBlock()

    def _duplicate_line(self):
        cursor = self.textCursor()
        text = cursor.block().text()
        cursor.movePosition(QTextCursor.EndOfBlock)
        cursor.insertText("\n" + text)

    def _delete_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()

    def _toggle_comment(self):
        cursor = self.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.setPosition(start)
        cursor.beginEditBlock()
        lines = []
        while cursor.position() <= end:
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            lines.append((cursor.position(), cursor.selectedText()))
            if not cursor.movePosition(QTextCursor.Down): break
        
        all_commented = all(l[1].lstrip().startswith("#") for l in lines)
        for pos, line in lines:
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            if all_commented:
                new = line.lstrip()
                if new.startswith("# "): new = new[2:]
                elif new.startswith("#"): new = new[1:]
                indent = line[:len(line) - len(line.lstrip())]
                cursor.insertText(indent + new)
            else:
                indent = line[:len(line) - len(line.lstrip())]
                cursor.insertText(indent + "# " + line.lstrip())
        cursor.endEditBlock()

    def find_text(self, text, case_sensitive=False, wrap=True):
        flags = QTextCursor.FindFlag(0)
        if case_sensitive: flags |= QTextCursor.FindCaseSensitively
        cursor = self.textCursor()
        result = self.document().find(text, cursor, flags)
        if result.isNull() and wrap:
            cursor = QTextCursor(self.document())
            result = self.document().find(text, cursor, flags)
        if not result.isNull():
            self.setTextCursor(result)
            return True
        return False

    def replace_all(self, find_text, replace_text, case_sensitive=False):
        count = 0
        cursor = QTextCursor(self.document())
        self.setTextCursor(cursor)
        while self.find_text(find_text, case_sensitive=case_sensitive, wrap=False):
            self.textCursor().insertText(replace_text)
            count += 1
        return count

# =============================================================================
#   TOAST NOTIFICATIONS
# =============================================================================
class Toast(QWidget):
    def __init__(self, message, level="info", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._build_ui(message, level)
        self._setup_animation()

    def _build_ui(self, message, level):
        colors = {
            "info": (C('accent_info'), "ℹ️"),
            "success": (C('accent_success'), "✅"),
            "warning": (C('accent_warning'), "⚠️"),
            "error": (C('accent_error'), "❌"),
        }
        color, icon = colors.get(level, colors["info"])
        container = QWidget(self)
        container.setStyleSheet(f"""
            background: {C('bg_surface')}; border: 1px solid {color};
            border-left: 4px solid {color}; border-radius: 6px; padding: 10px 16px;
        """)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        
        icon_label = QLabel(icon)
        icon_label.setFont(QFont(F.ui, 14))
        layout.addWidget(icon_label)
        
        text_label = QLabel(message)
        text_label.setWordWrap(True)
        text_label.setMaximumWidth(400)
        text_label.setStyleSheet(f"color: {C('text_primary')}; background: transparent; font-size: {F.body}pt;")
        layout.addWidget(text_label, 1)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)
        
        self.setFixedWidth(420)
        self.setMinimumHeight(50)

    def _setup_animation(self):
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        
        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.deleteLater)
        
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)

    def show_toast(self):
        self._fade_in.start()
        self._timer.start(3500)

    def dismiss(self):
        self._timer.stop()
        self._fade_out.start()

class ToastManager:
    _toasts = []
    
    @classmethod
    def show(cls, message, level="info", parent=None):
        if parent is None: parent = QApplication.activeWindow()
        toast = Toast(message, level, parent)
        if parent:
            geo = parent.geometry()
            x = geo.right() - 440
            y = geo.bottom() - 80 - (len(cls._toasts) * 70)
            toast.move(x, max(20, y))
        cls._toasts.append(toast)
        toast.show_toast()
        QTimer.singleShot(4000, lambda: cls._toasts.remove(toast) if toast in cls._toasts else None)

def toast_info(msg, parent=None): ToastManager.show(msg, "info", parent)
def toast_success(msg, parent=None): ToastManager.show(msg, "success", parent)
def toast_warning(msg, parent=None): ToastManager.show(msg, "warning", parent)
def toast_error(msg, parent=None): ToastManager.show(msg, "error", parent)

# =============================================================================
#   HTML EDITOR
# =============================================================================
class HtmlEditor(QWidget):
    content_changed = Signal(str)
    saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = ""
        self._temp_preview = None
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(400)
        self._refresh_timer.timeout.connect(self._do_refresh)
        self._build_ui()
        AutoSaveManager.instance().register("html_editor", "")
        self.editor.content_changed.connect(self._on_content_changed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{ background: {C('bg_elevated')}; border: none;
            border-bottom: 1px solid {C('border')}; padding: 4px; spacing: 4px; }}
        """)
        toolbar.addAction("📄 New").triggered.connect(self.new_document)
        toolbar.addAction("📂 Open").triggered.connect(self.open_file)
        toolbar.addAction("💾 Save").triggered.connect(self.save_file)
        toolbar.addSeparator()
        toolbar.addAction("✨ Format").triggered.connect(self.format_html)
        toolbar.addAction("📦 Minify").triggered.connect(self.minify_html)
        toolbar.addSeparator()
        
        wrap_btn = QPushButton("↩ Wrap")
        wrap_btn.setCheckable(True)
        wrap_btn.clicked.connect(lambda: self.editor.toggle_word_wrap())
        toolbar.addWidget(wrap_btn)
        
        zoom_in_btn = QPushButton("A+")
        zoom_in_btn.clicked.connect(self.editor.zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("A-")
        zoom_out_btn.clicked.connect(self.editor.zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        zoom_reset_btn = QPushButton("A₀")
        zoom_reset_btn.clicked.connect(self.editor.zoom_reset)
        toolbar.addWidget(zoom_reset_btn)
        toolbar.addSeparator()
        
        toolbar.addAction("🌐 Open in Browser").triggered.connect(self.open_in_browser)
        layout.addWidget(toolbar)
        
        splitter = QSplitter(Qt.Horizontal)
        self.editor = CodeEditor()
        self.highlighter = HtmlHighlighter(self.editor.document())
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance("  "))
        self.editor.tab_width = 2
        self.editor.setPlaceholderText("<!-- Write HTML here -->")
        splitter.addWidget(self.editor)
        
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        device_bar = QHBoxLayout()
        device_bar.setContentsMargins(8, 4, 8, 4)
        device_bar.addWidget(QLabel("Preview:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems([
            "Desktop (1920×1080)", "Laptop (1366×768)",
            "Tablet (768×1024)", "Mobile (375×667)", "Fit to window",
        ])
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        device_bar.addWidget(self.device_combo)
        device_bar.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._do_refresh)
        device_bar.addWidget(refresh_btn)
        
        self.auto_refresh_check = QCheckBox("Auto-refresh")
        self.auto_refresh_check.setChecked(True)
        device_bar.addWidget(self.auto_refresh_check)
        preview_layout.addLayout(device_bar)
        
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEngineSettings
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet(f"background: {C('bg_base')}; border: 1px solid {C('border')};")
            settings = self.web_view.page().settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            preview_layout.addWidget(self.web_view, 1)
            self._has_webengine = True
        except ImportError:
            self.web_view = QLabel("QtWebEngine not available")
            self.web_view.setAlignment(Qt.AlignCenter)
            preview_layout.addWidget(self.web_view, 1)
            self._has_webengine = False
            
        splitter.addWidget(preview_container)
        splitter.setSizes([900, 900])
        layout.addWidget(splitter, 1)

    def _on_content_changed(self):
        content = self.editor.toPlainText()
        self.content_changed.emit(content)
        AutoSaveManager.instance().register("html_editor", content)
        self._schedule_refresh()

    def set_content(self, html: str):
        self.editor.setPlainText(html)
        self._do_refresh()

    def load_file(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            self.set_content(f.read())
        self.file_path = path

    def save_file(self, path: str = None):
        path = path or self.file_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save HTML", "", "HTML (*.html)")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        self.file_path = path
        AutoSaveManager.instance().mark_clean("html_editor")
        self.saved.emit(path)
        toast_success(f"Saved {os.path.basename(path)}")

    def new_document(self):
        self.editor.clear()
        self.file_path = ""

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open HTML", "", "HTML (*.html *.htm)")
        if path: self.load_file(path)

    def open_in_browser(self):
        fd, path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        webbrowser.open(f"file://{path}")

    def _schedule_refresh(self):
        if self.auto_refresh_check.isChecked():
            self._refresh_timer.start()

    def _do_refresh(self):
        if not self._has_webengine: return
        content = self.editor.toPlainText()
        if self._temp_preview is None:
            fd, self._temp_preview = tempfile.mkstemp(suffix=".html")
            os.close(fd)
        with open(self._temp_preview, "w", encoding="utf-8") as f:
            f.write(content)
        self.web_view.load(QUrl.fromLocalFile(self._temp_preview))

    def _on_device_changed(self, index):
        if not self._has_webengine: return
        sizes = [(1920, 1080), (1366, 768), (768, 1024), (375, 667), None]
        size = sizes[index]
        if size:
            view_size = self.web_view.size()
            scale = min(view_size.width() / size[0], view_size.height() / size[1])
            self.web_view.setZoomFactor(scale)
        else:
            self.web_view.setZoomFactor(1.0)

    def format_html(self):
        html_text = self.editor.toPlainText()
        tokens = re.split(r"(<[^>]+>)", html_text)
        formatted = []
        indent = 0
        for t in tokens:
            if not t.strip(): continue
            if t.startswith("</"):
                indent = max(0, indent - 1)
                formatted.append("  " * indent + t)
            elif t.startswith("<") and not t.endswith("/>") and not t.startswith("<!"):
                formatted.append("  " * indent + t)
                indent += 1
            else:
                formatted.append("  " * indent + t.strip())
        self.editor.setPlainText("\n".join(formatted))

    def minify_html(self):
        html_text = self.editor.toPlainText()
        html_text = re.sub(r"<!--[\s\S]*?-->", "", html_text)
        html_text = re.sub(r">\s+<", "><", html_text)
        html_text = re.sub(r"\s+", " ", html_text)
        self.editor.setPlainText(html_text.strip())

# =============================================================================
#   SCRIPT EDITOR
# =============================================================================
class ScriptEditor(QWidget):
    content_changed = Signal(str)
    saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = ""
        self._current_tts_worker = None
        self._media_player = None
        self._build_ui()
        AutoSaveManager.instance().register("script_editor", "")
        self.editor.content_changed.connect(self._on_content_changed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{ background: {C('bg_elevated')}; border: none;
            border-bottom: 1px solid {C('border')}; padding: 4px; spacing: 4px; }}
        """)
        toolbar.addAction("📄 New").triggered.connect(self.new_document)
        toolbar.addAction("📂 Open").triggered.connect(self.open_file)
        toolbar.addAction("💾 Save").triggered.connect(self.save_file)
        toolbar.addSeparator()
        
        insert_menu = QMenu()
        for tag in ["[PAUSE]", "[PAUSE — 1s]", "[EMPHASIS] ", "[TONE: serious] ",
                    "[MUSIC: ]", "[B-ROLL: ]", "[SFX: ]"]:
            insert_menu.addAction(tag, lambda t=tag: self._insert_tag(t))
        insert_btn = QPushButton("⊕ Insert ▾")
        insert_btn.setMenu(insert_menu)
        toolbar.addWidget(insert_btn)
        toolbar.addSeparator()
        
        self.tts_voice = QComboBox()
        self.tts_voice.addItems(["en-US-GuyNeural", "en-US-AndrewNeural",
                                 "en-GB-RyanNeural", "en-US-JennyNeural"])
        toolbar.addWidget(self.tts_voice)
        
        self.tts_rate = QSpinBox()
        self.tts_rate.setRange(-50, 100)
        self.tts_rate.setValue(0)
        self.tts_rate.setSuffix("%")
        self.tts_rate.setFixedWidth(70)
        toolbar.addWidget(self.tts_rate)
        
        self.tts_btn = QPushButton("🔊 Preview TTS")
        self.tts_btn.clicked.connect(self._preview_tts)
        toolbar.addWidget(self.tts_btn)
        
        self.tts_stop_btn = QPushButton("⛔ Stop")
        self.tts_stop_btn.setProperty("danger", True)
        self.tts_stop_btn.clicked.connect(self._stop_tts)
        self.tts_stop_btn.setEnabled(False)
        toolbar.addWidget(self.tts_stop_btn)
        toolbar.addSeparator()
        
        toolbar.addAction("🧹 Clean for TTS").triggered.connect(self._copy_clean_script)
        layout.addWidget(toolbar)
        
        self.editor = CodeEditor()
        self.highlighter = ScriptHighlighter(self.editor.document())
        self.editor.setPlaceholderText("Write narration script here...")
        layout.addWidget(self.editor, 1)
        
        status_bar = QWidget()
        status_bar.setStyleSheet(f"background: {C('bg_elevated')}; "
                                 f"border-top: 1px solid {C('border')}; padding: 3px 10px;")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(10, 0, 10, 0)
        sb_layout.setSpacing(15)
        
        self.words_label = QLabel("0 words")
        self.words_label.setStyleSheet(f"color: {C('text_primary')}; font-size: {F.small}pt; font-weight: 600;")
        sb_layout.addWidget(self.words_label)
        sb_layout.addStretch()
        
        self.narration_label = QLabel("🎙 0:00")
        self.narration_label.setStyleSheet(f"""
            background: rgba(78, 201, 176, 0.15); color: {C('accent_success')};
            padding: 2px 8px; border-radius: 10px; font-size: {F.tiny}pt; font-weight: 600;
        """)
        sb_layout.addWidget(self.narration_label)
        layout.addWidget(status_bar)

    def _on_content_changed(self):
        text = self.editor.toPlainText()
        self.content_changed.emit(text)
        AutoSaveManager.instance().register("script_editor", text)
        self._update_stats(text)

    def _update_stats(self, text):
        words = len(text.split()) if text.strip() else 0
        self.words_label.setText(f"{words:,} words")
        clean = self._clean_script(text)
        spoken = len(clean.split()) if clean.strip() else 0
        narr_min = spoken / 150 if spoken else 0
        self.narration_label.setText(f"🎙 {self._fmt_time(narr_min)}")

    @staticmethod
    def _fmt_time(minutes):
        if minutes < 1: return f"0:{int(minutes * 60):02d}"
        m = int(minutes)
        s = int((minutes - m) * 60)
        return f"{m}:{s:02d}"

    @staticmethod
    def _clean_script(text):
        lines = text.split("\n")
        clean = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("=") or line.startswith("-"): continue
            if any(line.startswith(p) for p in ["SLIDE", "Runtime:", "[MUSIC:", "[B-ROLL:",
                                                "[SFX:", "[PAUSE", "[EMPHASIS", "[END]"]): continue
            if line.startswith("[") and line.endswith("]"): continue
            line = re.sub(r"\[[^\]]*\]", "", line).strip()
            if line: clean.append(line)
        return " ".join(clean)

    def set_content(self, text): self.editor.setPlainText(text)

    def load_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self.set_content(f.read())
        self.file_path = path

    def save_file(self, path=None):
        path = path or self.file_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Script", "", "Text (*.txt)")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        self.file_path = path
        AutoSaveManager.instance().mark_clean("script_editor")
        self.saved.emit(path)
        toast_success(f"Saved {os.path.basename(path)}")

    def new_document(self):
        self.editor.clear()
        self.file_path = ""

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Script", "", "Text (*.txt)")
        if path: self.load_file(path)

    def _insert_tag(self, tag):
        cursor = self.editor.textCursor()
        cursor.insertText("\n" + tag + "\n")

    def _preview_tts(self):
        text = self._clean_script(self.editor.toPlainText())
        if not text.strip():
            QMessageBox.warning(self, "Empty Script", "Nothing to preview.")
            return
        if self._current_tts_worker and self._current_tts_worker.isRunning():
            self._current_tts_worker.cancel()
            self._current_tts_worker.wait(1000)
        
        voice = self.tts_voice.currentText()
        rate = f"{self.tts_rate.value():+d}%"
        self.tts_btn.setEnabled(False)
        self.tts_stop_btn.setEnabled(True)
        
        self._current_tts_worker = TTSPreviewWorker(text, voice, rate)
        self._current_tts_worker.result_ready.connect(self._on_tts_ready)
        self._current_tts_worker.error_occurred.connect(self._on_tts_error)
        self._current_tts_worker.finished.connect(self._on_tts_finished)
        self._current_tts_worker.start()

    def _on_tts_ready(self, task_id, audio_path):
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            if self._media_player is None:
                self._media_player = QMediaPlayer(self)
                self._audio_output = QAudioOutput(self)
                self._audio_output.setVolume(0.7)
                self._media_player.setAudioOutput(self._audio_output)
                self._media_player.mediaStatusChanged.connect(self._on_media_status)
            self._media_player.setSource(QUrl.fromLocalFile(audio_path))
            self._media_player.play()
        except Exception as e:
            log_error(f"Playback error: {e}")
            self._reset_tts_ui()

    def _on_tts_error(self, task_id, error):
        toast_error(f"TTS failed: {error[:100]}")
        self._reset_tts_ui()

    def _on_tts_finished(self, task_id, success):
        if not success: self._reset_tts_ui()

    def _on_media_status(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        if status in (QMediaPlayer.EndOfMedia, QMediaPlayer.StalledMedia,
                      QMediaPlayer.InvalidMedia):
            self._reset_tts_ui()

    def _stop_tts(self):
        if self._current_tts_worker and self._current_tts_worker.isRunning():
            self._current_tts_worker.cancel()
        if self._media_player: self._media_player.stop()
        self._reset_tts_ui()

    def _reset_tts_ui(self):
        self.tts_btn.setEnabled(True)
        self.tts_stop_btn.setEnabled(False)

    def _copy_clean_script(self):
        clean = self._clean_script(self.editor.toPlainText())
        QApplication.clipboard().setText(clean)
        toast_success(f"Clean script copied ({len(clean.split())} words)")

# =============================================================================
#   FILE EXPLORER
# =============================================================================
class FileExplorer(QWidget):
    file_selected = Signal(str)
    file_open_requested = Signal(str)
    FILE_ICONS = {
        ".html": "🌐", ".txt": "📝", ".md": "📘", ".json": "📋",
        ".png": "🖼️", ".jpg": "🖼️", ".mp3": "🎵", ".mp4": "🎬",
        ".sh": "⚙️", ".py": "🐍",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace = ""
        self._current_scan_worker = None
        self._scan_result = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QWidget()
        header.setStyleSheet(f"background: {C('bg_elevated')}; padding: 8px;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 5, 10, 5)
        self.title_label = QLabel("📁 PROJECT")
        self.title_label.setFont(QFont(F.ui, F.small, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {C('text_secondary')}; letter-spacing: 1px;")
        hl.addWidget(self.title_label)
        hl.addStretch()
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.clicked.connect(self.refresh)
        hl.addWidget(self.refresh_btn)
        layout.addWidget(header)
        
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Filter files...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_tree)
        layout.addWidget(self.search)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree, 1)
        
        self.footer = QLabel("No workspace")
        self.footer.setStyleSheet(f"background: {C('bg_surface')}; color: {C('text_secondary')}; "
                                  f"padding: 6px 10px; font-size: {F.tiny}pt;")
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)

    def set_workspace(self, workspace):
        self.workspace = workspace
        if workspace and os.path.isdir(workspace):
            self.title_label.setText(f"📁 {os.path.basename(workspace).upper()}")
            self.footer.setText(workspace)
            self.refresh()
        else:
            self.tree.clear()
            self.title_label.setText("📁 PROJECT")
            self.footer.setText("No workspace")

    def refresh(self):
        self.tree.clear()
        if not self.workspace or not os.path.isdir(self.workspace): return
        if self._current_scan_worker and self._current_scan_worker.isRunning():
            self._current_scan_worker.cancel()
            self._current_scan_worker.wait(1000)
        
        loading = QTreeWidgetItem(self.tree, ["⏳ Scanning..."])
        loading.setForeground(0, Qt.gray)
        
        self._current_scan_worker = FileSystemScanWorker(self.workspace)
        self._current_scan_worker.result_ready.connect(self._on_scan_complete)
        self._current_scan_worker.error_occurred.connect(self._on_scan_error)
        self._current_scan_worker.finished.connect(self._on_scan_finished)
        self._current_scan_worker.start()
        self.refresh_btn.setEnabled(False)

    def _on_scan_complete(self, task_id, result):
        self._scan_result = result
        self._populate_tree(result)

    def _on_scan_error(self, task_id, error):
        self.footer.setText(f"Scan error: {error[:100]}")

    def _on_scan_finished(self, task_id, success):
        self.refresh_btn.setEnabled(True)
        if success and self._scan_result:
            count = self._scan_result.get("total_files", 0)
            size = self._scan_result.get("total_size", 0)
            self.footer.setText(f"{count} files • {self._fmt_size(size)}")

    def _populate_tree(self, result):
        self.tree.clear()
        root_name = os.path.basename(self.workspace)
        root_item = QTreeWidgetItem(self.tree, [f"📁 {root_name}"])
        root_item.setData(0, Qt.UserRole, self.workspace)
        root_item.setData(0, Qt.UserRole + 1, "folder")
        root_item.setExpanded(True)
        
        by_category = result.get("by_category", {})
        cat_labels = {
            "slides": ("🎨 Slides", by_category.get("slides", [])),
            "scripts": ("📝 Scripts", by_category.get("scripts", [])),
            "youtube": ("📺 YouTube", by_category.get("youtube", [])),
            "images": ("🖼️ Images", by_category.get("images", [])),
            "audio": ("🎵 Audio", by_category.get("audio", [])),
            "video": ("🎬 Video", by_category.get("video", [])),
            "other": ("📄 Other", by_category.get("other", [])),
        }
        for cat_key, (label, files) in cat_labels.items():
            if not files: continue
            cat_item = QTreeWidgetItem(root_item, [f"{label} ({len(files)})"])
            cat_item.setData(0, Qt.UserRole + 1, "category")
            cat_item.setExpanded(True)
            for fe in files:
                icon = self.FILE_ICONS.get(fe["ext"], "📄")
                size_str = self._fmt_size(fe["size"])
                item = QTreeWidgetItem(cat_item, [f"{icon} {fe['name']}  ({size_str})"])
                item.setData(0, Qt.UserRole, fe["path"])
                item.setData(0, Qt.UserRole + 1, "file")
                item.setData(0, Qt.UserRole + 2, fe["ext"])

    @staticmethod
    def _fmt_size(size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024: return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _on_item_clicked(self, item, col):
        path = item.data(0, Qt.UserRole)
        kind = item.data(0, Qt.UserRole + 1)
        if kind == "file" and path:
            self.file_selected.emit(path)

    def _on_item_double_clicked(self, item, col):
        path = item.data(0, Qt.UserRole)
        kind = item.data(0, Qt.UserRole + 1)
        if kind == "file" and path:
            self.file_open_requested.emit(path)
        elif kind in ("folder", "category"):
            item.setExpanded(not item.isExpanded())

    def _filter_tree(self, text):
        text = text.lower().strip()
        self._filter_item(self.tree.invisibleRootItem(), text)

    def _filter_item(self, item, text):
        if item is self.tree.invisibleRootItem():
            any_match = False
            for i in range(item.childCount()):
                if self._filter_item(item.child(i), text): any_match = True
            return any_match
        
        name = item.text(0).lower()
        matches = text in name if text else True
        child_match = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), text): child_match = True
        
        visible = matches or child_match
        item.setHidden(not visible)
        if child_match and text: item.setExpanded(True)
        return visible

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        path = item.data(0, Qt.UserRole)
        kind = item.data(0, Qt.UserRole + 1)
        menu = QMenu(self)
        if kind == "file":
            menu.addAction("📂 Open in Editor",
                           lambda: self.file_open_requested.emit(path))
            menu.addAction("🌐 Open with Default App",
                           lambda: self._open_external(path))
            menu.addSeparator()
            menu.addAction("📋 Copy Path",
                           lambda: QApplication.clipboard().setText(path))
        elif kind in ("folder", "category") and path:
            menu.addAction("📂 Open Folder",
                           lambda: self._open_external(path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _open_external(self, path):
        try:
            if platform.system() == "Darwin": subprocess.Popen(["open", path])
            elif platform.system() == "Windows": os.startfile(path)
            else: subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open: {e}")

# =============================================================================
#   COMMAND PALETTE
# =============================================================================
class CommandPalette(QDialog):
    command_executed = Signal(str)
    COMMANDS = [
        {"id": "file.open", "label": "Open File...", "category": "File", "shortcut": "Ctrl+O"},
        {"id": "file.new_prompt", "label": "New Project", "category": "File", "shortcut": "Ctrl+N"},
        {"id": "examples.browse", "label": "Browse Example Presentations", "category": "File", "shortcut": "Ctrl+Shift+E"},
        {"id": "edit.find", "label": "Find", "category": "Edit", "shortcut": "Ctrl+F"},
        {"id": "edit.toggle_wrap", "label": "Toggle Word Wrap", "category": "Edit", "shortcut": "Alt+Z"},
        {"id": "edit.zoom_in", "label": "Zoom In", "category": "Edit", "shortcut": "Ctrl+="},
        {"id": "edit.zoom_out", "label": "Zoom Out", "category": "Edit", "shortcut": "Ctrl+-"},
        {"id": "edit.zoom_reset", "label": "Reset Zoom", "category": "Edit", "shortcut": "Ctrl+0"},
        {"id": "view.theme_toggle", "label": "Toggle Theme (Dark/Light)", "category": "View", "shortcut": "Ctrl+Shift+T"},
        {"id": "view.fullscreen", "label": "Toggle Fullscreen", "category": "View", "shortcut": "F11"},
        {"id": "workflow.generate", "label": "Generate Prompt", "category": "Workflow"},
        {"id": "workflow.copy_prompt", "label": "Copy Prompt to Clipboard", "category": "Workflow"},
        {"id": "workflow.validate", "label": "Validate Script", "category": "Workflow"},
        {"id": "workflow.execute", "label": "Execute Script", "category": "Workflow"},
        {"id": "workflow.stop", "label": "Stop Execution", "category": "Workflow"},
        {"id": "help.shortcuts", "label": "Show Keyboard Shortcuts", "category": "Help", "shortcut": "Ctrl+K"},
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        self.setFixedSize(600, 400)
        self.setStyleSheet(f"""
            QDialog {{ background: {C('bg_elevated')};
            border: 1px solid {C('border')}; border-radius: 8px; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command...")
        self.search.setFont(QFont(F.ui, 14))
        self.search.setStyleSheet(f"""
            QLineEdit {{ background: {C('bg_surface')}; color: {C('text_primary')};
            border: none; border-bottom: 1px solid {C('border')};
            padding: 14px 18px; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
        """)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)
        
        self.list = QListWidget()
        self.list.setFont(QFont(F.ui, F.body))
        self.list.setStyleSheet(f"""
            QListWidget {{ background: {C('bg_elevated')}; border: none;
            color: {C('text_primary')}; outline: none; }}
            QListWidget::item {{ padding: 10px 18px; border-bottom: 1px solid {C('divider')}; }}
            QListWidget::item:hover {{ background: {C('bg_hover')}; }}
            QListWidget::item:selected {{ background: {C('bg_active')}; }}
        """)
        self.list.itemActivated.connect(self._execute_selected)
        self.list.itemDoubleClicked.connect(self._execute_selected)
        layout.addWidget(self.list, 1)
        
        footer = QWidget()
        footer.setStyleSheet(f"background: {C('bg_surface')}; padding: 6px 18px; "
                             f"border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("↑↓ navigate • ↵ execute • esc close")
        hint.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.tiny}pt;")
        fl.addWidget(hint)
        layout.addWidget(footer)
        
        self._populate(self.COMMANDS)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _populate(self, commands):
        self.list.clear()
        for cmd in commands:
            label = cmd["label"]
            category = cmd.get("category", "")
            shortcut = cmd.get("shortcut", "")
            display = f"{category} › {label}" if category else label
            if shortcut: display += f"    {shortcut}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, cmd["id"])
            self.list.addItem(item)

    def _filter(self, query):
        query = query.lower().strip()
        if not query:
            self._populate(self.COMMANDS)
            return
        matches = []
        for cmd in self.COMMANDS:
            label = cmd["label"].lower()
            category = cmd.get("category", "").lower()
            score = 0
            if query == label: score = 100
            elif label.startswith(query): score = 80
            elif query in label: score = 60
            elif query in category: score = 40
            if score > 0: matches.append((score, cmd))
        matches.sort(key=lambda x: -x[0])
        self._populate([m[1] for m in matches])
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _execute_selected(self):
        item = self.list.currentItem()
        if item:
            cmd_id = item.data(Qt.UserRole)
            self.command_executed.emit(cmd_id)
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key_Up:
            row = self.list.currentRow()
            if row > 0: self.list.setCurrentRow(row - 1)
        elif event.key() == Qt.Key_Down:
            row = self.list.currentRow()
            if row < self.list.count() - 1: self.list.setCurrentRow(row + 1)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._execute_selected()
        else:
            super().keyPressEvent(event)

    def show_at_cursor(self):
        parent = self.parent()
        if parent:
            geo = parent.geometry()
            x = geo.center().x() - self.width() // 2
            y = geo.top() + 80
            self.move(x, y)
        self.search.clear()
        self.search.setFocus()
        self._populate(self.COMMANDS)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        self.exec()

# =============================================================================
#   EXAMPLES DIALOG
# =============================================================================
class ExamplesDialog(QDialog):
    project_installed = Signal(str)
    load_in_workflow = Signal(str)

    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.library = library
        self.projects = library.list_all()
        self.selected: Optional[ExampleProject] = None
        self.setWindowTitle("🎨 Example Gallery")
        self.setMinimumSize(1100, 720)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        header = QWidget()
        header.setStyleSheet(f"background: {C('bg_elevated')}; "
                             f"border-bottom: 1px solid {C('border')}; padding: 18px 24px;")
        hl = QHBoxLayout(header)
        title = QLabel("🎨 Example Gallery")
        title.setFont(QFont(F.ui, F.title, QFont.Bold))
        hl.addWidget(title)
        hl.addStretch()
        count = QLabel(f"{len(self.projects)} ready-to-run projects")
        count.setStyleSheet(f"color: {C('text_secondary')};")
        hl.addWidget(count)
        root.addWidget(header)
        
        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)
        
        left = QWidget()
        left.setFixedWidth(380)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Search examples...")
        self.search.textChanged.connect(self._filter)
        ll.addWidget(self.search)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setSpacing(12)
        scroll.setWidget(self.card_container)
        ll.addWidget(scroll, 1)
        self._populate_cards(self.projects)
        body.addWidget(left)
        
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        self.detail_title = QLabel("Select an example")
        self.detail_title.setFont(QFont(F.ui, 24, QFont.Bold))
        self.detail_title.setWordWrap(True)
        rl.addWidget(self.detail_title)
        
        self.detail_desc = QLabel("")
        self.detail_desc.setWordWrap(True)
        self.detail_desc.setStyleSheet(f"color: {C('text_secondary')}; "
                                       f"font-size: {F.body + 1}pt; line-height: 1.6;")
        rl.addWidget(self.detail_desc)
        
        self.disclaimer = QLabel("")
        self.disclaimer.setWordWrap(True)
        self.disclaimer.setStyleSheet(f"""
            background: rgba(220,220,170,0.08);
            border-left: 3px solid {C('accent_warning')};
            color: {C('accent_warning')};
            padding: 12px 16px; border-radius: 4px;
            font-size: {F.small}pt;
        """)
        self.disclaimer.setVisible(False)
        rl.addWidget(self.disclaimer)
        
        rl.addWidget(QLabel("Slide Outline"))
        self.slide_list = QListWidget()
        self.slide_list.setFont(QFont(F.ui, F.body))
        rl.addWidget(self.slide_list, 1)
        
        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Install to:"))
        self.dest = QLineEdit()
        self.dest.setText("examples")
        dest_row.addWidget(self.dest, 1)
        browse = QPushButton("📂")
        browse.clicked.connect(self._browse_dest)
        dest_row.addWidget(browse)
        rl.addLayout(dest_row)
        
        actions = QHBoxLayout()
        install_btn = QPushButton("📥 Install Example")
        install_btn.setProperty("accent", True)
        install_btn.setMinimumHeight(42)
        install_btn.clicked.connect(self._install_direct)
        actions.addWidget(install_btn)
        
        bash_btn = QPushButton("⚙️ Run Via Bash")
        bash_btn.setMinimumHeight(42)
        bash_btn.clicked.connect(self._run_via_bash)
        actions.addWidget(bash_btn)
        rl.addLayout(actions)
        
        self.status = QLabel("Choose an example to begin.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt;")
        rl.addWidget(self.status)
        body.addWidget(right, 1)
        root.addLayout(body, 1)
        
        if self.projects:
            self._select(self.projects[0])

    def _populate_cards(self, projects):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for p in projects:
            card = QPushButton()
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet(f"""
                QPushButton {{
                    background: {C('bg_elevated')};
                    border: 1px solid {C('border')};
                    border-left: 4px solid {p.accent};
                    border-radius: 8px;
                    padding: 14px 16px;
                    text-align: left;
                }}
                QPushButton:hover {{ background: {C('bg_hover')}; }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(4)
            name = QLabel(p.title.replace("\n", " "))
            name.setWordWrap(True)
            name.setFont(QFont(F.ui, F.body + 1, QFont.Bold))
            name.setStyleSheet("background: transparent;")
            cl.addWidget(name)
            meta = QLabel(f"{p.category.upper()}   •   {p.slide_count} slides   •   {p.est_runtime}")
            meta.setStyleSheet(f"color: {C('text_secondary')}; "
                               f"font-size: {F.tiny}pt; background: transparent;")
            cl.addWidget(meta)
            card.clicked.connect(lambda _, proj=p: self._select(proj))
            self.card_layout.addWidget(card)
        self.card_layout.addStretch()

    def _filter(self, query):
        q = query.lower().strip()
        matches = [p for p in self.projects
                   if not q or q in p.title.lower() or q in p.category.lower()
                   or q in p.slug or any(q in t for t in p.tags)]
        self._populate_cards(matches)

    def _select(self, p):
        self.selected = p
        self.detail_title.setText(p.title.replace("\n", " "))
        self.detail_desc.setText(p.description)
        self.disclaimer.setVisible(bool(p.disclaimer))
        self.disclaimer.setText(p.disclaimer)
        self.slide_list.clear()
        for i, s in enumerate(p.slides, 1):
            self.slide_list.addItem(f"{i:02d}   {s.title.replace(chr(10), ' ')}")
        self.status.setText(f"Ready: {p.slug}")

    def _browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Install Examples To")
        if folder: self.dest.setText(folder)

    def _install_direct(self):
        if not self.selected: return
        try:
            path = self.library.install(self.selected.slug, self.dest.text())
            result = self.library.verify(self.selected.slug, path)
            self.status.setText(
                f"✅ Installed to {path}\n"
                f"{result['total']} checks — "
                f"{'ALL PASSED' if result['passed'] else 'SOME CHECKS FAILED'}"
            )
            toast_success(f"Installed {self.selected.slug}")
            RecentProjects().add(path, self.selected.title, self.selected.slide_count)
            self.load_in_workflow.emit(path)
            self.accept()
        except Exception as e:
            toast_error(f"Install failed: {e}")

    def _run_via_bash(self):
        if not self.selected: return
        parent = self.window()
        wt = getattr(parent, "workflow_tab", None)
        if not wt:
            toast_warning("Workflow tab not available")
            return
        try:
            script = self.library.installer_script(self.selected.slug)
            workspace = os.path.abspath(
                os.path.join(self.dest.text(), self.selected.slug))
            wt.prompt_topic.setText(self.selected.title.replace("\n", " "))
            wt.current_run = wt.history.create_run(
                self.selected.title.replace("\n", " "), workspace)
            wt.history.save_script(wt.current_run, script)
            wt.bash_editor.setPlainText(script)
            wt.prop_topic.setText(self.selected.title.replace("\n", " "))
            wt.prop_workspace.setText(workspace)
            wt.prop_status.setText("script_loaded")
            wt.approve_check.setChecked(False)
            wt.execute_btn.setEnabled(False)
            wt._validate_script()
            self.accept()
            parent.tabs.setCurrentIndex(0)
            wt.editor_tabs.setCurrentIndex(1)
            toast_info("Installer loaded. Review → approve → Execute.")
        except Exception as e:
            toast_error(f"Could not prepare installer: {e}")

# =============================================================================
#   WELCOME SCREEN
# =============================================================================
class WelcomeScreen(QWidget):
    open_project = Signal(str)
    new_project = Signal()
    open_file = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recent = RecentProjects()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        logo = QLabel("🎬")
        logo.setFont(QFont(F.ui, 48))
        hl.addWidget(logo)
        
        title_box = QVBoxLayout()
        title = QLabel("AI Presentation Studio")
        title.setFont(QFont(F.ui, 28, QFont.Bold))
        title.setStyleSheet(f"color: {C('text_primary')};")
        title_box.addWidget(title)
        subtitle = QLabel("Ultimate Edition")
        subtitle.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.heading}pt;")
        title_box.addWidget(subtitle)
        hl.addLayout(title_box)
        hl.addStretch()
        layout.addWidget(header)
        
        columns = QHBoxLayout()
        columns.setSpacing(30)
        
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        section_title = QLabel("Quick Actions")
        section_title.setFont(QFont(F.ui, F.heading, QFont.Bold))
        section_title.setStyleSheet(f"color: {C('accent_primary')};")
        left_layout.addWidget(section_title)
        
        actions = [
            ("✨ New Presentation", "Start a new project", self.new_project.emit),
            ("🎨 Example Gallery", "5 ready-to-run presentations", self._browse_examples),
            ("📂 Open Project...", "Open an existing presentation", self._open_project),
            ("📄 Open File...", "Open a specific file", self._open_file),
            ("⌨️ Keyboard Shortcuts", "View all shortcuts", self._show_shortcuts),
        ]
        for title, desc, callback in actions:
            btn = self._make_action_button(title, desc, callback)
            left_layout.addWidget(btn)
        left_layout.addStretch()
        columns.addWidget(left, 1)
        
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        recent_title = QLabel("Recent Projects")
        recent_title.setFont(QFont(F.ui, F.heading, QFont.Bold))
        recent_title.setStyleSheet(f"color: {C('accent_primary')};")
        right_layout.addWidget(recent_title)
        
        self.recent_list = QListWidget()
        self.recent_list.setFont(QFont(F.ui, F.body))
        self.recent_list.itemDoubleClicked.connect(self._on_recent_clicked)
        right_layout.addWidget(self.recent_list, 1)
        self._refresh_recent()
        columns.addWidget(right, 1)
        layout.addLayout(columns, 1)
        
        footer = QLabel("Tip: Press Ctrl+Shift+P to open the Command Palette")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt; "
                             f"font-style: italic; padding: 10px;")
        layout.addWidget(footer)

    def _make_action_button(self, title, desc, callback):
        btn = QPushButton()
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {C('bg_elevated')};
                border: 1px solid {C('border')};
                border-radius: 6px;
                padding: 12px 16px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {C('bg_hover')};
                border-color: {C('accent_primary')};
            }}
        """)
        layout = QVBoxLayout(btn)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        t = QLabel(title)
        t.setFont(QFont(F.ui, F.body, QFont.Bold))
        t.setStyleSheet(f"color: {C('text_primary')}; background: transparent;")
        layout.addWidget(t)
        d = QLabel(desc)
        d.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt; background: transparent;")
        layout.addWidget(d)
        btn.clicked.connect(callback)
        return btn

    def _refresh_recent(self):
        self.recent_list.clear()
        items = self.recent.list_all()
        if not items:
            empty = QListWidgetItem("No recent projects yet")
            empty.setForeground(Qt.gray)
            self.recent_list.addItem(empty)
            return
        for item in items:
            topic = item.get("topic", "Untitled")
            workspace = item.get("workspace", "")
            opened = item.get("opened_at", "")
            try:
                dt = datetime.fromisoformat(opened)
                time_str = dt.strftime("%b %d, %H:%M")
            except: time_str = ""
            display = f"{topic or os.path.basename(workspace)}"
            if time_str: display += f"    {time_str}"
            li = QListWidgetItem(display)
            li.setData(Qt.UserRole, workspace)
            li.setToolTip(workspace)
            self.recent_list.addItem(li)

    def _on_recent_clicked(self, item):
        workspace = item.data(Qt.UserRole)
        if workspace and os.path.isdir(workspace):
            self.open_project.emit(workspace)

    def _browse_examples(self):
        dlg = ExamplesDialog(ExampleLibrary(), self.window())
        dlg.load_in_workflow.connect(lambda path: self.open_project.emit(path))
        dlg.exec()

    def _open_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Project")
        if folder: self.open_project.emit(folder)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "",
                                              "All Supported (*.html *.txt *.md *.sh *.json);;All (*)")
        if path: self.open_file.emit(path)

    def _show_shortcuts(self):
        QMessageBox.information(self, "Keyboard Shortcuts",
            "Ctrl+Shift+P — Command Palette\n"
            "Ctrl+Shift+E — Browse Examples\n"
            "Ctrl+Shift+T — Toggle Theme\n"
            "Ctrl+O — Open File\n"
            "Ctrl+N — New Project\n"
            "Ctrl+S — Save Current\n"
            "Ctrl+F — Find\n"
            "Ctrl+G — Go to Line\n"
            "Ctrl+D — Duplicate Line\n"
            "Ctrl+/ — Toggle Comment\n"
            "Ctrl+=/-/0 — Zoom In/Out/Reset\n"
            "Alt+Z — Toggle Word Wrap\n"
            "F11 — Toggle Fullscreen\n"
            "Ctrl+K — This Dialog")

    def refresh(self):
        self._refresh_recent()

# =============================================================================
#   WORKFLOW TAB
# =============================================================================
class WorkflowTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = WorkflowHistory()
        self.template_library = TemplateLibrary()
        self.recent_projects = RecentProjects()
        self.current_run: Optional[WorkflowRun] = None
        self.executor: Optional[ScriptExecutor] = None
        self.validation_result: Optional[ValidationResult] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        steps = self._build_steps_indicator()
        root.addWidget(steps)
        
        main_splitter = QSplitter(Qt.Horizontal)
        self.file_explorer = FileExplorer()
        self.file_explorer.setMaximumWidth(320)
        self.file_explorer.setMinimumWidth(200)
        self.file_explorer.file_open_requested.connect(self._open_file_in_editor)
        main_splitter.addWidget(self.file_explorer)
        
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setMovable(True)
        self.prompt_tab = self._build_prompt_tab()
        self.editor_tabs.addTab(self.prompt_tab, "✨ Prompt")
        self.script_tab = self._build_script_tab()
        self.editor_tabs.addTab(self.script_tab, "⚙️ Bash Script")
        self.html_editor = HtmlEditor()
        self.html_editor.content_changed.connect(self._on_html_changed)
        self.editor_tabs.addTab(self.html_editor, "🌐 HTML Slide")
        self.script_editor = ScriptEditor()
        self.editor_tabs.addTab(self.script_editor, "📝 Narration")
        self.console_tab = self._build_console_tab()
        self.editor_tabs.addTab(self.console_tab, "📟 Console")
        center_layout.addWidget(self.editor_tabs, 1)
        
        action_bar = self._build_action_bar()
        center_layout.addWidget(action_bar)
        main_splitter.addWidget(center)
        
        right_tabs = QTabWidget()
        right_tabs.setMaximumWidth(420)
        right_tabs.setMinimumWidth(320)
        right_tabs.addTab(self._build_properties_panel(), "⚙️ Properties")
        right_tabs.addTab(self._build_validation_panel(), "🔍 Validate")
        right_tabs.addTab(self._build_export_panel(), "📤 Export")
        right_tabs.addTab(self._build_history_panel(), "📚 History")
        main_splitter.addWidget(right_tabs)
        
        main_splitter.setSizes([240, 1200, 360])
        root.addWidget(main_splitter, 1)

    def _build_steps_indicator(self):
        w = QWidget()
        w.setStyleSheet(f"background: {C('bg_elevated')}; "
                        f"border-bottom: 1px solid {C('border')}; padding: 8px 16px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(15, 5, 15, 5)
        self.step_labels = []
        steps = ["Generate Prompt", "Copy to AI", "Paste Script",
                 "Validate", "Execute", "Preview", "Export"]
        for i, label in enumerate(steps):
            step_w = QWidget()
            sl = QHBoxLayout(step_w)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(6)
            num = QLabel(str(i + 1))
            num.setFixedSize(22, 22)
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"""
                background: {C('bg_surface')}; color: {C('text_secondary')};
                border-radius: 11px; font-weight: bold; font-size: {F.small}pt;
            """)
            sl.addWidget(num)
            txt = QLabel(label)
            txt.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt;")
            sl.addWidget(txt)
            layout.addWidget(step_w)
            self.step_labels.append((num, txt))
            if i < len(steps) - 1:
                arrow = QLabel("›")
                arrow.setStyleSheet(f"color: {C('text_disabled')}; font-size: 16pt; margin: 0 4px;")
                layout.addWidget(arrow)
        layout.addStretch()
        return w

    def _set_step(self, n):
        for i, (num, txt) in enumerate(self.step_labels):
            if i + 1 < n:
                num.setStyleSheet(f"background: {C('accent_success')}; color: {C('text_inverse')}; "
                                  f"border-radius: 11px; font-weight: bold; font-size: {F.small}pt;")
                txt.setStyleSheet(f"color: {C('accent_success')}; font-size: {F.small}pt;")
            elif i + 1 == n:
                num.setStyleSheet(f"background: {C('accent_primary')}; color: white; "
                                  f"border-radius: 11px; font-weight: bold; font-size: {F.small}pt;")
                txt.setStyleSheet(f"color: {C('text_primary')}; font-weight: 600; font-size: {F.small}pt;")
            else:
                num.setStyleSheet(f"background: {C('bg_surface')}; color: {C('text_secondary')}; "
                                  f"border-radius: 11px; font-weight: bold; font-size: {F.small}pt;")
                txt.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt;")

    def _form_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt;")
        return lbl

    def _build_prompt_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        title = QLabel("✨ Generate Presentation Prompt")
        title.setStyleSheet(f"font-size: {F.title}pt; font-weight: 700;")
        layout.addWidget(title)
        
        form = QFormLayout()
        form.setSpacing(10)
        self.prompt_topic = QLineEdit()
        self.prompt_topic.setPlaceholderText("e.g., Why Hasan Piker is not a socialist")
        form.addRow(self._form_label("Topic *"), self.prompt_topic)
        
        row1 = QHBoxLayout()
        self.prompt_style = QComboBox()
        self.prompt_style.addItems(["video_essay", "tutorial", "debate", "documentary", "explainer"])
        row1.addWidget(self.prompt_style)
        row1.addWidget(self._form_label("Slides:"))
        self.prompt_slides = QSpinBox()
        self.prompt_slides.setRange(3, 30)
        self.prompt_slides.setValue(9)
        row1.addWidget(self.prompt_slides)
        row1.addWidget(self._form_label("Format:"))
        self.prompt_format = QComboBox()
        self.prompt_format.addItems(["bash", "json"])
        row1.addWidget(self.prompt_format)
        form.addRow(self._form_label("Style"), row1)
        
        self.prompt_tone = QLineEdit()
        self.prompt_tone.setText("provocative, analytical, engaging")
        form.addRow(self._form_label("Tone"), self.prompt_tone)
        
        self.prompt_extra = QLineEdit()
        self.prompt_extra.setPlaceholderText("Extra instructions (optional)")
        form.addRow(self._form_label("Extra"), self.prompt_extra)
        layout.addLayout(form)
        
        btn_row = QHBoxLayout()
        self.generate_prompt_btn = QPushButton("✨ Generate Prompt")
        self.generate_prompt_btn.setProperty("accent", True)
        self.generate_prompt_btn.setMinimumHeight(38)
        self.generate_prompt_btn.clicked.connect(self._generate_prompt)
        btn_row.addWidget(self.generate_prompt_btn)
        
        self.copy_prompt_btn = QPushButton("📋 Copy to Clipboard")
        self.copy_prompt_btn.clicked.connect(self._copy_prompt)
        btn_row.addWidget(self.copy_prompt_btn)
        layout.addLayout(btn_row)
        
        preview_label = QLabel("Generated Prompt")
        preview_label.setStyleSheet(f"font-size: {F.heading}pt; font-weight: 600; color: {C('accent_primary')};")
        layout.addWidget(preview_label)
        
        self.prompt_editor = CodeEditor()
        self.prompt_editor.setReadOnly(True)
        self.prompt_editor.setPlaceholderText("Your generated prompt will appear here...")
        self.prompt_editor.line_numbers_visible = False
        self.prompt_editor._update_ln_width(0)
        layout.addWidget(self.prompt_editor, 1)
        return tab

    def _build_script_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        banner = QLabel("⚙️  Paste the bash script generated by AI here.")
        banner.setStyleSheet(f"""
            background: rgba(0, 122, 204, 0.1); color: {C('accent_info')};
            padding: 10px 16px; border-bottom: 1px solid {C('border')}; font-size: {F.small}pt;
        """)
        layout.addWidget(banner)
        
        self.bash_editor = CodeEditor()
        self.bash_highlighter = BashHighlighter(self.bash_editor.document())
        self.bash_editor.setPlaceholderText("#!/usr/bin/env bash\n# Paste your bash script here...")
        layout.addWidget(self.bash_editor, 1)
        return tab

    def _build_console_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont(F.mono, F.editor))
        self.console.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.console.setStyleSheet(f"""
            QPlainTextEdit {{ background: #0a0a0a; color: {C('accent_success')};
            border: none; padding: 12px; }}
        """)
        layout.addWidget(self.console, 1)
        
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: {C('bg_elevated')}; "
                              f"border-top: 1px solid {C('border')}; padding: 6px;")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(10, 0, 10, 0)
        clear_btn = QPushButton("🧹 Clear")
        clear_btn.clicked.connect(self.console.clear)
        tl.addWidget(clear_btn)
        copy_btn = QPushButton("📋 Copy Log")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.console.toPlainText()))
        tl.addWidget(copy_btn)
        tl.addStretch()
        self.exec_progress = QProgressBar()
        self.exec_progress.setMaximumWidth(200)
        self.exec_progress.setVisible(False)
        tl.addWidget(self.exec_progress)
        layout.addWidget(toolbar)
        return tab

    def _build_action_bar(self):
        bar = QWidget()
        bar.setStyleSheet(f"background: {C('bg_elevated')}; "
                          f"border-top: 1px solid {C('border')}; padding: 10px 16px;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)
        
        self.validate_btn = QPushButton("🔍 Validate")
        self.validate_btn.clicked.connect(self._validate_script)
        layout.addWidget(self.validate_btn)
        
        self.execute_btn = QPushButton("▶ Execute")
        self.execute_btn.setProperty("success", True)
        self.execute_btn.setEnabled(False)
        self.execute_btn.setMinimumHeight(36)
        self.execute_btn.clicked.connect(self._execute_script)
        layout.addWidget(self.execute_btn)
        
        self.stop_btn = QPushButton("⛔ Stop")
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_script)
        layout.addWidget(self.stop_btn)
        layout.addSpacing(20)
        
        self.approve_check = QCheckBox("I approve execution of this script")
        self.approve_check.setStyleSheet(f"color: {C('accent_warning')}; font-weight: 600;")
        self.approve_check.toggled.connect(self._on_approve_toggled)
        layout.addWidget(self.approve_check)
        layout.addStretch()
        
        self.action_status = QLabel("Ready")
        self.action_status.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt;")
        layout.addWidget(self.action_status)
        return bar

    def _on_approve_toggled(self, checked):
        if self.validation_result and self.validation_result.valid:
            self.execute_btn.setEnabled(checked)

    def _build_properties_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        title = QLabel("⚙️ Project Properties")
        title.setStyleSheet(f"font-size: {F.heading}pt; font-weight: 600; color: {C('accent_primary')};")
        layout.addWidget(title)
        
        form = QFormLayout()
        form.setSpacing(8)
        self.prop_topic = QLabel("—")
        self.prop_topic.setWordWrap(True)
        form.addRow(self._form_label("Topic"), self.prop_topic)
        self.prop_workspace = QLabel("—")
        self.prop_workspace.setWordWrap(True)
        form.addRow(self._form_label("Workspace"), self.prop_workspace)
        self.prop_status = QLabel("—")
        form.addRow(self._form_label("Status"), self.prop_status)
        self.prop_files = QLabel("0")
        form.addRow(self._form_label("Files"), self.prop_files)
        layout.addLayout(form)
        layout.addSpacing(10)
        
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet(f"font-size: {F.heading}pt; font-weight: 600; color: {C('accent_primary')};")
        layout.addWidget(actions_label)
        
        open_btn = QPushButton("📂 Open Workspace")
        open_btn.clicked.connect(self._open_workspace)
        layout.addWidget(open_btn)
        
        change_btn = QPushButton("📁 Change Workspace")
        change_btn.clicked.connect(self._change_workspace)
        layout.addWidget(change_btn)
        layout.addStretch()
        return panel

    def _build_validation_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        title = QLabel("🔍 Validation Results")
        title.setStyleSheet(f"font-size: {F.heading}pt; font-weight: 600; color: {C('accent_primary')};")
        layout.addWidget(title)
        
        self.validation_display = QLabel("Run validation to see results.")
        self.validation_display.setWordWrap(True)
        self.validation_display.setStyleSheet(f"""
            background: {C('bg_surface')}; padding: 12px; border-radius: 6px;
            color: {C('text_secondary')}; border: 1px solid {C('border')};
        """)
        layout.addWidget(self.validation_display)
        
        self.validation_details = QPlainTextEdit()
        self.validation_details.setReadOnly(True)
        self.validation_details.setFont(QFont(F.mono, F.small))
        layout.addWidget(self.validation_details, 1)
        return panel

    def _build_export_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        title = QLabel("📤 Export Presentation")
        title.setStyleSheet(f"font-size: {F.heading}pt; font-weight: 600; color: {C('accent_primary')};")
        layout.addWidget(title)
        
        form = QFormLayout()
        self.export_format = QComboBox()
        self.export_format.addItems([
            "HTML (combined navigable)", "PDF (one slide per page)",
            "PowerPoint (PPTX)",
        ])
        form.addRow(self._form_label("Format"), self.export_format)
        
        self.export_path = QLineEdit()
        self.export_path.setPlaceholderText("output/presentation.ext")
        form.addRow(self._form_label("Output"), self.export_path)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_export)
        form.addRow("", browse_btn)
        layout.addLayout(form)
        
        self.export_btn = QPushButton("📤 Export")
        self.export_btn.setProperty("accent", True)
        self.export_btn.setMinimumHeight(38)
        self.export_btn.clicked.connect(self._start_export)
        layout.addWidget(self.export_btn)
        
        self.export_progress = QProgressBar()
        self.export_progress.setVisible(False)
        layout.addWidget(self.export_progress)
        
        self.export_log = QPlainTextEdit()
        self.export_log.setReadOnly(True)
        self.export_log.setFont(QFont(F.mono, F.small))
        layout.addWidget(self.export_log, 1)
        return panel

    def _browse_export(self):
        format_map = {
            0: ("HTML", "*.html"), 1: ("PDF", "*.pdf"), 2: ("PowerPoint", "*.pptx"),
        }
        name, filt = format_map[self.export_format.currentIndex()]
        path, _ = QFileDialog.getSaveFileName(self, f"Export {name}",
                                              f"output/presentation.{filt[2:]}", filt)
        if path: self.export_path.setText(path)

    def _build_history_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        title = QLabel("📚 Workflow History")
        title.setStyleSheet(f"font-size: {F.heading}pt; font-weight: 600; color: {C('accent_primary')};")
        layout.addWidget(title)
        
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("🔄")
        refresh_btn.clicked.connect(self._refresh_history)
        btn_row.addWidget(refresh_btn)
        load_btn = QPushButton("📥 Load")
        load_btn.clicked.connect(self._load_history_run)
        btn_row.addWidget(load_btn)
        delete_btn = QPushButton("🗑️")
        delete_btn.clicked.connect(self._delete_history_run)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._load_history_run)
        layout.addWidget(self.history_list, 1)
        return panel

    def _refresh_history(self):
        self.history_list.clear()
        for run in self.history.list_runs():
            icon = {"completed": "✅", "failed": "❌", "running": "🔄"}.get(run.status, "⏸")
            item = QListWidgetItem(f"{icon} {run.topic[:40]}")
            item.setToolTip(f"{run.topic}\n{run.workspace}\n{run.created_at}")
            item.setData(Qt.UserRole, run.id)
            self.history_list.addItem(item)

    def _load_history_run(self):
        item = self.history_list.currentItem()
        if not item: return
        run_id = item.data(Qt.UserRole)
        run = self.history.load_run(run_id)
        if not run: return
        self.current_run = run
        self.prompt_topic.setText(run.topic)
        self.prop_topic.setText(run.topic)
        self.prop_workspace.setText(run.workspace)
        self.prop_status.setText(run.status)
        if run.prompt: self.prompt_editor.setPlainText(run.prompt)
        if run.script: self.bash_editor.setPlainText(run.script)
        if run.execution_log: self.console.setPlainText(run.execution_log)
        self.file_explorer.set_workspace(run.workspace)
        self.recent_projects.add(run.workspace, run.topic)
        toast_success(f"Loaded: {run.topic}")

    def _delete_history_run(self):
        item = self.history_list.currentItem()
        if not item: return
        run_id = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete", "Delete this workflow run?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history.delete_run(run_id)
            self._refresh_history()

    def _generate_prompt(self):
        topic = self.prompt_topic.text().strip()
        if not topic:
            toast_warning("Enter a topic first")
            return
        config = PromptConfig(
            topic=topic,
            style=self.prompt_style.currentText(),
            slide_count=self.prompt_slides.value(),
            tone=self.prompt_tone.text(),
            extra=self.prompt_extra.text(),
            output_format=self.prompt_format.currentText(),
        )
        prompt = PromptGenerator.generate_bash_prompt(config)
        self.prompt_editor.setPlainText(prompt)
        workspace = os.path.join("presentations", PromptGenerator._make_slug(topic))
        self.current_run = self.history.create_run(topic, workspace)
        self.history.save_prompt(self.current_run, prompt)
        self.prop_topic.setText(topic)
        self.prop_workspace.setText(workspace)
        self.prop_status.setText("prompt_generated")
        self._set_step(2)
        toast_success("Prompt generated")

    def _copy_prompt(self):
        prompt = self.prompt_editor.toPlainText()
        if not prompt:
            toast_warning("Generate a prompt first")
            return
        QApplication.clipboard().setText(prompt)
        toast_success("Prompt copied to clipboard")
        self._set_step(3)

    def _validate_script(self):
        script = self.bash_editor.toPlainText().strip()
        if not script:
            toast_warning("Paste a bash script first")
            return
        if not self.current_run:
            topic = self.prompt_topic.text().strip() or "untitled"
            workspace = os.path.join("presentations", PromptGenerator._make_slug(topic))
            self.current_run = self.history.create_run(topic, workspace)
        
        validator = ScriptValidator(self.current_run.workspace)
        self.validation_result = validator.validate(script)
        r = self.validation_result
        
        if r.valid:
            color = C('accent_success') if not r.warnings else C('accent_warning')
            icon = "✅" if not r.warnings else "⚠️"
            status = "APPROVED" if not r.warnings else "APPROVED WITH WARNINGS"
        else:
            color = C('accent_error')
            icon = "❌"
            status = "REJECTED"
            
        self.validation_display.setText(f"{icon} {status}")
        self.validation_display.setStyleSheet(f"""
            background: {C('bg_surface')}; padding: 12px; border-radius: 6px;
            color: {color}; border-left: 4px solid {color};
            font-weight: 600; font-size: {F.heading}pt;
        """)
        
        details = []
        if r.errors:
            details.append("ERRORS:")
            for issue in r.errors:
                details.append(f"  Line {issue.line}: {issue.message}")
                if issue.suggestion:
                    details.append(f"    💡 {issue.suggestion}")
        if r.warnings:
            details.append("\nWARNINGS:")
            for issue in r.warnings:
                details.append(f"  Line {issue.line}: {issue.message}")
                if issue.suggestion:
                    details.append(f"    💡 {issue.suggestion}")
        details.append(f"\n📊 Commands: {len(r.detected_commands)}")
        details.append(f"📄 Files: ~{r.estimated_files_created}")
        self.validation_details.setPlainText("\n".join(details))
        
        self.history.save_script(self.current_run, script)
        self.history.save_validation(self.current_run, r.summary)
        self.execute_btn.setEnabled(r.valid and self.approve_check.isChecked())
        self.approve_check.setEnabled(r.valid)
        self._set_step(4 if not r.valid else 5)
        if r.valid:
            toast_success("Script validation passed")
        else:
            toast_error(f"Validation failed: {len(r.errors)} errors")

    def _execute_script(self):
        if not self.current_run: return
        script = self.bash_editor.toPlainText()
        self.history.add_version(self.current_run, script, "Pre-execution")
        
        self.executor = ScriptExecutor(self.current_run.workspace)
        self.executor.output_line.connect(self._on_exec_output)
        self.executor.progress.connect(self._on_exec_progress)
        self.executor.started.connect(self._on_exec_started)
        self.executor.finished.connect(self._on_exec_finished)
        self.executor.error.connect(self._on_exec_error)
        self.executor.file_created.connect(self._on_file_created)
        
        self.exec_progress.setVisible(True)
        self.exec_progress.setValue(0)
        self.console.clear()
        
        ok = self.executor.execute(script)
        if not ok: toast_error("Failed to start execution")

    def _stop_script(self):
        if self.executor: self.executor.stop()

    def _on_exec_started(self):
        self.execute_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.validate_btn.setEnabled(False)
        self.history.update_status(self.current_run, "running")
        self.prop_status.setText("running")
        self._set_step(5)
        self.editor_tabs.setCurrentWidget(self.console_tab)

    def _on_exec_output(self, line):
        self.console.appendPlainText(line)

    def _on_exec_progress(self, pct, msg):
        self.exec_progress.setValue(pct)
        self.action_status.setText(msg)

    def _on_exec_finished(self, exit_code):
        self.execute_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)
        self.exec_progress.setVisible(False)
        
        log = self.executor.get_full_output() if self.executor else ""
        self.history.save_log(self.current_run, log)
        self.history.update_status(self.current_run,
                                   "completed" if exit_code == 0 else "failed",
                                   exit_code)
        self.prop_status.setText("completed" if exit_code == 0 else "failed")
        
        if exit_code == 0:
            self._set_step(6)
            toast_success("Script completed successfully")
            self.file_explorer.set_workspace(self.current_run.workspace)
            self.file_explorer.refresh()
            self._count_files()
            if self.current_run:
                self.recent_projects.add(self.current_run.workspace,
                                         self.current_run.topic)
        else:
            toast_error(f"Script failed (exit {exit_code})")
            self._offer_error_recovery(log, exit_code)

    def _on_exec_error(self, msg):
        self.console.appendPlainText(f"\n⚠️  ERROR: {msg}")
        self.stop_btn.setEnabled(False)
        self.validate_btn.setEnabled(True)

    def _on_file_created(self, path):
        QTimer.singleShot(500, self.file_explorer.refresh)

    def _offer_error_recovery(self, log, exit_code):
        reply = QMessageBox.question(self, "Script Failed",
                                     f"Script failed with exit code {exit_code}.\n"
                                     "Generate a troubleshooting prompt?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            script = self.bash_editor.toPlainText()
            prompt = ErrorRecovery.generate_fix_prompt(script, log, exit_code, self.current_run.workspace)
            QApplication.clipboard().setText(prompt)
            self.prompt_editor.setPlainText(prompt)
            self.editor_tabs.setCurrentWidget(self.prompt_tab)
            toast_info("Troubleshooting prompt copied to clipboard")

    def _open_file_in_editor(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in (".html", ".htm"):
            self.html_editor.load_file(path)
            self.editor_tabs.setCurrentWidget(self.html_editor)
        elif ext in (".txt", ".md"):
            self.script_editor.load_file(path)
            self.editor_tabs.setCurrentWidget(self.script_editor)
        elif ext in (".sh", ".json"):
            with open(path, "r", encoding="utf-8") as f:
                self.bash_editor.setPlainText(f.read())
            self.editor_tabs.setCurrentWidget(self.script_tab)
        else:
            try:
                if platform.system() == "Darwin": subprocess.Popen(["open", path])
                elif platform.system() == "Windows": os.startfile(path)
                else: subprocess.Popen(["xdg-open", path])
            except Exception as e:
                toast_error(f"Could not open: {e}")

    def _on_html_changed(self, content):
        if self.html_editor.file_path:
            try:
                with open(self.html_editor.file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except: pass

    def _start_export(self):
        if not self.current_run:
            toast_warning("Generate or load a presentation first")
            return
        output = self.export_path.text().strip()
        if not output:
            toast_warning("Specify an output path")
            return
        
        format_map = {0: "html", 1: "pdf", 2: "pptx"}
        fmt = format_map[self.export_format.currentIndex()]
        
        self.export_btn.setEnabled(False)
        self.export_progress.setVisible(True)
        self.export_progress.setValue(0)
        self.export_log.clear()
        
        self._export_worker = ExportPresentationWorker(
            self.current_run.workspace, fmt, output)
        self._export_worker.progress.connect(
            lambda tid, p, m: (self.export_progress.setValue(p),
                               self.action_status.setText(m)))
        self._export_worker.log.connect(
            lambda tid, m: self._export_log_append(m))
        self._export_worker.result_ready.connect(
            lambda tid, path: self._on_export_done(path))
        self._export_worker.error_occurred.connect(
            lambda tid, err: self._on_export_error(err))
        self._export_worker.start()

    def _export_log_append(self, msg):
        self.export_log.appendPlainText(
            f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def _on_export_done(self, path):
        self.export_btn.setEnabled(True)
        self.export_progress.setVisible(False)
        self._export_log_append(f"\n✅ EXPORTED: {path}")
        self._set_step(7)
        toast_success(f"Exported to {os.path.basename(path)}")

    def _on_export_error(self, err):
        self.export_btn.setEnabled(True)
        self.export_progress.setVisible(False)
        self._export_log_append(f"\n❌ ERROR: {err}")
        toast_error(f"Export failed: {err[:100]}")

    def _open_workspace(self):
        if not self.current_run:
            toast_warning("No active workspace")
            return
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", self.current_run.workspace])
            elif platform.system() == "Windows":
                os.startfile(self.current_run.workspace)
            else:
                subprocess.Popen(["xdg-open", self.current_run.workspace])
        except Exception as e:
            toast_error(f"Could not open: {e}")

    def _change_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Workspace")
        if folder:
            self.set_workspace(folder)

    def set_workspace(self, workspace: str, topic: str = ""):
        """Load an installed project into the workflow."""
        workspace = os.path.abspath(workspace)
        if not os.path.isdir(workspace):
            toast_warning(f"Workspace not found: {workspace}")
            return
        
        existing = next(
            (r for r in self.history.list_runs()
             if os.path.abspath(r.workspace) == workspace),
            None
        )
        self.current_run = existing or self.history.create_run(
            topic or os.path.basename(workspace), workspace)
        
        self.prop_topic.setText(self.current_run.topic)
        self.prop_workspace.setText(workspace)
        self.prop_status.setText(self.current_run.status)
        
        if self.current_run.prompt:
            self.prompt_editor.setPlainText(self.current_run.prompt)
        if self.current_run.script:
            self.bash_editor.setPlainText(self.current_run.script)
            
        slides = sorted(globmod.glob(os.path.join(workspace, "slides", "slide_*.html")))
        scripts = sorted(globmod.glob(os.path.join(workspace, "scripts", "script_*.txt")))
        if slides:
            self.html_editor.load_file(slides[0])
        if scripts:
            self.script_editor.load_file(scripts[0])
            
        self.file_explorer.set_workspace(workspace)
        self.editor_tabs.setCurrentWidget(self.html_editor)
        self.recent_projects.add(workspace, self.current_run.topic, len(slides))
        self._count_files()
        self._set_step(6)
        toast_success(f"Loaded {os.path.basename(workspace)}")

    def _count_files(self):
        if not self.current_run or not os.path.isdir(self.current_run.workspace):
            self.prop_files.setText("0")
            return
        count = sum(len(files) for _, _, files in os.walk(self.current_run.workspace))
        self.prop_files.setText(str(count))

    def handle_command(self, cmd_id: str):
        handlers = {
            "workflow.generate": self._generate_prompt,
            "workflow.copy_prompt": self._copy_prompt,
            "workflow.validate": self._validate_script,
            "workflow.execute": self._execute_script,
            "workflow.stop": self._stop_script,
        }
        if cmd_id in handlers:
            handlers[cmd_id]()
            return True
        
        current = self.editor_tabs.currentWidget()
        if isinstance(current, (HtmlEditor, ScriptEditor)):
            editor = current.editor
            if cmd_id == "edit.toggle_wrap":
                editor.toggle_word_wrap()
                return True
            elif cmd_id == "edit.zoom_in":
                editor.zoom_in()
                return True
            elif cmd_id == "edit.zoom_out":
                editor.zoom_out()
                return True
            elif cmd_id == "edit.zoom_reset":
                editor.zoom_reset()
                return True
            elif cmd_id == "file.save":
                current.save_file()
                return True
        return False

# =============================================================================
#    MAIN WINDOW
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎬 AI Presentation Studio — Ultimate Edition")
        self.setMinimumSize(1600, 1000)
        self.resize(1800, 1100)
        self.settings = QSettings("VideoGen", "PresentationStudio")
        self.command_palette = None
        self.example_library = ExampleLibrary()
        self._build_ui()
        self._apply_theme()
        self._setup_shortcuts()
        self._load_settings()
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.root_layout = QVBoxLayout(central)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        
        self.stack = QStackedWidget()
        self.welcome = WelcomeScreen()
        self.welcome.open_project.connect(self._open_project)
        self.welcome.new_project.connect(self._new_project)
        self.welcome.open_file.connect(self._open_file)
        self.stack.addWidget(self.welcome)
        
        self.main_widget = self._build_main_widget()
        self.stack.addWidget(self.main_widget)
        
        if self.settings.value("show_welcome", True, type=bool):
            self.stack.setCurrentWidget(self.welcome)
        else:
            self.stack.setCurrentWidget(self.main_widget)
            
        self.root_layout.addWidget(self.stack, 1)
        
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready. Press Ctrl+Shift+P for Command Palette.")

    def _build_main_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setStyleSheet(f"background: {C('bg_elevated')}; "
                                f"border-bottom: 1px solid {C('border')}; padding: 10px 20px;")
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(20, 5, 20, 5)
        logo = QLabel("🎬")
        logo.setFont(QFont(F.ui, 20))
        tl.addWidget(logo)
        title = QLabel("AI PRESENTATION STUDIO")
        title.setFont(QFont(F.ui, F.title, QFont.Bold))
        title.setStyleSheet(f"color: {C('text_primary')}; letter-spacing: 2px;")
        tl.addWidget(title)
        version = QLabel("Ultimate Edition")
        version.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt; margin-left: 10px;")
        tl.addWidget(version)
        tl.addStretch()
        
        self.theme_btn = QPushButton("🌙" if ThemeManager.instance().current == "dark" else "☀️")
        self.theme_btn.setToolTip("Toggle theme")
        self.theme_btn.clicked.connect(lambda: ThemeManager.instance().toggle())
        tl.addWidget(self.theme_btn)
        
        cmd_btn = QPushButton("⌘ Commands")
        cmd_btn.setToolTip("Open Command Palette (Ctrl+Shift+P)")
        cmd_btn.clicked.connect(self._show_command_palette)
        tl.addWidget(cmd_btn)
        
        examples_btn = QPushButton("🎨 Examples")
        examples_btn.setToolTip("Browse example presentations (Ctrl+Shift+E)")
        examples_btn.clicked.connect(self._show_examples)
        tl.addWidget(examples_btn)
        
        home_btn = QPushButton("🏠 Home")
        home_btn.setToolTip("Back to welcome screen")
        home_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.welcome))
        tl.addWidget(home_btn)
        layout.addWidget(title_bar)
        
        api_bar = QWidget()
        api_bar.setStyleSheet(f"background: {C('bg_surface')}; "
                              f"border-bottom: 1px solid {C('border')}; padding: 6px 20px;")
        al = QHBoxLayout(api_bar)
        al.setContentsMargins(20, 4, 20, 4)
        al.setSpacing(10)
        al.addWidget(self._api_label("🔑 Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenAI", "OpenRouter", "Groq", "Ollama", "Custom"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.provider_combo.setMaximumWidth(130)
        al.addWidget(self.provider_combo)
        
        al.addWidget(self._api_label("Base URL:"))
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.openai.com/v1")
        self.base_url_input.setMaximumWidth(260)
        al.addWidget(self.base_url_input)
        
        al.addWidget(self._api_label("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setMaximumWidth(220)
        al.addWidget(self.api_key_input)
        
        al.addWidget(self._api_label("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(["gpt-4o-mini", "gpt-4o", "claude-3-5-sonnet", "llama3.1"])
        self.model_combo.setMaximumWidth(180)
        al.addWidget(self.model_combo)
        
        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._save_settings)
        al.addWidget(save_btn)
        layout.addWidget(api_bar)
        
        self.tabs = QTabWidget()
        self.workflow_tab = WorkflowTab()
        self.tabs.addTab(self.workflow_tab, "🎯 Workflow")
        layout.addWidget(self.tabs, 1)
        return widget

    def _api_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C('text_secondary')}; font-size: {F.small}pt;")
        return lbl

    def _on_provider_changed(self, provider):
        urls = {
            "OpenAI": "https://api.openai.com/v1",
            "OpenRouter": "https://openrouter.ai/api/v1",
            "Groq": "https://api.groq.com/openai/v1",
            "Ollama": "http://localhost:11434/v1",
            "Custom": "",
        }
        self.base_url_input.setText(urls.get(provider, ""))

    def _show_command_palette(self):
        if self.command_palette is None:
            self.command_palette = CommandPalette(self)
            self.command_palette.command_executed.connect(self._handle_command)
        self.command_palette.show_at_cursor()

    def _handle_command(self, cmd_id: str):
        if cmd_id == "view.theme_toggle":
            ThemeManager.instance().toggle()
            return
        if cmd_id == "view.fullscreen":
            if self.isFullScreen(): self.showNormal()
            else: self.showFullScreen()
            return
        if cmd_id == "help.shortcuts":
            self.welcome._show_shortcuts()
            return
        if cmd_id == "file.open":
            self._open_file_dialog()
            return
        if cmd_id == "file.new_prompt":
            self._new_project()
            return
        if cmd_id == "examples.browse":
            self._show_examples()
            return
        if hasattr(self, 'workflow_tab'):
            if self.workflow_tab.handle_command(cmd_id):
                return
        toast_warning(f"Command not implemented: {cmd_id}")

    def _show_examples(self):
        dlg = ExamplesDialog(self.example_library, self)
        dlg.load_in_workflow.connect(self._open_project)
        dlg.exec()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self._show_command_palette)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, lambda: ThemeManager.instance().toggle())
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+K"), self, lambda: self.welcome._show_shortcuts())
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_file_dialog)
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_project)
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, self._show_examples)

    def _toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def _open_project(self, workspace):
        self.stack.setCurrentWidget(self.main_widget)
        self.workflow_tab.set_workspace(workspace)
        self.welcome.refresh()

    def _new_project(self):
        self.stack.setCurrentWidget(self.main_widget)
        self.workflow_tab.prompt_topic.setFocus()

    def _open_file(self, path):
        self.stack.setCurrentWidget(self.main_widget)
        self.workflow_tab._open_file_in_editor(path)

    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "",
                                              "All Supported (*.html *.txt *.md *.sh *.json);;All (*)")
        if path:
            self.stack.setCurrentWidget(self.main_widget)
            self.workflow_tab._open_file_in_editor(path)

    def _apply_theme(self):
        self.setStyleSheet(build_stylesheet())

    def _on_theme_changed(self, theme_name):
        self._apply_theme()
        self.theme_btn.setText("🌙" if theme_name == "dark" else "☀️")
        toast_info(f"Switched to {theme_name} theme")

    def _save_settings(self):
        self.settings.setValue("provider", self.provider_combo.currentText())
        self.settings.setValue("base_url", self.base_url_input.text())
        self.settings.setValue("api_key", self.api_key_input.text())
        self.settings.setValue("model", self.model_combo.currentText())
        toast_success("Settings saved", self)

    def _load_settings(self):
        self.provider_combo.setCurrentText(self.settings.value("provider", "OpenAI"))
        self.base_url_input.setText(self.settings.value("base_url", "https://api.openai.com/v1"))
        self.api_key_input.setText(self.settings.value("api_key", ""))
        self.model_combo.setCurrentText(self.settings.value("model", "gpt-4o-mini"))
        self._on_provider_changed(self.provider_combo.currentText())

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)
