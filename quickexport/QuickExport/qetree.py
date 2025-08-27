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
from .qewidgets import QEMenu, CheckToolButton, ColourToolButton, QEComboBox, FadingStackedWidget, SpinBoxSlider, FlowLayout
from .multilineelidedbutton import MultiLineElidedText, MultiLineElidedButton
from .filenameedit import FileNameEdit

class ItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        if index.column() in (QECols.OPEN_FILE_COLUMN, QECols.THUMBNAIL_COLUMN, QECols.SOURCE_FILENAME_COLUMN, QECols.BUTTONS_COLUMN):
            return None
        else:
            return super().createEditor(parent, option, index)
    
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        
        tree = QETree.instance
        if size.height() < tree.min_row_height:
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
            painter.fillRect(option.rect, QColor(64,128,255,int(readSetting("highlight_alpha", "64"))))

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
        if self.hovered_item and (widget := self.itemWidget(self.hovered_item, QECols.SETTINGS_COLUMN)):
            widget.setOpacity(hover=False)
        self.hovered_item = None
    
    def refilter(self):
        show_unstored = str2bool(readSetting("show_unstored", "true"))
        show_unopened = str2bool(readSetting("show_unopened", "false"))
        show_non_kra  = str2bool(readSetting("show_non_kra",  "false"))
        for index, s in enumerate(qe_settings):
            self.items[index].setHidden(
                   (not show_unstored and s["store"] == False)
                or (not show_unopened and s["document"] == None)
                or (not show_non_kra  and s["path"].suffix != ".kra")
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
    
    def _on_output_name_edit_editing_finished(self, doc, edit, item, store_button):
        doc["output_name"] = edit.text()
        item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, doc["output_name"].lower())
        #print("_on_output_lineedit_changed ->", doc["output"])
        self.set_settings_modified(store_button)
    
    def _on_item_btn_export_clicked(self, checked, doc, filename, store_button):
        print(f"Clicked export for {doc['path']}")
        self.sender().setText("Exporting...")
        
        result = export_image(doc)
        
        if not result:
            failed_msg = export_failed_msg()
            self.sender().setIcon(app.icon('window-close'))
            self.dialog.sbar.showMessage(f"Export failed. {failed_msg}")
        else:
            self.sender().setIcon(app.icon('dialog-ok'))
            self.dialog.sbar.showMessage(f"Exported to '{str(doc['output_abs_dir'].joinpath(doc['output_name']).with_suffix(doc['ext']))}'")
        
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
    
    def _on_output_path_menu_triggered(self, value, path_button, name_edit, ext_combobox, doc, store_button):
        if value in (True, False):
            print("Selected absolute/relative:", value)
            doc["output_is_abs"] = value
            
        elif value == "change":
            print("Selected Change...")
            
            if False:
                if path_button.text() == "." or path_button.text().startswith("./"):
                    file_path = doc["path"].with_name(Path(doc["output_name"]).name).with_suffix(doc["ext"])
                else:
                    file_path = Path(doc["output_name"]).with_suffix(doc["ext"])
            else:
                file_path = doc["output_abs_dir"].joinpath(doc["output_name"]).with_suffix(doc["ext"])
            
            file_path_string = QFileDialog.getSaveFileName(
                parent = self,
                directory = str(file_path),
                filter = f"Images ({' '.join(['*'+ext for ext in supported_extensions()])});;" + ";;".join([ext[1:]+' (*'+ext+')' for ext in supported_extensions()])
            )[0]
            
            if file_path_string == "":
                return
            
            ext = Path(file_path_string).suffix
            file_path = Path(file_path_string).with_suffix("")
            
            doc["output_abs_dir"] = file_path.parent
            doc["output_name"] = file_path.name
            path_button.setText(str(file_path.parent) if file_path.parent != doc["path"].parent else ".")
            name_edit.setText(file_path.name)
            
            if ext and ext in supported_extensions():
                ext_combobox.setCurrentIndex(ext_combobox.findData(ext))
            
        self.set_settings_modified(store_button)
    
    def _on_outputext_combobox_current_index_changed(self, index, combobox, settings_stack, doc, item, store_button):
        ext = combobox.itemText(index)
        doc["ext"] = ext
        item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, doc["ext"])
        self.set_item_settings_stack_page_for_extension(settings_stack, ext)
        self.set_settings_modified(store_button)
    
    def set_item_settings_stack_page_for_extension(self, settings_stack, ext):
        settings_stack.setCurrentIndex(self.settings_stack_page_index_for_extension(ext))
        self._on_column_resized(QECols.SETTINGS_COLUMN, QECols.SETTINGS_COLUMN, -1)
    
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
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setAlternatingRowColors(True)
        self.updateAlternatingRowContrast()
        
        from PyQt5.QtCore import QItemSelectionModel
        self.setSelectionMode(QTreeWidget.NoSelection)
        
        self.setMouseTracking(True)
        self.filter = QETreeFilter()
        self.installEventFilter(self.filter)
        
        self.hovered_item = None
        
        fm = QFontMetrics(self.font())
        self.thumb_height = fm.height() * 4
        self.min_row_height = fm.height() * 5
        
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
        self.setHeaderLabels(["", "", "", "File Path", "File Name", "Versions", "Export Path", "Export Name", "Type", "Settings", ""])
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
        
        self.settings_stack_page_order = [[".gif", ".pbm", ".pgm", ".ppm", ".tga", ".bmp", ".ico", ".xbm", ".xpm"], ".png", [".jpg",".jpeg"]]
                
        item_delegate = ItemDelegate()
        self.setItemDelegate(item_delegate)
        
        self.itemClicked.connect(self._on_item_clicked)
        
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
        
        self.refilter()
        
        for i in range(0, QECols.COLUMN_COUNT):
            self.resizeColumnToContents(i)
        
        QTimer.singleShot(0, self.scheduleDelayedItemsLayout)

        if len(self.thumbnail_queue) == 0:
            return
        
        self.thumbnail_column_resized_to_contents_once = False
        self.thumbnail_worker = self.thumbnail_worker_process()
        self.thumbnail_worker_timer = QTimer(self)
        self.thumbnail_worker_timer.setInterval(0)
        self.thumbnail_worker_timer.setSingleShot(True)
        self.thumbnail_worker_timer.timeout.connect(lambda: next(self.thumbnail_worker, None))
        self.thumbnail_worker_timer.start()
    
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
        
        # TODO: adapt to theme light/dark.
        checkbox_stylesheet = "QCheckBox::indicator:unchecked {border: 1px solid rgba(255,255,255,0.1);}" if extension().theme_is_dark else ""
        
        file_path = s["path"]
        
        item = MyTreeWidgetItem(self)
        item.setHidden(True)
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
        
        item.setData(QECols.OPEN_FILE_COLUMN, QERoles.CustomSortRole, str(s["doc_index"]))
        
        file_path_parent = str(file_path.parent)
        if False and file_path_parent.startswith(str(Path.home())):
            file_path_parent = file_path_parent.replace(str(Path.home()), "/home")
        
        filepath_widget = MultiLineElidedText(file_path_parent, margin=5)
        filepath_widget.setDisabled(s["document"] == None)
        
        self.setItemWidget(item, QECols.SOURCE_FILEPATH_COLUMN, filepath_widget)
        item.setData(QECols.SOURCE_FILEPATH_COLUMN, QERoles.CustomSortRole, file_path_parent.lower())
        
        filename_widget = MultiLineElidedText(file_path.name, margin=5)
        filename_widget.setDisabled(s["document"] == None)
        
        self.setItemWidget(item, QECols.SOURCE_FILENAME_COLUMN, filename_widget)
        item.setData(QECols.SOURCE_FILENAME_COLUMN, QERoles.CustomSortRole, file_path.name.lower())
        
        if s["document"] == None:
            btn_open.clicked.connect(lambda checked, b=btn_open, db=[btns_export,scale_reset_action,scale_settings_action,filepath_widget,filename_widget], d=s, i=item: self._on_btn_open_clicked(checked, b, db, d, i))
        
        output_path_button = MultiLineElidedButton(str(s["output_abs_dir"]) if s["output_abs_dir"] != s["path"].parent else ".", margin=0)
        
        output_name_edit = FileNameEdit(s["output_name"])
        output_name_edit.edit.settings = s
        
        outputext_combobox = QEComboBox()
        self.extension_comboboxes.append(outputext_combobox)
        
        output_path_button.setStyleSheet("QToolButton::menu-indicator {image: none;}")
        output_path_button.setPopupMode(QToolButton.InstantPopup)
        
        output_path_menu = QEMenu(keep_open=False)
        output_path_action_group = QActionGroup(output_path_menu)
        output_path_absolute_action = output_path_menu.addAction("Absolute", True)
        output_path_relative_action = output_path_menu.addAction("Relative", False)
        for i, action in enumerate(output_path_menu.actions()):
            action.setCheckable(True)
            action.setActionGroup(output_path_action_group)
            action.setChecked(action.data() == s["output_is_abs"])
        output_path_menu.addSeparator()
        output_path_change_action = output_path_menu.addAction("Change...", "change")
        output_path_menu.triggered.connect(lambda a, pb=output_path_button, ne=output_name_edit, ec=outputext_combobox, d=s, sb=btn_store_forget: self._on_output_path_menu_triggered(a.data(), pb, ne, ec, d, sb))
        
        output_path_button.setMenu(output_path_menu)
        
        self.setItemWidget(item, QECols.OUTPUT_FILEPATH_COLUMN, output_path_button)
        item.setData(QECols.OUTPUT_FILEPATH_COLUMN, QERoles.CustomSortRole, file_path_parent.lower())
        
        output_name_edit.edit.editingFinished.connect(lambda d=s, e=output_name_edit.edit, i=item, sb=btn_store_forget: self._on_output_name_edit_editing_finished(d, e, i, sb))
        
        output_name_edit.edit.document().contentsChanged.connect(output_name_edit.edit.recalc_height)
        output_name_edit.edit.document().contentsChanged.connect(self.scheduleDelayedItemsLayout)
        
        self.setItemWidget(item, QECols.OUTPUT_FILENAME_COLUMN, output_name_edit)
        item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, s["output_name"].lower())
        
        outputext_widget = QWidget()
        outputext_layout = QHBoxLayout()
        
        for e in supported_extensions():
            outputext_combobox.addItem(e, e)
        
        outputext_combobox.setCurrentIndex(outputext_combobox.findData(s["ext"]))
        
        outputext_layout.addWidget(outputext_combobox)
        outputext_widget.setLayout(outputext_layout)
        
        self.setItemWidget(item, QECols.OUTPUT_FILETYPE_COLUMN, outputext_widget)
        item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, s["ext"])
        
        settings_stack = FadingStackedWidget()
        
        no_settings_page = QWidget()
        no_settings_page_layout = FlowLayout()
        
        no_settings_label = QLabel("(No settings.)")
        no_settings_page_layout.addWidget(no_settings_label)
        
        no_settings_scale_button = CheckToolButton(icon_name="scale", checked=s["scale"], tooltip="scale image before export")
        no_settings_scale_button.setPopupMode(QToolButton.InstantPopup)
        
        no_settings_scale_button.setMenu(scale_menu)
        no_settings_page_layout.addWidget(no_settings_scale_button)
        
        no_settings_page.setLayout(no_settings_page_layout)
        settings_stack.addWidget(no_settings_page)
        
        png_settings_page = QWidget()
        png_settings_page_layout = FlowLayout()
        
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
        jpeg_settings_page_layout = FlowLayout()
        
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
        
        jpeg_smooth_slider = SpinBoxSlider(label_text="Smooth", label_suffix="%", range_min=0, range_max=100, snap_interval=5)
        jpeg_smooth_slider.setValue(s["jpeg_smooth"])
        jpeg_smooth_slider.valueChanged.connect(lambda value, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_smooth", value, d, sb))
        jpeg_settings_page_layout.addWidget(jpeg_smooth_slider)
        
        jpeg_progressive_checkbox = CheckToolButton(icon_name="progressive", checked=s["jpeg_progressive"], tooltip="progressive")
        jpeg_progressive_checkbox.toggled.connect(lambda checked, d=s, sb=btn_store_forget: self._on_generic_setting_changed("jpeg_progressive", checked, d, sb))
        jpeg_settings_page_layout.addWidget(jpeg_progressive_checkbox)
        
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
        label.setAlignment(Qt.AlignCenter)
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
        label.setAlignment(Qt.AlignCenter)
        label.setPixmap(thumbnail)
        self.setItemWidget(item, QECols.THUMBNAIL_COLUMN, label)
    
    def updateAlternatingRowContrast(self):
        pal = QApplication.palette()
        base = pal.color(QPalette.Base)
        altbase = pal.color(QPalette.AlternateBase)
        f = int(readSetting("alt_row_contrast", str(100))) * 0.01
        pal.setColor(QPalette.AlternateBase, QColor(
            round(base.red()   + (altbase.red()   - base.red())   * f - 0.333),
            round(base.green() + (altbase.green() - base.green()) * f),
            round(base.blue()  + (altbase.blue()  - base.blue())  * f + 0.333),
            altbase.alpha()
        ))
        self.setPalette(pal)
