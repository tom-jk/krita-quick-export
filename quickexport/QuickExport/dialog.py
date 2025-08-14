from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate, QMenu,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup,
                             QActionGroup, QToolButton, QComboBox, QStackedWidget, QStyle, QStyleOption,
                             QStyleOptionButton, QSpinBox, QStyleOptionSpinBox, QGraphicsOpacityEffect)
from PyQt5.QtCore import Qt, QObject, QRegExp, QModelIndex, pyqtSignal, QEvent
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor, QPainter, QPalette, QMouseEvent, QTabletEvent
import zipfile
from pathlib import Path
from functools import partial
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita
from .utils import *

app = Krita.instance()

class QEComboBox(QComboBox):
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
    
    def addAction(self, text, data=None):
        action = super().addAction(text)
        if data:
            action.setData(data)
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
        fade = int(readSetting("unhovered_fade", "75")) / 100.0
        if opacity == -1:
            opacity = 1.0 if hover else fade
        self._opacity.setOpacity(opacity)

class SpinBoxSlider(QSpinBox):
    def __init__(self, label_text="", label_suffix="", range_min=0, range_max=100, snap_interval=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_text = label_text
        self.label_suffix = label_suffix
        self._snap_interval = snap_interval
        
        self.setRange(range_min, range_max)
        
        fm = QFontMetrics(self.font())
        pixelsWide = fm.width(f"  {self.label_text}: {self.maximum()}{self.label_suffix}  ")
        self._default_width = pixelsWide
        
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
        pixelsWide = fm.width(text)
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
        extension().themeChanged.connect(self._on_theme_changed)
        if checked:
            self.setChecked(checked)
        if tooltip:
            self.setToolTip(tooltip)
    
    def _on_theme_changed(self):
        self.setIcon(extension().get_icon(*self.icon_name))
    
    def set_icon_name(self, icon_name):
        if icon_name:
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
        
        # if not mouse_is_over:
            # painter.setOpacity(0.5)
        if mouse_is_over:
            self.style().drawPrimitive(QStyle.PE_PanelButtonCommand, style_option, painter)
        
        painter.setOpacity(0.95 if self.isChecked() else 0.65 if mouse_is_over else 0.25)
        
        #style_option.rect.adjust(2,2,-2,-2)
        if not self.isChecked():
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

class MyLineEdit(QLineEdit):
    def focusInEvent(self, event):
        self.setStyleSheet("")
        super().focusInEvent(event)
    
    def focusOutEvent(self, event):
        self.setStyleSheet("QLineEdit {background: rgba(0,0,0,0);}")
        super().focusOutEvent(event)
    
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        header = menu.addAction("Suggestions")
        header.setDisabled(True)
        text = (self.settings['path'].stem)
        suggestions = truncated_name_suggestions(text)
        
        t = suggestions[0]
        suggestion_actions = []
        suggestion_actions.append(menu.addAction(t))
        for i in range(1, len(suggestions)):
            t += suggestions[i]
            if suggestions[i] in "._-+":
                continue
            suggestion_actions.append(menu.addAction(t))
        
        result = menu.exec(event.globalPos(), header)
        
        if result in suggestion_actions:
            self.setText(result.text())

class ItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        if index.column() in (QECols.OPEN_FILE_COLUMN, QECols.THUMBNAIL_COLUMN, QECols.SOURCE_FILENAME_COLUMN, QECols.BUTTONS_COLUMN):
            return None
        else:
            return super().createEditor(parent, option, index)
    
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        
        tree = QETree.instance
        
        size.setHeight(tree.min_row_height)
        return size
    
    def paint(self, painter, option, index):
        # TODO: lightly highlight row if mouse over.
        is_highlighted = index.model().index(index.row(), QECols.OPEN_FILE_COLUMN, QModelIndex()).data(QERoles.CustomSortRole) == QETree.instance.highlighted_doc_index
        is_stored = index.model().index(index.row(), QECols.STORE_SETTINGS_COLUMN, QModelIndex()).data(QERoles.CustomSortRole) == "1"
        super().paint(painter, option, index)
        if is_highlighted:
            painter.fillRect(option.rect, QColor(192,255,96,48))
        if is_stored:
            painter.fillRect(option.rect, QColor(64,128,255,QEDialog.instance.stored_highlight_slider.value()))

class MyTreeWidgetItem(QTreeWidgetItem):
    def __lt__(self, other):
        if not isinstance(other, MyTreeWidgetItem):
            return super(MyTreeWidgetItem, self).__lt__(other)

        tree = self.treeWidget()
        column = tree.sortColumn() if tree else 0

        return self.sortData(column) < other.sortData(column)
    
    def sortData(self, column):
        d = self.data(column, QERoles.CustomSortRole)
        if isinstance(d, str):
            if d.isnumeric():
                return int(d)
            return d
        return self.text(column)

class QETreeFilter(QObject):
    def eventFilter(self, tree, event):
        #print(f"eventFilter {self=} {tree=} {event=}")
        
        if not (isinstance(event, QMouseEvent) or isinstance(event, QTabletEvent)):
            return False
        
        #print("mouse/tablet event")
        pos = tree.viewport().mapFromGlobal(event.globalPos())
        item = tree.itemAt(pos)
        #print(f"{pos=}: {item.text(QECols.SOURCE_FILENAME_COLUMN) if item else 'no item'}")
        if item != tree.hovered_item:
            if tree.hovered_item:
                tree.itemWidget(tree.hovered_item, QECols.SETTINGS_COLUMN).setOpacity(hover=False)
            tree.hovered_item = item
            if tree.hovered_item:
                tree.itemWidget(tree.hovered_item, QECols.SETTINGS_COLUMN).setOpacity(hover=True)
        return False

class QECols(IntEnum):
    STORE_SETTINGS_COLUMN = 0
    OPEN_FILE_COLUMN = auto()
    THUMBNAIL_COLUMN = auto()
    SOURCE_FILENAME_COLUMN = auto()
    OUTPUT_FILENAME_COLUMN = auto()
    OUTPUT_FILETYPE_COLUMN = auto()
    SETTINGS_COLUMN = auto()
    BUTTONS_COLUMN = auto()
    COLUMN_COUNT = auto()

class QERoles(IntEnum):
    CustomSortRole = Qt.UserRole
    #MoreRoles = auto()...

class QETree(QTreeWidget):
    instance = None
    
    def leaveEvent(self, event):
        if self.hovered_item:
            self.itemWidget(self.hovered_item, QECols.SETTINGS_COLUMN).setOpacity(hover=False)
        self.hovered_item = None
    
    def refilter(self):
        for index, s in enumerate(qe_settings):
            #print(index, s["document"])
            self.items[index].setHidden(
                   (self.dialog.show_unstored_button.checkState() == Qt.Unchecked and s["store"] == False)
                or (self.dialog.show_unopened_button.checkState() == Qt.Unchecked and s["document"] == None)
                or (self.dialog.show_non_kra_button.checkState() == Qt.Unchecked and s["path"].suffix != ".kra")
            )
    
    def _on_btn_open_clicked(self, checked, btn, disabled_buttons, doc, item):
        print("_on_btn_open_clicked for", doc)
        print("opening doc")
        new_doc = app.openDocument(str(doc['path']))
        print("new_doc:", new_doc)
        if new_doc == None:
            self.dialog.sbar.showMessage(f"Couldn't open '{str(doc['path'])}'", 5000)
            return
        self.dialog.sbar.showMessage(f"Opened '{str(doc['path'])}'", 5000)
        app.activeWindow().addView(new_doc)
        item.setDisabled(False)
        self.setItemWidget(item, QECols.OPEN_FILE_COLUMN, None)
        doc['document'] = new_doc
        doc['doc_index'] = app.documents().index(new_doc)
        item.setData(QECols.OPEN_FILE_COLUMN, QERoles.CustomSortRole, str(doc['doc_index']))
        for db in disabled_buttons:
            db.setDisabled(False)
        new_doc.waitForDone()
        self.thumbnail_queue.append([new_doc, item])
        self.thumbnail_worker_timer.start()
        print("done")
    
    def _on_output_name_lineedit_editing_finished(self, doc, lineedit, item, store_button):
        doc["output_name"] = lineedit.text()
        item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, doc["output_name"].lower())
        #print("_on_output_lineedit_changed ->", doc["output"])
        self.set_settings_modified(store_button)
    
    def _on_item_btn_export_clicked(self, checked, doc, filename, store_button):
        print(f"Clicked export for {doc['path']}")
        self.sender().setText("Exporting...")
        
        result = export_image(doc)
        
        if not result:
            failed_msg = export_failed_msg()
            self.sender().setText("Failed!")
            self.dialog.sbar.showMessage(f"Export failed. {failed_msg}")
        else:
            self.sender().setText("Done!")
            self.dialog.sbar.showMessage(f"Exported to '{str(doc['path'].with_name(doc['output_name']).with_suffix(doc['ext']))}'")
        
        if self.dialog.auto_store_on_export_button.checkState() == Qt.Checked:
            store_button.setCheckState(Qt.Checked)
    
    def _on_item_scale_checkbox_action_triggered(self, checked, doc, checkboxes, store_button):
        doc["scale"] = checked
        for checkbox in checkboxes:
            checkbox.setChecked(checked)
        self.set_settings_modified(store_button)
    
    def _on_item_scale_reset_action_triggered(self, checked, doc, store_button):
        doc["scale_width"]  = -1
        doc["scale_height"] = -1
        doc["scale_filter"] = "Auto"
        doc["scale_res"]    = -1
        self.set_settings_modified(store_button)
    
    def _on_item_scale_settings_action_triggered(self, checked, doc, store_button):
        document = doc['document']
        
        w  = document.width()      if doc['scale_width'] == -1  else doc['scale_width']
        h  = document.height()     if doc['scale_height'] == -1 else doc['scale_height']
        f  = doc['scale_filter']
        r  = document.resolution() if doc['scale_res'] == -1    else doc['scale_res']
        
        print(f"start scale dialog with {w=} {h=} {f=} {r=}")
        
        from .scaledialog import ScaleDialog
        sd = ScaleDialog(parent=self, doc=document, width=w, height=h, filter_=f, res=r)
        
        sd.exec_()
        
        if sd.result_accepted:
            doc["scale_width"]  = sd.result_width
            doc["scale_height"] = sd.result_height
            doc["scale_filter"] = sd.result_filter
            doc["scale_res"]    = sd.result_res
        del sd
        
        self.set_settings_modified(store_button)
    
    def _on_item_btn_store_forget_clicked(self, checked, btn, doc, filename, item):
        #print("store/forget changed ->", checked, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["store"] = not doc["store"]
        item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+doc["store"]))
        self.redraw()
        self.set_settings_modified()
    
    def _on_outputext_combobox_current_index_changed(self, index, combobox, settings_stack, doc, item, store_button):
        ext = combobox.itemText(index)
        doc["ext"] = ext
        item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, doc["ext"])
        self.set_item_settings_stack_page_for_extension(settings_stack, ext)
        self.set_settings_modified(store_button)
    
    def set_item_settings_stack_page_for_extension(self, settings_stack, ext):
        settings_stack.setCurrentIndex(self.settings_stack_page_index_for_extension(ext))
    
    def settings_stack_page_index_for_extension(self, ext):
        try:
            return self.settings_stack_page_order.index(ext)
        except ValueError:
            for i,v in enumerate(self.settings_stack_page_order):
                if ext in v:
                    return i
            print(f"couldn't find settings stack page index for extension '{ext}'.")
    
    def _on_png_alpha_checkbox_toggled(self, checked, doc, item, store_button):
        #print("alpha checkbox changed ->", state, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["png_alpha"] = checked
        #item.setData(QECols.PNG_STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+doc["png_alpha"]))
        self.set_settings_modified(store_button)
    
    def _on_jpeg_subsampling_menu_triggered(self, value, button, doc, store_button):
        self._on_generic_setting_changed("jpeg_subsampling", value, doc, store_button)
        button.set_icon_name(("subsampling", value))
    
    def _on_jpeg_metadata_checkbox_toggled(self, checked, metadata_options_button, doc, store_button):
        self._on_generic_setting_changed("jpeg_metadata", checked, doc, store_button)
        metadata_options_button.setChecked(checked)
    
    def _on_generic_setting_changed(self, key, value, doc, store_button):
        doc[key] = value
        self.set_settings_modified(store_button)
    
    def set_settings_modified(self, store_button=None):
        if not self.dialog.tree_is_ready:
            return
        
        if generate_save_string() != readSetting("settings", ""):
            if not self.dialog.save_button.isEnabled():
                self.dialog.save_button.setText("Save Settings*")
                self.dialog.save_button.setDisabled(False)
        else:
            if self.dialog.save_button.isEnabled():
                self.dialog.save_button.setText("Save Settings")
                self.dialog.save_button.setDisabled(True)
        
        if store_button:
            if self.dialog.auto_store_on_modify_button.checkState() == Qt.Checked:
                store_button.setCheckState(Qt.Checked)
    
    def redraw(self):
        for child in self.children():
            if hasattr(child, "update"):
                child.update()
    
    def __init__(self, dialog, parent=None):
        super().__init__(parent)
        self.__class__.instance = self
        self.dialog = dialog
        
        self.setIndentation(False)
        self.setAlternatingRowColors(True)
        from PyQt5.QtCore import QItemSelectionModel
        self.setSelectionMode(QTreeWidget.NoSelection)
        
        self.setMouseTracking(True)
        self.filter = QETreeFilter()
        self.installEventFilter(self.filter)
        
        self.hovered_item = None
        
        fm = QFontMetrics(self.font())
        self.thumb_height = fm.height() * 4
        self.min_row_height = fm.height() * 5
    
    def _on_item_clicked(self, item, column):
        widget = self.itemWidget(item, column)
        if not widget:
            return
        children = widget.findChildren(QCheckBox)
        if len(children) == 1:
            children[0].animateClick()
            return
        children = widget.findChildren(QLineEdit)
        if len(children) == 1:
            children[0].setFocus(Qt.MouseFocusReason)
    
    def setup(self):
        docs = app.documents()
        
        # detect if multiple documents have the same filepath.
        self.dup_counts = {}
        for i, doc in enumerate(docs):
            doc_fn = doc.fileName()
            # ignore unsaved files.
            # TODO: better handling of Recovery files (from autosave).
            if doc_fn == "":
                continue
            for i2, doc2 in enumerate(docs):
                if i2 <= i:
                    continue
                if doc_fn == doc2.fileName():
                    self.dup_counts[doc_fn] = self.dup_counts[doc_fn]+1 if doc_fn in self.dup_counts else 1
        
        self.store_button_groups = {}
        for filename in self.dup_counts.keys():
            self.store_button_groups[filename] = UncheckableButtonGroup()
        
        # add default settings for currently open documents that didn't have corresponding stored settings.
        for i, doc in enumerate(docs):
            doc_is_in_settings = False
            if doc.fileName() == "":
                continue
            
            path = Path(doc.fileName())
            
            for s in qe_settings:
                if s["document"] == doc:
                    doc_is_in_settings = True
                    break
                if str(s["path"]) == doc.fileName():
                    # this doc is the same file as one already seen, copy settings.
                    s_copy = s.copy()
                    s_copy["store"] = False
                    qe_settings.append(s_copy)
                    doc_is_in_settings = True
                    break
            
            if doc_is_in_settings:
                continue
            
            qe_settings.append(default_settings(document=doc, doc_index=i, path=path, output_name=path.stem))
        
        # TODO: detect if multiple documents would export to the same output file.
        
        self.highlighted_doc_index = -1
        if self.dialog.highlighted_doc:
            for s in qe_settings:
                if s["document"] == self.dialog.highlighted_doc:
                    self.highlighted_doc_index = str(s["doc_index"])
                    break
        
        self.setColumnCount(QECols.COLUMN_COUNT)
        self.setHeaderLabels(["", "", "", "Filename", "Export to", "Type", "Settings", "Actions"])
        self.headerItem().setIcon(QECols.STORE_SETTINGS_COLUMN, app.icon('document-save'))
        self.items = []
        
        post_setup = []
        
        self.thumbnail_queue = []
        
        # TODO: should probably have an option to force removal of extensions from output name.
        #       an *option* because user could wish to export myfile.kra as myfile.kra.png, so output
        #       text would be myfile.kra. could instead only automatically remove an extension matching
        #       export type, but what if user wants to export myfile.png as myfile.png.png? each time they
        #       edited the output name, would they have to offer the extra .png as a sacrifice to protect
        #       the inner .png?
        #       ...I guess it could just check if output text starts with exact source filename
        #       and always leave that bit alone. Probably do that.
        filename_regex = QRegExp("^[^<>:;,?\"*|/]+$")
        
        longest_output = ""
        for s in qe_settings:
            output = s["path"].stem
            if len(output) > len(longest_output):
                longest_output = output
        
        self.settings_stack_page_order = [[".gif", ".pbm", ".pgm", ".ppm", ".tga", ".bmp", ".ico", ".xbm", ".xpm"], ".png", [".jpg",".jpeg"]]
        
        def centered_checkbox_widget(checkbox):
            widget = QWidget()
            layout = QHBoxLayout()
            layout.addStretch()
            layout.addWidget(checkbox)
            layout.addStretch()
            layout.setContentsMargins(0,0,0,0)
            widget.setLayout(layout)
            return widget
        
        # TODO: adapt to theme light/dark.
        checkbox_stylesheet = "QCheckBox::indicator:unchecked {border: 1px solid rgba(255,255,255,0.1);}"
        
        item_delegate = ItemDelegate()
        self.setItemDelegate(item_delegate)
        
        self.itemClicked.connect(self._on_item_clicked)
        
        for s in qe_settings:
            file_path = s["path"]
            
            item = MyTreeWidgetItem(self)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            
            btns_export = QToolButton()
            btns_export.setAutoRaise(True)
            btns_export.setIcon(app.icon('document-export'))
            btns_export.setToolTip("Export now")
            
            btn_store_forget = QCheckBox()
            btn_store_forget.setChecked(s["store"])
            btn_store_forget.setStyleSheet(checkbox_stylesheet)
            btn_store_forget.toggled.connect(lambda checked, btn=btn_store_forget, d=s, fn=file_path.name, i=item: self._on_item_btn_store_forget_clicked(checked, btn, d, fn, i))
            btn_store_widget = centered_checkbox_widget(btn_store_forget)
            self.setItemWidget(item, QECols.STORE_SETTINGS_COLUMN, btn_store_widget)
            item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+s["store"]))
            
            scale_menu = QEMenu(keep_open=False)
            scale_checkbox_action = scale_menu.addAction("Enabled")
            scale_checkbox_action.setCheckable(True)
            scale_checkbox_action.setChecked(s["scale"])
            scale_reset_action = scale_menu.addAction("Reset to current size and resolution")
            scale_reset_action.setDisabled(s["document"] == None)
            scale_reset_action.triggered.connect(lambda checked, d=s, sb=btn_store_forget: self._on_item_scale_reset_action_triggered(checked, d, sb))
            scale_settings_action = scale_menu.addAction("Settings...")
            scale_settings_action.setDisabled(s["document"] == None)
            scale_settings_action.triggered.connect(lambda checked, d=s, sb=btn_store_forget: self._on_item_scale_settings_action_triggered(checked, d, sb))
            
            if (btn_group_key := str(s["path"])) in self.store_button_groups:
                self.store_button_groups[btn_group_key].addButton(btn_store_forget)
                if s["store"] and self.store_button_groups[btn_group_key].btnLastChecked == None:
                    self.store_button_groups[btn_group_key].btnLastChecked = btn_store_forget
            
            if s["document"] != None:
                self.thumbnail_queue.append([s["document"], item])
                if s["document"] == app.activeDocument():
                    item.setText(QECols.OPEN_FILE_COLUMN, "*")
                    item.setTextAlignment(QECols.OPEN_FILE_COLUMN, Qt.AlignCenter)
            else:
                if str2bool(readSetting("show_thumbnails_for_unopened", "true")):
                    self.thumbnail_queue.append([s["path"], item])
                item.setDisabled(True)
                btn_open = QPushButton("")
                btn_open.setIcon(app.icon('document-open'))
                btn_open.setStyleSheet("QPushButton {border:none; background:transparent;}")
                self.setItemWidget(item, QECols.OPEN_FILE_COLUMN, btn_open)
                btn_open.clicked.connect(lambda checked, b=btn_open, db=[btns_export,scale_reset_action,scale_settings_action], d=s, i=item: self._on_btn_open_clicked(checked, b, db, d, i))
            
            item.setData(QECols.OPEN_FILE_COLUMN, QERoles.CustomSortRole, str(s["doc_index"]))
            
            item.setText(QECols.SOURCE_FILENAME_COLUMN, file_path.name)
            item.setData(QECols.SOURCE_FILENAME_COLUMN, QERoles.CustomSortRole, file_path.name.lower())
            
            output_name_widget = QWidget()
            output_name_layout = QHBoxLayout()
            output_name_edit = MyLineEdit(s["output_name"])
            output_name_edit.settings = s
            output_name_edit.setStyleSheet("QLineEdit {background: rgba(0,0,0,0);}")
            
            input_validator = QRegExpValidator(filename_regex, output_name_edit)
            output_name_edit.setValidator(input_validator)
            
            text = longest_output + "PAD"
            fm = QFontMetrics(output_name_edit.font())
            pixelsWide = fm.width(text)
            output_name_edit.setMinimumWidth(pixelsWide)
            output_name_edit.editingFinished.connect(lambda d=s, oe=output_name_edit, i=item, sb=btn_store_forget: self._on_output_name_lineedit_editing_finished(d, oe, i, sb))
            
            output_name_layout.addWidget(output_name_edit)
            output_name_widget.setLayout(output_name_layout)
            
            self.setItemWidget(item, QECols.OUTPUT_FILENAME_COLUMN, output_name_widget)
            item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, s["output_name"].lower())
            
            outputext_widget = QWidget()
            outputext_layout = QHBoxLayout()
            
            outputext_combobox = QEComboBox()
            for e in supported_extensions():
                outputext_combobox.addItem(e, e)
            
            outputext_combobox.setCurrentIndex(outputext_combobox.findData(s["ext"]))
            
            outputext_layout.addWidget(outputext_combobox)
            outputext_widget.setLayout(outputext_layout)
            
            self.setItemWidget(item, QECols.OUTPUT_FILETYPE_COLUMN, outputext_widget)
            item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, s["ext"])
            
            settings_stack = FadingStackedWidget()
            
            no_settings_page = QWidget()
            no_settings_page_layout = QHBoxLayout()
            
            no_settings_label = QLabel("(No settings.)")
            no_settings_page_layout.addWidget(no_settings_label)
            
            no_settings_scale_button = CheckToolButton(icon_name="scale", checked=s["scale"], tooltip="scale image before export")
            no_settings_scale_button.setPopupMode(QToolButton.InstantPopup)
            
            no_settings_scale_button.setMenu(scale_menu)
            no_settings_page_layout.addWidget(no_settings_scale_button)
            
            no_settings_page.setLayout(no_settings_page_layout)
            settings_stack.addWidget(no_settings_page)
            
            png_settings_page = QWidget()
            png_settings_page_layout = QHBoxLayout()
            
            png_alpha_checkbox = CheckToolButton(icon_name="alpha", checked=s["png_alpha"], tooltip="store alpha channel (transparency)")
            png_alpha_checkbox.toggled.connect(lambda checked, d=s, i=item, sb=btn_store_forget: self._on_png_alpha_checkbox_toggled(checked, d, i, sb))
            png_settings_page_layout.addWidget(png_alpha_checkbox)
            
            png_fillcolour_button = ColourToolButton(colour=s["png_fillcolour"], tooltip="transparent colour")
            png_fillcolour_button.setDisabled(png_alpha_checkbox.isChecked())
            png_alpha_checkbox.toggled.connect(lambda checked, fcb=png_fillcolour_button: fcb.setDisabled(checked))
            png_fillcolour_button.colourChanged.connect(lambda colour, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_fillcolour", colour, d, sb))
            png_settings_page_layout.addWidget(png_fillcolour_button)
            
            png_compression_slider = SpinBoxSlider(label_text="Compression", range_min=1, range_max=9, snap_interval=1)
            png_compression_slider.setValue(s["png_compression"])
            png_compression_slider.valueChanged.connect(lambda value, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_compression", value, d, sb))
            png_settings_page_layout.addWidget(png_compression_slider)
            
            png_indexed_checkbox = CheckToolButton(icon_name="indexed", checked=s["png_indexed"], tooltip="Save as indexed PNG, if possible")
            png_indexed_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_indexed", checked, d, sb))
            png_settings_page_layout.addWidget(png_indexed_checkbox)
            
            png_interlaced_checkbox = CheckToolButton(icon_name="progressive", checked=s["png_interlaced"], tooltip="interlacing")
            png_interlaced_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_interlaced", checked, d, sb))
            png_settings_page_layout.addWidget(png_interlaced_checkbox)
            
            png_hdr_checkbox = CheckToolButton(icon_name="hdr", checked=s["png_hdr"], tooltip="save as HDR image (Rec. 2020 PQ)")
            png_hdr_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_hdr", checked, d, sb))
            png_settings_page_layout.addWidget(png_hdr_checkbox)
            
            png_embed_srgb_checkbox = CheckToolButton(icon_name="embed_profile", checked=s["png_embed_srgb"], tooltip="embed sRGB profile")
            png_embed_srgb_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_embed_srgb", checked, d, sb))
            png_settings_page_layout.addWidget(png_embed_srgb_checkbox)
            
            png_force_srgb_checkbox = CheckToolButton(icon_name="force_profile", checked=s["png_force_srgb"], tooltip="force convert to sRGB")
            png_force_srgb_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_force_srgb", checked, d, sb))
            png_settings_page_layout.addWidget(png_force_srgb_checkbox)
            
            png_force_8bit_checkbox = CheckToolButton(icon_name="force_8bit", checked=s["png_force_8bit"], tooltip="force convert to 8bits/channel")
            png_force_8bit_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_force_8bit", checked, d, sb))
            png_settings_page_layout.addWidget(png_force_8bit_checkbox)
            
            png_metadata_checkbox = CheckToolButton(icon_name="metadata", checked=s["png_metadata"], tooltip="store metadata")
            png_metadata_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_metadata", checked, d, sb))
            png_settings_page_layout.addWidget(png_metadata_checkbox)
            
            png_author_checkbox = CheckToolButton(icon_name="author", checked=s["png_author"], tooltip="sign with author data")
            png_author_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("png_author", checked, d, sb))
            png_settings_page_layout.addWidget(png_author_checkbox)
            
            png_scale_button = CheckToolButton(icon_name="scale", checked=s["scale"], tooltip="scale image before export")
            png_scale_button.setPopupMode(QToolButton.InstantPopup)
            
            png_scale_button.setMenu(scale_menu)
            png_settings_page_layout.addWidget(png_scale_button)
            
            png_settings_page.setLayout(png_settings_page_layout)
            settings_stack.addWidget(png_settings_page)
            
            jpeg_settings_page = QWidget()
            jpeg_settings_page_layout = QHBoxLayout()
            
            jpeg_icc_profile_checkbox = CheckToolButton(icon_name="embed_profile", checked=s["jpeg_icc_profile"], tooltip="save ICC profile")
            jpeg_icc_profile_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_icc_profile", checked, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_icc_profile_checkbox)
            
            jpeg_fillcolour_checkbox = ColourToolButton(colour=s["jpeg_fillcolour"], tooltip="transparent pixel fill colour")
            jpeg_fillcolour_checkbox.colourChanged.connect(lambda colour, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_fillcolour", colour, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_fillcolour_checkbox)
            
            jpeg_quality_slider = SpinBoxSlider(label_text="Quality", label_suffix="%", range_min=0, range_max=100, snap_interval=5)
            jpeg_quality_slider.setValue(s["jpeg_quality"])
            jpeg_quality_slider.valueChanged.connect(lambda value, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_quality", value, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_quality_slider)
            
            jpeg_progressive_checkbox = CheckToolButton(icon_name="progressive", checked=s["jpeg_progressive"], tooltip="progressive")
            jpeg_progressive_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_progressive", checked, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_progressive_checkbox)
            
            jpeg_smooth_slider = SpinBoxSlider(label_text="Smooth", label_suffix="%", range_min=0, range_max=100, snap_interval=5)
            jpeg_smooth_slider.setValue(s["jpeg_smooth"])
            jpeg_smooth_slider.valueChanged.connect(lambda value, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_smooth", value, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_smooth_slider)
            
            jpeg_subsampling_button = CheckToolButton(icon_name=("subsampling", s["jpeg_subsampling"]), checked=True, tooltip="subsampling")
            jpeg_subsampling_button.setPopupMode(QToolButton.InstantPopup)
            
            jpeg_subsampling_menu = QEMenu(keep_open=False)
            jpeg_subsampling_action_group = QActionGroup(jpeg_subsampling_menu)
            jpeg_subsampling_2x2_action = jpeg_subsampling_menu.addAction("2x2, 1x1, 1x1 (smallest file)", "2x2")
            jpeg_subsampling_2x1_action = jpeg_subsampling_menu.addAction("2x1, 1x1, 1x1", "2x1")
            jpeg_subsampling_1x2_action = jpeg_subsampling_menu.addAction("1x2, 1x1, 1x1", "1x2")
            jpeg_subsampling_1x1_action = jpeg_subsampling_menu.addAction("1x1, 1x1, 1x1 (best quality)", "1x1")
            for i, action in enumerate(jpeg_subsampling_menu.actions()):
                action.setCheckable(True)
                action.setActionGroup(jpeg_subsampling_action_group)
                action.setChecked(action.data() == s["jpeg_subsampling"])
            jpeg_subsampling_menu.triggered.connect(lambda a, b=jpeg_subsampling_button, d=s, sb=btn_store_forget: self._on_jpeg_subsampling_menu_triggered(a.data(), b, d, sb))
            
            jpeg_subsampling_button.setMenu(jpeg_subsampling_menu)
            jpeg_settings_page_layout.addWidget(jpeg_subsampling_button)
            
            jpeg_force_baseline_checkbox = CheckToolButton(icon_name="jpeg_baseline", checked=s["jpeg_force_baseline"], tooltip="force baseline JPEG")
            jpeg_force_baseline_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_force_baseline", checked, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_force_baseline_checkbox)
            
            jpeg_optimise_checkbox = CheckToolButton(icon_name="optimise", checked=s["jpeg_optimise"], tooltip="optimise")
            jpeg_optimise_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_optimise", checked, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_optimise_checkbox)
            
            jpeg_metadata_options_button = CheckToolButton(icon_name="metadata_options", checked=s["jpeg_metadata"], tooltip="formats")
            jpeg_metadata_options_button.setPopupMode(QToolButton.InstantPopup)
            
            jpeg_metadata_options_menu = QEMenu()
            
            jpeg_metadata_options_header_action = jpeg_metadata_options_menu.addAction("Metadata formats")
            jpeg_metadata_options_header_action.setDisabled(True)
            jpeg_metadata_options_Exif_action = jpeg_metadata_options_menu.addAction("Exif", "exif")
            jpeg_metadata_options_IPTC_action = jpeg_metadata_options_menu.addAction("IPTC", "iptc")
            jpeg_metadata_options_XMP_action = jpeg_metadata_options_menu.addAction("XMP", "xmp")
            
            jpeg_filters_header_action = jpeg_metadata_options_menu.addAction("Filters")
            jpeg_filters_header_action.setDisabled(True)
            jpeg_metadata_options_info_action = jpeg_metadata_options_menu.addAction("Tool information", "tool_information")
            jpeg_metadata_options_anon_action = jpeg_metadata_options_menu.addAction("Anonymiser", "anonymiser")
            
            for action in jpeg_metadata_options_menu.actions():
                if not action.data():
                    continue
                action.setCheckable(True)
                action.setChecked(s[f"jpeg_{action.data()}"])
            jpeg_metadata_options_menu.triggered.connect(lambda a, d=s, sb=btn_store_forget: self._on_generic_setting_changed(f"jpeg_{a.data()}", a.isChecked(), d, sb))
            
            jpeg_metadata_options_button.setMenu(jpeg_metadata_options_menu)
            jpeg_settings_page_layout.addWidget(jpeg_metadata_options_button)
            
            jpeg_metadata_checkbox = CheckToolButton(icon_name="metadata", checked=s["jpeg_metadata"], tooltip="store metadata")
            jpeg_metadata_checkbox.toggled.connect(lambda checked, mob=jpeg_metadata_options_button, d=s, sb=btn_store_forget: self._on_jpeg_metadata_checkbox_toggled(checked, mob, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_metadata_checkbox)
            
            jpeg_author_checkbox = CheckToolButton(icon_name="author", checked=s["jpeg_author"], tooltip="sign with author data")
            jpeg_author_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_author", checked, d, sb))
            jpeg_settings_page_layout.addWidget(jpeg_author_checkbox)
            
            jpeg_scale_button = CheckToolButton(icon_name="scale", checked=s["scale"], tooltip="scale image before export")
            jpeg_scale_button.setPopupMode(QToolButton.InstantPopup)
            
            jpeg_scale_button.setMenu(scale_menu)
            jpeg_settings_page_layout.addWidget(jpeg_scale_button)
            
            jpeg_settings_page.setLayout(jpeg_settings_page_layout)
            settings_stack.addWidget(jpeg_settings_page)
            
            self.setItemWidget(item, QECols.SETTINGS_COLUMN, settings_stack)
            self.set_item_settings_stack_page_for_extension(settings_stack, s["ext"])
            
            scale_checkbox_action.triggered.connect(lambda checked, d=s, cb=[no_settings_scale_button,png_scale_button,jpeg_scale_button], sb=btn_store_forget: self._on_item_scale_checkbox_action_triggered(checked, d, cb, sb))
            
            btns_widget = QWidget()
            btns_layout = QHBoxLayout()
            btns_export.setDisabled(s["document"] == None)
            btns_export.clicked.connect(lambda checked, d=s, fn=file_path.name, sb=btn_store_forget: self._on_item_btn_export_clicked(checked, d, fn, sb))
            btns_layout.addWidget(btns_export)
            
            btns_widget.setLayout(btns_layout)
            
            self.setItemWidget(item, QECols.BUTTONS_COLUMN, btns_widget)
            
            outputext_combobox.currentIndexChanged.connect(lambda index, cb=outputext_combobox, ss=settings_stack, d=s, i=item, sb=btn_store_forget: self._on_outputext_combobox_current_index_changed(index, cb, ss, d, i, sb))
            
            self.items.append(item)
        
        for i in range(0, QECols.COLUMN_COUNT):
            self.resizeColumnToContents(i)

        if len(self.thumbnail_queue) == 0:
            return
        
        self.thumbnail_column_resized_to_contents_once = False
        self.thumbnail_worker = self.thumbnail_worker_process()
        self.thumbnail_worker_timer = QTimer(self)
        self.thumbnail_worker_timer.setInterval(0)
        self.thumbnail_worker_timer.setSingleShot(True)
        self.thumbnail_worker_timer.timeout.connect(lambda: next(self.thumbnail_worker, None))
        self.thumbnail_worker_timer.start()

    def thumbnail_worker_process(self):
        print("thumbnail worker: start.")
        
        try:
            while True:
                while len(self.thumbnail_queue) == 0:
                    print("thumbnail worker: job queue empty.")
                    yield
                
                job = self.thumbnail_queue.pop(0)
                
                item = job[1]
                
                if isinstance(job[0], Path):
                    file_path = job[0]
                    
                    print(f"thumbnail_worker: do job for unopened document {file_path=}")
                    
                    self._make_thumbnail_for_file(file_path, item)
                else:
                    doc = job[0]
                
                    print(f"thumbnail_worker: do job for open document {doc.fileName()=}")
                
                    self._make_thumbnail(doc, item)
                
                print("thumbnail_worker: job done.")
                
                if not self.thumbnail_column_resized_to_contents_once:
                    self.resizeColumnToContents(QECols.THUMBNAIL_COLUMN)
                    self.thumbnail_column_resized_to_contents_once = True
                
                yield self.thumbnail_worker_timer.start()
        
        finally:
            print("thumbnail worker: end.")
    
    def _make_thumbnail(self, doc, item):
        thumbnail = QPixmap.fromImage(doc.thumbnail(self.thumb_height, self.thumb_height))
        label = QLabel()
        label.setPixmap(thumbnail)
        self.setItemWidget(item, QECols.THUMBNAIL_COLUMN, label)
    
    # borrowed from the Last Documents Docker.
    def _make_thumbnail_for_file(self, path, item):
        thumbnail = QPixmap()
        extension = path.suffix
        try:
            if extension == '.kra':
                page = zipfile.ZipFile(path, "r")
                thumbnail.loadFromData(page.read("preview.png"))
            else:
                thumbnail = QPixmap(str(path))
        except FileNotFoundError:
            print(f"file '{path}' not found.")
        except Exception as e:
            print(f"error trying to read file '{path}'. the error is:\n{type(e).__name__}: {e}")

        if thumbnail.isNull():
            print(f"couldn't make thumbnail for file '{path}'.")
            thumbnail = app.icon('window-close').pixmap(self.thumb_height, self.thumb_height)

        thumb_size = QSize(int(self.thumb_height*self.devicePixelRatioF()), int(self.thumb_height*self.devicePixelRatioF()))
        thumbnail = thumbnail.scaled(thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumbnail.setDevicePixelRatio(self.devicePixelRatioF()) # TODO: should do for doc.thumbnail thumbs too?
        
        label = QLabel()
        label.setPixmap(thumbnail)
        self.setItemWidget(item, QECols.THUMBNAIL_COLUMN, label)

class QEDialog(QDialog):
    instance = None

    def __init__(self, msg="", doc=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.__class__.instance = self

        self.highlighted_doc = doc

        layout = QVBoxLayout()

        # TODO: save user changes to tree column sizes and retrieve at each start.
        self.tree_is_ready = False
        self.tree = QETree(self)
        self.tree.setup()
        # TODO: disallow sorting by thumbnail and action button columns.
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(QECols.OPEN_FILE_COLUMN, Qt.AscendingOrder)
        layout.addWidget(self.tree)
        self.tree_is_ready = True

        view_buttons = QWidget()
        view_buttons_layout = QHBoxLayout()

        # TODO: inform user that some items are currently hidden, and how many.

        # show unstored button.
        self.show_unstored_button = QCheckBox("Show unstored")
        self.show_unstored_button.setToolTip("Enable this to pick the images you're interested in exporting, then disable it to hide the rest.")
        self.show_unstored_button.setCheckState(str2qtcheckstate(readSetting("show_unstored", "true")))
        self.show_unstored_button.clicked.connect(self._on_show_unstored_button_clicked)

        # show unopened button.
        self.show_unopened_button = QCheckBox("Show unopened")
        self.show_unopened_button.setToolTip("Show the export settings of every file - currently open or not - for which settings have been saved.")
        self.show_unopened_button.setCheckState(str2qtcheckstate(readSetting("show_unopened", "false")))
        self.show_unopened_button.clicked.connect(self._on_show_unopened_button_clicked)

        # show .png files button.
        self.show_non_kra_button = QCheckBox("Show non-kra files")
        self.show_non_kra_button.setToolTip("Show export settings for files of usually exported types, such as .png and .jpg. Disabled by default because it's kind of redundant.")
        self.show_non_kra_button.setCheckState(str2qtcheckstate(readSetting("show_non_kra", "false")))
        self.show_non_kra_button.clicked.connect(self._on_show_non_kra_button_clicked)

        # slider for settings fade for unhovered rows.
        unhovered_fade_widget = QWidget()
        unhovered_fade_layout = QHBoxLayout()

        unhovered_fade_widget.setMinimumWidth(64)
        unhovered_fade_widget.setMaximumWidth(256)

        unhovered_fade_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        unhovered_fade_label = QLabel("Fade")
        unhovered_fade_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        unhovered_fade_layout.addWidget(unhovered_fade_label)

        self.unhovered_fade_slider = SnapSlider(5, 0, 100, Qt.Horizontal)
        self.unhovered_fade_slider.setValue(int(readSetting("unhovered_fade", "75")))
        self.unhovered_fade_slider.setMinimumWidth(64)
        self.unhovered_fade_slider.valueChanged.connect(self._on_unhovered_fade_slider_value_changed)
        unhovered_fade_layout.addWidget(self.unhovered_fade_slider)

        unhovered_fade_widget.setLayout(unhovered_fade_layout)

        # slider for row highlight intensity for stored settings.
        stored_highlight_widget = QWidget()
        stored_highlight_layout = QHBoxLayout()

        stored_highlight_widget.setMinimumWidth(64)
        stored_highlight_widget.setMaximumWidth(256)

        stored_highlight_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        stored_highlight_label = QLabel("Highlight stored")
        stored_highlight_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        stored_highlight_layout.addWidget(stored_highlight_label)

        self.stored_highlight_slider = SnapSlider(8, 0, 64, Qt.Horizontal)
        self.stored_highlight_slider.setValue(int(readSetting("highlight_alpha", "64")))
        self.stored_highlight_slider.setMinimumWidth(64)
        self.stored_highlight_slider.valueChanged.connect(self._on_stored_highlight_slider_value_changed)
        stored_highlight_layout.addWidget(self.stored_highlight_slider)

        stored_highlight_widget.setLayout(stored_highlight_layout)

        view_buttons_layout.addWidget(self.show_non_kra_button)
        view_buttons_layout.addWidget(self.show_unopened_button)
        view_buttons_layout.addWidget(self.show_unstored_button)
        view_buttons_layout.addStretch()
        view_buttons_layout.addWidget(unhovered_fade_widget)
        view_buttons_layout.addWidget(stored_highlight_widget)

        view_buttons_layout.setContentsMargins(0,0,0,0)
        view_buttons.setLayout(view_buttons_layout)
        layout.addWidget(view_buttons)

        config_buttons = QWidget()
        config_buttons_layout = QHBoxLayout()

        # advanced mode button.
        self.advanced_mode_button = QCheckBox("Advanced mode")
        self.advanced_mode_button.setToolTip("Basic mode: export settings are saved by default (recommended).\nAdvanced mode: configure how settings are stored.")
        self.advanced_mode_button.setCheckState(str2qtcheckstate(readSetting("advanced_mode", "false")))
        self.advanced_mode_button.clicked.connect(self._on_advanced_mode_button_clicked)

        # auto store for modified button.
        self.auto_store_on_modify_button = QCheckBox("Store on modify")
        self.auto_store_on_modify_button.setToolTip("Automatically check the store button for a file when you modify any of its export settings.")
        self.auto_store_on_modify_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_modify", "true")))
        self.auto_store_on_modify_button.clicked.connect(self._on_auto_store_on_modify_button_clicked)

        # auto store for exported button.
        self.auto_store_on_export_button = QCheckBox("Store on export")
        self.auto_store_on_export_button.setToolTip("Automatically check the store button for a file when you export it.")
        self.auto_store_on_export_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_export", "true")))
        self.auto_store_on_export_button.clicked.connect(self._on_auto_store_on_export_button_clicked)

        # auto save settings on close button.
        self.auto_save_on_close_button = QCheckBox("Save settings on close")
        self.auto_save_on_close_button.setToolTip("Automatically save changes to settings without asking when you close the dialog.")
        self.auto_save_on_close_button.setCheckState(str2qtcheckstate(readSetting("auto_save_on_close", "true")))
        self.auto_save_on_close_button.clicked.connect(self._on_auto_save_on_close_button_clicked)

        # save button.
        self.save_button = QPushButton("Save Settings")
        self.save_button.setDisabled(True)
        self.save_button.clicked.connect(self._on_save_button_clicked)

        config_buttons_layout.addWidget(self.advanced_mode_button)
        config_buttons_layout.addWidget(self.auto_store_on_modify_button)
        config_buttons_layout.addWidget(self.auto_store_on_export_button)
        config_buttons_layout.addWidget(self.auto_save_on_close_button)
        config_buttons_layout.addStretch()
        config_buttons_layout.addWidget(self.save_button)

        config_buttons_layout.setContentsMargins(0,0,0,0)
        config_buttons.setLayout(config_buttons_layout)
        layout.addWidget(config_buttons)

        self.tree.refilter()

        self.set_advanced_mode(self.advanced_mode_button.checkState() == Qt.Checked)

        # status bar area.
        status_widget = QWidget()
        status_layout = QHBoxLayout()
        
        # qe options menu.
        options_button = QToolButton()
        options_button.setIcon(app.icon('view-choose'))
        options_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        options_button.setAutoRaise(True)
        options_button.setStyleSheet("QToolButton::menu-indicator {image: none;}")
        options_button.setPopupMode(QToolButton.InstantPopup)
        status_layout.addWidget(options_button)
        
        options_menu = QEMenu()
        options_menu.setToolTipsVisible(True)

        use_custom_icons_action = options_menu.addAction("Use custom icons")
        use_custom_icons_action.setCheckable(True)
        use_custom_icons_action.setChecked(str2qtcheckstate(readSetting("use_custom_icons", "true")))
        use_custom_icons_action.toggled.connect(self._on_use_custom_icons_action_toggled)

        options_menu.addSeparator()

        custom_icons_theme_action_group = QActionGroup(options_menu)
        custom_icons_theme_action_group.triggered.connect(lambda action, grp=custom_icons_theme_action_group: self._on_custom_icons_theme_action_group_triggered(action, grp))

        icons_follow_theme_action = options_menu.addAction("Try to follow theme")
        icons_follow_theme_action.setToolTip("If using one of the themes bundled with Krita, the correct icons will be used.\n" \
                                             "If not, guesses which icons to use based on keywords in the theme name ('dark', 'black', etc.)\n" \
                                             "If there are no such keywords, assumes light theme. You can force a theme if the guess is wrong.")
        icons_follow_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_follow_theme_action.setCheckable(True)
        icons_follow_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme", "follow"), "follow"))

        icons_light_theme_action = options_menu.addAction("Use light theme icons")
        icons_light_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_light_theme_action.setCheckable(True)
        icons_light_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme", "follow"), "light"))

        icons_dark_theme_action = options_menu.addAction("Use dark theme icons")
        icons_dark_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_dark_theme_action.setCheckable(True)
        icons_dark_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme", "follow"), "dark"))

        options_menu.addSeparator()
        
        show_export_name_in_menu_action = options_menu.addAction("Show export name in File menu")
        show_export_name_in_menu_action.setToolTip("When possible, show in the File menu as 'Quick Export to 'myImageName.png'.\n" \
                                                   "Otherwise show as 'Quick Export' only.")
        show_export_name_in_menu_action.setCheckable(True)
        show_export_name_in_menu_action.setChecked(str2qtcheckstate(readSetting("show_export_name_in_menu", "true")))
        show_export_name_in_menu_action.toggled.connect(self._on_show_export_name_in_menu_action_toggled)
        
        options_menu.addSeparator()

        default_export_unsaved_action = options_menu.addAction("Default export for unsaved images")
        default_export_unsaved_action.setToolTip("Run the normal Krita exporter for not-yet-saved images.\n" \
                                                 "Otherwise don't export, just show a reminder to save the file.")
        default_export_unsaved_action.setCheckable(True)
        default_export_unsaved_action.setChecked(str2qtcheckstate(readSetting("default_export_unsaved", "false")))
        default_export_unsaved_action.toggled.connect(self._on_default_export_unsaved_action_toggled)
        
        options_menu.addSeparator()
        
        use_previous_version_settings_action_group = QActionGroup(options_menu)
        
        use_previous_version_settings_prompt_header = options_menu.addAction("When first exporting a new version of an image:")
        use_previous_version_settings_prompt_header.setDisabled(True)
        
        use_previous_version_settings_copy_action = options_menu.addAction("Always copy settings from previous version")
        use_previous_version_settings_copy_action.setToolTip("Make a copy of the old version settings. Separate export settings will be kept for each version of the image you export.")
        use_previous_version_settings_copy_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_copy_action.setCheckable(True)
        use_previous_version_settings_copy_action.setChecked(str2qtcheckstate(readSetting("use_previous_version_settings", "replace"), "copy"))
        use_previous_version_settings_copy_action.triggered.connect(lambda checked: writeSetting("use_previous_version_settings", "copy"))
        
        use_previous_version_settings_replace_action = options_menu.addAction("Always replace settings of previous version (Recommended)")
        use_previous_version_settings_replace_action.setToolTip("Replace the old version settings. Only settings for the most recently exported version will be kept.")
        use_previous_version_settings_replace_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_replace_action.setCheckable(True)
        use_previous_version_settings_replace_action.setChecked(str2qtcheckstate(readSetting("use_previous_version_settings", "replace"), "replace"))
        use_previous_version_settings_replace_action.triggered.connect(lambda checked: writeSetting("use_previous_version_settings", "replace"))
        
        use_previous_version_settings_ignore_action = options_menu.addAction("Always ignore previous versions")
        use_previous_version_settings_ignore_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_ignore_action.setCheckable(True)
        use_previous_version_settings_ignore_action.setChecked(str2qtcheckstate(readSetting("use_previous_version_settings", "replace"), "ignore"))
        use_previous_version_settings_ignore_action.triggered.connect(lambda checked: writeSetting("use_previous_version_settings", "ignore"))
        
        use_previous_version_settings_ask_action = options_menu.addAction("Always ask")
        use_previous_version_settings_ask_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_ask_action.setCheckable(True)
        use_previous_version_settings_ask_action.setChecked(str2qtcheckstate(readSetting("use_previous_version_settings", "replace"), "ask"))
        use_previous_version_settings_ask_action.triggered.connect(lambda checked: writeSetting("use_previous_version_settings", "ask"))
        
        options_menu.addSeparator()
        
        show_thumbnails_for_unopened_images_action = options_menu.addAction("Show thumbnails for unopened images")
        show_thumbnails_for_unopened_images_action.setToolTip("Will take effect when this dialog next runs.")
        show_thumbnails_for_unopened_images_action.setCheckable(True)
        show_thumbnails_for_unopened_images_action.setChecked(str2qtcheckstate(readSetting("show_thumbnails_for_unopened", "true")))
        show_thumbnails_for_unopened_images_action.toggled.connect(lambda checked: writeSetting("show_thumbnails_for_unopened", bool2str(checked)))

        options_button.setMenu(options_menu)
        
        # status bar.
        # TODO: allow custom prompt messages on startup to be reset once eg. an image has been exported?
        self.sbar = QStatusBar()
        sbar_ready_label = QLabel(" Ready." if msg == "" else " "+msg) # extra space to align with showmessage.
        self.sbar.insertWidget(0, sbar_ready_label)
        status_layout.addWidget(self.sbar)
        
        status_layout.setContentsMargins(0,0,0,0)
        status_widget.setLayout(status_layout)
        layout.addWidget(status_widget)
        
        # TODO: inform user about having multiple copies of same file open.
        if len(self.tree.dup_counts) == 1:
            sbar_ready_label.setText(f"Note: Multiple copies of '{list(self.tree.dup_counts.keys())[0]}' are currently open in Krita.")
        elif len(self.tree.dup_counts) > 1:
            sbar_ready_label.setText(f"Note: Multiple copies of multiple files (hover mouse here to see) are currently open in Krita.")
            sbar_ready_label.setToolTip("\n".join(self.tree.dup_counts.keys()))

        # create dialog and show it
        self.setLayout(layout)
        self.setWindowTitle("Quick Export")
        dialog_width = int(readSetting("dialogWidth", "1024"))
        dialog_height = int(readSetting("dialogHeight", "640"))
        self.resize(dialog_width, dialog_height)

    def resizeEvent(self, event):
        writeSetting("dialogWidth", str(event.size().width()))
        writeSetting("dialogHeight", str(event.size().height()))
    
    def reject(self):
        self.close()
    
    def closeEvent(self, event):
        # TODO: export file name not set if user doesn't unfocus lineedit before closing.
        ret = QMessageBox.Discard
        
        if self.auto_save_on_close_button.checkState() == Qt.Checked:
            # save without asking.
            ret = QMessageBox.Save
        elif self.save_button.isEnabled():
            # ask user.
            msgBox = QMessageBox(self)
            msgBox.setText("There are unsaved changes to export settings.")
            msgBox.setInformativeText("Do you want to save your changes?")
            msgBox.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msgBox.setDefaultButton(QMessageBox.Save)
            ret = msgBox.exec()
        
        if ret == QMessageBox.Cancel:
            event.ignore()
            return
        
        self.tree.thumbnail_worker.close()
        
        if ret == QMessageBox.Save:
            save_settings_to_config()
        
        extension().update_quick_export_display()
        event.accept()

    def _on_show_unstored_button_clicked(self, checked):
        writeSetting("show_unstored", bool2str(checked))
        self.tree.refilter()

    def _on_show_unopened_button_clicked(self, checked):
        writeSetting("show_unopened", bool2str(checked))
        self.tree.refilter()

    def _on_show_non_kra_button_clicked(self, checked):
        writeSetting("show_non_kra", bool2str(checked))
        self.tree.refilter()
    
    def _on_unhovered_fade_slider_value_changed(self):
        writeSetting("unhovered_fade", str(self.unhovered_fade_slider.value()))
        root = self.tree.invisibleRootItem()
        for item in (root.child(i) for i in range(root.childCount())):
            self.tree.itemWidget(item, QECols.SETTINGS_COLUMN).setOpacity(hover=False)
        self.tree.redraw()
    
    def _on_stored_highlight_slider_value_changed(self):
        writeSetting("highlight_alpha", str(self.stored_highlight_slider.value()))
        self.tree.redraw()

    def _on_advanced_mode_button_clicked(self, checked):
        writeSetting("advanced_mode", bool2str(checked))
        self.set_advanced_mode(checked)

    def set_advanced_mode(self, enabled):
        if enabled:
            self.tree.showColumn(QECols.STORE_SETTINGS_COLUMN)
            self.show_unstored_button.show()
            self.show_unstored_button.setCheckState(str2qtcheckstate(readSetting("show_unstored", "true")))
            self.auto_store_on_modify_button.show()
            self.auto_store_on_modify_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_modify", "true")))
            self.auto_store_on_export_button.show()
            self.auto_store_on_export_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_export", "true")))
            self.auto_save_on_close_button.show()
            self.auto_save_on_close_button.setCheckState(str2qtcheckstate(readSetting("auto_save_on_close", "true")))
            self.save_button.show()
        else:
            self.tree.hideColumn(QECols.STORE_SETTINGS_COLUMN)
            self.show_unstored_button.hide()
            self.show_unstored_button.setCheckState(Qt.Checked)
            self.auto_store_on_modify_button.hide()
            self.auto_store_on_modify_button.setCheckState(Qt.Checked)
            self.auto_store_on_export_button.hide()
            self.auto_store_on_export_button.setCheckState(Qt.Checked)
            self.auto_save_on_close_button.hide()
            self.auto_save_on_close_button.setCheckState(Qt.Checked)
            self.save_button.hide()

    def _on_auto_store_on_modify_button_clicked(self, checked):
        writeSetting("auto_store_on_modify", bool2str(checked))

    def _on_auto_store_on_export_button_clicked(self, checked):
        writeSetting("auto_store_on_export", bool2str(checked))

    def _on_auto_save_on_close_button_clicked(self, checked):
        writeSetting("auto_save_on_close", bool2str(checked))

    def _on_use_custom_icons_action_toggled(self, checked):
        writeSetting("use_custom_icons", bool2str(checked))
        extension().update_action_icons()

    def _on_custom_icons_theme_action_group_triggered(self, action, group):
        writeSetting("custom_icons_theme", ["follow","light","dark"][group.actions().index(action)])
        extension().update_action_icons()
    
    def _on_show_export_name_in_menu_action_toggled(self, checked):
        writeSetting("show_export_name_in_menu", bool2str(checked))
        extension().update_quick_export_display()
    
    def _on_default_export_unsaved_action_toggled(self, checked):
        writeSetting("default_export_unsaved", bool2str(checked))
        extension().update_quick_export_display()

    def _on_save_button_clicked(self, checked):
        save_settings_to_config()
        self.save_button.setText("Save Settings")
        self.save_button.setIcon(QIcon())
        self.save_button.setDisabled(True)
        self.sbar.showMessage("Settings saved.", 2500)


# TODO: if __main__ etc. to allow running script by itself?
