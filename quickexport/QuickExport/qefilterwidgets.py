from PyQt5.QtWidgets import (QLabel, QHBoxLayout, QVBoxLayout, QLineEdit, QStyle, QCompleter)
from PyQt5.QtCore import Qt, QSize, QPoint, QObject, QModelIndex, pyqtSignal, QEvent, QTimer
from PyQt5.QtGui import QFontMetrics, QIcon, QPixmap, QColor, QPainter, QPalette
from pathlib import Path
import krita

app = Krita.instance()

class FilterLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.setPlaceholderText("Filter by name...")
        self.setClearButtonEnabled(True)
        self.completer = QCompleter()
        self.completer_popup_width_set = False
        
        self.textChanged.connect(self._on_text_changed)
    
    def mouseDoubleClickEvent(self, event):
        #print(f"mouseDoubleClickEvent: ")
        popup = self.completer.popup()
        
        if popup.isVisible():
            return

        if self.text() == "":
            self.completer.setCompletionPrefix("")
            self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
            popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        else:
            self.completer.setCompletionMode(QCompleter.PopupCompletion)

        self.set_completer_popup_width_from_widest_item()
        #popup.show()
        self.completer.complete()
    
    def _on_text_changed(self, text):
        popup = self.completer.popup()
        
        if text == "":
            self.completer.setCompletionPrefix("")
            self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
            popup.move(self.mapToGlobal(self.rect().bottomLeft()))
            QTimer.singleShot(0, popup.show) # popup auto-hides, so force it visible again.
        else:
            self.completer.setCompletionMode(QCompleter.PopupCompletion)
            
        self.set_completer_popup_width_from_widest_item()
        #popup.show()
        self.completer.complete()
    
    def set_completer_popup_width_from_widest_item(self):
        popup = self.completer.popup()
        
        if popup.isVisible() or self.completer_popup_width_set:
            return
        
        model = self.completer.model()
        column = self.completer.completionColumn()
        max_w = 0
        for i in range(model.rowCount()):
            w = model.data(model.index(i, column), Qt.SizeHintRole).width()
            max_w = max(max_w, w)
            #print(i, "->", w)
        
        cm = popup.contentsMargins()
        s = popup.style()
        smpw = s.pixelMetric(QStyle.PM_MenuPanelWidth)
        smhm = s.pixelMetric(QStyle.PM_MenuHMargin)
        smdfw = s.pixelMetric(QStyle.PM_MenuDesktopFrameWidth)
        sdfw = s.pixelMetric(QStyle.PM_DefaultFrameWidth)
        
        #print(s, smpw, smhm, smdfw, sdfw, popup.width()-popup.viewport().width())
        w_pad = cm.left()+cm.right() + 2*smpw + 2*smhm + 2*smdfw + 2*sdfw + popup.width()-popup.viewport().width()
        w_kludge = 4
        w = max(self.rect().width(), max_w + w_pad + w_kludge)
        
        popup.setMinimumWidth(w)
        self.completer_popup_width_set = True
