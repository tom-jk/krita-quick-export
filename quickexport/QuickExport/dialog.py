from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate,
                             QSizePolicy, QWidget)
from PyQt5.QtCore import Qt
from pathlib import Path
import krita

class NoEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None

class MyButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)

class MyTreeWidget(QTreeWidget):
    def _on_item_btn_clicked(self, filename, checked):
        print("I, button of", filename, "was clicked!", checked, self.sender().objectName())
    
    def __init__(self, parent=None):
        super().__init__(parent)
        #tree = QTreeWidget()
        self.setColumnCount(5)
        self.setHeaderLabels(["Filename", "Export to", "", "Compression", "btn"])
        self.items = []
        self.item_btns = []
        app = krita.Krita.instance()
        documents = app.documents()
        x = 0
        for doc in documents:
            item = QTreeWidgetItem(self)
            item.setText(0, Path(doc.fileName()).name)
            item.setText(1, Path(doc.fileName()).with_suffix(".png").name)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setCheckState(2, Qt.Unchecked)
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
            self.setItemWidget(item, 3, compression_widget)
            compression_label.setText("9")
            #self.item_btns.append(QPushButton("Export now " + str(x)))
            self.item_btns.append(MyButton("Export now " + str(x)))
            self.item_btns[-1].setObjectName("Export Button " + str(x))
            self.item_btns[-1].clicked.connect(lambda checked, v=x: self._on_item_btn_clicked(v, checked))
            x += 1
            self.setItemWidget(item, 4, self.item_btns[-1])
            self.items.append(item)
        for i in range(0, 5):
            self.resizeColumnToContents(i)
        ned = NoEditDelegate()
        self.setItemDelegateForColumn(0, ned)
        self.setItemDelegateForColumn(2, ned)
        self.headerItem().setIcon(2, app.icon('transparency-unlocked'))

# add button and layout for button
layoutForButtons = QHBoxLayout()
newButton = QPushButton("Press me") 
#layoutForButtons.addWidget(newButton)

#add a checkbox
newCheckbox = QCheckBox()
newCheckbox.setText('I am a checkbox')
#layoutForButtons.addWidget(newCheckbox)

tree = MyTreeWidget()
layoutForButtons.addWidget(tree)

# create dialog  and show it
newDialog = QDialog() 
newDialog.setLayout(layoutForButtons)
newDialog.setWindowTitle("New Dialog Title!")
newDialog.resize(1024,640)
newDialog.exec_() # show the dialog
