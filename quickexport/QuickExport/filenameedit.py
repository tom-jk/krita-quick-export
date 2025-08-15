from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget, QTreeWidget, QTreeWidgetItem, QItemDelegate, QPlainTextEdit
from PyQt5.QtCore import pyqtSignal
from krita import *
from timeit import default_timer
from .utils import *
app = Krita.instance()

class WrappingLineEdit(QPlainTextEdit):
    editingFinished = pyqtSignal()
    
    def __init__(self, text, *args, **kwargs):
        self._preferred_width = 0
        self._preferred_height = 0
        self._last_recalc_height_at_width = -1
        self._text_changed_since_last_recalc_height = True
        super().__init__(*args, **kwargs)
        self._old_plaintext = ""
        self._max_chars = 256
        self._doc_margin = round(self.document().documentMargin())
        print(f"{'WrappingLineEdit:':18} doc margin = {self._doc_margin}")
        self.textChanged.connect(self._on_text_changed)
        
        self.setMaximumBlockCount(1)
        self.setTabChangesFocus(True)
        #self.setCenterOnScroll(True)
        textoption = self.document().defaultTextOption()
        textoption.setWrapMode(QTextOption.WrapAnywhere)#WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(textoption)
        #self.document().setDocumentMargin(0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setStyleSheet("QPlainTextEdit {background: transparent;}")
        
        fm = QFontMetrics(self.font())
        #self.setMinimumWidth(fm.width("a"*12))
        self._preferred_width = min(fm.width("a")*60, fm.width(text+"PAD"))
        self._preferred_height = fm.height() + fm.descent() + self._doc_margin*2
        
        self.setPlainText(text)
        
        self._in_context_menu = False
    
    def text(self):
        return self.toPlainText()
    
    def setText(self, text):
        self.setPlainText(text)
    
    def sizeHint(self):
        #print(f"{'WrappingLineEdit:':18}{'sizeHint:':18} {self._preferred_width=} x {self._preferred_height=}")
        return QSize(self._preferred_width, self._preferred_height)
    
    def keyPressEvent(self, event):
        print(f"{'WrappingLineEdit:':18}{'keyPressEvent:':18} {event.text()}")
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            print("NEWLINE")
            self.clearFocus()
            return
        if any(char in "^<>:;?\*|/" for char in event.text()):
            print("FORBIDDEN CHAR")
            return
        super().keyPressEvent(event)
    
    def insertFromMimeData(self, source):
        print(source.text())
        self.textCursor().removeSelectedText()
        text = source.text()[:min(len(source.text()), self._max_chars)]
        for c in ('\n', '^','<','>',':',';',',','?','\\', '*','|','/'):
            if c in text:
                text = text.replace(c, "")
            source_copy = QMimeData()
            source_copy.setText(text[:min(
                len(text), self._max_chars - len(self.toPlainText())
            )])
        super().insertFromMimeData(source_copy)
        return
        self.insertPlainText(
            text[:min(
                len(text), self._max_chars - len(self.toPlainText())
            )]
        )
    
    def _on_text_changed(self):
        opt = "'" + self._old_plaintext + "'"
        pt = "'" + self.toPlainText() + "'"
        print(f"{'WrappingLineEdit:':18}{'_on_text_changed:':18} (length: {len(opt)-2:2} chars) {opt:12} --> (length: {len(pt)-2:2} chars) {pt:12}")
        if len(self.toPlainText()) > self._max_chars:
            cursor = self.textCursor()
            cursor_pos = cursor.position()
            self.setPlainText(self._old_plaintext)
            cursor.setPosition(cursor_pos-1)
            self.setTextCursor(cursor)
        else:
            self._old_plaintext = self.toPlainText()
            self._text_changed_since_last_recalc_height = True
            old_h = self._preferred_height
            self.recalc_height()
            if self._preferred_height != old_h:
                pass
                #tree.itemDelegate().sizeHintChanged.emit(tree.model().index(0, 3))
    
    def recalc_height(self, width=-1):
        if width == -1:
            width = self.width()
        
        width += - 2 - self._doc_margin*2  # do those 2 pixels come from the 1px border set from stylesheet?
        
        if False:
            # ignore width
            width = 0
        
        if False:
            if True:
                if self._last_recalc_height_at_width == width and not self._text_changed_since_last_recalc_height:
                    # print(f"{'WrappingLineEdit:':18}{'recalc_height:':18} {width=} skipped because "
                          # f"{self._last_recalc_height_at_width==width} {not self._text_changed_since_last_recalc_height} "
                          # f" - preferred_height remains {self._preferred_height}"
                    # )
                    return
            else:
                if not self._text_changed_since_last_recalc_height:
                    # print(f"{'WrappingLineEdit:':18}{'recalc_height:':18} {width=} skipped because "
                          # f"text unchanged since last call"
                          # f" - preferred_height remains {self._preferred_height}"
                    # )
                    return
        
        #fm = QFontMetrics(self.font())
        #pixelsTall = fm.boundingRect(0, 0, width, 0, Qt.AlignLeft|Qt.AlignTop|Qt.TextWrapAnywhere, self._old_plaintext).height()
        #self.setFixedHeight(pixelsTall+0+self._doc_margin*2)
        #self._preferred_height = pixelsTall+0+self._doc_margin*2
        
        fm = QFontMetrics(self.font())
        fh = fm.height()
        fs = fm.lineSpacing()
        fd = fm.descent()
        dh = self.document().size().height()
        cm = self.contentsMargins()
        dm = self.document().documentMargin()
        h = round(dh*fs + fd + dm*2.0 + cm.top() + cm.bottom())
        #h = 100
        #print(f"{fh=} {fs=} {fd=} {dh=} {h=} {self.size().height()=} cm=(top:{cm.top()},btm:{cm.bottom()}) {dm=}")
        self.setFixedHeight(h)
        self._preferred_height = h
        
        self._last_recalc_height_at_width = width
        self._text_changed_since_last_recalc_height = False
        #print(f"{'WrappingLineEdit:':18}{'recalc_height:':18} {width=} new preferred_height = {self._preferred_height}")
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, w):
        self.recalc_height(w)
        #print(f"{'WrappingLineEdit:':18}{'heightForWidth:':18} {w=} {self._preferred_height=}")
        return self._preferred_height
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.recalc_height()
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.setStyleSheet("")
    
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if self._in_context_menu:
            return
        text_cursor = self.textCursor()
        text_cursor.clearSelection()
        self.setTextCursor(text_cursor)
        self.setStyleSheet("QPlainTextEdit {background: transparent;}")
        self.editingFinished.emit()
    
    def contextMenuEvent(self, event):
        self._in_context_menu = True
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        header = menu.addAction("Suggestions")
        header.setDisabled(True)
        text = self.settings['path'].stem
        suggestions = truncated_name_suggestions(text)
        
        # note: text to use is stored in and retrieved from action data
        #       rather than action text, as Qt will add the accelarator
        #       ampersand to the text (at least, it does now, it didn't
        #       used to).
        
        t = suggestions[0]
        suggestion_actions = []
        action = menu.addAction(t)
        action.setData(t)
        suggestion_actions.append(action)
        for i in range(1, len(suggestions)):
            t += suggestions[i]
            if suggestions[i] in ",._-+":
                continue
            action = menu.addAction(t)
            action.setData(t)
            suggestion_actions.append(action)
        
        result = menu.exec(event.globalPos(), header)
        
        if result in suggestion_actions:
            self.setText(result.data())
        
        self._in_context_menu = False

class FileNameEditLayout(QVBoxLayout):
    def __init__(self, filenameedit, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filenameedit = filenameedit
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, width):
        #print(f"{'FileNameEditLayout:':18}{'heightForWidth:':18} {width=}")
        return self.doLayout(QRect(0,0,width,0))
        
    def setGeometry(self, r):
        #print(f"{'FileNameEditLayout:':18}{'setGeometry:':18} {r=}")
        
        old_h = r.height()
        h = self.doLayout(r, test_only=False)
        #print(f"{'':36} {old_h=}, {h=}")
        if old_h != h:
            pass
            #tree.update()
            #tree.updateGeometry()
    
    def doLayout(self, r, test_only=True):
        #print(f"{'FileNameEditLayout:':18}{'doLayout:':18} {r=} {test_only=}")
        if self.count() == 0:
            return 0
        
        item = self.itemAt(0)
        ir = QRect(QPoint(0,0), QSize(r.width(), item.heightForWidth(r.width())))
        #print(f"{'':36} pre:  {ir=}, {r=}, {ir.height()<r.height()}")
        if not test_only:
            if ir.height() < r.height():
                ir.translate(0, r.height()//2 - ir.height()//2)
            #print(f"{'':36} post: {ir=}")
            item.setGeometry(ir)
        
        return ir.height()

class FileNameEdit(QWidget):
    def __init__(self, text="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.layout = FileNameEditLayout(self)
        self.edit = WrappingLineEdit(text)
        self.layout.addWidget(self.edit)
        self.setLayout(self.layout)
        #self.setStyleSheet("border: 1px solid")
    
    def text(self):
        return self.edit.text()
    
    def setText(self, text):
        self.edit.setText(text)
