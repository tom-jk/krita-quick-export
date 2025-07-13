from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup)
from PyQt5.QtCore import Qt, QRegExp, QModelIndex
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor
from pathlib import Path
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita
from .utils import *

app = Krita.instance()

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

class ItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        if index.column() in (QECols.OPEN_FILE_COLUMN, QECols.THUMBNAIL_COLUMN, QECols.SOURCE_FILENAME_COLUMN, QECols.BUTTONS_COLUMN):
            return None
        else:
            return super().createEditor(parent, option, index)
    
    def paint(self, painter, option, index):
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

class QECols(IntEnum):
    STORE_SETTINGS_COLUMN = 0
    OPEN_FILE_COLUMN = auto()
    THUMBNAIL_COLUMN = auto()
    SOURCE_FILENAME_COLUMN = auto()
    OUTPUT_FILENAME_COLUMN = auto()
    STORE_ALPHA_COLUMN = auto()
    COMPRESSION_COLUMN = auto()
    BUTTONS_COLUMN = auto()
    COLUMN_COUNT = auto()

class QERoles(IntEnum):
    CustomSortRole = Qt.UserRole
    #MoreRoles = auto()...

class QETree(QTreeWidget):
    instance = None
    
    def refilter(self):
        for index, s in enumerate(qe_settings):
            #print(index, s["document"])
            self.items[index].setHidden(
                   (self.dialog.show_unstored_button.checkState() == Qt.Unchecked and s["store"] == False)
                or (self.dialog.show_unopened_button.checkState() == Qt.Unchecked and s["document"] == None)
                or (self.dialog.show_png_button.checkState() == Qt.Unchecked and s["path"].suffix == ".png")
            )
    
    def _on_btn_open_clicked(self, checked, btn, export_btn, doc, item):
        print("_on_btn_open_clicked for", doc)
        print("opening doc")
        new_doc = app.openDocument(str(doc['path']))
        print("new_doc:", new_doc)
        if new_doc == None:
            sbar.showMessage(f"Couldn't open '{str(doc['path'])}'", 5000)
            return
        sbar.showMessage(f"Opened '{str(doc['path'])}'", 5000)
        app.activeWindow().addView(new_doc)
        item.setDisabled(False)
        self.setItemWidget(item, QECols.OPEN_FILE_COLUMN, None)
        doc['document'] = new_doc
        doc['doc_index'] = app.documents().index(new_doc)
        item.setData(QECols.OPEN_FILE_COLUMN, QERoles.CustomSortRole, str(doc['doc_index']))
        new_doc.waitForDone()
        item.setIcon(QECols.THUMBNAIL_COLUMN, QIcon(QPixmap.fromImage(new_doc.thumbnail(64,64))))
        export_btn.setDisabled(False)
        print("done")
    
    def _on_output_lineedit_editing_finished(self, doc, lineedit, item, store_button):
        doc["output"] = lineedit.text()
        item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, doc["output"].lower())
        #print("_on_output_lineedit_changed ->", doc["output"])
        self.set_settings_modified(store_button)
    
    def _on_item_btn_export_clicked(self, checked, doc, filename, store_button):
        print(f"Clicked export for {doc['path']}")
        self.sender().setText("Exporting...")
        
        result = export_image(doc)
        
        if not result:
            self.sender().setText("Export failed!")
            self.dialog.sbar.showMessage(f"Export failed", 5000)
        else:
            self.sender().setText("Done!")
            self.dialog.sbar.showMessage(f"Exported to '{str(doc['path'].with_name(doc['output']))}'")
        
        if self.dialog.auto_store_on_export_button.checkState() == Qt.Checked:
            store_button.setCheckState(Qt.Checked)
    
    def _on_item_btn_store_forget_clicked(self, checked, btn, doc, filename, item):
        #print("store/forget changed ->", checked, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["store"] = not doc["store"]
        item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+doc["store"]))
        self.redraw()
        self.set_settings_modified()
    
    def _on_alpha_checkbox_state_changed(self, state, doc, item, store_button):
        #print("alpha checkbox changed ->", state, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["alpha"] = True if state == Qt.Checked else False
        item.setData(QECols.STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+doc["alpha"]))
        self.set_settings_modified(store_button)
    
    def _on_compression_slider_value_changed(self, value, doc, slider, label, item, store_button):
        #print("slider value changed ->", value, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["compression"] = value
        item.setData(QECols.COMPRESSION_COLUMN, QERoles.CustomSortRole, str(doc["compression"]))
        label.setText(str(value))
        self.set_settings_modified(store_button)
    
    def set_settings_modified(self, store_button=None):
        if not self.dialog.tree_is_ready:
            return
        
        if generate_save_string() != app.readSetting("TomJK_QuickExport", "settings", ""):
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
                    qe_settings.append({"document":doc, "doc_index":i, "store":False, "path":path, "alpha":s["alpha"], "compression":s["compression"], "output":s["output"]})
                    doc_is_in_settings = True
                    break
            
            if doc_is_in_settings:
                continue
            
            qe_settings.append({"document":doc, "doc_index":i, "store":False, "path":path, "alpha":False, "compression":9, "output":path.with_suffix(".png").name})
        
        # TODO: detect if multiple documents would export to the same output file.
        
        self.highlighted_doc_index = -1
        if self.dialog.highlighted_doc:
            for s in qe_settings:
                if s["document"] == self.dialog.highlighted_doc:
                    self.highlighted_doc_index = str(s["doc_index"])
                    break
        
        self.setColumnCount(QECols.COLUMN_COUNT)
        self.setHeaderLabels(["", "", "", "Filename", "Export to", "", "Compression", "Actions"])
        self.headerItem().setIcon(QECols.STORE_SETTINGS_COLUMN, app.icon('document-save'))
        self.headerItem().setIcon(QECols.STORE_ALPHA_COLUMN, app.icon('transparency-unlocked'))
        self.items = []
        
        # TODO: still need to ensure output filename ends with ".png".
        filename_regex = QRegExp("^[^<>:;,?\"*|/]+$")
        
        longest_output = ""
        for s in qe_settings:
            output = s["path"].with_suffix(".png").name
            if len(output) > len(longest_output):
                longest_output = output
        
        def centered_checkbox_widget(checkbox):
            widget = QWidget()
            layout = QHBoxLayout()
            layout.addStretch()
            layout.addWidget(checkbox)
            layout.addStretch()
            layout.setContentsMargins(0,0,0,0)
            widget.setLayout(layout)
            return widget
        
        checkbox_stylesheet = "QCheckBox::indicator:unchecked {border: 1px solid rgba(255,255,255,0.1);}"
        
        item_delegate = ItemDelegate()
        
        self.itemClicked.connect(self._on_item_clicked)
        
        for s in qe_settings:
            file_path = s["path"]
            
            item = MyTreeWidgetItem(self)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.setItemDelegate(item_delegate)
            
            btns_export = QPushButton("Export now")
            
            btn_store_forget = QCheckBox()
            btn_store_forget.setChecked(s["store"])
            btn_store_forget.setStyleSheet(checkbox_stylesheet)
            btn_store_forget.toggled.connect(lambda checked, btn=btn_store_forget, d=s, fn=file_path.name, i=item: self._on_item_btn_store_forget_clicked(checked, btn, d, fn, i))
            btn_store_widget = centered_checkbox_widget(btn_store_forget)
            self.setItemWidget(item, QECols.STORE_SETTINGS_COLUMN, btn_store_widget)
            item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+s["store"]))
            
            if (btn_group_key := str(s["path"])) in self.store_button_groups:
                self.store_button_groups[btn_group_key].addButton(btn_store_forget)
                if s["store"] and self.store_button_groups[btn_group_key].btnLastChecked == None:
                    self.store_button_groups[btn_group_key].btnLastChecked = btn_store_forget
            
            if s["document"] != None:
                item.setIcon(QECols.THUMBNAIL_COLUMN, QIcon(QPixmap.fromImage(s["document"].thumbnail(64,64))))
                if s["document"] == app.activeDocument():
                    item.setText(QECols.OPEN_FILE_COLUMN, "*")
                    item.setTextAlignment(QECols.OPEN_FILE_COLUMN, Qt.AlignCenter)
            else:
                item.setDisabled(True)
                btn_open = QPushButton("")
                btn_open.setIcon(app.icon('document-open'))
                btn_open.setStyleSheet("QPushButton {border:none; background:transparent;}")
                self.setItemWidget(item, QECols.OPEN_FILE_COLUMN, btn_open)
                btn_open.clicked.connect(lambda checked, b=btn_open, be=btns_export, d=s, i=item: self._on_btn_open_clicked(checked, b, be, d, i))
            
            item.setData(QECols.OPEN_FILE_COLUMN, QERoles.CustomSortRole, str(s["doc_index"]))
            
            item.setText(QECols.SOURCE_FILENAME_COLUMN, file_path.name)
            item.setData(QECols.SOURCE_FILENAME_COLUMN, QERoles.CustomSortRole, file_path.name.lower())
            
            output_widget = QWidget()
            output_layout = QHBoxLayout()
            output_edit = MyLineEdit(s["output"])
            output_edit.setStyleSheet("QLineEdit {background: rgba(0,0,0,0);}")
            
            input_validator = QRegExpValidator(filename_regex, output_edit)
            output_edit.setValidator(input_validator)
            
            text = longest_output + "PAD"
            fm = QFontMetrics(output_edit.font())
            pixelsWide = fm.width(text)
            output_edit.setMinimumWidth(pixelsWide)
            output_edit.editingFinished.connect(lambda d=s, oe=output_edit, i=item, sb=btn_store_forget: self._on_output_lineedit_editing_finished(d, oe, i, sb))
            
            output_layout.addWidget(output_edit)
            output_widget.setLayout(output_layout)
            
            self.setItemWidget(item, QECols.OUTPUT_FILENAME_COLUMN, output_widget)
            item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, s["output"].lower())
            
            alpha_checkbox = QCheckBox()
            alpha_checkbox.setStyleSheet(checkbox_stylesheet)
            
            alpha_checkbox.setCheckState(Qt.Checked if s["alpha"] else Qt.Unchecked)
            alpha_checkbox.stateChanged.connect(lambda state, d=s, i=item, sb=btn_store_forget: self._on_alpha_checkbox_state_changed(state, d, i, sb))
            alpha_checkbox_widget = centered_checkbox_widget(alpha_checkbox)
            self.setItemWidget(item, QECols.STORE_ALPHA_COLUMN, alpha_checkbox_widget)
            item.setData(QECols.STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+s["alpha"]))
            
            compression_widget = QWidget()
            compression_layout = QHBoxLayout()
            compression_label = QLabel()
            compression_slider = QSlider(Qt.Horizontal)
            compression_slider.setRange(1, 9)
            compression_slider.valueChanged.connect(lambda value, d=s, cs=compression_slider, cl=compression_label, i=item, sb=btn_store_forget: self._on_compression_slider_value_changed(value, d, cs, cl, i, sb))
            compression_slider.setValue(s["compression"])
            compression_label.setText(str(s["compression"]))
            compression_layout.addWidget(compression_slider)
            compression_layout.addWidget(compression_label)
            compression_widget.setLayout(compression_layout)
            self.setItemWidget(item, QECols.COMPRESSION_COLUMN, compression_widget)
            item.setData(QECols.COMPRESSION_COLUMN, QERoles.CustomSortRole, str(s["compression"]))
            
            btns_widget = QWidget()
            btns_layout = QHBoxLayout()
            btns_export.setDisabled(s["document"] == None)
            btns_export.clicked.connect(lambda checked, d=s, fn=file_path.name, sb=btn_store_forget: self._on_item_btn_export_clicked(checked, d, fn, sb))
            btns_layout.addWidget(btns_export)
            btns_widget.setLayout(btns_layout)
            
            self.setItemWidget(item, QECols.BUTTONS_COLUMN, btns_widget)
            
            self.items.append(item)
        
        for i in range(0, QECols.COLUMN_COUNT):
            self.resizeColumnToContents(i)


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

        # show unstored button.
        self.show_unstored_button = QCheckBox("Show unstored")
        self.show_unstored_button.setToolTip("Enable this to pick the images you're interested in exporting, then disable it to hide the rest.")
        self.show_unstored_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_unstored", "true") == "true" else Qt.Unchecked)
        self.show_unstored_button.clicked.connect(self._on_show_unstored_button_clicked)

        # show unopened button.
        self.show_unopened_button = QCheckBox("Show unopened")
        self.show_unopened_button.setToolTip("Show the export settings of every file - currently open or not - for which settings have been saved.")
        self.show_unopened_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_unopened", "false") == "true" else Qt.Unchecked)
        self.show_unopened_button.clicked.connect(self._on_show_unopened_button_clicked)

        # show .png files button.
        self.show_png_button = QCheckBox("Show .png files")
        self.show_png_button.setToolTip("Show export settings for .png files. Disabled by default because it's kind of redundant.")
        self.show_png_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_png", "false") == "true" else Qt.Unchecked)
        self.show_png_button.clicked.connect(self._on_show_png_button_clicked)

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
        self.stored_highlight_slider.setValue(int(app.readSetting("TomJK_QuickExport", "highlight_alpha", "64")))
        self.stored_highlight_slider.setMinimumWidth(64)
        self.stored_highlight_slider.valueChanged.connect(self._on_stored_highlight_slider_value_changed)
        stored_highlight_layout.addWidget(self.stored_highlight_slider)

        stored_highlight_widget.setLayout(stored_highlight_layout)

        view_buttons_layout.addWidget(self.show_png_button)
        view_buttons_layout.addWidget(self.show_unopened_button)
        view_buttons_layout.addWidget(self.show_unstored_button)
        view_buttons_layout.addStretch()
        view_buttons_layout.addWidget(stored_highlight_widget)

        view_buttons_layout.setContentsMargins(0,0,0,0)
        view_buttons.setLayout(view_buttons_layout)
        layout.addWidget(view_buttons)

        config_buttons = QWidget()
        config_buttons_layout = QHBoxLayout()

        # advanced mode button.
        self.advanced_mode_button = QCheckBox("Advanced mode")
        self.advanced_mode_button.setToolTip("Basic mode: export settings are saved by default (recommended).\nAdvanced mode: configure how settings are stored.")
        self.advanced_mode_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "advanced_mode", "false") == "true" else Qt.Unchecked)
        self.advanced_mode_button.clicked.connect(self._on_advanced_mode_button_clicked)

        # auto store for modified button.
        self.auto_store_on_modify_button = QCheckBox("Store on modify")
        self.auto_store_on_modify_button.setToolTip("Automatically check the store button for a file when you modify any of its export settings.")
        self.auto_store_on_modify_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "auto_store_on_modify", "true") == "true" else Qt.Unchecked)
        self.auto_store_on_modify_button.clicked.connect(self._on_auto_store_on_modify_button_clicked)

        # auto store for exported button.
        self.auto_store_on_export_button = QCheckBox("Store on export")
        self.auto_store_on_export_button.setToolTip("Automatically check the store button for a file when you export it.")
        self.auto_store_on_export_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "auto_store_on_export", "true") == "true" else Qt.Unchecked)
        self.auto_store_on_export_button.clicked.connect(self._on_auto_store_on_export_button_clicked)

        # auto save settings on close button.
        self.auto_save_on_close_button = QCheckBox("Save settings on close")
        self.auto_save_on_close_button.setToolTip("Automatically save changes to settings without asking when you close the dialog.")
        self.auto_save_on_close_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "auto_save_on_close", "true") == "true" else Qt.Unchecked)
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

        # status bar.
        self.sbar = QStatusBar()
        sbar_ready_label = QLabel(" Ready." if msg == "" else " "+msg) # extra space to align with showmessage.
        self.sbar.insertWidget(0, sbar_ready_label)
        layout.addWidget(self.sbar)

        # TODO: inform user about having multiple copies of same file open.
        if len(self.tree.dup_counts) == 1:
            sbar_ready_label.setText(f"Note: Multiple copies of '{list(self.tree.dup_counts.keys())[0]}' are currently open in Krita.")
        elif len(self.tree.dup_counts) > 1:
            sbar_ready_label.setText(f"Note: Multiple copies of multiple files (hover mouse here to see) are currently open in Krita.")
            sbar_ready_label.setToolTip("\n".join(self.tree.dup_counts.keys()))

        # create dialog and show it
        self.setLayout(layout)
        self.setWindowTitle("Quick Export")
        dialog_width = int(app.readSetting("TomJK_QuickExport", "dialogWidth", "1024"))
        dialog_height = int(app.readSetting("TomJK_QuickExport", "dialogHeight", "640"))
        self.resize(dialog_width, dialog_height)

    def resizeEvent(self, event):
        app.writeSetting("TomJK_QuickExport", "dialogWidth", str(event.size().width()))
        app.writeSetting("TomJK_QuickExport", "dialogHeight", str(event.size().height()))
    
    def reject(self):
        self.close()
    
    def closeEvent(self, event):
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
        elif ret == QMessageBox.Save:
            save_settings_to_config()
        event.accept()

    def _on_show_unstored_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "show_unstored", "true" if checked else "false")
        self.tree.refilter()

    def _on_show_unopened_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "show_unopened", "true" if checked else "false")
        self.tree.refilter()

    def _on_show_png_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "show_png", "true" if checked else "false")
        self.tree.refilter()
    
    def _on_stored_highlight_slider_value_changed(self):
        app.writeSetting("TomJK_QuickExport", "highlight_alpha", str(self.stored_highlight_slider.value()))
        self.tree.redraw()

    def _on_advanced_mode_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "advanced_mode", "true" if checked else "false")
        self.set_advanced_mode(checked)

    def set_advanced_mode(self, enabled):
        if enabled:
            self.tree.showColumn(QECols.STORE_SETTINGS_COLUMN)
            self.show_unstored_button.show()
            self.show_unstored_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_unstored", "true") == "true" else Qt.Unchecked)
            self.auto_store_on_modify_button.show()
            self.auto_store_on_modify_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "auto_store_on_modify", "true") == "true" else Qt.Unchecked)
            self.auto_store_on_export_button.show()
            self.auto_store_on_export_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "auto_store_on_export", "true") == "true" else Qt.Unchecked)
            self.auto_save_on_close_button.show()
            self.auto_save_on_close_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "auto_save_on_close", "true") == "true" else Qt.Unchecked)
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
        app.writeSetting("TomJK_QuickExport", "auto_store_on_modify", "true" if checked else "false")

    def _on_auto_store_on_export_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "auto_store_on_export", "true" if checked else "false")

    def _on_auto_save_on_close_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "auto_save_on_close", "true" if checked else "false")

    def _on_save_button_clicked(self, checked):
        save_settings_to_config()
        self.save_button.setText("Save Settings")
        self.save_button.setIcon(QIcon())
        self.save_button.setDisabled(True)
        self.sbar.showMessage("Settings saved.", 2500)


# TODO: if __main__ etc. to allow running script by itself?
