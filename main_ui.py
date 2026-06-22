import sys
import threading
import markdown
import re
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, 
    QPushButton, QLabel, QSizeGrip, QSplitter, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QBrush, QFont, QShortcut, QKeySequence

from ai_analyzer import look_at_screen, chat, get_api_key, AnalysisResult, check_limits

# ─── Палитра — Apple HIG (Dark Mode / iOS 17 style) ─────────────────────
class P:
    BG_WINDOW   = QColor(28, 28, 30, 240)    
    BG_CHAT     = QColor(28, 28, 30, 0)      
    BG_CODE     = QColor(18, 18, 20, 200)    
    BG_INPUT    = QColor(255, 255, 255, 20)  
    BG_HOVER    = QColor(255, 255, 255, 35)
    
    BLUE        = QColor(10, 132, 255)       
    BLUE_PRESS  = QColor(0, 113, 227)
    GREEN       = QColor(48, 209, 88)        
    RED         = QColor(255, 69, 58)        
    
    TEXT_PRI    = QColor(255, 255, 255)      
    TEXT_SEC    = QColor(235, 235, 245, 153) 
    TEXT_TER    = QColor(235, 235, 245, 76)  


class WorkerSignals(QWidget):
    result = pyqtSignal(object)


class AIGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.sigs = WorkerSignals()
        self.sigs.result.connect(self._done)

        self._drag = QPoint()
        self._collapsed = False
        self._busy = False
        
        self._scale = 1.0
        self._f = "Segoe UI" 

        self._pulse_t = QTimer(self)
        self._pulse_t.timeout.connect(self._pulse_tick)
        self._pulse_t.start(400)

        self.setMinimumSize(400, 200)
        self.resize(680, 750)
        self._to_corner()
        self._build()
        self._apply_scale()

    def _to_corner(self):
        s = QApplication.primaryScreen()
        if s:
            g = s.availableGeometry()
            self.move(g.right() - self.width() - 24, g.bottom() - self.height() - 24)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ━━━ HEADER ━━━
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 12, 0)

        self._dot = QLabel("●")
        self._dot.setFixedSize(14, 14)
        hl.addWidget(self._dot)

        self._title = QLabel("S.N.E.P.")
        hl.addWidget(self._title)

        hl.addStretch()

        self._btns = []
        controls = [
            ("-", self._zoom_out, P.TEXT_SEC, "18px"), 
            ("+", self._zoom_in, P.TEXT_SEC, "18px"), 
            ("–", self._toggle, P.TEXT_PRI, "18px"), 
            ("×", self.close, P.TEXT_PRI, "22px")
        ]
        for sym, cb, hover_col, font_sz in controls:
            b = QPushButton(sym)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("f_sz", font_sz)
            b.clicked.connect(cb)
            self._btns.append(b)
            hl.addWidget(b)

        root.addWidget(hdr)

        # ━━━ BODY ━━━
        self._body = QWidget()
        bl = QVBoxLayout(self._body)
        bl.setContentsMargins(16, 8, 16, 16)
        bl.setSpacing(14)

        # Splitter for Chat and Code
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setStyleSheet("QSplitter::handle { background-color: transparent; }")

        # Chat output 
        self._out = QTextEdit()
        self._out.setReadOnly(True)
        self._apply_md_style(self._out)
        self._splitter.addWidget(self._out)

        # Code pane
        self._code_pane = QWidget()
        self._code_pane.hide()
        cl = QVBoxLayout(self._code_pane)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        
        # Code header (Description + Close button)
        ch = QHBoxLayout()
        self._code_desc = QLabel("Описание скрипта:")
        self._code_desc.setStyleSheet("color: #FFFFFF; font-weight: bold; font-family: 'Segoe UI'; font-size: 14px;")
        self._code_desc.setWordWrap(True)
        ch.addWidget(self._code_desc)
        
        ch.addStretch()
        
        cclose = QPushButton("×")
        cclose.setFixedSize(28, 28)
        cclose.setCursor(Qt.CursorShape.PointingHandCursor)
        cclose.setStyleSheet("QPushButton { background: rgba(255,255,255,20); color: white; border-radius: 14px; font-weight: bold; font-size: 16px; padding-bottom: 2px; } QPushButton:hover { background: rgba(255,69,58,200); }")
        cclose.clicked.connect(self._close_code)
        ch.addWidget(cclose)
        
        cl.addLayout(ch)

        # Code output
        self._code_out = QTextEdit()
        self._code_out.setReadOnly(True)
        self._apply_md_style(self._code_out, is_code_pane=True)
        cl.addWidget(self._code_out)

        self._splitter.addWidget(self._code_pane)

        bl.addWidget(self._splitter)

        self._greet()

        # Main Action Button (Apple Blue)
        self._eye = QPushButton("Анализ экрана")
        self._eye.setCursor(Qt.CursorShape.PointingHandCursor)
        self._eye.clicked.connect(self._look)
        bl.addWidget(self._eye)

        # Input Row
        irow = QHBoxLayout()
        irow.setSpacing(10)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["💻 Код", "💬 Общение"])
        self._mode_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        irow.addWidget(self._mode_combo)

        self._inp = QLineEdit()
        self._inp.setPlaceholderText("Сообщение...")
        self._inp.returnPressed.connect(self._send)
        irow.addWidget(self._inp)

        self._send_btn = QPushButton("↑")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._send)
        irow.addWidget(self._send_btn)

        bl.addLayout(irow)

        # Status Bar with Size Grip
        sbar = QHBoxLayout()
        sbar.setContentsMargins(4, 0, 0, 0)

        self._sts = QLabel("Ready")
        sbar.addWidget(self._sts)
        
        self._check_btn = QPushButton("📡 Статус API")
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.clicked.connect(self._check_api)
        sbar.addWidget(self._check_btn)
        
        sbar.addStretch()

        self._model_lbl = QLabel("gemini (2.5/2.0)")
        sbar.addWidget(self._model_lbl)
        
        grip = QSizeGrip(self)
        grip.setFixedSize(16, 16)
        sbar.addWidget(grip)

        bl.addLayout(sbar)

        root.addWidget(self._body)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._toggle)

    def _close_code(self):
        self._code_pane.hide()
        if self.width() > 800:
            self.resize(int(680 * self._scale), self.height())

    def _apply_md_style(self, text_edit: QTextEdit, is_code_pane=False):
        bg = P.BG_CODE.name() if is_code_pane else "transparent"
        border = "1px solid rgba(255, 255, 255, 30)" if is_code_pane else "none"
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {bg};
                border: {border};
                border-radius: 8px;
                padding: 10px;
                selection-background-color: {P.BLUE.name()};
            }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: rgba(255,255,255,50); border-radius: 4px; min-height: 24px; }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,80); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background:transparent;}}
        """)
        
        code_font_size = "16px" if is_code_pane else "14px"
        text_edit.document().setDefaultStyleSheet(f"""
            p {{ margin-top: 6px; margin-bottom: 6px; line-height: 1.5; color: #FFFFFF; font-size: 15px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI"; }}
            pre {{ background-color: #121214; color: #D4D4D4; padding: 14px; margin: 8px 0; font-family: Consolas, monospace; border-radius: 8px; font-size: {code_font_size}; border: 1px solid rgba(255,255,255,20); }}
            code {{ background-color: #2D2D30; color: #32D74B; font-family: Consolas, monospace; padding: 2px 4px; border-radius: 4px; font-size: {code_font_size}; }}
            h1, h2, h3 {{ color: #0A84FF; margin-top: 12px; margin-bottom: 6px; font-weight: bold; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI"; }}
            ul, ol {{ margin-top: 6px; margin-bottom: 6px; }}
            li {{ margin-bottom: 4px; color: #FFFFFF; font-size: 15px; }}
            b, strong {{ color: #FFFFFF; font-weight: bold; }}
        """)

    def _zoom_in(self):
        self._scale = min(self._scale + 0.1, 2.0)
        self._apply_scale()

    def _zoom_out(self):
        self._scale = max(self._scale - 0.1, 0.6)
        self._apply_scale()

    def _apply_scale(self):
        s = self._scale

        self._title.setFont(QFont(self._f, int(15*s), QFont.Weight.Medium))
        self._title.setStyleSheet(f"color: {P.TEXT_PRI.name()}; letter-spacing: 0px;")

        btn_sz = int(30*s)
        for b in self._btns:
            b.setFixedSize(btn_sz, btn_sz)
            f_sz = float(b.property("f_sz").replace("px","")) * s
            b.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 15);
                    color: {P.TEXT_PRI.name()};
                    border: none;
                    border-radius: {int(btn_sz/2)}px;
                    font-size: {int(f_sz)}px;
                    font-family: {self._f};
                    padding-bottom: 2px;
                }}
                QPushButton:hover {{ background: rgba(255, 255, 255, 30); }}
                QPushButton:pressed {{ background: rgba(255, 255, 255, 10); }}
            """)

        self._eye.setFixedHeight(int(50*s))
        self._eye.setFont(QFont(self._f, int(15*s), QFont.Weight.Bold))
        self._eye.setStyleSheet(f"""
            QPushButton {{
                background: {P.BLUE.name()};
                color: #FFFFFF;
                border: none;
                border-radius: {int(14*s)}px;
            }}
            QPushButton:hover {{ background: {QColor(40, 150, 255).name()}; }}
            QPushButton:pressed {{ background: {P.BLUE_PRESS.name()}; }}
        """)

        self._inp.setFixedHeight(int(40*s))
        self._inp.setFont(QFont(self._f, int(13*s)))
        self._inp.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 10);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: {int(20*s)}px;
                padding: 0 {int(16*s)}px;
                selection-background-color: {P.BLUE.name()};
            }}
            QLineEdit:focus {{
                background: rgba(255, 255, 255, 15);
                border: 1px solid rgba(255, 255, 255, 30);
            }}
        """)

        self._mode_combo.setFixedHeight(int(40*s))
        self._mode_combo.setFont(QFont(self._f, int(12*s), QFont.Weight.Medium))
        self._mode_combo.setStyleSheet(f"""
            QComboBox {{
                background: rgba(255, 255, 255, 10);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: {int(20*s)}px;
                padding: 0 {int(14*s)}px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {P.BG_WINDOW.name()};
                color: #FFFFFF;
                selection-background-color: {P.BLUE.name()};
                border: 1px solid rgba(255,255,255,30);
                border-radius: 8px;
            }}
        """)

        self._send_btn.setFixedSize(int(40*s), int(40*s))
        self._send_btn.setFont(QFont(self._f, int(16*s), QFont.Weight.Bold))
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {P.BLUE.name()};
                color: #FFFFFF;
                border: none;
                border-radius: {int(20*s)}px;
                padding-bottom: 2px;
            }}
            QPushButton:hover {{ background: {QColor(40, 150, 255).name()}; }}
            QPushButton:pressed {{ background: {P.BLUE_PRESS.name()}; }}
        """)

        self._sts.setFont(QFont(self._f, int(10*s)))
        self._sts.setStyleSheet(f"color: {P.TEXT_SEC.name()};")
        
        self._check_btn.setFont(QFont(self._f, int(11*s), QFont.Weight.Medium))
        self._check_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {P.TEXT_SEC.name()};
                border: none;
                padding: 2px 8px;
            }}
            QPushButton:hover {{ color: {P.TEXT_PRI.name()}; background: rgba(255,255,255,10); border-radius: 4px; }}
        """)
        
        self._model_lbl.setFont(QFont(self._f, int(10*s)))
        self._model_lbl.setStyleSheet(f"color: {P.TEXT_TER.name()};")

    def _greet(self):
        key = get_api_key()
        self._out.clear()
        
        self._log(" S.N.E.P. AI Assistant", P.TEXT_PRI)
        self._log("")
        
        if key:
            self._log("System Online.", P.TEXT_SEC)
            self._log("Ready for analysis.", P.TEXT_SEC)
        else:
            self._log("API Key required.", P.RED)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        path = QPainterPath()
        radius = int(16 * self._scale)
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
        p.fillPath(path, QBrush(P.BG_WINDOW))
        p.end()

    def _pulse_tick(self):
        if not self._busy:
            self._dot.setStyleSheet(f"color: {P.GREEN.name()}; font-size: {int(16*self._scale)}px;")
        else:
            self._dot.setStyleSheet(f"color: {P.BLUE.name()}; font-size: {int(16*self._scale)}px;")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)
            e.accept()

    def _log(self, text, color: QColor = None):
        if color:
            self._out.append(f'<p style="color:{color.name()}">{text}</p>')
        else:
            self._out.append(f'<p style="color:{P.TEXT_PRI.name()}">{text}</p>')
        sb = self._out.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _log_md(self, md_text: str):
        html = markdown.markdown(md_text, extensions=['fenced_code', 'tables'])
        self._out.append(html)
        sb = self._out.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _lock(self, st: bool):
        self._busy = st
        self._eye.setEnabled(not st)
        self._inp.setEnabled(not st)
        self._send_btn.setEnabled(not st)

    def _look(self):
        self._lock(True)
        self._log("<br><b>● Снимок экрана...</b>", P.TEXT_TER)
        
        self.hide()
        QTimer.singleShot(200, self._do_grab)

    def _do_grab(self):
        img = "scr.jpg"
        from PIL import ImageGrab
        try:
            ImageGrab.grab(all_screens=True).save(img, quality=70)
        except:
            ImageGrab.grab().save(img, quality=70)
            
        self.show()
        self._log("<b>● Думаю...</b>", P.TEXT_TER)
        
        def task():
            mode_text = self._mode_combo.currentText()
            mode = "chat" if "Общение" in mode_text else "code"
            res = look_at_screen(img, mode=mode)
            self.sigs.result.emit(res)
        threading.Thread(target=task, daemon=True).start()

    def _send(self):
        txt = self._inp.text().strip()
        if not txt:
            return
        self._inp.clear()
        self._lock(True)
        self._log(f"<br><b>You:</b> {txt}", P.TEXT_SEC)
        self._log("<b>● Думаю...</b>", P.TEXT_TER)
        
        def task():
            mode_text = self._mode_combo.currentText()
            mode = "chat" if "Общение" in mode_text else "code"
            res = chat(txt, mode=mode)
            self.sigs.result.emit(res)
        threading.Thread(target=task, daemon=True).start()

    def _check_api(self):
        self._lock(True)
        self._log("<br><b>📡 Пинг серверов Google...</b>", P.TEXT_TER)
        
        def task():
            res = check_limits()
            self.sigs.result.emit(res)
        threading.Thread(target=task, daemon=True).start()

    def _done(self, r: AnalysisResult):
        self._lock(False)
        if not r.success:
            self._log(f"<b>Error:</b> {r.error}", P.RED)
            return

        self._log(f"<b>S.N.E.P:</b>", P.BLUE)
        
        # Попытка извлечь описание скрипта
        desc_match = re.search(r"ОПИСАНИЕ СКРИПТА:\s*(.*?)\n```", r.text, re.IGNORECASE | re.DOTALL)
        desc = desc_match.group(1).strip() if desc_match else "Скрипт по вашему запросу:"

        code_blocks = re.findall(r"```(.*?)```", r.text, re.DOTALL)
        
        if code_blocks:
            # Очищаем текст чата от кода и от строки ОПИСАНИЕ СКРИПТА
            chat_text = re.sub(r"ОПИСАНИЕ СКРИПТА:.*?\n```.*?```", "", r.text, flags=re.IGNORECASE | re.DOTALL).strip()
            chat_text = re.sub(r"```.*?```", "", chat_text, flags=re.DOTALL).strip()
            
            if chat_text:
                self._log_md(chat_text)
            
            self._code_desc.setText(desc)
            
            code_md = ""
            for code in code_blocks:
                code_md += f"```{code.strip()}```\n\n"
            
            self._code_out.clear()
            self._code_out.setHtml(markdown.markdown(code_md, extensions=['fenced_code']))
            self._code_pane.show()
            
            if self.width() < 900:
                self.resize(int(1050 * self._scale), self.height())
        else:
            self._log_md(r.text)
            self._code_pane.hide()
            if self.width() > 800:
                self.resize(int(680 * self._scale), self.height())

        self._sts.setText(f"{r.tokens_used} tk")

    def _toggle(self):
        if self._collapsed:
            self._body.show()
            self.resize(int(680 * self._scale), int(750 * self._scale))
            self._collapsed = False
        else:
            self._body.hide()
            self.resize(int(680 * self._scale), int(48 * self._scale))
            self._collapsed = True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AIGui()
    w.show()
    sys.exit(app.exec())
