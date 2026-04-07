from PyQt5.QtWidgets import QWidget, QSizePolicy, QDialog, QFileDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QPushButton, QAbstractItemView, QTreeView, QLabel, QStyledItemDelegate, QStyle, QHeaderView, QToolButton, QGraphicsOpacityEffect
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QPixmap, QImage, QBrush, QPainter, QWindow
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRegExp, QRect
import zipfile
import re
from pathlib import Path
from krita import Krita, InfoObject
app = Krita.instance()

# cleanup if last run bugged.
#app.documents()[1].close()
#STOP

#import sys
#myModulePath='/home/user/Projects/kritaQuickExport/quickexport/QuickExport'
#if myModulePath not in sys.path: sys.path.append(myModulePath)
#import qemacrobuilder.py

# TODO: merge folders and files into one list. are separate currently so files don't create no-settings folder items before
#       the settings for the folder are read (they would be discarded as the folder item already existed).
store = {
    Path("path/with/settings"): {"node_type":"folder", "basic_export_settings":{"file_name_src":"proj", "type":".png", "location":"same"}},
    Path("/home/user/Projects/Game/design/environments"): {"node_type":"folder", "basic_export_settings":{"file_name_src":"proj", "type":".png", "location":"same"}},
    Path("path/to/file"): {"node_type":"base", "basic_export_settings":{"file_name_src":"proj", "type":".png", "location":"same"}},
    Path("path/to/another_file"): {"node_type":"base", "basic_export_settings":{"file_name_src":"proj", "type":".png", "location":"same"}},
    Path("path/with/settings/a_file"): {"node_type":"base", "basic_export_settings":{"file_name_src":"proj", "type":".png", "location":"same"}},
    Path("/home/user/Projects/Game/design/environments/volcanoenv290326"): {"node_type":"base", "basic_export_settings":{"file_name_src":"proj", "type":".png", "location":"same"}},
    Path("/home/user/Projects/Game/design/environments/spanishtown0"): {"node_type":"base", "basic_export_settings":{"file_name_src":"proj", "type":".png", "location":"same"}},
    Path("path/to"): {"node_type":"folder", "basic_export_settings":{"file_name_src":"proj", "type":".jpg", "location":"parsib"}}
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
        #if not index.parent() == model_root.index(): # if not at folder level
        if index.data(PathRole) not in store:
            painter.setOpacity(0.5)
        super().paint(painter, option, index)
        painter.restore()

item_delegate = ItemDelegate()

tree = QTreeView()
dialog_layout.addWidget(tree)


basic_export_settings_container = QWidget()
basic_export_settings_container.setDisabled(True)
basic_export_settings_container_layout = QVBoxLayout(basic_export_settings_container)
basic_export_settings_container.setContentsMargins(0,0,0,0)
basic_export_settings_container_layout.setContentsMargins(0,0,0,0)

basic_export_settings_file_container = QWidget()
basic_export_settings_file_container_layout = QHBoxLayout(basic_export_settings_file_container)
basic_export_settings_file_container.setContentsMargins(0,0,0,0)
basic_export_settings_file_container_layout.setContentsMargins(0,0,0,0)

basic_export_settings_file_name = QComboBox()
basic_export_settings_file_name.addItems(["Project name", "File name", "Custom name"])
basic_export_settings_file_container_layout.addWidget(basic_export_settings_file_name)
basic_export_settings_file_name_custom = QLineEdit("Hello")
sp = basic_export_settings_file_name_custom.sizePolicy()
sp.setRetainSizeWhenHidden(True)
basic_export_settings_file_name_custom.setSizePolicy(sp)
basic_export_settings_file_name_custom.hide()
basic_export_settings_file_container_layout.addWidget(basic_export_settings_file_name_custom)
basic_export_settings_file_type = QComboBox()
basic_export_settings_file_type.addItems([".png", ".jpg", ".jxl"])
basic_export_settings_file_type.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
basic_export_settings_file_container_layout.addWidget(basic_export_settings_file_type)

basic_export_settings_folder_container = QWidget()
basic_export_settings_folder_container_layout = QHBoxLayout(basic_export_settings_folder_container)
basic_export_settings_folder_container.setContentsMargins(0,0,0,0)
basic_export_settings_folder_container_layout.setContentsMargins(0,0,0,0)

basic_export_settings_folder_location = QComboBox()
basic_export_settings_folder_location.addItems(["In same folder", "In subfolder", "As parent sibling", "In parent sibling folder", "In another folder"])
basic_export_settings_folder_location.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
basic_export_settings_folder_container_layout.addWidget(basic_export_settings_folder_location)
basic_export_settings_folder_name = QComboBox()
basic_export_settings_folder_name.addItems(["with project name", "with custom name"])
basic_export_settings_folder_name.hide()
basic_export_settings_folder_container_layout.addWidget(basic_export_settings_folder_name)
basic_export_settings_folder_name_custom = QLineEdit("Hello")
sp = basic_export_settings_folder_name_custom.sizePolicy()
sp.setRetainSizeWhenHidden(True)
basic_export_settings_folder_name_custom.setSizePolicy(sp)
basic_export_settings_folder_name_custom.hide()
basic_export_settings_folder_container_layout.addWidget(basic_export_settings_folder_name_custom)
basic_export_settings_folder_pick_custom = QToolButton()
basic_export_settings_folder_pick_custom.setIcon(app.icon("folder"))
basic_export_settings_folder_pick_custom.hide()
basic_export_settings_folder_container_layout.addWidget(basic_export_settings_folder_pick_custom)

basic_export_settings_output_path = QLabel("")
basic_export_settings_output_path.setWordWrap(True)
basic_export_settings_output_path.setAlignment(Qt.AlignHCenter)

basic_export_settings_container_layout.addWidget(basic_export_settings_file_container)
basic_export_settings_container_layout.addWidget(basic_export_settings_folder_container)
dialog_layout.addWidget(basic_export_settings_container)
dialog_layout.addWidget(basic_export_settings_output_path)

suppress_store_on_widget_edit = False

def update_basic_export_settings_output_path_label():
    sel_rows = tree.selectionModel().selectedRows()
    
    if len(sel_rows) != 1:
        return
    
    index = sel_rows[0]
    index = model.mapToSource(index)
    
    path = index.data(PathRole)#Path(app.activeDocument().fileName())
    item_type = index.data(ItemTypeRole)
    
    name_index = basic_export_settings_file_name.currentIndex()
    custom_name = basic_export_settings_file_name_custom.text()
    file_name = path.stem
    
    if item_type in ("base", "file"):
        folder = path.parent
        base, version = base_stem_and_version_number_for_versioned_file(path)
        print(base, version)
        if item_type == "base":
            file_name = "<FileName>"
    else:
        folder = path
        base, version = ("<ProjectName>", "VERSION")
        file_name = "<FileName>"
    
    output_stem = base if name_index == 0 else file_name if name_index == 1 else custom_name
    
    folder_index = basic_export_settings_folder_location.currentIndex()
    folder_name_index = basic_export_settings_folder_name.currentIndex()
    folder_custom_name = basic_export_settings_folder_name_custom.text()
    
    #folder_name = path.stem if folder_name_index == 0 and folder_index != 4 else folder_custom_name
    folder_name = base if folder_name_index == 0 and folder_index != 4 else folder_custom_name
    
    output_folder = folder if folder_index == 0 else folder / folder_name if folder_index == 1 else folder.parent if folder_index == 2 else folder.parent / folder_name if folder_index == 3 else folder_name
    
    output_extension = basic_export_settings_file_type.currentText()
    
    basic_export_settings_output_path.setText(str(Path(output_folder) / (output_stem + output_extension)))
    
    global suppress_store_on_widget_edit
    if suppress_store_on_widget_edit:
        print("suppressed store on widget edit")
        return
    
    s = store[index.data(PathRole)]["basic_export_settings"]
    s["file_name_src"] = ("proj", "file", "cust")[name_index]
    s["file_name_cust"] = custom_name
    s["type"] = output_extension
    s["location"] = ("same", "sub", "parsib", "parsibdir", "cust")[folder_index]
    s["folder_name_src"] = ("proj", "cust")[folder_name_index]
    s["location_cust"] = folder_custom_name
    
    print("--update_basic_export_settings_output_path_label--")
    for x,y in enumerate(store):
        print(x, y, store[y])
    print("--")

def _on_basic_export_settings_file_name_current_index_changed(index):
    basic_export_settings_file_name_custom.setVisible(index == 2)
    update_basic_export_settings_output_path_label()

basic_export_settings_file_name.currentIndexChanged.connect(_on_basic_export_settings_file_name_current_index_changed)
basic_export_settings_file_name_custom.textChanged.connect(update_basic_export_settings_output_path_label)
basic_export_settings_file_type.currentIndexChanged.connect(update_basic_export_settings_output_path_label)

def _on_basic_export_settings_folder_location_current_index_changed(index):
    basic_export_settings_folder_name.setVisible(index in (1,3))
    basic_export_settings_folder_name_custom.setVisible((index in (1,3) and basic_export_settings_folder_name.currentIndex() == 1) or index == 4)
    basic_export_settings_folder_pick_custom.setVisible(index == 4)
    update_basic_export_settings_output_path_label()

basic_export_settings_folder_location.currentIndexChanged.connect(_on_basic_export_settings_folder_location_current_index_changed)

def _on_basic_export_settings_folder_name_current_index_changed(index):
    #basic_export_settings_folder_name.setVisible(index in (1,3))
    basic_export_settings_folder_name_custom.setVisible(basic_export_settings_folder_location.currentIndex() in (1,3,4) and index == 1)
    update_basic_export_settings_output_path_label()

basic_export_settings_folder_name.currentIndexChanged.connect(_on_basic_export_settings_folder_name_current_index_changed)
basic_export_settings_folder_name_custom.textChanged.connect(update_basic_export_settings_output_path_label)

def _on_basic_export_settings_folder_pick_custom_clicked():
    result = QFileDialog.getExistingDirectory(dialog, "Locate file", str(Path(app.activeDocument().fileName()).parent), QFileDialog.ShowDirsOnly)
    basic_export_settings_folder_name_custom.setText(result)
    update_basic_export_settings_output_path_label()

basic_export_settings_folder_pick_custom.clicked.connect(_on_basic_export_settings_folder_pick_custom_clicked)


def set_basic_export_settings_controls_for_path(path):
    global suppress_store_on_widget_edit
    
    if False:#path not in store:
        basic_export_settings_container.setDisabled(True)
        suppress_store_on_widget_edit = True
        update_basic_export_settings_output_path_label()
        suppress_store_on_widget_edit = False
        return
    
    if path in store:
        s = store[path]["basic_export_settings"]
    else:
        basic_export_settings_container.setDisabled(True)
        inherit_from_path = path.parent / base_stem_and_version_number_for_versioned_file(path)[0]
        if inherit_from_path not in store:
            inherit_from_path = path.parent
            if inherit_from_path not in store:
                basic_export_settings_output_path.setText("")
                return
        s = store[inherit_from_path]["basic_export_settings"]
    
    suppress_store_on_widget_edit = True
    
    basic_export_settings_file_name.setCurrentIndex(("proj", "file", "cust").index(s["file_name_src"]))
    basic_export_settings_file_name_custom.setText(s["file_name_cust"] if "file_name_cust" in s else "")
    basic_export_settings_file_type.setCurrentIndex((".png", ".jpg", ".jxl").index(s["type"]))
    basic_export_settings_folder_location.setCurrentIndex(("same", "sub", "parsib", "parsibdir", "cust").index(s["location"]))
    basic_export_settings_folder_name.setCurrentIndex(("proj", "cust").index(s["folder_name_src"]) if "folder_name_src" in s else 0)
    basic_export_settings_folder_name_custom.setText(s["location_cust"] if "location_cust" in s else "")
    
    print("--set_basic_export_settings_controls_for_path--")
    for x,y in enumerate(store):
        print(x, y, store[y])
    print("--")
    
    update_basic_export_settings_output_path_label()
    
    suppress_store_on_widget_edit = False


tree_icon_size = tree.style().pixelMetric(QStyle.PM_SmallIconSize)

PathRole = Qt.UserRole
ItemTypeRole = Qt.UserRole + 1

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
tree.setAlternatingRowColors(True)
#tree.setModel(source_model)

model_root = source_model.invisibleRootItem()

class TreeButton(QToolButton):
    def __init__(self, role, path, item_type, icon, item=None, item2=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        self.path = path
        self.item_type = item_type
        self.item = item
        self.item2 = item2
        self.setIcon(icon)
        self.setAutoRaise(True)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        print("clicked", self.role, self.path)
        
        global store
        
        if self.role == "del":
            if self.path not in store:
                store[self.path] = {
                    "node_type": self.item_type,
                    "basic_export_settings": {
                        "file_name_src": "proj",
                        "type": ".png",
                        "location": "same"
                    }
                }
                self.setIcon(app.icon("edit-delete"))
                l = self.parent().layout()
                for i in (1,2,4):
                    l.itemAt(i).widget().show()
            else:
                del store[self.path]
                self.setIcon(app.icon("list-add"))
                l = self.parent().layout()
                for i in (1,2,4):
                    l.itemAt(i).widget().hide()
            
            model.dataChanged.emit(self.item.index(), self.item2.index())
            _on_tree_selection_changed(None, None)
        
        elif self.role == "opn":
            doc = app.openDocument(str(self.path))
            
            app.activeWindow().addView(doc)
            doc.waitForDone()
        
        elif self.role == "cfg":
            plugin_dir = Path(app.getAppDataLocation()) / "pykrita" / "QuickExport"

            doc = app.createDocument(2,2,"QuickExportDummyDoc","RGBA","U8","",72.0)
            
            extension = store[self.path]["basic_export_settings"]["type"]
            dummy_file_name = "ExportDummy" + extension
            
            info = InfoObject()
            
            if "type_export_settings" in store[self.path]:
                tes = store[self.path]["type_export_settings"]
                if extension in tes:
                    for k,v in tes[extension].items():
                        info.setProperty(k, v)
            
            for p in info.properties():
                print(p)
            
            result = doc.exportImage(str(plugin_dir / dummy_file_name), info)
            print(result, info.properties())
            
            if result:
                print("BEFORE:")
                print(store[self.path])
                
                if "type_export_settings" not in store[self.path]:
                    store[self.path]["type_export_settings"] = {}
                store[self.path]["type_export_settings"][extension] = info.properties()
                
                print("AFTER:")
                print(store[self.path])

            doc.waitForDone()
            doc.close()
            print(doc)

def add_item_to_tree(parent, path, text, icon, item_type):
    item = QStandardItem()
    item2 = QStandardItem()
    parent.appendRow([item, item2])
    item.setData(path, PathRole)
    item.setData(item_type, ItemTypeRole)
    item.setData(text, Qt.DisplayRole)
    item.setIcon(icon)
    
    global row_height
    buttons_widget = QWidget()
    buttons_layout = QHBoxLayout(buttons_widget)
    buttons_widget.setContentsMargins(0,0,0,0)
    buttons_layout.setContentsMargins(0,0,0,0)
    buttons_layout.setSpacing(0)
    del_button = TreeButton(role="del", path=path, item_type=item_type, icon=app.icon("edit-delete"), item=item, item2=item2)
    row_height = del_button.sizeHint().height()
    cpy_button = TreeButton(role="cpy", path=path, item_type=item_type, icon=app.icon("edit-copy"))
    cfg_button = TreeButton(role="cfg", path=path, item_type=item_type, icon=app.icon("configure"))
    opn_button = TreeButton(role="opn", path=path, item_type=item_type, icon=app.icon("document-open"))
    exp_button = TreeButton(role="exp", path=path, item_type=item_type, icon=app.icon("document-export"))
    sp = del_button.sizePolicy()
    sp.setRetainSizeWhenHidden(True)
    del_button.setSizePolicy(sp)
    cpy_button.setSizePolicy(sp)
    cfg_button.setSizePolicy(sp)
    opn_button.setSizePolicy(sp)
    exp_button.setSizePolicy(sp)
    buttons_layout.addWidget(del_button)
    buttons_layout.addWidget(cpy_button)
    buttons_layout.addWidget(cfg_button)
    buttons_layout.addWidget(opn_button)
    buttons_layout.addWidget(exp_button)
    buttons_layout.addStretch()
    
    if item_type == "file":
        del_button.hide()
        cpy_button.hide()
        cfg_button.hide()
    
    if path not in store or "TEMP" in store[path]:
        del_button.setIcon(app.icon("list-add"))
        cpy_button.hide()
        cfg_button.hide()
        exp_button.hide()
    
    index = model.mapFromSource(item2.index())
    tree.setIndexWidget(index, buttons_widget)
    
    return item

def add_base_to_tree(path):
    print(path)
    folder = path.parent
    folder_item = add_folder_to_tree(folder)
    
    for i in range(folder_item.rowCount()):
        item = folder_item.child(i, 0)
        #print(i, index, folder_item.data(index, PathRole))
        if item.data(PathRole) == path:
            return item
    
    thumb = _make_thumbnail_for_file(path)
    icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
    
    return add_item_to_tree(folder_item, path, path.name, icon, "base")

def add_file_to_tree(path):
    base, version = base_stem_and_version_number_for_versioned_file(path)
    base_item = add_base_to_tree(path.parent / base)
    
    for i in range(base_item.rowCount()):
        item = base_item.child(i, 0)
        #print(i, index, folder_item.data(index, PathRole))
        if item.data(PathRole) == path:
            return item
    
    thumb = _make_thumbnail_for_file(path)
    icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
    
    return add_item_to_tree(base_item, path, path.name, icon, "file")

def add_folder_to_tree(path):
    for i in range(source_model.rowCount()):
        index = source_model.index(i, 0)
        if source_model.data(index, PathRole) == path:
            return source_model.item(i)
    
    return add_item_to_tree(source_model, path, str(path), app.icon("folder"), "folder")

# temporarily add projects currently open in krita to store so they appear in dialog with thumbnails and files.
for doc in app.documents():
    file = Path(doc.fileName())
    base = base_stem_and_version_number_for_versioned_file(file)[0]
    path = file.parent / base
    if not path in store:
        store[path] = {"node_type": "base", "TEMP":True}

for k,v in store.items():
    print(k,":",v)

for path in store:
    if store[path]["node_type"] == "folder":
        item = add_folder_to_tree(path)
    else:
        item = add_base_to_tree(path)
        
        if path.parent.exists():
            sorted_list = sorted(path.parent.glob("*.kra"), key = lambda file: Path(file).stat().st_mtime)
            latest_file = None
            for file in sorted_list:#path.parent.iterdir():
                #if file.suffix != ".kra":
                #    continue
                file_base = base_stem_and_version_number_for_versioned_file(file)[0]
                #print(f"{path.stem=} {file_base=} {path.stem==file_base}")
                if path.stem == file_base:
                    print("add file", file, "for base", path.stem)
                    add_file_to_tree(file)
                    latest_file = file
            if latest_file:
                thumb = _make_thumbnail_for_file(latest_file)
                icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
                item.setIcon(icon)

# remove temporarily added docs from store.
# TODO: 
d = []
for path in store:
    if "TEMP" in store[path]:
        d.append(path)
for path in d:
    del store[path]

#for doc in app.documents():
#    file = Path(doc.fileName())
#    item = add_file_to_tree(file)

add_file_to_tree(Path("path/to/file_001.kra"))
add_file_to_tree(Path("path/to/file_002.kra"))
add_file_to_tree(Path("path/to/file_003.kra"))

def _on_tree_expanded(model_index):
    pass

tree.expanded.connect(_on_tree_expanded)

for i in range(source_model.rowCount()):
    index = model.mapFromSource(source_model.index(i, 0))
    tree.setExpanded(index, True)

def _on_tree_selection_changed(selected, deselected):
    #print(len(selected), "selected", selected)
    #print(len(deselected), "deselected", deselected)
    
    rows = tree.selectionModel().selectedRows()#selected.indexes()
    
    if len(rows) == 1:
        basic_export_settings_container.setDisabled(False)
        
        index = rows[0]
        index = model.mapToSource(index)
        print("_on_tree_selection_changed:", index.row(), index.column(), index.parent(), index.model(), index.data(PathRole))
        set_basic_export_settings_controls_for_path(index.data(PathRole))
    else:
        basic_export_settings_container.setDisabled(True)
        basic_export_settings_output_path.setText("")

tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
tree.selectionModel().selectionChanged.connect(_on_tree_selection_changed)


dialog.resize(512, 640)
dialog.open()
