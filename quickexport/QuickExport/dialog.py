from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox)
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap
from pathlib import Path
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

class MyButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)

class MyTreeWidget(QTreeWidget):
    
    THUMBNAIL_COLUMN = 0
    SOURCE_FILENAME_COLUMN = 1
    OUTPUT_FILENAME_COLUMN = 2
    STORE_ALPHA_COLUMN = 3
    COMPRESSION_COLUMN = 4
    BUTTONS_COLUMN = 5
    
    def _on_output_lineedit_editing_finished(self, doc, lineedit):
        doc["output"] = lineedit.text()
        print("_on_output_lineedit_changed ->", doc["output"])
        self.write_settings_for_doc(doc)
    
    def _on_item_btn_export_clicked(self, checked, doc, filename):
        #print("I, button of", filename, "was clicked!", checked, self.sender().objectName())
        print(f"Clicked export for {doc['path']}")
        self.sender().setText("Exporting...")
        
        exportParameters = InfoObject()
        exportParameters.setProperty("alpha", True if doc["alpha"] == "true" else False)
        exportParameters.setProperty("compression", int(doc["compression"]))
        exportParameters.setProperty("indexed", True)
        
        export_path = doc["path"].with_name(doc["output"])
        
        doc["document"].setBatchmode(True)
        doc["document"].waitForDone()
        result = doc["document"].exportImage(str(export_path), exportParameters)
        doc["document"].setBatchmode(False)
        
        if result == False:
            self.sender().setText("Export failed!")
            sbar.showMessage(f"Export failed")
        else:
            self.sender().setText("Done!")
            sbar.showMessage(f"Exported to '{str(export_path)}'")
    
    def _on_item_btn_forget_clicked(self, checked, doc, filename):
        # TODO: can't actually delete settings from kritarc with python api.
        #       possible workarounds: store each files settings with number index instead of file path,
        #       or store all settings in a big string that can be edited freely.
        #print("I, button of", filename, "was clicked!", checked, self.sender().objectName())
        print(f"Clicked forget for {doc['path']}")
        app.writeSetting("TomJK_QuickExport", str(doc["path"]), "")
    
    def _on_alpha_checkbox_state_changed(self, state, doc):
        print("alpha checkbox changed ->", state, "for doc", doc["document"].fileName())
        doc["alpha"] = "true" if state == Qt.Checked else "false"
        self.write_settings_for_doc(doc)
    
    def _on_compression_slider_value_changed(self, value, doc, slider, label):
        print("slider value changed ->", value, "for doc", doc["document"].fileName())
        doc["compression"] = str(value)
        self.write_settings_for_doc(doc)
        label.setText(str(value))
    
    def read_settings_for_doc(self, doc):
        file_path = doc["path"]
        default_string = "alpha=false,compression=9,output="+doc["path"].with_suffix(".png").name
        settings_string = app.readSetting("TomJK_QuickExport", str(doc["path"]), default_string) or default_string
        #print(f"{settings_string=}")
        settings = [[y.strip() for y in x.split('=', 1)] for x in settings_string.split(',')]
        for kvpair in settings:
            if kvpair[0] not in ("alpha", "compression", "output"):
                print(f"unrecognised parameter name '{kvpair[0]}'")
                continue
            doc[kvpair[0]] = kvpair[1]
    
    def write_settings_for_doc(self, doc):
        file_path = doc["path"]
        app.writeSetting("TomJK_QuickExport", str(file_path), f"alpha={doc['alpha']},compression={doc['compression']},output={doc['output']}")
    
    def __init__(self, parent=None):
        super().__init__(parent)
        app = krita.Krita.instance()
        
        self.setColumnCount(6)
        self.setHeaderLabels(["", "Filename", "Export to", "", "Compression", "btn"])
        self.headerItem().setIcon(self.STORE_ALPHA_COLUMN, app.icon('transparency-unlocked'))
        self.items = []
        self.documents = [{"document":doc, "path":Path(doc.fileName())} for doc in app.documents() if doc.fileName()!=""]
        
        # TODO: still need to ensure output filename ends with ".png".
        filename_regex = QRegExp("^[^<>:;,?\"*|/]+$")
        
        longest_output = ""
        for doc in self.documents:
            output = doc["path"].with_suffix(".png").name
            if len(output) > len(longest_output):
                longest_output = output
        
        for doc in self.documents:
            self.read_settings_for_doc(doc)
            #print(doc)
            
            file_path = doc["path"]
            
            item = QTreeWidgetItem(self)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            
            item.setIcon(self.THUMBNAIL_COLUMN, QIcon(QPixmap.fromImage(doc["document"].thumbnail(64,64))))
            
            item.setText(self.SOURCE_FILENAME_COLUMN, file_path.name)
            
            output_edit = QLineEdit(doc["output"])
            
            input_validator = QRegExpValidator(filename_regex, output_edit)
            output_edit.setValidator(input_validator)
            
            text = longest_output + "PAD"
            fm = QFontMetrics(output_edit.font())
            pixelsWide = fm.width(text)
            output_edit.setMinimumWidth(pixelsWide)
            output_edit.editingFinished.connect(lambda d=doc, oe=output_edit: self._on_output_lineedit_editing_finished(d, oe))
            
            self.setItemWidget(item, self.OUTPUT_FILENAME_COLUMN, output_edit)
            
            alpha_checkbox = QCheckBox()
            alpha_checkbox.setStyleSheet("""
                QCheckBox::indicator:unchecked {
                    border: 1px solid rgba(255,255,255,0.1);
                }
                """)
            
            alpha_checkbox.setCheckState(Qt.Checked if doc["alpha"] == "true" else Qt.Unchecked)
            alpha_checkbox.stateChanged.connect(lambda state, d=doc: self._on_alpha_checkbox_state_changed(state, d))
            self.setItemWidget(item, self.STORE_ALPHA_COLUMN, alpha_checkbox)
            
            compression_widget = QWidget()
            compression_layout = QHBoxLayout()
            compression_slider = QSlider(Qt.Horizontal)
            compression_label = QLabel()
            compression_slider.setRange(1, 9)
            compression_slider.valueChanged.connect(lambda value, d=doc, s=compression_slider, sl=compression_label: self._on_compression_slider_value_changed(value, d, s, sl))
            compression_slider.setValue(int(doc["compression"]))
            compression_layout.addWidget(compression_slider)
            compression_layout.addWidget(compression_label)
            compression_widget.setLayout(compression_layout)
            self.setItemWidget(item, self.COMPRESSION_COLUMN, compression_widget)
            
            btns_widget = QWidget()
            btns_layout = QHBoxLayout()
            btns_export = QPushButton("Export now")
            btns_export.clicked.connect(lambda checked, d=doc, fn=file_path.name: self._on_item_btn_export_clicked(checked, d, fn))
            btns_forget = QPushButton("")
            btns_forget.setIcon(app.icon('edit-delete'))
            btns_forget.setEnabled(False)
            btns_forget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            btns_forget.clicked.connect(lambda checked, d=doc, fn=file_path.name: self._on_item_btn_forget_clicked(checked, d, fn))
            btns_layout.addWidget(btns_export)
            btns_layout.addWidget(btns_forget)
            btns_widget.setLayout(btns_layout)
            
            self.setItemWidget(item, self.BUTTONS_COLUMN, btns_widget)
            
            self.items.append(item)
        
        for i in range(0, 6):
            self.resizeColumnToContents(i)
            
        ned = NoEditDelegate()
        self.setItemDelegateForColumn(self.SOURCE_FILENAME_COLUMN, ned)
        self.setItemDelegateForColumn(self.STORE_ALPHA_COLUMN, ned)

layout = QVBoxLayout()

tree = MyTreeWidget()
layout.addWidget(tree)

from PyQt5.QtWidgets import QStatusBar
sbar = QStatusBar()
sbar.showMessage("Ready.")
layout.addWidget(sbar)

# create dialog  and show it
newDialog = QDialog() 
newDialog.setLayout(layout)
newDialog.setWindowTitle("Quick Export")
newDialog.resize(1024,640)
newDialog.exec_() # show the dialog
