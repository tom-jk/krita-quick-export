from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate, QMenu,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup,
                             QActionGroup, QToolButton, QComboBox, QStackedWidget, QStyle, QStyleOption,
                             QStyleOptionButton, QSpinBox, QStyleOptionSpinBox, QGraphicsOpacityEffect,
                             QFileDialog, QProxyStyle)
from PyQt5.QtCore import Qt, QObject, QRegExp, QModelIndex, pyqtSignal, QEvent
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor, QPainter, QPalette, QMouseEvent, QTabletEvent
import zipfile
from pathlib import Path
from functools import partial
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita
from .utils import *
from .qewidgets import QEMenu, CheckToolButton, ColourToolButton, QEComboBox, FadingStackedWidget, SpinBoxSlider, FlowLayout
from .multilineelidedbutton import MultiLineElidedText, MultiLineElidedButton
from .filenameedit import FileNameEdit

class SettingsWidget(QWidget):
    def popOut(self, settings_stack, index):
        self._settings_stack = settings_stack
        self._index = index
        self._default_flags = self.windowFlags()
        self.setParent(settings_stack)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.move(settings_stack.mapToGlobal(settings_stack.rect().bottomLeft()))
        new_size = QSize(*self.layout()._do_layout(QRect(0,0,0,0), test_only=True, auto_wrap=False, for_popup=True))
        self.setGeometry(QRect(self.pos(), new_size))
        self.show()
    
    def closeEvent(self, event):
        self._settings_stack.insertWidget(self._index, self)
        self.setWindowFlags(self._default_flags)

class MyHeaderStyle(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None):
        if metric == QStyle.PM_HeaderGripMargin:
            return 2 * super().pixelMetric(metric, option, widget)
        else:
            return super().pixelMetric(metric, option, widget)

class ItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        if index.column() in (QECols.OPEN_FILE_COLUMN, QECols.THUMBNAIL_COLUMN, QECols.SOURCE_FILENAME_COLUMN, QECols.BUTTONS_COLUMN):
            return None
        else:
            return super().createEditor(parent, option, index)
    
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        
        tree = QETree.instance
        
        if not tree:
            return size
        
        item = tree.itemFromIndex(index)
        
        if tree.indexOfTopLevelItem(item) == -1:
            return size
        
        if tree.isItemMinimized(item):
            size.setHeight(tree.minimized_row_height)
            return size
        
        if size.height() < tree.min_row_height:
            size.setHeight(tree.min_row_height)
        
        return size
    
    def paint(self, painter, option, index):
        tree = QETree.instance
        
        # TODO: lightly highlight row if mouse over.
        if tree.indexOfTopLevelItem(tree.itemFromIndex(index)) != -1:
            is_highlighted = index.model().index(index.row(), QECols.OPEN_FILE_COLUMN, QModelIndex()).data(QERoles.CustomSortRole) == tree.highlighted_doc_index
            is_stored = index.model().index(index.row(), QECols.STORE_SETTINGS_COLUMN, QModelIndex()).data(QERoles.CustomSortRole) == "1"
        else:
            is_highlighted = False
            is_stored = False
            
            header = tree.header()
            visual_index_for_span_start_col = header.visualIndex(QECols.SOURCE_FILEPATH_COLUMN)
            visual_index_for_this_col = header.visualIndex(index.column())
            if visual_index_for_this_col >= visual_index_for_span_start_col:
                left_margin = 5
                item = tree.itemFromIndex(index)
                text = item.data(QECols.SOURCE_FILEPATH_COLUMN, QERoles.CustomSortRole)
                vRect = option.rect.translated(0,0) # (makes copy)
                x = vRect.left()
                for visual_index in range(visual_index_for_span_start_col, visual_index_for_this_col):
                    x -= header.sectionSize(header.logicalIndex(visual_index))
                vRect.setLeft(x + left_margin)
                painter.save()
                painter.setClipping(True)
                painter.setClipRect(option.rect)
                painter.drawText(vRect, Qt.AlignLeft, text)
                painter.restore()
            else:
                super().paint(painter, option, index)
            return
            
        super().paint(painter, option, index)
        if is_highlighted:
            painter.fillRect(option.rect, QColor(192,255,96,48))
        if is_stored:
            painter.fillRect(option.rect, QColor(64,128,255,tree.stored_highlight_alpha))

class MyTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, doc_settings=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # document export settings associated with this item.
        self.doc_settings = doc_settings
        
        # some controls associated with this item that are used in many places.
        self.thumbnail_normal = QPixmap()
        self.thumbnail_minimized = QPixmap()
        self.thumbnail_label = None
        self.store_forget_button = None
        self.export_button = None
        self.warning_label = None
        self.settings_stack = None
        self.source_filepath_widget = None
        self.source_filename_widget = None
        self.versions_show_button = None
        self.output_filepath_button = None
        self.output_filename_edit = None
        self.output_filetype_combobox = None
    
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
        
        pos = tree.viewport().mapFromGlobal(event.globalPos())
        item = tree.itemAt(pos)
        
        display_mode = readSetting("settings_display_mode")
        minimize_unfocused = str2bool(readSetting("minimize_unfocused"))
        
        if display_mode == "minimized" or (display_mode == "focused" and minimize_unfocused):
            tree.hovered_item = item
            return False
        
        #print("mouse/tablet event")
        #print(f"{pos=}: {item.text(QECols.SOURCE_FILENAME_COLUMN) if item else 'no item'}")
        if item != tree.hovered_item:
            if tree.hovered_item and (widget := tree.itemWidget(tree.hovered_item, QECols.SETTINGS_COLUMN)):
                widget.setOpacity(hover=False)
            tree.hovered_item = item
            if tree.hovered_item and (widget := tree.itemWidget(tree.hovered_item, QECols.SETTINGS_COLUMN)):
                widget.setOpacity(hover=True)
        return False

class QECols(IntEnum):
    STORE_SETTINGS_COLUMN = 0
    OPEN_FILE_COLUMN = auto()
    THUMBNAIL_COLUMN = auto()
    SOURCE_FILEPATH_COLUMN = auto()
    SOURCE_FILENAME_COLUMN = auto()
    SOURCE_VERSIONS_COLUMN = auto()
    OUTPUT_FILEPATH_COLUMN = auto()
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
        display_mode = readSetting("settings_display_mode")
        minimize_unfocused = str2bool(readSetting("minimize_unfocused"))
        
        if display_mode == "minimized" or (display_mode == "focused" and minimize_unfocused):
            self.hovered_item = None
            return
        
        if self.hovered_item and (widget := self.itemWidget(self.hovered_item, QECols.SETTINGS_COLUMN)):
            widget.setOpacity(hover=False)
        self.hovered_item = None
    
    def refilter(self):
        show_unstored = str2bool(readSetting("show_unstored"))
        show_unopened = str2bool(readSetting("show_unopened"))
        show_non_kra  = str2bool(readSetting("show_non_kra"))
        for index, s in enumerate(qe_settings):
            self.items[index].setHidden(
                   (not show_unstored and s["store"] == False)
                or (not show_unopened and s["document"] == None)
                or (not show_non_kra  and s["path"].suffix != ".kra")
            )
    
    def _on_btn_open_clicked(self, checked, btn, disabled_buttons, item):
        doc = item.doc_settings
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
        item.export_button.setGraphicsEffect(None)
        new_doc.waitForDone()
        self.thumbnail_queue.append([new_doc, item])
        self.thumbnail_worker_timer.start()
        print("done")
    
    def _on_versions_menu_triggered(self, value, button, item):
        doc = item.doc_settings
        self._on_generic_setting_changed("versions", value, item)
        button.set_icon_name(("versions", value))
        button.setChecked(value != "single")
        item.setData(QECols.SOURCE_VERSIONS_COLUMN, QERoles.CustomSortRole, doc["versions"])
        self.add_file_versioning_subitems_for_all_items(doc["base_version_string"])
        self.update_names_and_labels(item)
    
    def _on_versions_show_button_clicked(self, checked, item):
        button = item.versions_show_button
        checked = not item.isExpanded()
        item.setExpanded(checked)
        button.setIcon(app.icon("arrowup") if checked else app.icon("arrowdown"))
    
    def _on_output_name_edit_editing_finished(self, item):
        edit = item.output_filename_edit
        doc = item.doc_settings
        doc["output_name"] = edit.text()
        self.update_names_and_labels(item)
        item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, doc["output_name"].lower())
        #print("_on_output_lineedit_changed ->", doc["output"])
        self.set_settings_modified(item.store_forget_button)
    
    def update_names_and_labels(self, item):
        doc = item.doc_settings
        export_path = export_file_path(doc)
        item.export_button.setToolTip(f"Export now\n{str(export_path)}")
        if self.dialog.tree_is_ready:
            self.update_warning_label(item)
    
    def update_warning_label(self, item):
        doc = item.doc_settings
        warning_text = []
        if any(doc["output_name"].endswith((match:=ext)) for ext in supported_extensions()):
            warning_text.append(f"Exporting with name ending '{match}{doc['ext']}'")
        if doc["path"].parent == doc["output_abs_dir"]:
            test_name = export_file_path(doc).name
            if any(test_name == (match:=item.child(subitem_index).data(QECols.SOURCE_FILEPATH_COLUMN, QERoles.CustomSortRole)) for subitem_index in range(item.childCount())):
                warning_text.append(f"Source file '{match}' will be overwritten!")
        if len(warning_text) > 0:
            item.warning_label.setText("/n".join(warning_text))
            if not item.warning_label.isVisible():
                item.warning_label.show()
                self.scheduleDelayedItemsLayout()
        else:
            if item.warning_label.isVisible():
                item.warning_label.hide()
                self.scheduleDelayedItemsLayout()
    
    def _on_item_btn_export_clicked(self, item):
        doc = item.doc_settings
        print(f"Clicked export for {doc['path']}")
        
        result = export_image(doc)
        
        if not result:
            failed_msg = export_failed_msg()
            self.sender().setIcon(app.icon('window-close'))
            self.dialog.sbar.showMessage(f"Export failed. {failed_msg}")
        else:
            self.sender().setIcon(app.icon('dialog-ok'))
            self.dialog.sbar.showMessage(f"Exported to '{export_file_path(doc)}'")
        
        if self.dialog.auto_store_on_export_button.checkState() == Qt.Checked:
            item.store_forget_button.setCheckState(Qt.Checked)
    
    def _on_settings_stack_popout_button_clicked(self, item):
        doc_settings = item.doc_settings
        settings_stack = item.settings_stack
        index = self.settings_stack_page_index_for_extension(doc_settings["ext"])
        page = settings_stack.widget(index)
        page.popOut(settings_stack, index)
    
    def _on_item_scale_checkbox_action_triggered(self, checked, checkboxes, item):
        doc = item.doc_settings
        doc["scale"] = checked
        for checkbox in checkboxes:
            checkbox.setChecked(checked)
        self.set_settings_modified(item.store_forget_button)
    
    def _on_item_scale_reset_action_triggered(self, checked, item):
        doc = item.doc_settings
        doc["scale_width"]  = -1
        doc["scale_height"] = -1
        doc["scale_filter"] = "Auto"
        doc["scale_res"]    = -1
        self.set_settings_modified(item.store_forget_button)
    
    def _on_item_scale_settings_action_triggered(self, checked, item):
        doc = item.doc_settings
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
        
        self.set_settings_modified(item.store_forget_button)
    
    def _on_item_btn_store_forget_clicked(self, checked, item):
        btn = item.store_forget_button
        doc = item.doc_settings
        #print("store/forget changed ->", checked, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["store"] = not doc["store"]
        item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+doc["store"]))
        self.redraw()
        self.set_settings_modified()
        self.add_file_versioning_subitems_for_all_items(doc["base_version_string"])
    
    def add_file_versioning_subitems_for_all_items(self, bvs=None):
        for item_ in self.items:
            if not bvs or item_.doc_settings["base_version_string"] == bvs:
                self.add_file_versioning_subitems(item_)
    
    def _on_output_path_menu_triggered(self, value, item):
        name_edit = item.output_filename_edit
        path_button = item.output_filepath_button
        ext_combobox = item.output_filetype_combobox
        doc = item.doc_settings
        if value in (True, False):
            print("Selected absolute/relative:", value)
            doc["output_is_abs"] = value
            
        elif value == "change":
            print("Selected Change...")
            
            file_path = export_file_path(doc)
            
            file_path_string = QFileDialog.getSaveFileName(
                parent = self,
                caption = "Choose Export Location and Name",
                directory = str(file_path),
                filter = f"Images ({' '.join(['*'+ext for ext in supported_extensions()])});;" + ";;".join([ext[1:]+' (*'+ext+')' for ext in supported_extensions()])
            )[0]
            
            if file_path_string == "":
                return
            
            ext = Path(file_path_string).suffix
            file_path = Path(file_path_string).with_suffix("")
            
            if not (file_path.parent.exists() and file_path.parent.is_dir()):
                QMessageBox.warning(self, "Invalid file path", f"The directory {file_path.parent} does not exist.")
                return
            
            if any(char in windows_forbidden_filename_chars for char in file_path.name):
                QMessageBox.warning(self, "Invalid file name", f"File names containing the characters {windows_forbidden_filename_chars} are not allowed.")
                return
            
            doc["output_abs_dir"] = file_path.parent
            doc["output_name"] = file_path.name
            path_button.setText(str(file_path.parent) if file_path.parent != doc["path"].parent else ".")
            name_edit.setText(file_path.name)
            
            if ext and ext in supported_extensions():
                ext_combobox.setCurrentIndex(ext_combobox.findData(ext))
            
            self.update_names_and_labels(item)
        self.set_settings_modified(item.store_forget_button)
    
    def _on_outputext_combobox_current_index_changed(self, index, item):
        doc = item.doc_settings
        combobox = item.output_filetype_combobox
        ext = combobox.itemText(index)
        doc["ext"] = ext
        item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, doc["ext"])
        self.set_item_settings_stack_page_for_extension(item, ext)
        self.set_settings_modified(item.store_forget_button)
        self.update_names_and_labels(item)
    
    def set_item_settings_stack_page_for_extension(self, item, ext):
        settings_stack = item.settings_stack
        index = self.settings_stack_page_index_for_extension(ext)
        is_minimized = self.isItemMinimized(item)
        settings_stack.widget(index).setVisible(not is_minimized)
        settings_stack.setCurrentIndex(0 if readSetting("settings_display_mode") == "minimized" else index)
        self._on_column_resized(QECols.SETTINGS_COLUMN, QECols.SETTINGS_COLUMN, -1)
    
    def settings_stack_page_index_for_extension(self, ext):
        try:
            return self.settings_stack_page_order.index(ext)
        except ValueError:
            for i,v in enumerate(self.settings_stack_page_order):
                if ext in v:
                    return i
            print(f"couldn't find settings stack page index for extension '{ext}'.")
    
    def _on_png_alpha_checkbox_toggled(self, checked, item):
        doc = item.doc_settings
        #print("alpha checkbox changed ->", state, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["png_alpha"] = checked
        #item.setData(QECols.PNG_STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+doc["png_alpha"]))
        self.set_settings_modified(item.store_forget_button)
    
    def _on_jpeg_subsampling_menu_triggered(self, value, button, item):
        self._on_generic_setting_changed("jpeg_subsampling", value, item)
        button.set_icon_name(("subsampling", value))
    
    def _on_jpeg_metadata_checkbox_toggled(self, checked, metadata_options_button, item):
        self._on_generic_setting_changed("jpeg_metadata", checked, item)
        metadata_options_button.setChecked(checked)
    
    def _on_generic_setting_changed(self, key, value, item):
        doc = item.doc_settings
        doc[key] = value
        self.set_settings_modified(item.store_forget_button)
    
    def set_settings_modified(self, store_button=None):
        if not self.dialog.tree_is_ready:
            return
        
        if generate_save_string() != readSetting("settings"):
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
    
    def set_stored_highlight_alpha(self, value):
        self.stored_highlight_alpha = value
    
    def redraw(self):
        for child in self.children():
            if hasattr(child, "update"):
                child.update()
    
    def isItemMinimized(self, item):
        mode = readSetting("settings_display_mode")
        minimize_unfocused = str2bool(readSetting("minimize_unfocused"))
        return mode == "minimized" or (mode == "focused" and self.focused_item != item and minimize_unfocused)
    
    def set_settings_display_mode(self, mode=None):
        mode = readSetting("settings_display_mode") if not mode else mode
        minimize_unfocused = str2bool(readSetting("minimize_unfocused"))
        
        for item in self.items:
            is_compact = mode == "compact" or (mode == "focused" and self.focused_item != item)
            is_minimized = self.isItemMinimized(item)
            is_expanded = item.isExpanded() and (mode != "focused" or (mode == "focused" and self.focused_item == item))
            
            settings_stack = item.settings_stack
            
            item.thumbnail_label.setPixmap(item.thumbnail_minimized if is_minimized else item.thumbnail_normal)
            item.source_filepath_widget.setMaxLines(2 if is_minimized else 4)
            item.source_filename_widget.setMaxLines(2 if is_minimized else 4)
            item.output_filepath_button.text_widget.setMaxLines(2 if is_minimized else 4)
            
            item.versions_show_button.setVisible(not is_minimized)
            item.versions_show_button.setIcon(app.icon("arrowup") if is_expanded else app.icon("arrowdown"))
            item.setExpanded(is_expanded)
            
            textoption = item.output_filename_edit.edit.document().defaultTextOption()
            textoption.setWrapMode(QTextOption.NoWrap if is_minimized else QTextOption.WrapAnywhere)
            item.output_filename_edit.edit.document().setDefaultTextOption(textoption)
            item.output_filename_edit.edit.updateGeometry()
            
            settings_stack.setCurrentIndex(0 if mode=="minimized" else self.settings_stack_page_index_for_extension(item.doc_settings["ext"]))
            settings_stack.setOpacity(hover=mode=="minimized" or (mode=="focused" and minimize_unfocused))
            for page_index in range(1, settings_stack.count()):
                page = settings_stack.widget(page_index)
                page.setVisible(page == settings_stack.currentWidget() and not is_minimized)
                page.layout().setIgnoreBreaks(is_compact)
                for widget in page.children():
                    if isinstance(widget, QLabel):
                        widget.setVisible(not is_compact)
                page.updateGeometry()
        
        self.header().resizeSection(QECols.THUMBNAIL_COLUMN, self.minimized_thumb_height if mode=="minimized" else self.thumb_height)
        self.updateGeometries()
        self.scheduleDelayedItemsLayout()
    
    def __init__(self, dialog, parent=None):
        super().__init__(parent)
        self.__class__.instance = self
        self.dialog = dialog
        
        self.setIndentation(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setAlternatingRowColors(True)
        self.updateAlternatingRowContrast()
        
        from PyQt5.QtCore import QItemSelectionModel
        self.setSelectionMode(QTreeWidget.NoSelection)
        
        self.setMouseTracking(True)
        self.filter = QETreeFilter()
        self.installEventFilter(self.filter)
        
        self.hovered_item = None
        
        self.highlighted_doc_index = -1
        self.focused_item = None
        
        self.stored_highlight_alpha = round(int(readSetting("highlight_alpha"))*0.64)
        
        fm = QFontMetrics(self.font())
        self.thumb_height = fm.height() * 4
        self.min_row_height = fm.height() * 5
        self.minimized_thumb_height = fm.height() * 1
        self.minimized_row_height = fm.height() * 2
        
        self.setExpandsOnDoubleClick(False)
        
        self.wide_header_style = MyHeaderStyle()
        if str2bool(readSetting("wide_column_resize_grabber")):
            self.header().setStyle(self.wide_header_style)
        
        self.header().setStretchLastSection(False)
        self.header().sectionResized.connect(self._on_column_resized)
    
    def _on_column_resized(self, column, old_size, new_size):
        #print("columnResized")
        if column not in (QECols.SOURCE_FILEPATH_COLUMN, QECols.SOURCE_FILENAME_COLUMN, QECols.OUTPUT_FILEPATH_COLUMN, QECols.OUTPUT_FILENAME_COLUMN, QECols.SETTINGS_COLUMN):
            return
        
        self.updateGeometries()
        QTimer.singleShot(0, self.scheduleDelayedItemsLayout)
    
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
    
    def _on_item_double_clicked(self, item, column):
        self.focused_item = item
        self.set_settings_display_mode()
    
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
        
        if self.dialog.highlighted_doc:
            for s in qe_settings:
                if s["document"] == self.dialog.highlighted_doc:
                    self.highlighted_doc_index = str(s["doc_index"])
                    break
        
        self.setColumnCount(QECols.COLUMN_COUNT)
        self.setHeaderLabels(["", "", "", "File Path", "File Name", "Ver.", "Export Path", "Export Name", "Type", "Settings", ""])
        self.headerItem().setIcon(QECols.STORE_SETTINGS_COLUMN, app.icon('document-save'))
        
        fm = QFontMetrics(self.font())
        min_col_size = fm.horizontalAdvance("x"*4)
        self.header().setMinimumSectionSize(min_col_size)
        
        if False:
            self.header().setStretchLastSection(False)
            for col in (QECols.SOURCE_FILEPATH_COLUMN, QECols.SOURCE_FILENAME_COLUMN, QECols.OUTPUT_FILEPATH_COLUMN, QECols.OUTPUT_FILENAME_COLUMN):
                self.header().setSectionResizeMode(col, QHeaderView.Stretch)
        
        self.items = []
        self.extension_comboboxes = []
        
        self.thumbnail_queue = []
        
        self.settings_stack_page_order = ["minimized", [".gif", ".pbm", ".pgm", ".ppm", ".tga", ".bmp", ".ico", ".xbm", ".xpm"], ".png", [".jpg",".jpeg"]]
        
        item_delegate = ItemDelegate()
        self.setItemDelegate(item_delegate)
        
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # TODO: should probably have an option to force removal of extensions from output name.
        #       an *option* because user could wish to export myfile.kra as myfile.kra.png, so output
        #       text would be myfile.kra. could instead only automatically remove an extension matching
        #       export type, but what if user wants to export myfile.png as myfile.png.png? each time they
        #       edited the output name, would they have to offer the extra .png as a sacrifice to protect
        #       the inner .png?
        #       ...I guess it could just check if output text starts with exact source filename
        #       and always leave that bit alone. Probably do that.
        #filename_regex = QRegExp("^[^<>:;,?\"*|/]+$")
        
        for s in qe_settings:
            self.add_item(s)
        
        for item in self.items:
            if item.doc_settings["document"] == self.dialog.highlighted_doc:
                self.focused_item = item
                break
        
        self.refilter()
        
        if not self.restore_columns():
            for i in range(0, QECols.COLUMN_COUNT):
                self.resizeColumnToContents(i)
        
        for item in self.items:
            self.update_names_and_labels(item)
        
        QTimer.singleShot(0, self.scheduleDelayedItemsLayout)

        if len(self.thumbnail_queue) == 0:
            return
        
        self.thumbnail_worker = self.thumbnail_worker_process()
        self.thumbnail_worker_timer = QTimer(self)
        self.thumbnail_worker_timer.setInterval(0)
        self.thumbnail_worker_timer.setSingleShot(True)
        self.thumbnail_worker_timer.timeout.connect(lambda: next(self.thumbnail_worker, None))
        self.thumbnail_worker_timer.start()
    
    def restore_columns(self):
        state_str = readSetting("columns_state")
        if state_str == "":
            return False
        state = QByteArray.fromBase64(bytearray(state_str, "utf-8"))
        return self.header().restoreState(state)
    
    def add_item(self, s):
        def centered_checkbox_widget(checkbox):
            widget = QWidget()
            layout = QHBoxLayout()
            layout.addStretch()
            layout.addWidget(checkbox)
            layout.addStretch()
            layout.setContentsMargins(0,0,0,0)
            widget.setLayout(layout)
            return widget
        
        def setting_label_and_layout_break(page_layout, text):
            widget = QLabel(text)
            page_layout.addWidget(widget)
            page_layout.addBreak()
            return widget
        
        # TODO: adapt to theme light/dark.
        checkbox_stylesheet = "QCheckBox::indicator:unchecked {border: 1px solid rgba(255,255,255,0.1);}" if extension().theme_is_dark else ""
        
        file_path = s["path"]
        
        item = MyTreeWidgetItem(s, self)
        item.setHidden(True)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        
        item.export_button = QToolButton()
        item.export_button.setAutoRaise(True)
        item.export_button.setIcon(app.icon('document-export'))
        item.export_button.setToolTip("Export now")
        
        if s["document"] == None:
            item.export_button.setDisabled(True)
            item.export_button_opacity = QGraphicsOpacityEffect(item.export_button)
            item.export_button_opacity.setOpacity(0.33)
            item.export_button.setGraphicsEffect(item.export_button_opacity)
        
        item.store_forget_button = QCheckBox()
        item.store_forget_button.setChecked(s["store"])
        item.store_forget_button.setStyleSheet(checkbox_stylesheet)
        item.store_forget_button.toggled.connect(lambda checked, i=item: self._on_item_btn_store_forget_clicked(checked, i))
        btn_store_widget = centered_checkbox_widget(item.store_forget_button)
        self.setItemWidget(item, QECols.STORE_SETTINGS_COLUMN, btn_store_widget)
        item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+s["store"]))
        
        scale_menu = QEMenu(keep_open=False)
        scale_checkbox_action = scale_menu.addAction("Enabled")
        scale_checkbox_action.setCheckable(True)
        scale_checkbox_action.setChecked(s["scale"])
        scale_reset_action = scale_menu.addAction("Reset to current size and resolution")
        scale_reset_action.setDisabled(s["document"] == None)
        scale_reset_action.triggered.connect(lambda checked, i=item: self._on_item_scale_reset_action_triggered(checked, i))
        scale_settings_action = scale_menu.addAction("Settings...")
        scale_settings_action.setDisabled(s["document"] == None)
        scale_settings_action.triggered.connect(lambda checked, i=item: self._on_item_scale_settings_action_triggered(checked, i))
        
        if (btn_group_key := str(s["path"])) in self.store_button_groups:
            self.store_button_groups[btn_group_key].addButton(item.store_forget_button)
            if s["store"] and self.store_button_groups[btn_group_key].btnLastChecked == None:
                self.store_button_groups[btn_group_key].btnLastChecked = item.store_forget_button
        
        if s["document"] != None:
            self.thumbnail_queue.append([s["document"], item])
            if s["document"] == app.activeDocument():
                item.setText(QECols.OPEN_FILE_COLUMN, "*")
                item.setTextAlignment(QECols.OPEN_FILE_COLUMN, Qt.AlignCenter)
        else:
            if str2bool(readSetting("show_thumbnails_for_unopened")):
                self.thumbnail_queue.append([s["path"], item])
            item.setDisabled(True)
            btn_open = QPushButton("")
            btn_open.setIcon(app.icon('document-open'))
            btn_open.setStyleSheet("QPushButton {border:none; background:transparent;}")
            self.setItemWidget(item, QECols.OPEN_FILE_COLUMN, btn_open)
        
        item.setData(QECols.OPEN_FILE_COLUMN, QERoles.CustomSortRole, str(s["doc_index"]))
        
        item.thumbnail_label = QLabel()
        item.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.setItemWidget(item, QECols.THUMBNAIL_COLUMN, item.thumbnail_label)
        
        file_path_parent = str(file_path.parent)
        if False and file_path_parent.startswith(str(Path.home())):
            file_path_parent = file_path_parent.replace(str(Path.home()), "/home")
        
        item.source_filepath_widget = MultiLineElidedText(file_path_parent, margin=5)
        item.source_filepath_widget.setDisabled(s["document"] == None)
        
        self.setItemWidget(item, QECols.SOURCE_FILEPATH_COLUMN, item.source_filepath_widget)
        item.setData(QECols.SOURCE_FILEPATH_COLUMN, QERoles.CustomSortRole, file_path_parent.lower())
        
        item.source_filename_widget = MultiLineElidedText(file_path.name, margin=5)
        item.source_filename_widget.setDisabled(s["document"] == None)
        
        self.setItemWidget(item, QECols.SOURCE_FILENAME_COLUMN, item.source_filename_widget)
        item.setData(QECols.SOURCE_FILENAME_COLUMN, QERoles.CustomSortRole, file_path.name.lower())
        
        if s["document"] == None:
            btn_open.clicked.connect(lambda checked, b=btn_open, db=[item.export_button,scale_reset_action,scale_settings_action,item.source_filepath_widget,item.source_filename_widget], i=item: self._on_btn_open_clicked(checked, b, db, i))
        
        item.warning_label = QLabel("")
        
        versions_widget = QWidget()
        versions_widget_layout = QVBoxLayout(versions_widget)
        versions_widget_layout.setSpacing(2)
        
        versions_button = CheckToolButton(icon_name=("versions", s["versions"]), checked=(s["versions"] != "single"), tooltip="how to use settings for different versions of this image")
        versions_button.setPopupMode(QToolButton.InstantPopup)
        
        bvs, mvn = base_stem_and_version_number_for_versioned_file(file_path, unversioned_version_num=0)
        stm, suf = file_path.stem, file_path.suffix
        
        # cache bvs and mvn.
        s["base_version_string"] = bvs
        s["matched_version_number"] = mvn
        
        versions_menu = QEMenu(keep_open=False)
        versions_menu.setToolTipsVisible(True)
        versions_action_group = QActionGroup(versions_menu)
        versions_single_action      = versions_menu.addAction("This exact file", "single", f"applies only to '{file_path.name}'.")
        versions_all_action         = versions_menu.addAction("Versions of this image", "all", f"applies to:\n'{file_path.name}'\n'{stm}_001{suf}'\n'{stm}_002{suf}'\n'{stm}_003{suf}'\netc.")
        versions_all_forward_action = versions_menu.addAction("This and later versions of this image", "all_forward", f"applies to:\n'{file_path.name}'\n'{bvs}_{mvn+1:03}{suf}'\n'{bvs}_{mvn+2:03}{suf}'\n'{bvs}_{mvn+3:03}{suf}'\netc.")
        for i, action in enumerate(versions_menu.actions()):
            action.setCheckable(True)
            action.setActionGroup(versions_action_group)
            action.setChecked(action.data() == s["versions"])
        versions_menu.triggered.connect(lambda a, b=versions_button, d=s, i=item: self._on_versions_menu_triggered(a.data(), b, i))
        
        versions_button.setMenu(versions_menu)
        
        item.versions_show_button = QToolButton()
        item.versions_show_button.setIcon(app.icon("arrowdown"))
        item.versions_show_button.setFixedSize(item.versions_show_button.sizeHint())
        item.versions_show_button.setIconSize(item.versions_show_button.iconSize()/2)
        item.versions_show_button.setAutoRaise(True)
        item.versions_show_button.clicked.connect(lambda checked, i=item: self._on_versions_show_button_clicked(checked, i))
        
        versions_widget_layout.addStretch()
        versions_widget_layout.addWidget(versions_button)
        versions_widget_layout.addWidget(item.versions_show_button)
        versions_widget_layout.addStretch()
        self.setItemWidget(item, QECols.SOURCE_VERSIONS_COLUMN, versions_widget)
        item.setData(QECols.SOURCE_VERSIONS_COLUMN, QERoles.CustomSortRole, s["versions"])
        
        item.output_filepath_button = MultiLineElidedButton(str(s["output_abs_dir"]) if s["output_abs_dir"] != s["path"].parent else ".", margin=0)
        
        item.output_filename_edit = FileNameEdit(s["output_name"])
        item.output_filename_edit.edit.settings = s
        
        item.output_filetype_combobox = QEComboBox()
        self.extension_comboboxes.append(item.output_filetype_combobox)
        
        item.output_filepath_button.setStyleSheet("QToolButton::menu-indicator {image: none;}")
        item.output_filepath_button.setPopupMode(QToolButton.InstantPopup)
        
        output_path_menu = QEMenu(keep_open=False)
        output_path_menu.setToolTipsVisible(True)
        output_path_action_group = QActionGroup(output_path_menu)
        output_path_absolute_action = output_path_menu.addAction("Absolute", True)
        output_path_relative_action = output_path_menu.addAction("Relative", False)
        for i, action in enumerate(output_path_menu.actions()):
            action.setCheckable(True)
            action.setActionGroup(output_path_action_group)
            action.setChecked(action.data() == s["output_is_abs"])
        output_path_menu.addSeparator()
        output_path_change_action = output_path_menu.addAction("Change...", "change", ("Choose the export location, and optionally change the file name and type.\n"
                                                                                       "Note that this does not actually export the file, only changes where it will export to.\n"
                                                                                       "If the file already exists, you will be asked if you want to export over it."))
        output_path_menu.triggered.connect(lambda a, i=item: self._on_output_path_menu_triggered(a.data(), i))
        
        item.output_filepath_button.setMenu(output_path_menu)
        
        self.setItemWidget(item, QECols.OUTPUT_FILEPATH_COLUMN, item.output_filepath_button)
        item.setData(QECols.OUTPUT_FILEPATH_COLUMN, QERoles.CustomSortRole, file_path_parent.lower())
        
        item.output_filename_edit.edit.document().contentsChanged.connect(item.output_filename_edit.edit.recalc_height)
        item.output_filename_edit.edit.document().contentsChanged.connect(self.scheduleDelayedItemsLayout)
        
        output_name_container_widget = QWidget()
        output_name_container_widget_layout = QVBoxLayout(output_name_container_widget)
        output_name_container_widget_layout.setSpacing(2)
        
        output_name_container_widget_layout.addWidget(item.output_filename_edit)
        
        item.warning_label.hide()
        item.warning_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item.warning_label_opacity = QGraphicsOpacityEffect(item.warning_label)
        item.warning_label_opacity.setOpacity(0.67)
        item.warning_label.setGraphicsEffect(item.warning_label_opacity)
        item.warning_label_font = QFont(item.warning_label.font())
        item.warning_label_font.setPointSize(round(item.warning_label_font.pointSize()/1.5))
        item.warning_label.setFont(item.warning_label_font)
        output_name_container_widget_layout.addWidget(item.warning_label)
        
        item.output_filename_edit.edit.editingFinished.connect(lambda i=item: self._on_output_name_edit_editing_finished(i))
        
        self.setItemWidget(item, QECols.OUTPUT_FILENAME_COLUMN, output_name_container_widget)
        item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, s["output_name"].lower())
        
        outputext_widget = QWidget()
        outputext_layout = QHBoxLayout()
        
        for e in supported_extensions():
            item.output_filetype_combobox.addItem(e, e)
        
        item.output_filetype_combobox.setCurrentIndex(item.output_filetype_combobox.findData(s["ext"]))
        
        outputext_layout.addWidget(item.output_filetype_combobox)
        outputext_widget.setLayout(outputext_layout)
        
        self.setItemWidget(item, QECols.OUTPUT_FILETYPE_COLUMN, outputext_widget)
        item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, s["ext"])
        
        item.settings_stack = FadingStackedWidget()
        
        popout_button_page = QWidget()
        popout_button_page_layout = QHBoxLayout()
        
        popout_button = CheckToolButton(icon_name="settings", checked=True)
        popout_button.setCheckable(False)
        popout_button.clicked.connect(lambda checked, i=item: self._on_settings_stack_popout_button_clicked(i))
        
        popout_button_page_layout.addWidget(popout_button)
        
        popout_button_page.setLayout(popout_button_page_layout)
        item.settings_stack.addWidget(popout_button_page)
        
        no_settings_page = SettingsWidget()
        no_settings_page_layout = FlowLayout()
        
        no_settings_label = setting_label_and_layout_break(no_settings_page_layout, "(No settings for image type.)")
        
        tooltip = "scale image before export"
        no_settings_scale_button = CheckToolButton(icon_name="scale", checked=s["scale"], tooltip=tooltip)
        no_settings_scale_button.setPopupMode(QToolButton.InstantPopup)
        
        no_settings_scale_button.setMenu(scale_menu)
        no_settings_page_layout.addWidget(no_settings_scale_button)
        
        no_settings_scale_label = setting_label_and_layout_break(no_settings_page_layout, tooltip.partition("\n")[0])
        
        no_settings_page.setLayout(no_settings_page_layout)
        item.settings_stack.addWidget(no_settings_page)
        
        png_settings_page = SettingsWidget()
        png_settings_page_layout = FlowLayout()
        
        tooltip = "Compression\n\n" \
                  "Adjust the compression time. Better compression takes longer.\n" \
                  "Note: the compression level does not change the quality of the result."
        png_compression_slider = SpinBoxSlider(label_text="Compression", range_min=1, range_max=9, snap_interval=1, tooltip=tooltip)
        png_compression_slider.setValue(s["png_compression"])
        png_compression_slider.valueChanged.connect(lambda value, i=item: self._on_generic_setting_changed("png_compression", value, i))
        png_settings_page_layout.addWidget(png_compression_slider)
        
        png_settings_page_layout.addBreak()
        
        tooltip = "Store alpha channel (transparency)\n\n" \
                  "Disable to get smaller files if your image has no transparency.\n\n" \
                  "The PNG file format allows transparency in your image to be stored by saving an alpha channel.\n" \
                  "You can uncheck the box if you are not using transparency and you want to make the resulting file smaller."
        png_alpha_checkbox = CheckToolButton(icon_name="alpha", checked=s["png_alpha"], tooltip=tooltip)
        png_alpha_checkbox.toggled.connect(lambda checked, i=item: self._on_png_alpha_checkbox_toggled(checked, i))
        png_settings_page_layout.addWidget(png_alpha_checkbox)
        
        png_alpha_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Transparent color\n\n" \
                  "Background color to replace transparent pixels with."
        png_fillcolour_button = ColourToolButton(colour=s["png_fillcolour"], tooltip=tooltip)
        png_fillcolour_button.setDisabled(png_alpha_checkbox.isChecked())
        png_alpha_checkbox.toggled.connect(lambda checked, fcb=png_fillcolour_button: fcb.setDisabled(checked))
        png_fillcolour_button.colourChanged.connect(lambda colour, i=item: self._on_generic_setting_changed("png_fillcolour", colour, i))
        png_settings_page_layout.addWidget(png_fillcolour_button)
        
        png_fillcolour_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Save as indexed PNG, if possible\n\n" \
                  "Indexed PNG images are smaller.\n" \
                  "If you enabled this option, your image will be analyzed to see whether it is possible to save as an indexed PNG."
        png_indexed_checkbox = CheckToolButton(icon_name="indexed", checked=s["png_indexed"], tooltip=tooltip)
        png_indexed_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_indexed", checked, i))
        png_settings_page_layout.addWidget(png_indexed_checkbox)
        
        png_index_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Interlacing\n\n" \
                  "Use interlacing when publishing on the Internet.\n\n" \
                  "Interlacing is useful if you intend to publish your image on the Internet.\n" \
                  "Enabling interlacing will cause the image to be displayed by the browser even while downloading."
        png_interlaced_checkbox = CheckToolButton(icon_name="progressive", checked=s["png_interlaced"], tooltip=tooltip)
        png_interlaced_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_interlaced", checked, i))
        png_settings_page_layout.addWidget(png_interlaced_checkbox)
        
        png_interlaced_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Save as HDR image (Rec. 2020 PQ)"
        png_hdr_checkbox = CheckToolButton(icon_name="hdr", checked=s["png_hdr"], tooltip=tooltip)
        png_hdr_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_hdr", checked, i))
        png_settings_page_layout.addWidget(png_hdr_checkbox)
        
        png_hdr_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Embed sRGB profile\n\n" \
                  "PNG files have two options to save sRGB information: as a tag or as an explicit profile.\n" \
                  "For use within websites, disable this option.\n" \
                  "For interchange with other applications, enable this option."
        png_embed_srgb_checkbox = CheckToolButton(icon_name="embed_profile", checked=s["png_embed_srgb"], tooltip=tooltip)
        png_embed_srgb_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_embed_srgb", checked, i))
        png_settings_page_layout.addWidget(png_embed_srgb_checkbox)
        
        png_embed_srgb_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Force convert to sRGB"
        png_force_srgb_checkbox = CheckToolButton(icon_name="force_profile", checked=s["png_force_srgb"], tooltip=tooltip)
        png_force_srgb_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_force_srgb", checked, i))
        png_settings_page_layout.addWidget(png_force_srgb_checkbox)
        
        png_force_srgb_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Force convert to 8bits/channel"
        png_force_8bit_checkbox = CheckToolButton(icon_name="force_8bit", checked=s["png_force_8bit"], tooltip=tooltip)
        png_force_8bit_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_force_8bit", checked, i))
        png_settings_page_layout.addWidget(png_force_8bit_checkbox)
        
        png_force_8bit_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Store Metadata\n\n" \
                  "Store information like keywords, title and subject and license, if possible."
        png_metadata_checkbox = CheckToolButton(icon_name="metadata", checked=s["png_metadata"], tooltip=tooltip)
        png_metadata_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_metadata", checked, i))
        png_settings_page_layout.addWidget(png_metadata_checkbox)
        
        png_metadata_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Sign with author data\n\n" \
                  "Save author nickname and first contact information of the author profile into the png, if possible."
        png_author_checkbox = CheckToolButton(icon_name="author", checked=s["png_author"], tooltip=tooltip)
        png_author_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("png_author", checked, i))
        png_settings_page_layout.addWidget(png_author_checkbox)
        
        png_author_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Scale image before export"
        png_scale_button = CheckToolButton(icon_name="scale", checked=s["scale"], tooltip=tooltip)
        png_scale_button.setPopupMode(QToolButton.InstantPopup)
        
        png_scale_button.setMenu(scale_menu)
        png_settings_page_layout.addWidget(png_scale_button)
        
        png_scale_label = setting_label_and_layout_break(png_settings_page_layout, tooltip.partition("\n")[0])
        
        png_settings_page.setLayout(png_settings_page_layout)
        item.settings_stack.addWidget(png_settings_page)
        
        jpeg_settings_page = SettingsWidget()
        jpeg_settings_page_layout = FlowLayout()
        
        tooltip = "Quality\n\n" \
                  "Determines how much information is lost during compression.\n" \
                  "Low: small files but bad quality. High: big files but good quality."
        jpeg_quality_slider = SpinBoxSlider(label_text="Quality", label_suffix="%", range_min=0, range_max=100, snap_interval=5, tooltip=tooltip)
        jpeg_quality_slider.setValue(s["jpeg_quality"])
        jpeg_quality_slider.valueChanged.connect(lambda value, i=item: self._on_generic_setting_changed("jpeg_quality", value, i))
        jpeg_settings_page_layout.addWidget(jpeg_quality_slider)
        
        tooltip = "Smooth\n\n" \
                  "The result will be artificially smoothed to hide jpeg artifacts."
        jpeg_smooth_slider = SpinBoxSlider(label_text="Smooth", label_suffix="%", range_min=0, range_max=100, snap_interval=5, tooltip=tooltip)
        jpeg_smooth_slider.setValue(s["jpeg_smooth"])
        jpeg_smooth_slider.valueChanged.connect(lambda value, i=item: self._on_generic_setting_changed("jpeg_smooth", value, i))
        jpeg_settings_page_layout.addWidget(jpeg_smooth_slider)
        
        jpeg_settings_page_layout.addBreak()
        
        tooltip = "Save ICC profile"
        jpeg_icc_profile_checkbox = CheckToolButton(icon_name="embed_profile", checked=s["jpeg_icc_profile"], tooltip=tooltip)
        jpeg_icc_profile_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("jpeg_icc_profile", checked, i))
        jpeg_settings_page_layout.addWidget(jpeg_icc_profile_checkbox)
        
        jpeg_icc_profile_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Transparent pixel fill color\n\n" \
                  "Background color to replace transparent pixels with."
        jpeg_fillcolour_checkbox = ColourToolButton(colour=s["jpeg_fillcolour"], tooltip=tooltip)
        jpeg_fillcolour_checkbox.colourChanged.connect(lambda colour, i=item: self._on_generic_setting_changed("jpeg_fillcolour", colour, i))
        jpeg_settings_page_layout.addWidget(jpeg_fillcolour_checkbox)
        
        jpeg_fillcolour_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Progressive\n\n" \
                  "A progressive jpeg can be displayed while loading."
        jpeg_progressive_checkbox = CheckToolButton(icon_name="progressive", checked=s["jpeg_progressive"], tooltip=tooltip)
        jpeg_progressive_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("jpeg_progressive", checked, i))
        jpeg_settings_page_layout.addWidget(jpeg_progressive_checkbox)
        
        jpeg_progressive_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Subsampling\n\n" \
                  "Subsampling stores chroma (colour) information at a lower resolution than luma (brightness).\n" \
                  "This takes advantage of the fact that eyes are more sensitive to variations in brightness than in colour."
        jpeg_subsampling_button = CheckToolButton(icon_name=("subsampling", s["jpeg_subsampling"]), checked=True, tooltip=tooltip)
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
        jpeg_subsampling_menu.triggered.connect(lambda a, b=jpeg_subsampling_button, i=item: self._on_jpeg_subsampling_menu_triggered(a.data(), b, i))
        
        jpeg_subsampling_button.setMenu(jpeg_subsampling_menu)
        jpeg_settings_page_layout.addWidget(jpeg_subsampling_button)
        
        jpeg_subsampling_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Force baseline JPEG\n\n" \
                  "Force full JPEG baseline compatibility.\n" \
                  "Only really useful for compatibility with old devices. Does nothing if Quality is above 25%."
        jpeg_force_baseline_checkbox = CheckToolButton(icon_name="jpeg_baseline", checked=s["jpeg_force_baseline"], tooltip=tooltip)
        jpeg_force_baseline_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("jpeg_force_baseline", checked, i))
        jpeg_settings_page_layout.addWidget(jpeg_force_baseline_checkbox)
        
        jpeg_force_baseline_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Optimize\n\n" \
                  "Compute optimal compression coding for the image, otherwise use the default coding.\n" \
                  "File size savings tend to be small. When Progressive is enabled, the image will be optimized regardless."
        jpeg_optimise_checkbox = CheckToolButton(icon_name="optimise", checked=s["jpeg_optimise"], tooltip=tooltip)
        jpeg_optimise_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("jpeg_optimise", checked, i))
        jpeg_settings_page_layout.addWidget(jpeg_optimise_checkbox)
        
        jpeg_optimise_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Metadata formats and filters"
        jpeg_metadata_options_button = CheckToolButton(icon_name="metadata_options", checked=s["jpeg_metadata"], tooltip=tooltip)
        jpeg_metadata_options_button.setPopupMode(QToolButton.InstantPopup)
        
        jpeg_metadata_options_menu = QEMenu()
        jpeg_metadata_options_menu.setToolTipsVisible(True)
        
        jpeg_metadata_options_header_action = jpeg_metadata_options_menu.addAction("Metadata formats")
        jpeg_metadata_options_header_action.setDisabled(True)
        jpeg_metadata_options_Exif_action = jpeg_metadata_options_menu.addAction("Exif", "exif")
        jpeg_metadata_options_IPTC_action = jpeg_metadata_options_menu.addAction("IPTC", "iptc")
        jpeg_metadata_options_XMP_action = jpeg_metadata_options_menu.addAction("XMP", "xmp")
        
        jpeg_filters_header_action = jpeg_metadata_options_menu.addAction("Filters")
        jpeg_filters_header_action.setDisabled(True)
        jpeg_metadata_options_info_action = jpeg_metadata_options_menu.addAction("Tool information", "tool_information", "Add the name of the tool used for creation and the modification date.")
        jpeg_metadata_options_anon_action = jpeg_metadata_options_menu.addAction("Anonymiser", "anonymiser", "Remove personal information: author, location...")
        
        for action in jpeg_metadata_options_menu.actions():
            if not action.data():
                continue
            action.setCheckable(True)
            action.setChecked(s[f"jpeg_{action.data()}"])
        jpeg_metadata_options_menu.triggered.connect(lambda a, i=item: self._on_generic_setting_changed(f"jpeg_{a.data()}", a.isChecked(), i))
        
        jpeg_metadata_options_button.setMenu(jpeg_metadata_options_menu)
        jpeg_settings_page_layout.addWidget(jpeg_metadata_options_button)
        
        jpeg_metadata_options_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Store Document Metadata\n\n" \
                  "Store document metadata that is in the document information.\n" \
                  "This will override any layer metadata."
        jpeg_metadata_checkbox = CheckToolButton(icon_name="metadata", checked=s["jpeg_metadata"], tooltip=tooltip)
        jpeg_metadata_checkbox.toggled.connect(lambda checked, mob=jpeg_metadata_options_button, i=item: self._on_jpeg_metadata_checkbox_toggled(checked, mob, i))
        jpeg_settings_page_layout.addWidget(jpeg_metadata_checkbox)
        
        jpeg_metadata_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Sign with Author Profile Data\n\n" \
                  "Add the author nickname and the first contact of the author profile.\n" \
                  "This is overwritten by the anonymizer."
        jpeg_author_checkbox = CheckToolButton(icon_name="author", checked=s["jpeg_author"], tooltip=tooltip)
        jpeg_author_checkbox.toggled.connect(lambda checked, i=item: self._on_generic_setting_changed("jpeg_author", checked, i))
        jpeg_settings_page_layout.addWidget(jpeg_author_checkbox)
        
        jpeg_author_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        tooltip = "Scale image before export"
        jpeg_scale_button = CheckToolButton(icon_name="scale", checked=s["scale"], tooltip=tooltip)
        jpeg_scale_button.setPopupMode(QToolButton.InstantPopup)
        
        jpeg_scale_button.setMenu(scale_menu)
        jpeg_settings_page_layout.addWidget(jpeg_scale_button)
        
        jpeg_scale_label = setting_label_and_layout_break(jpeg_settings_page_layout, tooltip.partition("\n")[0])
        
        jpeg_settings_page.setLayout(jpeg_settings_page_layout)
        item.settings_stack.addWidget(jpeg_settings_page)
        
        self.setItemWidget(item, QECols.SETTINGS_COLUMN, item.settings_stack)
        self.set_item_settings_stack_page_for_extension(item, s["ext"])
        
        scale_checkbox_action.triggered.connect(lambda checked, cb=[no_settings_scale_button,png_scale_button,jpeg_scale_button], i=item: self._on_item_scale_checkbox_action_triggered(checked, cb, i))
        
        btns_widget = QWidget()
        btns_layout = QHBoxLayout()
        item.export_button.clicked.connect(lambda checked, fn=file_path.name, i=item, sb=btn_store_forget: self._on_item_btn_export_clicked(checked, fn, i, sb))
        btns_layout.addWidget(item.export_button)
        
        btns_widget.setLayout(btns_layout)
        
        self.setItemWidget(item, QECols.BUTTONS_COLUMN, btns_widget)
        
        item.output_filetype_combobox.currentIndexChanged.connect(lambda index, i=item: self._on_outputext_combobox_current_index_changed(index, i))
        
        self.items.append(item)
        
        self.add_file_versioning_subitems(item)
        
    def add_file_versioning_subitems(self, item):
        doc = item.doc_settings
        file_path = doc["path"]
        bvs = doc["base_version_string"]
        suf = doc["path"].suffix
        
        still_used_subitem = [False]*item.childCount()
        
        new_subitem_texts = []
        
        col = QECols.SOURCE_FILEPATH_COLUMN
        
        # add new items.
        for test_path in file_path.parent.glob(f"{bvs}*{suf}"):
            if find_settings_for_file(test_path) != doc:
                continue
            subitem = None
            for index_ in range(item.childCount()):
                item_ = item.child(index_)
                if item_.data(col, QERoles.CustomSortRole) == test_path.name:
                    still_used_subitem[index_] = True
                    subitem = item_
                    break
            if subitem:
                continue
            new_subitem_texts.append(test_path.name)
        
        unused_subitems = [item.child(index) for index in range(len(still_used_subitem)) if still_used_subitem[index] == False]

        # repurpose unused existing subitems.
        index = 0
        while index < len(new_subitem_texts) and index < len(unused_subitems):
            subitem = unused_subitems[index]
            text = new_subitem_texts[index]
            subitem.setText(col, text)
            subitem.setData(col, QERoles.CustomSortRole, text)
            index += 1
        
        # removed unused subitems, if any remain.
        while index < len(unused_subitems):
            item.removeChild(unused_subitems[index])
            index += 1
        
        # add new subitems for remaining names, if any.
        while index < len(new_subitem_texts):
            subitem = QTreeWidgetItem(item)
            subitem.setText(col, new_subitem_texts[index])
            subitem.setData(col, QERoles.CustomSortRole, new_subitem_texts[index])
            index += 1
        
        item.sortChildren(col, Qt.AscendingOrder)

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
                
                yield self.thumbnail_worker_timer.start()
        
        finally:
            if self.thumbnail_worker_timer.isActive():
                self.thumbnail_worker_timer.stop()
            print("thumbnail worker: end.")
    
    def _make_thumbnail(self, doc, item):
        thumbnail = QPixmap.fromImage(doc.thumbnail(self.thumb_height, self.thumb_height))
        self.apply_thumbnail(item, thumbnail)
    
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
        self.apply_thumbnail(item, thumbnail)
    
    def apply_thumbnail(self, item, thumbnail):
        # make and store large and minimized copies of thumb.
        is_minimized = self.isItemMinimized(item)
        item.thumbnail_normal = thumbnail
        min_thumb_size = QSize(int(self.minimized_thumb_height), int(self.minimized_thumb_height))
        item.thumbnail_minimized = thumbnail.scaled(min_thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        item.thumbnail_label.setPixmap(item.thumbnail_minimized if is_minimized else thumbnail)
    
    def updateAlternatingRowContrast(self):
        pal = QApplication.palette()
        base = pal.color(QPalette.Base)
        altbase = pal.color(QPalette.AlternateBase)
        f = int(readSetting("alt_row_contrast")) * 0.01
        pal.setColor(QPalette.AlternateBase, QColor(
            round(base.red()   + (altbase.red()   - base.red())   * f - 0.333),
            round(base.green() + (altbase.green() - base.green()) * f),
            round(base.blue()  + (altbase.blue()  - base.blue())  * f + 0.333),
            altbase.alpha()
        ))
        self.setPalette(pal)
