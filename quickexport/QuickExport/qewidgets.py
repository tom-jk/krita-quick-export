from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate, QMenu,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup,
                             QActionGroup, QToolButton, QComboBox, QStackedWidget, QStyle, QStyleOption,
                             QStyleOptionButton, QSpinBox, QStyleOptionSpinBox, QGraphicsOpacityEffect,
                             QFileDialog)
from PyQt5.QtCore import Qt, QObject, QRegExp, QModelIndex, pyqtSignal, QEvent
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor, QPainter, QPalette, QMouseEvent, QTabletEvent
import zipfile
from pathlib import Path
from functools import partial
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita
from .utils import *

# copied from
# doc.qt.io/qtforpython-6/examples/example_widgets_layouts_flowlayout.html.
class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)

        if parent is not None:
            fm = QFontMetrics(parent.font)
            fw = fm.horizontalAdvance("x")
            fh = fm.height()
            self.setContentsMargins(QMargins(fw//2, fh//2, fw//2, fh//2))

        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]

        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)

        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        h = self._do_layout(QRect(0, 0, width, 0), True)
        return h

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        w = self.parentWidget().width()
        return QSize(w, self.heightForWidth(w))

    def minimumSize(self):
        return self.sizeHint()
        size = QSize()

        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        cm = self.contentsMargins()
        size += QSize(cm.left() + cm.right(), cm.top() + cm.bottom())
        return size

    def _do_layout(self, rect, test_only):
        pw = self.parentWidget()
        sw = pw.parent()
        if isinstance(sw, QStackedWidget) and sw.currentWidget() != pw:
            return 0
        if len(self._item_list) == 0:
            return 0
        #print(f"flowlayout:_do_layout: {rect=} {test_only=}")
        h = 0
        y_offset = 0
        if not test_only:
            h = self._do_layout(rect, test_only=True)
            y_offset = (rect.height() - h) // 2
        
        cm = self.contentsMargins()
        x = rect.x() + cm.left()
        y = rect.y() + cm.top()
        line_height = 0
        spacing = self.spacing()

        items_on_current_line = []
        last_line_height = 0
        final_item_index = len(self._item_list) - 1
        while self._item_list[final_item_index].isEmpty():
            final_item_index -= 1
            if final_item_index == -1:
                return 0

        for idx, item in enumerate(self._item_list):
            if item.isEmpty():
                continue
            style = item.widget().style()
            layout_spacing_x = style.layoutSpacing(
                QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Horizontal
            )
            layout_spacing_y = style.layoutSpacing(
                QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Vertical
            )
            space_x = spacing + layout_spacing_x
            space_y = spacing + layout_spacing_y
            item_sizeHint = item.sizeHint()
            next_x = x + item_sizeHint.width() + space_x
            end_of_line = False
            if next_x - space_x > rect.right() - cm.right() and line_height > 0:
                x = rect.x() + cm.left()
                y = y + line_height + space_y
                next_x = x + item_sizeHint.width() + space_x
                last_line_height = line_height
                line_height = 0
                end_of_line = True

            if not test_only:
                items_on_current_line.append((item, QRect(QPoint(x, y + y_offset), item_sizeHint)))

            x = next_x
            line_height = max(line_height, item_sizeHint.height())
            
            # go back and vertically center items on current line.
            if end_of_line or idx == final_item_index:
                if idx == final_item_index:
                    last_line_height = line_height
                if not test_only:
                    for item_, rect_ in items_on_current_line:
                        item_height = rect_.height()
                        if item_height < last_line_height:
                            rect_.translate(0, round(last_line_height/2 - item_height/2))
                        item_.setGeometry(rect_)
                    items_on_current_line.clear()

        #print(f"flowlayout:_do_layout: {rect=} {test_only=} height={y+line_height-rect.y()} {h=} {y_offset=}")
        return y + line_height - rect.y() + cm.bottom()

class QEComboBox(QComboBox):
    def addItem(self, text, data=None, tooltip=None):
        super().addItem(text, data)
        if tooltip:
            self.setItemData(self.count()-1, tooltip, Qt.ToolTipRole)
    
    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))
        
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        
        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)
        
        if bool(opt.state & QStyle.State_MouseOver) or bool(opt.state & QStyle.State_HasFocus):
            super().paintEvent(event)

class QEMenu(QMenu):
    def __init__(self, keep_open=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keep_open = keep_open
    
    def addAction(self, text, data=None, tooltip=None):
        action = super().addAction(text)
        if data is not None:
            action.setData(data)
        if tooltip is not None:
            action.setToolTip(tooltip)
        return action

    def mouseReleaseEvent(self, event):
        # keep menu open after toggling checkbox actions.
        if self.keep_open:
            if (action := self.activeAction()):
                if action.isCheckable():
                    action.trigger()
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

class FadingStackedWidget(QStackedWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self.setOpacity(hover=False)
    
    def setOpacity(self, opacity=-1, hover=False):
        fade = int(readSetting("unhovered_fade")) / 100.0
        if opacity == -1:
            opacity = 1.0 if hover else fade
        self._opacity.setOpacity(opacity)

class SpinBoxSlider(QSpinBox):
    def __init__(self, label_text="", label_suffix="", range_min=0, range_max=100, snap_interval=1, tooltip="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_text = label_text
        self.label_suffix = label_suffix
        self._snap_interval = snap_interval
        
        self.setRange(range_min, range_max)
        
        fm = QFontMetrics(self.font())
        pixelsWide = fm.horizontalAdvance(f"  {self.label_text}: {self.maximum()}{self.label_suffix}  ")
        self._default_width = pixelsWide
        
        if tooltip:
            self.setToolTip(tooltip)
        
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setSizePolicy(sp)
        self.setButtonSymbols(QSpinBox.NoButtons)
        self.lineEdit().hide()
    
    def sizeHint(self):
        return QSize(self._default_width, super().sizeHint().height())
    
    def mouseMoveEvent(self, event):
        w = self.width()
        new_value = self.minimum() + ((self.maximum()-self.minimum()) / w * event.localPos().x())
        snapped_value = self._snap_interval * round(new_value/self._snap_interval)
        self.setValue(snapped_value)
    
    def paintEvent(self, event):
        painter = QPainter(self)

        style = self.style()
        style_option = QStyleOptionSpinBox()
        style_option.initFrom(self)
        
        fill_width = int(style_option.rect.width() * (self.value() - self.minimum()) / (self.maximum() - self.minimum()))
        fill_rect = style_option.rect.adjusted(0,0,0,0)
        fill_rect.setWidth(fill_width)
        
        painter.setPen(Qt.NoPen)
        
        painter.setBrush(style_option.palette.base().color())
        painter.drawRoundedRect(style_option.rect, 1, 1)
        
        painter.setBrush(style_option.palette.highlight().color())
        painter.drawRoundedRect(fill_rect, 1, 1)
        
        painter.setPen(Qt.SolidLine)
        painter.setPen(self.palette().text().color())
        
        text = f"{self.label_text}: {self.value()}{self.label_suffix}"
        
        fm = painter.fontMetrics()
        text = fm.elidedText(text, Qt.ElideLeft, style_option.rect.width())
        pixelsWide = fm.horizontalAdvance(text)
        pixelsTall = fm.height()
        style_option.rect.adjust(0,-2,0,0)
        x = style_option.rect.center().x() - pixelsWide//2
        y = style_option.rect.center().y() + pixelsTall//2
        painter.drawText(style_option.rect, Qt.AlignCenter, text)

class ColourToolButton(QToolButton):
    colourChanged = pyqtSignal(QColor)
    
    def __init__(self, colour=None, tooltip=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.colour = colour if colour else QColor(255,255,255,255)
        if tooltip:
            self.setToolTip(tooltip)
        self.clicked.connect(self._on_clicked)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        
        style_option = QStyleOptionButton()
        style_option.initFrom(self)
        
        if self.isEnabled():
            self.style().drawPrimitive(QStyle.PE_PanelButtonCommand, style_option, painter)
        else:
            painter.setOpacity(0.1)
        
        style_option.rect.adjust(4,4,-4,-4)
        
        painter.fillRect(style_option.rect, self.colour)
    
    def _on_clicked(self, event):
        cd = QColorDialog(self.colour)
        cd.exec()
        selcol = cd.selectedColor()
        if cd.result() == QDialog.Rejected:
            return
        self.colour = cd.selectedColor()
        self.colourChanged.emit(self.colour)
        self.update()

class CheckToolButton(QToolButton):
    def __init__(self, icon_name=None, checked=False, tooltip=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCheckable(True)
        self.set_icon_name(icon_name)
        self.clicked.connect(self._on_clicked)
        extension().themeChanged.connect(self._on_theme_changed)
        if checked:
            self.setChecked(checked)
        if tooltip:
            self.setToolTip(tooltip)
    
    def setCheckState(self, check_state):
        self.setChecked(True if check_state == Qt.Checked else False)
    
    def _on_clicked(self, checked):
        if self.icon_name[0] == "visibility":
            self.icon_name = ("visibility", "show" if checked else "hide")
            self.setIcon(extension().get_icon(*self.icon_name))
    
    def _on_theme_changed(self):
        self.setIcon(extension().get_icon(*self.icon_name))
    
    def set_icon_name(self, icon_name):
        if icon_name:
            if icon_name == "visibility":
                self.icon_name = (icon_name, "show" if self.isChecked() else "hide")
            else:
                self.icon_name = icon_name if isinstance(icon_name, tuple) else (icon_name,)
            self.setIcon(extension().get_icon(*self.icon_name))
        else:
            self.icon_name = ""
            self.setIcon(QIcon())
    
    def paintEvent(self, event):
        #print("paint", event)
        
        painter = QPainter(self)
        
        style_option = QStyleOptionButton()
        style_option.initFrom(self)
        
        mouse_is_over = style_option.state & QStyle.State_MouseOver
        is_checked = not self.isCheckable() or self.isChecked()
        
        # if not mouse_is_over:
            # painter.setOpacity(0.5)
        if mouse_is_over:
            self.style().drawPrimitive(QStyle.PE_PanelButtonCommand, style_option, painter)
        
        painter.setOpacity(1.0 if is_checked else 0.65 if mouse_is_over else 0.25)
        
        #style_option.rect.adjust(2,2,-2,-2)
        if not is_checked:
            style_option.rect.adjust(2,2,-2,-2)
        
        self.style().drawItemPixmap(painter, style_option.rect, 0, self.icon().pixmap(style_option.rect.size()))
        
        if True:#not self.isChecked():
            return
        
        style_option.initFrom(self)
        style_option.state = QStyle.State_On
        style_option.rect.adjust(8,8,2,2)
        
        palette = style_option.palette
        palette.setColor(QPalette.Window, QColor(255,255,255,0))
        palette.setColor(QPalette.Base, QColor(0,0,0,0))
        palette.setColor(QPalette.Text, QColor(0,0,0,255))
        style_option.palette = palette
        
        painter.setOpacity(0.25)#0.75)
        
        # check shadow - top-left
        style_option.rect.adjust(-1,-1,-1,-1)
        self.style().drawPrimitive(QStyle.PE_IndicatorCheckBox, style_option, painter)
        
        # check shadow - top-right
        style_option.rect.adjust(3,0,3,0)
        self.style().drawPrimitive(QStyle.PE_IndicatorCheckBox, style_option, painter)
        
        # check shadow - bottom-left
        style_option.rect.adjust(-3,3,-3,3)
        self.style().drawPrimitive(QStyle.PE_IndicatorCheckBox, style_option, painter)
        
        # check shadow - bottom-right
        style_option.rect.adjust(3,0,3,0)
        self.style().drawPrimitive(QStyle.PE_IndicatorCheckBox, style_option, painter)
        
        painter.setOpacity(0.5)#1.0)
        
        # check
        style_option.rect.adjust(-2,-2,-2,-2)
        palette = style_option.palette
        palette.setColor(QPalette.Base, QColor(0,0,0,0))
        palette.setColor(QPalette.Text, QColor(255,255,255,255))
        style_option.palette = palette
        
        self.style().drawPrimitive(QStyle.PE_IndicatorCheckBox, style_option, painter)

class SnapSlider(QSlider):
    def __init__(self, snap_interval, range_min, range_max, orientation, parent=None):
        super().__init__(orientation, parent)
        self._snap_interval = snap_interval
        self.setSingleStep(snap_interval)
        self.setPageStep(snap_interval*3)
        self.setRange(range_min, range_max)
    
    def sliderChange(self, event):
        if event == QSlider.SliderValueChange:
            self.setValue(self._snap_interval * (self.value()//self._snap_interval))
        super().sliderChange(event)

class UncheckableButtonGroup(QButtonGroup):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.btnLastChecked = None
        self.buttonClicked.connect(self._on_button_clicked)
    
    def _on_button_clicked(self, btn):
        if not self.btnLastChecked:
            self.btnLastChecked = btn
        else:
            if self.btnLastChecked == btn:
                self.sender().setExclusive(False)
                btn.setChecked(Qt.Unchecked)
                self.sender().setExclusive(True)
                self.btnLastChecked = None
            else:
                self.btnLastChecked = btn
    
    def uncheckButtons(self):
        is_exclusive = self.exclusive()
        self.setExclusive(False)
        self.checkedButton().setChecked(False)
        self.setExclusive(is_exclusive)

