from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox)
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap
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

class NoEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None

class QECols(IntEnum):
    THUMBNAIL_COLUMN = 0
    SOURCE_FILENAME_COLUMN = auto()
    OUTPUT_FILENAME_COLUMN = auto()
    STORE_ALPHA_COLUMN = auto()
    COMPRESSION_COLUMN = auto()
    BUTTONS_COLUMN = auto()
    COLUMN_COUNT = auto()

class QETree(QTreeWidget):
    
    def _on_output_lineedit_editing_finished(self, doc, lineedit):
        doc["output"] = lineedit.text()
        print("_on_output_lineedit_changed ->", doc["output"])
    
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
        
        if not Result:
            self.sender().setText("Export failed!")
            sbar.showMessage(f"Export failed", 5000)
        else:
            self.sender().setText("Done!")
            sbar.showMessage(f"Exported to '{str(export_path)}'")
    
    def _on_item_btn_store_forget_clicked(self, checked, btn, doc, filename):
        print(f"{btn=}")
        if not doc["store"]:
            print("store doc with filename:", filename)
            doc["store"] = True
            btn.setIcon(app.icon('edit-delete'))
        else:
            print("forget doc with filename:", filename)
            doc["store"] = False
            btn.setIcon(app.icon('document-save'))
    
    def _on_alpha_checkbox_state_changed(self, state, doc):
        print("alpha checkbox changed ->", state, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["alpha"] = True if state == Qt.Checked else False
    
    def _on_compression_slider_value_changed(self, value, doc, slider, label):
        print("slider value changed ->", value, "for doc", doc["document"].fileName() if doc["document"] else "Untitled")
        doc["compression"] = value
        label.setText(str(value))
    
    def load_settings_from_config(self):
        """
        read in settings string from kritarc.
        example: "path=a/b.kra,alpha=false,ouput=b.png;c/d.kra,alpha=true,output=e/f.png"
        becomes: settings[{"document":<obj>, "store":True, "path":"a/b.kra", "alpha":False, "output":"b.png"}, {"document":<obj>, "store":True, "path":"c/d.kra", "alpha":True, "output":"d.png"}]
        """
        # TODO: will break if a filename contains a comma ',' char.
        settings_string = app.readSetting("TomJK_QuickExport", "settings", "")
        print(f"{settings_string=}")
        
        if settings_string != "":
            settings_as_arrays = [[[y for y in kvpair.split('=', 1)] for kvpair in file.split(',')] for file in settings_string.split(';')]
            print(f"{settings_as_arrays=}")
            
            print()
            
            for file_settings in settings_as_arrays:
                print("found file settings", file_settings)
                self.settings.append({"document":None, "store":True})
                for kvpair in file_settings:
                    if kvpair[0] == "path":
                        self.settings[-1][kvpair[0]] = Path(kvpair[1])
                        for d in app.documents():
                            if d.fileName() == kvpair[1]:
                                self.settings[-1]["document"] = d
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
                    print(" found", kvpair)
                print()

            print(f"{self.settings=}")
            print()
            for s in self.settings:
                print(s)
    
    def save_settings_to_config(self):
        print("save_settings_to_config")
        
        save_strings = []
        
        for s in self.settings:
            if not s["store"]:
                continue
            
            save_strings.append(f"path={str(s['path'])},alpha={'true' if s['alpha']==True else 'false'},compression={s['compression']},output={s['output']}")
        
        save_string = ";".join(save_strings)
        print(f"{save_string=}")
        app.writeSetting("TomJK_QuickExport", "settings", save_string)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setIndentation(False)
        self.setAlternatingRowColors(True)
        
        self.settings = []
        
        self.load_settings_from_config()
        
        # add default settings for currently open documents that didn't have corresponding stored settings.
        for doc in app.documents():
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
            self.settings.append({"document":doc, "store":False, "path":path, "alpha":False, "compression":9, "output":path.with_suffix(".png").name})
        
        # TODO: detect if multiple documents have the same filepath.
        # TODO: detect if multiple documents would export to the same output file.
        
        
        self.setColumnCount(QECols.COLUMN_COUNT)
        self.setHeaderLabels(["", "Filename", "Export to", "", "Compression", "btn"])
        self.headerItem().setIcon(QECols.STORE_ALPHA_COLUMN, app.icon('transparency-unlocked'))
        self.items = []
        
        # TODO: still need to ensure output filename ends with ".png".
        filename_regex = QRegExp("^[^<>:;,?\"*|/]+$")
        
        longest_output = ""
        for s in self.settings:
            output = s["path"].with_suffix(".png").name
            if len(output) > len(longest_output):
                longest_output = output
        
        for s in self.settings:
            file_path = s["path"]
            
            item = QTreeWidgetItem(self)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            
            if s["document"] != None:
                item.setIcon(QECols.THUMBNAIL_COLUMN, QIcon(QPixmap.fromImage(s["document"].thumbnail(64,64))))
            else:
                item.setDisabled(True)
            
            item.setText(QECols.SOURCE_FILENAME_COLUMN, file_path.name)
            
            output_edit = QLineEdit(s["output"])
            output_edit.setStyleSheet("QLineEdit {background: rgba(0,0,0,0);}")
            
            input_validator = QRegExpValidator(filename_regex, output_edit)
            output_edit.setValidator(input_validator)
            
            text = longest_output + "PAD"
            fm = QFontMetrics(output_edit.font())
            pixelsWide = fm.width(text)
            output_edit.setMinimumWidth(pixelsWide)
            output_edit.editingFinished.connect(lambda d=s, oe=output_edit: self._on_output_lineedit_editing_finished(d, oe))
            
            self.setItemWidget(item, QECols.OUTPUT_FILENAME_COLUMN, output_edit)
            
            alpha_checkbox = QCheckBox()
            alpha_checkbox.setStyleSheet("""
                QCheckBox::indicator:unchecked {
                    border: 1px solid rgba(255,255,255,0.1);
                }
                """)
            
            alpha_checkbox.setCheckState(Qt.Checked if s["alpha"] else Qt.Unchecked)
            alpha_checkbox.stateChanged.connect(lambda state, d=s: self._on_alpha_checkbox_state_changed(state, d))
            alpha_checkbox_widget = QWidget()
            alpha_checkbox_layout = QHBoxLayout()
            alpha_checkbox_layout.addStretch()
            alpha_checkbox_layout.addWidget(alpha_checkbox)
            alpha_checkbox_layout.addStretch()
            alpha_checkbox_layout.setContentsMargins(0,0,0,0)
            alpha_checkbox_widget.setLayout(alpha_checkbox_layout)
            self.setItemWidget(item, QECols.STORE_ALPHA_COLUMN, alpha_checkbox_widget)
            
            compression_widget = QWidget()
            compression_layout = QHBoxLayout()
            compression_label = QLabel()
            compression_slider = QSlider(Qt.Horizontal)
            compression_slider.setRange(1, 9)
            compression_slider.valueChanged.connect(lambda value, d=s, cs=compression_slider, cl=compression_label: self._on_compression_slider_value_changed(value, d, cs, cl))
            compression_slider.setValue(s["compression"])
            compression_label.setText(str(s["compression"]))
            compression_layout.addWidget(compression_slider)
            compression_layout.addWidget(compression_label)
            compression_widget.setLayout(compression_layout)
            self.setItemWidget(item, QECols.COMPRESSION_COLUMN, compression_widget)
            
            btns_widget = QWidget()
            btns_layout = QHBoxLayout()
            btns_export = QPushButton("Export now")
            btns_export.clicked.connect(lambda checked, d=s, fn=file_path.name: self._on_item_btn_export_clicked(checked, d, fn))
            btns_store_forget = QPushButton("")
            btns_store_forget.setIcon(app.icon('edit-delete') if s["store"] else app.icon('document-save'))
            #btns_store_forget.setEnabled(False)
            btns_store_forget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            btns_store_forget.clicked.connect(lambda checked, btn=btns_store_forget, d=s, fn=file_path.name: self._on_item_btn_store_forget_clicked(checked, btn, d, fn))
            btns_layout.addWidget(btns_export)
            btns_layout.addWidget(btns_store_forget)
            btns_widget.setLayout(btns_layout)
            
            self.setItemWidget(item, QECols.BUTTONS_COLUMN, btns_widget)
            
            self.items.append(item)
        
        for i in range(0, QECols.COLUMN_COUNT):
            self.resizeColumnToContents(i)
            
        ned = NoEditDelegate()
        self.setItemDelegateForColumn(QECols.SOURCE_FILENAME_COLUMN, ned)
        self.setItemDelegateForColumn(QECols.STORE_ALPHA_COLUMN, ned)

layout = QVBoxLayout()

tree = QETree()
layout.addWidget(tree)

# TODO: make view of list filterable.
buttons = QWidget()
buttons_layout = QHBoxLayout()
show_unstored_button = QCheckBox("Show unstored")
show_unopened_button = QCheckBox("Show unopened")
save_button = QPushButton("Save Settings")
buttons_layout.addWidget(show_unstored_button)
buttons_layout.addWidget(show_unopened_button)
buttons_layout.addWidget(save_button)
buttons.setLayout(buttons_layout)
layout.addWidget(buttons)
save_button.clicked.connect(tree.save_settings_to_config)

from PyQt5.QtWidgets import QStatusBar
sbar = QStatusBar()
sbar_ready_label = QLabel(" Ready.") # extra space to align with showmessage.
sbar.insertWidget(0, sbar_ready_label)
layout.addWidget(sbar)

# create dialog  and show it
newDialog = QDialog() 
newDialog.setLayout(layout)
newDialog.setWindowTitle("Quick Export")
newDialog.resize(1024,640)
newDialog.exec_() # show the dialog
