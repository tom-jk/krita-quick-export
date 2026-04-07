from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeView, QLabel
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRegExp
import zipfile
from pathlib import Path
from krita import *
app = Krita.instance()

#import sys
#myModulePath='/home/user/Projects/kritaQuickExport/quickexport/QuickExport'
#if myModulePath not in sys.path: sys.path.append(myModulePath)
#import qemacrobuilder.py

store = {
    "folders": [
        {"path":Path("path/with/settings")}
    ],
    "files": [
        {"path":Path("path/to/file.kra")},
        {"path":Path("path/to/another_file.kra")},
        {"path":Path("path/with/settings/a_file.kra")}
    ]
}

# borrowed from the Last Documents Docker.
def _make_thumbnail_for_file(path):
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
        thumbnail = app.icon('window-close').pixmap(64,64)#self.thumb_height, self.thumb_height)

    #thumb_size = QSize(int(self.thumb_height*self.devicePixelRatioF()), int(self.thumb_height*self.devicePixelRatioF()))
    #thumbnail = thumbnail.scaled(thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    #thumbnail.setDevicePixelRatio(self.devicePixelRatioF()) # TODO: should do for doc.thumbnail thumbs too?
    #self.apply_thumbnail(item, thumbnail)
    return thumbnail

# from https://www.geeksforgeeks.org/python/pyqt5-how-to-get-cropped-square-image-from-rectangular-image/
def _square_thumbnail(pixmap, size=8):
    image = QImage(pixmap)#.fromData(imgdata, imgtype)

    image.convertToFormat(QImage.Format_ARGB32)

    imgsize = min(image.width(), image.height())
    rect = QRect(
        (image.width() - imgsize) // 2,
        (image.height() - imgsize) // 2,
        imgsize,
        imgsize,
    )
    image = image.copy(rect)

    out_img = QImage(imgsize, imgsize, QImage.Format_ARGB32)
    out_img.fill(Qt.transparent)

    # Create a texture brush and paint a circle
    # with the original image onto
    # the output image:
    brush = QBrush(image)

    # Paint the output image
    painter = QPainter(out_img)
    painter.setBrush(brush)
    painter.setPen(Qt.NoPen)

    # drawing square
    painter.drawRect(0, 0, imgsize, imgsize)

    painter.end()

    # Convert the image to a pixmap and rescale it.
    pr = QWindow().devicePixelRatio()
    pm = QPixmap.fromImage(out_img)
    pm.setDevicePixelRatio(pr)
    size = int(size * pr)
    pm = pm.scaled(size, size, Qt.KeepAspectRatio, 
                               Qt.SmoothTransformation)

    # return back the pixmap data
    return pm

dialog = QDialog()
dialog_layout = QVBoxLayout(dialog)

row_height = -1

class ItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        global row_height
        #print(f"{row_height=}")
        size = super().sizeHint(option, index)
        if row_height != -1:
            size.setHeight(row_height)
        return size
    
    def paint(self, painter, option, index):
        painter.save()
        painter.setOpacity(0.5)
        super().paint(painter, option, index)
        painter.restore()

item_delegate = ItemDelegate()

tree = QTreeView()
dialog_layout.addWidget(tree)

tree_icon_size = tree.style().pixelMetric(QStyle.PM_SmallIconSize)

PathRole = Qt.UserRole

class MySortFilterProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        return True
#        if not filter_kra_only:
#            return True
#        index0 = self.sourceModel().index(source_row, 0, source_parent)
#        data0 = self.sourceModel().data(index0, Qt.UserRole)
#        if data0 == None:
#            print(f"{data0=}")
#            return True
#        print(f"{data0=} {data0.name=} {data0.is_dir()=} {data0.is_file()=}")
#        return data0 != None and (data0.is_dir() or (data0.is_file() and data0.name.endswith((".kra",))))

tree.setItemDelegate(item_delegate)
tree.setUniformRowHeights(True)
source_model = QStandardItemModel(0, 2)
model = MySortFilterProxyModel()
model.setSourceModel(source_model)
tree.setModel(model)
tree.header().setStretchLastSection(False)
tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
#tree.setModel(source_model)

model_root = source_model.invisibleRootItem()

class TreeButton(QToolButton):
    def __init__(self, role, path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        self.path = path
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        print("click", self.role, self.path)

def on_del_button_clicked(path):
    print("del button clicked", path)

def add_item_to_tree(parent, path, text, icon=QIcon()):
    item = QStandardItem()
    item2 = QStandardItem()
    parent.appendRow([item, item2])
    #item.setColumnCount(2)
    item.setData(path, PathRole)
    item.setData(text, Qt.DisplayRole)
    item.setIcon(icon)
    
    global row_height
    buttons_widget = QWidget()
    buttons_layout = QHBoxLayout(buttons_widget)
    buttons_widget.setContentsMargins(0,0,0,0)
    buttons_layout.setContentsMargins(0,0,0,0)
    buttons_layout.setSpacing(0)
    del_button = TreeButton("del", path)#QToolButton()
    row_height = del_button.sizeHint().height()
    del_button.setIcon(app.icon("edit-delete"))
    del_button.setAutoRaise(True)
    #del_button.clicked.connect(lambda: print("clicked del button for", path))
    #del_button.clicked.connect(on_del_button_clicked, path)
    cpy_button = QToolButton()
    cpy_button.setAutoRaise(True)
    cpy_button.setIcon(app.icon("edit-copy"))
    cpy_button.clicked.connect(lambda: print("clicked cpy button for", path))
    opn_button = QToolButton()
    opn_button.setAutoRaise(True)
    opn_button.setIcon(app.icon("document-open"))
    opn_button.clicked.connect(lambda: print("clicked opn button for", path))
    cfg_button = QToolButton()
    cfg_button.setAutoRaise(True)
    cfg_button.setIcon(app.icon("configure"))
    cfg_button.clicked.connect(lambda: print("clicked cfg button for", path))
    exp_button = QToolButton()
    exp_button.setAutoRaise(True)
    exp_button.setIcon(app.icon("document-export"))
    exp_button.clicked.connect(lambda: print("clicked exp button for", path))
    buttons_layout.addWidget(del_button)
    buttons_layout.addWidget(cpy_button)
    buttons_layout.addWidget(opn_button)
    buttons_layout.addWidget(cfg_button)
    buttons_layout.addWidget(exp_button)
    buttons_layout.addStretch()
    #list_wgt2.setIndexWidget(list_model.index(0,1,list_model.indexFromItem(parent)), buttons_widget)
    #tree.setIndexWidget(item.index().siblingAtColumn(1), buttons_widget)
    tree.setIndexWidget(model.mapFromSource(item2.index()), buttons_widget)
    
    return item

def add_base_to_tree(path):
    pass

def add_file_to_tree(path):
    pass

def add_folder_to_tree(path):
    for i in range(source_model.rowCount()):
        index = source_model.index(i, 0)
        if source_model.data(index, PathRole) == path:
            return source_model.item(i)
    
    return add_item_to_tree(source_model, path, str(path), app.icon("folder"))

for doc in app.documents():
    file = Path(doc.fileName())
    folder = file.parent
    print(f"{folder=}")
    
    folder_item = add_folder_to_tree(folder)
    
    thumb = _make_thumbnail_for_file(file)
    icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
    item = add_item_to_tree(folder_item, file, file.name, icon)


for store_item in store["folders"]:
    folder = store_item["path"]
    
    folder_item = add_folder_to_tree(folder)

for store_item in store["files"]:
    file = store_item["path"]
    folder = file.parent

    folder_item = add_folder_to_tree(folder)

    thumb = _make_thumbnail_for_file(file)
    icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
    item = add_item_to_tree(folder_item, file, file.name, icon)


def _on_tree_expanded(model_index):
    pass

tree.expanded.connect(_on_tree_expanded)

tree.expandAll()

dialog.resize(420, 640)
dialog.exec()
