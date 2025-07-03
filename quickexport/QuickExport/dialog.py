from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate,
                             QSizePolicy, QWidget)
from PyQt5.QtCore import Qt
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
print(ET)
for child in root:
    #print(child.tag, child.attrib, child.text)
    #print(child.text)
    value = None
    if child.text in ("true", "false"):
        value = True if child.text == "true" else False
    elif child.text in ("0","1","2","3","4","5","6","7","8","9"):
        value = int(child.text)
    elif child.text.startswith("<!DOCTYPE color>"):
        print("color")
        color = ManagedColor("RGBA", "U8", "sRGB-elle-V2-srgbtrc.icc")
        print("->", color)
        color.fromXML(child.text)
        value = color
        print(value.toXML())
    print(child.attrib['name'], "=", value)
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
    
    SOURCE_FILENAME_COLUMN = 0
    OUTPUT_FILENAME_COLUMN = 1
    STORE_ALPHA_COLUMN = 2
    COMPRESSION_COLUMN = 3
    BUTTONS_COLUMN = 4
    
    def _on_item_btn_clicked(self, filename, checked):
        print("I, button of", filename, "was clicked!", checked, self.sender().objectName())
    
    def __init__(self, parent=None):
        super().__init__(parent)
        app = krita.Krita.instance()
        
        self.setColumnCount(5)
        self.setHeaderLabels(["Filename", "Export to", "", "Compression", "btn"])
        self.headerItem().setIcon(self.STORE_ALPHA_COLUMN, app.icon('transparency-unlocked'))
        self.items = []
        self.item_btns = []
        self.documents = app.documents()
        
        x = 0
        for doc in self.documents:
            file_path = Path(doc.fileName())
            
            setting_string = app.readSetting("TomJK_QuickExport", str(file_path), "alpha=false,compression=9")
            settings = [[y.strip() for y in x.split('=')] for x in setting_string.split(',')]
            settings_dict = {"alpha":True, "compression":9}
            for kvpair in settings:
                #print(kvpair)
                settings_dict[kvpair[0]] = kvpair[1]
            print(settings_dict)
            #print(settings)
            #alpha = True if (settings[0].split('='))
            #alpha = setting
            #app.writeSetting("TomJK_QuickExport", str(file_path), "alpha=true,compression=9")
            
            item = QTreeWidgetItem(self)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            
            item.setText(self.SOURCE_FILENAME_COLUMN, file_path.name)
            
            item.setText(self.OUTPUT_FILENAME_COLUMN, file_path.with_suffix(".png").name)
            
            item.setCheckState(self.STORE_ALPHA_COLUMN, Qt.Unchecked)
            
            compression_widget = QWidget()
            compression_layout = QHBoxLayout()
            compression_slider = QSlider(Qt.Horizontal)
            compression_label = QLabel()
            compression_slider.setValue(9)
            compression_slider.setRange(1, 9)
            compression_slider.valueChanged.connect(lambda value, s=compression_slider, sl=compression_label: sl.setText(str(value)))
            compression_layout.addWidget(compression_slider)
            compression_layout.addWidget(compression_label)
            compression_widget.setLayout(compression_layout)
            compression_label.setText("9")
            self.setItemWidget(item, self.COMPRESSION_COLUMN, compression_widget)
            
            #self.item_btns.append(QPushButton("Export now " + str(x)))
            self.item_btns.append(MyButton("Export now " + str(x)))
            self.item_btns[-1].setObjectName("Export Button " + str(x))
            self.item_btns[-1].clicked.connect(lambda checked, v=x: self._on_item_btn_clicked(v, checked))
            x += 1
            self.setItemWidget(item, self.BUTTONS_COLUMN, self.item_btns[-1])
            
            self.items.append(item)
        
        for i in range(0, 5):
            self.resizeColumnToContents(i)
            
        ned = NoEditDelegate()
        self.setItemDelegateForColumn(self.SOURCE_FILENAME_COLUMN, ned)
        self.setItemDelegateForColumn(self.STORE_ALPHA_COLUMN, ned)
        
        for i in self.items:
            print(i)

layout = QHBoxLayout()

tree = MyTreeWidget()
layout.addWidget(tree)

# create dialog  and show it
newDialog = QDialog() 
newDialog.setLayout(layout)
newDialog.setWindowTitle("Quick Export")
newDialog.resize(1024,640)
newDialog.exec_() # show the dialog
