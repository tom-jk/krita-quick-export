from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar)
from PyQt5.QtCore import Qt, QRegExp, QModelIndex
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor
from pathlib import Path
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita

import xml

exportParameters = InfoObject()

app = Krita.instance()

doc = app.activeDocument()
#print(doc.name())
exportConfig = app.readSetting("", "ExportConfiguration-image/png", "")
ET = xml.etree.ElementTree
root = ET.fromstring(exportConfig)
#print(ET)
for child in root:
    #print(child.tag, child.attrib, child.text)
    #print(child.text)
    value = None
    if child.text in ("true", "false"):
        value = True if child.text == "true" else False
    elif child.text in ("0","1","2","3","4","5","6","7","8","9"):
        value = int(child.text)
    elif child.text.startswith("<!DOCTYPE color>"):
        #print("color")
        color = ManagedColor("RGBA", "U8", "sRGB-elle-V2-srgbtrc.icc")
        #print("->", color)
        color.fromXML(child.text)
        value = color
        #print(value.toXML())
    #print(child.attrib['name'], "=", value)
    exportParameters.setProperty(child.attrib['name'], child.text)
#exportInfo = 
#success = doc.exportImage("/home/thomas/Pictures/export_test.png")
#print(success)

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
        is_stored = index.model().index(index.row(), QECols.STORE_SETTINGS_COLUMN, QModelIndex()).data(QERoles.CustomSortRole) == "1"
        super().paint(painter, option, index)
        if is_stored:
            painter.fillRect(option.rect, QColor(64,128,255,64))

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
    def refilter(self):
        for index, s in enumerate(self.settings):
            #print(index, s["document"])
            self.items[index].setHidden(
                   (show_unstored_button.checkState() == Qt.Unchecked and s["store"] == False)
                or (show_unopened_button.checkState() == Qt.Unchecked and s["document"] == None)
                or (show_png_button.checkState() == Qt.Unchecked and s["path"].suffix == ".png")
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
        tree.setItemWidget(item, QECols.OPEN_FILE_COLUMN, None)
        doc['document'] = new_doc
        doc['doc_index'] = app.documents().index(new_doc)
        item.setData(QECols.OPEN_FILE_COLUMN, QERoles.CustomSortRole, str(doc['doc_index']))
        new_doc.waitForDone()
        item.setIcon(QECols.THUMBNAIL_COLUMN, QIcon(QPixmap.fromImage(new_doc.thumbnail(64,64))))
        export_btn.setDisabled(False)
        print("done")
    
    def _on_output_lineedit_editing_finished(self, doc, lineedit, item):
        doc["output"] = lineedit.text()
        item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, doc["output"].lower())
        #print("_on_output_lineedit_changed ->", doc["output"])
        self.set_settings_modified()
    
    def _on_item_btn_export_clicked(self, checked, doc, filename):
        print(f"Clicked export for {doc['path']}")
        self.sender().setText("Exporting...")
        
        exportParameters = InfoObject()
        exportParameters.setProperty("alpha", doc["alpha"])
        exportParameters.setProperty("compression", int(doc["compression"]))
        exportParameters.setProperty("indexed", True)
        
        export_path = doc["path"].with_name(doc["output"])
        
        doc["document"].setBatchmode(True)
        doc["document"].waitForDone()
        result = doc["document"].exportImage(str(export_path), exportParameters)
        doc["document"].setBatchmode(False)
        
        if not result:
            self.sender().setText("Export failed!")
            sbar.showMessage(f"Export failed", 5000)
        else:
            self.sender().setText("Done!")
            sbar.showMessage(f"Exported to '{str(export_path)}'")
    
    def _on_item_btn_store_forget_clicked(self, checked, btn, doc, filename, item):
        #print("store/forget changed ->", checked, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["store"] = not doc["store"]
        item.setData(QECols.STORE_SETTINGS_COLUMN, QERoles.CustomSortRole, str(+doc["store"]))
        self.redraw()
        self.set_settings_modified()
    
    def _on_alpha_checkbox_state_changed(self, state, doc, item):
        #print("alpha checkbox changed ->", state, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["alpha"] = True if state == Qt.Checked else False
        item.setData(QECols.STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+doc["alpha"]))
        self.set_settings_modified()
    
    def _on_compression_slider_value_changed(self, value, doc, slider, label, item):
        #print("slider value changed ->", value, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["compression"] = value
        item.setData(QECols.COMPRESSION_COLUMN, QERoles.CustomSortRole, str(doc["compression"]))
        label.setText(str(value))
        self.set_settings_modified()
    
    def set_settings_modified(self):
        if not tree_is_ready:
            return
        
        if self.generate_save_string() != app.readSetting("TomJK_QuickExport", "settings", ""):
            if not save_button.isEnabled():
                save_button.setText("Save Settings*")
                save_button.setDisabled(False)
        else:
            if save_button.isEnabled():
                save_button.setText("Save Settings")
                save_button.setDisabled(True)
    
    def load_settings_from_config(self):
        """
        read in settings string from kritarc.
        example: "path=a/b.kra,alpha=false,ouput=b.png;c/d.kra,alpha=true,output=e/f.png"
        becomes: settings[{"document":<obj>, "store":True, "path":"a/b.kra", "alpha":False, "output":"b.png"}, {"document":<obj>, "store":True, "path":"c/d.kra", "alpha":True, "output":"d.png"}]
        """
        # TODO: will break if a filename contains a comma ',' char.
        settings_string = app.readSetting("TomJK_QuickExport", "settings", "")
        #print(f"{settings_string=}")
        
        if settings_string != "":
            settings_as_arrays = [[[y for y in kvpair.split('=', 1)] for kvpair in file.split(',')] for file in settings_string.split(';')]
            #print(f"{settings_as_arrays=}")
            
            #print()
            
            for file_settings in settings_as_arrays:
                #print("found file settings", file_settings)
                self.settings.append({"document":None, "doc_index":1024, "store":True})
                for kvpair in file_settings:
                    if kvpair[0] == "path":
                        self.settings[-1][kvpair[0]] = Path(kvpair[1])
                        for i, d in enumerate(app.documents()):
                            if d.fileName() == kvpair[1]:
                                self.settings[-1]["document"] = d
                                self.settings[-1]["doc_index"] = i
                                break
                    elif kvpair[0] == "alpha":
                        self.settings[-1][kvpair[0]] = True if kvpair[1] == "true" else False
                    elif kvpair[0] == "compression":
                        self.settings[-1][kvpair[0]] = int(kvpair[1])
                    elif kvpair[0] == "output":
                        self.settings[-1][kvpair[0]] = kvpair[1]
                    else:
                        print(f" unrecognised parameter name '{kvpair[0]}'")
                        continue
                    #print(" found", kvpair)
                #print()

            #print(f"{self.settings=}")
            #print()
            for s in self.settings:
                pass#print(s)
    
    def generate_save_string(self):
        save_strings = []
        
        for s in self.settings:
            if not s["store"]:
                continue
            
            save_strings.append(f"path={str(s['path'])},alpha={'true' if s['alpha']==True else 'false'},compression={s['compression']},output={s['output']}")
        
        return ";".join(save_strings)
    
    def save_settings_to_config(self):
        print("save_settings_to_config")
        
        save_string = self.generate_save_string()

        print(f"{save_string=}")
        app.writeSetting("TomJK_QuickExport", "settings", save_string)
        
        save_button.setText("Save Settings")
        save_button.setIcon(QIcon())
        save_button.setDisabled(True)
        sbar.showMessage("Settings saved.", 2500)
    
    def redraw(self):
        for child in self.children():
            if hasattr(child, "update"):
                child.update()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setIndentation(False)
        self.setAlternatingRowColors(True)
        from PyQt5.QtCore import QItemSelectionModel
        self.setSelectionMode(QTreeWidget.NoSelection)
    
    def setup(self):
        self.settings = []
        
        self.load_settings_from_config()
        
        docs = app.documents()
        
        # add default settings for currently open documents that didn't have corresponding stored settings.
        for i, doc in enumerate(docs):
            doc_is_in_settings = False
            if doc.fileName() == "":
                continue
            
            for s in self.settings:
                if s["document"] == doc:
                    doc_is_in_settings = True
                    break
            
            if doc_is_in_settings:
                continue
            
            path = Path(doc.fileName())
            self.settings.append({"document":doc, "doc_index":i, "store":False, "path":path, "alpha":False, "compression":9, "output":path.with_suffix(".png").name})
        
        # TODO: detect if multiple documents have the same filepath.
        # TODO: detect if multiple documents would export to the same output file.
        
        
        self.setColumnCount(QECols.COLUMN_COUNT)
        self.setHeaderLabels(["", "", "", "Filename", "Export to", "", "Compression", "Actions"])
        self.headerItem().setIcon(QECols.STORE_SETTINGS_COLUMN, app.icon('document-save'))
        self.headerItem().setIcon(QECols.STORE_ALPHA_COLUMN, app.icon('transparency-unlocked'))
        self.items = []
        
        # TODO: still need to ensure output filename ends with ".png".
        filename_regex = QRegExp("^[^<>:;,?\"*|/]+$")
        
        longest_output = ""
        for s in self.settings:
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
        
        for s in self.settings:
            file_path = s["path"]
            
            item = MyTreeWidgetItem(self)#QTreeWidgetItem(self)
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
            output_edit.editingFinished.connect(lambda d=s, oe=output_edit, i=item: self._on_output_lineedit_editing_finished(d, oe, i))
            
            output_layout.addWidget(output_edit)
            output_widget.setLayout(output_layout)
            
            self.setItemWidget(item, QECols.OUTPUT_FILENAME_COLUMN, output_widget)
            item.setData(QECols.OUTPUT_FILENAME_COLUMN, QERoles.CustomSortRole, s["output"].lower())
            
            alpha_checkbox = QCheckBox()
            alpha_checkbox.setStyleSheet(checkbox_stylesheet)
            
            alpha_checkbox.setCheckState(Qt.Checked if s["alpha"] else Qt.Unchecked)
            alpha_checkbox.stateChanged.connect(lambda state, d=s, i=item: self._on_alpha_checkbox_state_changed(state, d, i))
            alpha_checkbox_widget = centered_checkbox_widget(alpha_checkbox)
            self.setItemWidget(item, QECols.STORE_ALPHA_COLUMN, alpha_checkbox_widget)
            item.setData(QECols.STORE_ALPHA_COLUMN, QERoles.CustomSortRole, str(+s["alpha"]))
            
            compression_widget = QWidget()
            compression_layout = QHBoxLayout()
            compression_label = QLabel()
            compression_slider = QSlider(Qt.Horizontal)
            compression_slider.setRange(1, 9)
            compression_slider.valueChanged.connect(lambda value, d=s, cs=compression_slider, cl=compression_label, i=item: self._on_compression_slider_value_changed(value, d, cs, cl, i))
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
            btns_export.clicked.connect(lambda checked, d=s, fn=file_path.name: self._on_item_btn_export_clicked(checked, d, fn))
            btns_layout.addWidget(btns_export)
            btns_widget.setLayout(btns_layout)
            
            self.setItemWidget(item, QECols.BUTTONS_COLUMN, btns_widget)
            
            self.items.append(item)
        
        for i in range(0, QECols.COLUMN_COUNT):
            self.resizeColumnToContents(i)

layout = QVBoxLayout()

# TODO: save user changes to tree column sizes and retrieve at each start.
tree_is_ready = False
tree = QETree()
tree.setup()
# TODO: disallow sorting by thumbnail and action button columns.
tree.setSortingEnabled(True)
tree.sortByColumn(QECols.OPEN_FILE_COLUMN, Qt.AscendingOrder)
layout.addWidget(tree)
tree_is_ready = True

def _on_show_unstored_button_clicked(checked):
    app.writeSetting("TomJK_QuickExport", "show_unstored", "true" if checked else "false")
    tree.refilter()

def _on_show_unopened_button_clicked(checked):
    app.writeSetting("TomJK_QuickExport", "show_unopened", "true" if checked else "false")
    tree.refilter()

def _on_show_png_button_clicked(checked):
    app.writeSetting("TomJK_QuickExport", "show_png", "true" if checked else "false")
    tree.refilter()

buttons = QWidget()
buttons_layout = QHBoxLayout()

# show unstored button.
show_unstored_button = QCheckBox("Show unstored")
show_unstored_button.setToolTip("Enable this to pick the images you're interested in exporting, then disable it to hide the rest.")
show_unstored_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_unstored", "true") == "true" else Qt.Unchecked)
show_unstored_button.clicked.connect(_on_show_unstored_button_clicked)
buttons_layout.addWidget(show_unstored_button)

# show unopened button.
show_unopened_button = QCheckBox("Show unopened")
show_unopened_button.setToolTip("Show the export settings of every file - currently open or not - for which settings have been saved.")
show_unopened_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_unopened", "true") == "true" else Qt.Unchecked)
show_unopened_button.clicked.connect(_on_show_unopened_button_clicked)
buttons_layout.addWidget(show_unopened_button)

# show .png files button.
show_png_button = QCheckBox("Show .png files")
show_png_button.setToolTip("Show export settings for .png files. Disabled by default because it's kind of redundant.")
show_png_button.setCheckState(Qt.Checked if app.readSetting("TomJK_QuickExport", "show_png", "false") == "true" else Qt.Unchecked)
show_png_button.clicked.connect(_on_show_png_button_clicked)
buttons_layout.addWidget(show_png_button)

# save button.
save_button = QPushButton("Save Settings")
save_button.setDisabled(True)
save_button.clicked.connect(tree.save_settings_to_config)
buttons_layout.addWidget(save_button)

buttons.setLayout(buttons_layout)
layout.addWidget(buttons)

tree.refilter()

# status bar.
sbar = QStatusBar()
sbar_ready_label = QLabel(" Ready.") # extra space to align with showmessage.
sbar.insertWidget(0, sbar_ready_label)
layout.addWidget(sbar)

# TODO: gracefully handle multiple open documents of the same file.
#       ideally, the settings controls for those docs would mirror each
#       other (ie. checking store alpha for one checks it for all).
#       next best: the store buttons for those docs would become radio
#       buttons so the user can choose one copy's settings to be saved.
#       on next run of the dialog, the saved settings woulb be applied
#       to each doc of that file.
#       I had some notes here about the pitfalls of trying to keep track
#       of which doc was the chosen 'source of truth' between dialogs,
#       before realising you don't need to do that: each dialog starts
#       with all of the same doc having the same settings as read from
#       config (in line with expectations: only one had the store button
#       checked), so it doesn't matter which one gets chosen.

class QEDialog(QDialog):
    def resizeEvent(self, event):
        app.writeSetting("TomJK_QuickExport", "dialogWidth", str(event.size().width()))
        app.writeSetting("TomJK_QuickExport", "dialogHeight", str(event.size().height()))
    
    def closeEvent(self, event):
        if save_button.isEnabled():
            msgBox = QMessageBox(self)
            msgBox.setText("There are unsaved changes to export settings.")
            msgBox.setInformativeText("Do you want to save your changes?")
            msgBox.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msgBox.setDefaultButton(QMessageBox.Save)
            ret = msgBox.exec()
            if ret == QMessageBox.Save:
                tree.save_settings_to_config()
            elif ret == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()

# create dialog  and show it
newDialog = QEDialog() 
newDialog.setLayout(layout)
newDialog.setWindowTitle("Quick Export")
dialog_width = int(app.readSetting("TomJK_QuickExport", "dialogWidth", "1024"))
dialog_height = int(app.readSetting("TomJK_QuickExport", "dialogHeight", "640"))
newDialog.resize(dialog_width, dialog_height)
newDialog.exec_() # show the dialog
