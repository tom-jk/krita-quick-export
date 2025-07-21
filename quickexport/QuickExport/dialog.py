from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate, QMenu,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup,
                             QActionGroup, QToolButton, QComboBox, QStackedWidget)
from PyQt5.QtCore import Qt, QRegExp, QModelIndex
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor
from pathlib import Path
from functools import partial
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
    
    def refilter(self):
        for index, s in enumerate(qe_settings):
            #print(index, s["document"])
            self.items[index].setHidden(
                   (self.dialog.show_unstored_button.checkState() == Qt.Unchecked and s["store"] == False)
                or (self.dialog.show_unopened_button.checkState() == Qt.Unchecked and s["document"] == None)
                or (self.dialog.show_non_kra_button.checkState() == Qt.Unchecked and s["path"].suffix != ".kra")
            )
    
    def _on_btn_open_clicked(self, checked, btn, export_btn, doc, item):
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
            self.dialog.sbar.showMessage(f"Exported to '{str(doc['path'].with_name(doc['output']).with_suffix(doc['ext']))}'")
        
        if self.dialog.auto_store_on_export_button.checkState() == Qt.Checked:
            store_button.setCheckState(Qt.Checked)
    
    def _on_item_btn_store_forget_clicked(self, checked, btn, doc, filename, item):
        #print("store/forget changed ->", checked, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["store"] = not doc["store"]
        item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+doc["store"]))
        self.redraw()
        self.set_settings_modified()
    
    def _on_outputext_combobox_activated(self, index, combobox, settings_stack, doc, item, store_button):
        ext = combobox.itemText(index)
        doc["ext"] = ext
        item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, doc["ext"])
        settings_stack.setCurrentIndex(self.settings_stack_page_order.index(ext))
        self.set_settings_modified(store_button)
    
    def _on_png_alpha_checkbox_state_changed(self, state, doc, item, store_button):
        #print("alpha checkbox changed ->", state, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["png_alpha"] = True if state == Qt.Checked else False
        #item.setData(QECols.PNG_STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+doc["png_alpha"]))
        self.set_settings_modified(store_button)
    
    def _on_png_compression_slider_value_changed(self, value, doc, slider, label, item, store_button):
        #print("slider value changed ->", value, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["png_compression"] = value
        #item.setData(QECols.PNG_COMPRESSION_COLUMN, QERoles.CustomSortRole, str(doc["png_compression"]))
        label.setText(str(value))
        self.set_settings_modified(store_button)
    
    def _on_jpeg_quality_slider_value_changed(self, doc, slider, label, item, store_button):
        #print("slider value changed ->", value, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        value = slider.value()
        doc["jpeg_quality"] = value
        #item.setData(QECols.JPEG_QUALITY_COLUMN, QERoles.CustomSortRole, str(doc["jpeg_quality"]))
        label.setText(f"{value}%")
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
                    s_copy = s.copy()
                    s_copy["store"] = False
                    qe_settings.append(s_copy)
                    doc_is_in_settings = True
                    break
            
            if doc_is_in_settings:
                continue
            
            qe_settings.append(default_settings(document=doc, doc_index=i, path=path, output=path.stem))
        
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
        
        self.settings_stack_page_order = [".png", ".jpg"]
        
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
            
            # TODO: move caret to before .extension when user clicks on unfocused textbox?
            #       maybe only if they click anywhere after the '.'?
            output_widget = QWidget()
            output_layout = QHBoxLayout()
            output_edit = MyLineEdit(s["output"])
            output_edit.settings = s
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
            
            outputext_widget = QWidget()
            outputext_layout = QHBoxLayout()
            
            outputext_combobox = QComboBox()
            outputext_combobox.addItem(".png", ".png")
            outputext_combobox.addItem(".jpg", ".jpg")
            outputext_combobox.setCurrentIndex(outputext_combobox.findData(s["ext"]))
            
            outputext_layout.addWidget(outputext_combobox)
            outputext_widget.setLayout(outputext_layout)
            
            self.setItemWidget(item, QECols.OUTPUT_FILETYPE_COLUMN, outputext_widget)
            item.setData(QECols.OUTPUT_FILETYPE_COLUMN, QERoles.CustomSortRole, s["ext"])
            
            settings_stack = QStackedWidget()
            
            png_settings_page = QWidget()
            png_settings_page_layout = QHBoxLayout()
            
            png_alpha_checkbox = QCheckBox()
            png_alpha_checkbox.setStyleSheet(checkbox_stylesheet)
            
            png_alpha_checkbox.setCheckState(Qt.Checked if s["png_alpha"] else Qt.Unchecked)
            png_alpha_checkbox.stateChanged.connect(lambda state, d=s, i=item, sb=btn_store_forget: self._on_png_alpha_checkbox_state_changed(state, d, i, sb))
            png_alpha_checkbox_widget = centered_checkbox_widget(png_alpha_checkbox)
            #item.setData(QECols.PNG_STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+s["png_alpha"]))
            png_settings_page_layout.addWidget(png_alpha_checkbox_widget)
            
            png_compression_widget = QWidget()
            png_compression_layout = QHBoxLayout()
            png_compression_label = QLabel()
            png_compression_slider = QSlider(Qt.Horizontal)
            png_compression_slider.setRange(1, 9)
            png_compression_slider.valueChanged.connect(lambda value, d=s, cs=png_compression_slider, cl=png_compression_label, i=item, sb=btn_store_forget: self._on_png_compression_slider_value_changed(value, d, cs, cl, i, sb))
            png_compression_slider.setValue(s["png_compression"])
            png_compression_label.setText(str(s["png_compression"]))
            png_compression_layout.addWidget(png_compression_slider)
            png_compression_layout.addWidget(png_compression_label)
            png_compression_widget.setLayout(png_compression_layout)
            #item.setData(QECols.PNG_COMPRESSION_COLUMN, QERoles.CustomSortRole, str(s["png_compression"]))
            png_settings_page_layout.addWidget(png_compression_widget)
            
            png_settings_page.setLayout(png_settings_page_layout)
            settings_stack.addWidget(png_settings_page)
            
            jpeg_settings_page = QWidget()
            jpeg_settings_page_layout = QHBoxLayout()
            
            jpeg_quality_widget = QWidget()
            jpeg_quality_layout = QHBoxLayout()
            jpeg_quality_label = QLabel()
            jpeg_quality_slider = SnapSlider(5, 0, 100, Qt.Horizontal)
            jpeg_quality_slider.valueChanged.connect(lambda value, d=s, js=jpeg_quality_slider, jl=jpeg_quality_label, i=item, sb=btn_store_forget: self._on_jpeg_quality_slider_value_changed(d, js, jl, i, sb))
            jpeg_quality_slider.setValue(s["jpeg_quality"])
            
            jpeg_quality_label.setText(f"{s['jpeg_quality']}%")
            fm = QFontMetrics(jpeg_quality_label.font())
            pixelsWide = fm.width("100%")
            jpeg_quality_label.setMinimumWidth(pixelsWide)
            jpeg_quality_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            
            jpeg_quality_layout.addWidget(jpeg_quality_slider)
            jpeg_quality_layout.addWidget(jpeg_quality_label)
            jpeg_quality_widget.setLayout(jpeg_quality_layout)
            #item.setData(QECols.JPEG_QUALITY_COLUMN, QERoles.CustomSortRole, str(s["jpeg_quality"]))
            jpeg_settings_page_layout.addWidget(jpeg_quality_widget)
            
            jpeg_settings_page.setLayout(jpeg_settings_page_layout)
            settings_stack.addWidget(jpeg_settings_page)
            
            self.setItemWidget(item, QECols.SETTINGS_COLUMN, settings_stack)
            settings_stack.setCurrentIndex(self.settings_stack_page_order.index(s["ext"]))
            
            btns_widget = QWidget()
            btns_layout = QHBoxLayout()
            btns_export.setDisabled(s["document"] == None)
            btns_export.clicked.connect(lambda checked, d=s, fn=file_path.name, sb=btn_store_forget: self._on_item_btn_export_clicked(checked, d, fn, sb))
            btns_layout.addWidget(btns_export)
            btns_widget.setLayout(btns_layout)
            
            self.setItemWidget(item, QECols.BUTTONS_COLUMN, btns_widget)
            
            outputext_combobox.activated.connect(lambda index, cb=outputext_combobox, ss=settings_stack, d=s, i=item, sb=btn_store_forget: self._on_outputext_combobox_activated(index, cb, ss, d, i, sb))
            
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
        self.show_non_kra_button = QCheckBox("Show non-kra files")
        self.show_non_kra_button.setToolTip("Show export settings for files of usually exported types, such as .png and .jpg. Disabled by default because it's kind of redundant.")
        self.show_non_kra_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_non_kra", "false") == "true" else Qt.Unchecked)
        self.show_non_kra_button.clicked.connect(self._on_show_non_kra_button_clicked)

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

        view_buttons_layout.addWidget(self.show_non_kra_button)
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
        
        options_menu = QMenu()
        options_menu.setToolTipsVisible(True)

        use_custom_icons_action = options_menu.addAction("Use custom icons")
        use_custom_icons_action.setCheckable(True)
        use_custom_icons_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "use_custom_icons", "true") == "true" else Qt.Unchecked)
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
        icons_follow_theme_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "custom_icons_theme", "follow") == "follow" else Qt.Unchecked)

        icons_light_theme_action = options_menu.addAction("Use light theme icons")
        icons_light_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_light_theme_action.setCheckable(True)
        icons_light_theme_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "custom_icons_theme", "follow") == "light" else Qt.Unchecked)

        icons_dark_theme_action = options_menu.addAction("Use dark theme icons")
        icons_dark_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_dark_theme_action.setCheckable(True)
        icons_dark_theme_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "custom_icons_theme", "follow") == "dark" else Qt.Unchecked)

        options_menu.addSeparator()
        
        show_export_name_in_menu_action = options_menu.addAction("Show export name in File menu")
        show_export_name_in_menu_action.setToolTip("When possible, show in the File menu as 'Quick Export to 'myImageName.png'.\n" \
                                                   "Otherwise show as 'Quick Export' only.")
        show_export_name_in_menu_action.setCheckable(True)
        show_export_name_in_menu_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_export_name_in_menu", "true") == "true" else Qt.Unchecked)
        show_export_name_in_menu_action.toggled.connect(self._on_show_export_name_in_menu_action_toggled)
        
        options_menu.addSeparator()

        default_export_unsaved_action = options_menu.addAction("Default export for unsaved images")
        default_export_unsaved_action.setToolTip("Run the normal Krita exporter for not-yet-saved images.\n" \
                                                 "Otherwise don't export, just show a reminder to save the file.")
        default_export_unsaved_action.setCheckable(True)
        default_export_unsaved_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "default_export_unsaved", "false") == "true" else Qt.Unchecked)
        default_export_unsaved_action.toggled.connect(self._on_default_export_unsaved_action_toggled)
        
        options_menu.addSeparator()
        
        use_previous_version_settings_action_group = QActionGroup(options_menu)
        
        use_previous_version_settings_prompt_header = options_menu.addAction("When first exporting a new version of an image:")
        use_previous_version_settings_prompt_header.setDisabled(True)
        
        use_previous_version_settings_copy_action = options_menu.addAction("Always copy settings from previous version")
        use_previous_version_settings_copy_action.setToolTip("Make a copy of the old version settings. Separate export settings will be kept for each version of the image you export.")
        use_previous_version_settings_copy_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_copy_action.setCheckable(True)
        use_previous_version_settings_copy_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "use_previous_version_settings", "replace") == "copy" else Qt.Unchecked)
        use_previous_version_settings_copy_action.triggered.connect(lambda checked: app.writeSetting("TomJK_QuickExport", "use_previous_version_settings", "copy"))
        
        use_previous_version_settings_replace_action = options_menu.addAction("Always replace settings of previous version (Recommended)")
        use_previous_version_settings_replace_action.setToolTip("Replace the old version settings. Only settings for the most recently exported version will be kept.")
        use_previous_version_settings_replace_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_replace_action.setCheckable(True)
        use_previous_version_settings_replace_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "use_previous_version_settings", "replace") == "replace" else Qt.Unchecked)
        use_previous_version_settings_replace_action.triggered.connect(lambda checked: app.writeSetting("TomJK_QuickExport", "use_previous_version_settings", "replace"))
        
        use_previous_version_settings_ignore_action = options_menu.addAction("Always ignore previous versions")
        use_previous_version_settings_ignore_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_ignore_action.setCheckable(True)
        use_previous_version_settings_ignore_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "use_previous_version_settings", "replace") == "ignore" else Qt.Unchecked)
        use_previous_version_settings_ignore_action.triggered.connect(lambda checked: app.writeSetting("TomJK_QuickExport", "use_previous_version_settings", "ignore"))
        
        use_previous_version_settings_ask_action = options_menu.addAction("Always ask")
        use_previous_version_settings_ask_action.setActionGroup(use_previous_version_settings_action_group)
        use_previous_version_settings_ask_action.setCheckable(True)
        use_previous_version_settings_ask_action.setChecked(Qt.Checked if app.readSetting("TomJK_QuickExport", "use_previous_version_settings", "replace") == "ask" else Qt.Unchecked)
        use_previous_version_settings_ask_action.triggered.connect(lambda checked: app.writeSetting("TomJK_QuickExport", "use_previous_version_settings", "ask"))

        options_button.setMenu(options_menu)
        
        # status bar.
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
        dialog_width = int(app.readSetting("TomJK_QuickExport", "dialogWidth", "1024"))
        dialog_height = int(app.readSetting("TomJK_QuickExport", "dialogHeight", "640"))
        self.resize(dialog_width, dialog_height)

    def resizeEvent(self, event):
        app.writeSetting("TomJK_QuickExport", "dialogWidth", str(event.size().width()))
        app.writeSetting("TomJK_QuickExport", "dialogHeight", str(event.size().height()))
    
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
        elif ret == QMessageBox.Save:
            save_settings_to_config()
        
        extension().update_quick_export_display()
        event.accept()

    def _on_show_unstored_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "show_unstored", "true" if checked else "false")
        self.tree.refilter()

    def _on_show_unopened_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "show_unopened", "true" if checked else "false")
        self.tree.refilter()

    def _on_show_non_kra_button_clicked(self, checked):
        app.writeSetting("TomJK_QuickExport", "show_non_kra", "true" if checked else "false")
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

    def _on_use_custom_icons_action_toggled(self, checked):
        app.writeSetting("TomJK_QuickExport", "use_custom_icons", "true" if checked else "false")
        extension().update_action_icons()

    def _on_custom_icons_theme_action_group_triggered(self, action, group):
        app.writeSetting("TomJK_QuickExport", "custom_icons_theme", ["follow","light","dark"][group.actions().index(action)])
        extension().update_action_icons()
    
    def _on_show_export_name_in_menu_action_toggled(self, checked):
        app.writeSetting("TomJK_QuickExport", "show_export_name_in_menu", "true" if checked else "false")
        extension().update_quick_export_display()
    
    def _on_default_export_unsaved_action_toggled(self, checked):
        app.writeSetting("TomJK_QuickExport", "default_export_unsaved", "true" if checked else "false")
        extension().update_quick_export_display()

    def _on_save_button_clicked(self, checked):
        save_settings_to_config()
        self.save_button.setText("Save Settings")
        self.save_button.setIcon(QIcon())
        self.save_button.setDisabled(True)
        self.sbar.showMessage("Settings saved.", 2500)


# TODO: if __main__ etc. to allow running script by itself?
