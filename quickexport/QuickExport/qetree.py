from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate, QMenu,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup,
                             QActionGroup, QToolButton, QComboBox, QStackedWidget, QStyle, QStyleOption,
                             QStyleOptionButton, QSpinBox, QStyleOptionSpinBox, QGraphicsOpacityEffect,
                             QFileDialog, QProxyStyle)
from PyQt5.QtCore import Qt, QObject, QRegExp, QModelIndex, pyqtSignal, QEvent, QIdentityProxyModel
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor, QPainter, QPalette, QMouseEvent, QTabletEvent
import zipfile
from pathlib import Path
from functools import partial
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita
from .utils import *
from .qewidgets import QEMenu, UncheckableButtonGroup, CheckToolButton, ColourToolButton, QEComboBox, FadingStackedWidget, SpinBoxSlider, FlowLayout
from .multilineelidedbutton import MultiLineElidedText, MultiLineElidedButton
from .filenameedit import FileNameEdit

class QECols(IntEnum):
    NAME = 0
    BUTTONS = auto()
    COUNT = auto()

class QETree(QTreeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.setColumnCount(QECols.COUNT)
    
    def setup(self):
        for s in qe_settings:
            item = QTreeWidgetItem(self)
            item.setText(QECols.NAME, s['path'].name)
