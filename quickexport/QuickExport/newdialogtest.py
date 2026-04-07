from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeView, QLabel, QStyledItemDelegate, QStyle, QHeaderView, QToolButton
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QPixmap, QImage, QBrush, QPainter, QWindow
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRegExp, QRect
import zipfile
import re
from pathlib import Path
from krita import Krita, InfoObject
app = Krita.instance()

#import sys
#myModulePath='/home/user/Projects/kritaQuickExport/quickexport/QuickExport'
#if myModulePath not in sys.path: sys.path.append(myModulePath)
#import qemacrobuilder.py

store = {
    "folders": [
        {"path":Path("path/with/settings")},
        {"path":Path("/home/user/Projects/Game/design/environments")}
    ],
    "files": [
        {"path":Path("path/to/file.kra")},
        {"path":Path("path/to/another_file.kra")},
        {"path":Path("path/with/settings/a_file.kra")},
        {"path":Path("/home/user/Projects/Game/design/environments/volcanoenv290326_001.kra")}
    ]
}

def base_stem_and_version_number_for_versioned_file(file_path, unversioned_version_num=None):
    """
    for file with stem "filename0_000", return ("filename0", 0).
    for file with stem "filename0_003", return ("filename0", 3).
    for file with stem "filename0_003_007", return ("filename0_003", 7).
    if not versioned, eg. "filename0", return ("filename0", unversioned_version_num).
    """
    matches = list(re.finditer("(_[0-9]+)$", file_path.stem))
    base_version_stem = file_path.stem
    match_version_num = unversioned_version_num
    if matches:
        match = matches[0]
        base_version_stem = file_path.stem[:match.start()]
        match_version_num = int(match.group()[1:])
    return base_version_stem, match_version_num

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
        #print(index.row(), index.column(), index.model(), model, source_model, model_root, model.mapToSource(index.parent()), PathRole, model.data(index, PathRole))
        painter.save()
        if not index.parent() == model_root.index(): # if not at folder level
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
    def __init__(self, role, path, icon, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        self.path = path
        self.setIcon(icon)
        self.setAutoRaise(True)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        print("clicked", self.role, self.path)
        
        if self.role == "opn":
            doc = app.openDocument(str(self.path))
            
            app.activeWindow().addView(doc)
            doc.waitForDone()
        
        elif self.role == "cfg":
            plugin_dir = Path(app.getAppDataLocation()) / "pykrita" / "QuickExport"

            doc = app.createDocument(2,2,"QuickExportDummyDoc","RGBA","U8","",72.0)

            info = InfoObject()
            result = doc.exportImage(str(plugin_dir / "ExportDummy.jxl"), info)
            print(result, info.properties())

            doc.waitForDone()
            doc.close()
            print(doc)

def on_del_button_clicked(path):
    print("del button clicked", path)

def add_item_to_tree(parent, path, text, icon=QIcon()):
    item = QStandardItem()
    item2 = QStandardItem()
    parent.appendRow([item, item2])
    item.setData(path, PathRole)
    item.setData(text, Qt.DisplayRole)
    item.setIcon(icon)
    
    global row_height
    buttons_widget = QWidget()
    buttons_layout = QHBoxLayout(buttons_widget)
    buttons_widget.setContentsMargins(0,0,0,0)
    buttons_layout.setContentsMargins(0,0,0,0)
    buttons_layout.setSpacing(0)
    del_button = TreeButton(role="del", path=path, icon=app.icon("edit-delete"))
    row_height = del_button.sizeHint().height()
    cpy_button = TreeButton(role="cpy", path=path, icon=app.icon("edit-copy"))
    opn_button = TreeButton(role="opn", path=path, icon=app.icon("document-open"))
    cfg_button = TreeButton(role="cfg", path=path, icon=app.icon("configure"))
    exp_button = TreeButton(role="exp", path=path, icon=app.icon("document-export"))
    buttons_layout.addWidget(del_button)
    buttons_layout.addWidget(cpy_button)
    buttons_layout.addWidget(opn_button)
    buttons_layout.addWidget(cfg_button)
    buttons_layout.addWidget(exp_button)
    buttons_layout.addStretch()
    tree.setIndexWidget(model.mapFromSource(item2.index()), buttons_widget)
    
    return item

def add_base_to_tree(path):
    pass

def add_file_to_tree(path):
    folder = path.parent
    folder_item = add_folder_to_tree(folder)
    
    for i in range(folder_item.rowCount()):
        item = folder_item.child(i, 0)
        #print(i, index, folder_item.data(index, PathRole))
        if item.data(PathRole) == path:
            return item
    
    thumb = _make_thumbnail_for_file(path)
    icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
    
    return add_item_to_tree(folder_item, path, path.name, icon)

def add_folder_to_tree(path):
    for i in range(source_model.rowCount()):
        index = source_model.index(i, 0)
        if source_model.data(index, PathRole) == path:
            return source_model.item(i)
    
    return add_item_to_tree(source_model, path, str(path), app.icon("folder"))

for doc in app.documents():
    file = Path(doc.fileName())
    item = add_file_to_tree(file)

for store_item in store["folders"]:
    folder = store_item["path"]
    folder_item = add_folder_to_tree(folder)

for store_item in store["files"]:
    file = store_item["path"]
    item = add_file_to_tree(file)

def _on_tree_expanded(model_index):
    pass

tree.expanded.connect(_on_tree_expanded)

tree.expandAll()

dialog.resize(420, 640)
dialog.open()
