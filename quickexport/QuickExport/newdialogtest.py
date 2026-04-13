from PyQt5.QtWidgets import QWidget, QSizePolicy, QDialog, QDialogButtonBox, QMessageBox, QFileDialog, QMenu, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QCheckBox, QPushButton, QAbstractItemView, QTreeView, QLabel, QStyledItemDelegate, QStyle, QHeaderView, QToolButton, QGraphicsOpacityEffect
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QPixmap, QImage, QBrush, QPainter, QWindow
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRegExp, QRect, QTimer
import zipfile
import re
from copy import deepcopy
import platform, os, subprocess
from pathlib import Path
from krita import Krita, InfoObject, FileDialog
app = Krita.instance()

# for testing menu icons.
from PyQt5.QtCore import QCoreApplication
#QCoreApplication.setAttribute(Qt.AA_DontShowIconsInMenus, False)

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

for path in store:
    store[path]["type_export_settings"] = {}

config_clipboard = {}

def add_default_store_for_path(path, item_type):
    store[path] = {
        "node_type": item_type,
        "basic_export_settings": {
            "file_name_src": "proj",
            "type": ".png",
            "location": "same"
        },
        "type_export_settings": {}
    }

# https://stackoverflow.com/a/16204023
def open_folder_in_file_browser(path):
    if not (path.exists() and path.is_dir()):
        print(f"Folder not found at {path}")
        return
    
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

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
        # TODO: make and return only one copy of the not-found icon.
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


class Tree(QTreeView):
    def dropEvent(self, event):
        if event.source() != self:
            return
        
        dropped_on_item = source_model.itemFromIndex(model.mapToSource(self.indexAt(event.pos())))
        
        if not dropped_on_item:
            return
        
        print(f"dropEvent: source: {event.source()}, mimeData.formats: {event.mimeData().formats()}, dropAction: {event.dropAction()}, dropped on: {dropped_on_item.data(PathRole)}")
        
        if dropped_on_item.data(ItemTypeRole) == "file":
            dropped_on_item = dropped_on_item.parent()
            print(f"dropped on file -> project: {dropped_on_item.data(PathRole)}")
        
        if dropped_on_item.data(ItemTypeRole) == "base":
            dropped_on_item = dropped_on_item.parent()
            print(f"dropped on project -> folder: {dropped_on_item.data(PathRole)}")
        
        relocate_rows_in_tree(dropped_on_item.data(PathRole))


tree = Tree()
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
    result = FileDialog.getExistingDirectory(dialog, "Locate folder", str(Path(app.activeDocument().fileName()).parent), "QE_CustomExportFolder")
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
                add_default_store_for_path(self.path, self.item_type)
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

def add_item_to_tree(parent, path, text, icon, item_type, selectable=True):
    item = QStandardItem()
    item2 = QStandardItem()
    parent.appendRow([item, item2])
    item.setData(path, PathRole)
    item.setData(item_type, ItemTypeRole)
    item.setData(text, Qt.DisplayRole)
    item.setIcon(icon)
    item.setSelectable(selectable)
    item2.setSelectable(selectable)
    item.setDropEnabled(selectable)
    item2.setDropEnabled(False)
    
    add_buttons_for_row(path, item_type, item, item2)
    
    return item

def add_buttons_for_row(path, item_type, item, item2):
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
    
    del_button.setObjectName("StoreAddDeleteButton")
    
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

def add_base_to_tree(path):
    #print(path)
    folder = path.parent
    folder_item = add_folder_to_tree(folder)
    
    for i in range(folder_item.rowCount()):
        item = folder_item.child(i, 0)
        #print(i, index, folder_item.data(index, PathRole))
        if item.data(PathRole) == path:
            return item
    
    thumb = _make_thumbnail_for_file(path)
    icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
    
    item = add_item_to_tree(folder_item, path, path.name, icon, "base")
    
    populate_base_item_with_file_items(item, path)

def populate_base_item_with_file_items(item, path=None):
    if not path:
        path = item.data(PathRole)
    
    while item.child(0):
        item.takeRow(0)
    
    latest_file = None
    
    if path.parent.exists():
        sorted_list = sorted(path.parent.glob("*.kra"), key = lambda file: Path(file).stat().st_mtime)
        for file in sorted_list:
            file_base = base_stem_and_version_number_for_versioned_file(file)[0]
            if path.stem == file_base:
                #print("add file", file, "for base", path.stem)
                add_file_to_tree(file)
                latest_file = file
        if latest_file:
            thumb = _make_thumbnail_for_file(latest_file)
            icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
            item.setIcon(icon)
    
    if not latest_file:
        # fallback to file-not-found icon.
        thumb = _make_thumbnail_for_file(path)
        icon = QIcon(_square_thumbnail(thumb, tree_icon_size))
        item.setIcon(icon)

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
    
    return add_item_to_tree(base_item, path, path.name, icon, "file", selectable=False)

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


def _on_tree_custom_context_menu_requested(pos):
    # Defer context menu until after tree selection has updated.
    # otherwise, closing a context menu and reopening one on another item by rapidly right-clicking
    # twice will show the menu with the old selection, both visually and in selection model.
    QTimer.singleShot(0, lambda: _on_tree_custom_context_menu_requested_main(pos))
    
def _on_tree_custom_context_menu_requested_main(pos):
    print("context menu", pos, tree.indexAt(pos), tree.indexAt(pos).data(PathRole))
    
    global config_clipboard
    
    rows = tree.selectionModel().selectedRows()
    
    if len(rows) == 0:
        return
    
    selection_folder_count = 0
    selection_project_count = 0
    selection_contains_children_of_other_selected = False
    print("selected rows:")
    for i, row_index in enumerate(rows):
        #row_source_index = model.mapToSource(row_index)
        if row_index.data(ItemTypeRole) == "folder":
            selection_folder_count += 1
        else:
            selection_project_count += 1
            if row_index.parent() in rows:
                selection_contains_children_of_other_selected = True
        print("   ",i,":", row_index.data(PathRole))    
    
    print(f"Selection contains {selection_folder_count} Folders and {selection_project_count} Projects.")
    if selection_contains_children_of_other_selected:
        print("Some selected projects are inside folders that are also selected.")
    
    index = tree.indexAt(pos)
    print(index.row(), index.column(), index.data(PathRole), index.data(ItemTypeRole), index.model())
    
    path = index.data(PathRole)
    item_type = index.data(ItemTypeRole)
    
    if not path:
        return
    
    menu = QMenu(dialog)
    ac_add_folder = ac_add_project = ac_relocate = ac_remove = ac_add_all_projects_in_folder = ac_remove_unconfigured_in_folder = ac_show_in_file_browser = None
    ac_copy_config = ac_paste_config = None
    if len(rows) == 1:
        ac_add_folder = menu.addAction("Add folder...")
        ac_add_project = menu.addAction("Add project...")
        if item_type == "folder":
            menu.addSeparator()
            ac_add_all_projects_in_folder = menu.addAction("Add all projects in folder")
            ac_remove_unconfigured_in_folder = menu.addAction("Remove unconfigured projects")
            menu.addSeparator()
            ac_show_in_file_browser = menu.addAction("Show in file browser")
        menu.addSeparator()
    ac_copy_config = menu.addAction(app.icon("edit-copy"), "Copy")
    ac_paste_config = menu.addAction(app.icon("edit-paste"), "Paste")
    if not (len(rows) == 1 and path in store):
        ac_copy_config.setDisabled(True)
    if not config_clipboard:
        ac_paste_config.setDisabled(True)
    menu.addSeparator()
    if item_type != "file":
        ac_relocate = menu.addAction("Relocate...")
        menu.addSeparator()
        ac_remove = menu.addAction(app.icon("list-remove"), "Remove")
    
    result = menu.exec(tree.viewport().mapToGlobal(pos))
    
    if not result:
        return
    
    folder_path = path if item_type == "folder" else path.parent
    
    if result == ac_add_folder:
        _on_add_folder_action_triggered(start_path = folder_path, force_use_start_path = True)
        
    elif result == ac_add_project:
        _on_add_project_action_triggered(start_path = folder_path, force_use_start_path = True)
        
    elif result == ac_add_all_projects_in_folder:
        if not folder_path.exists():
            print(f"Folder not found at {path}")
            return

        sorted_list = sorted(folder_path.glob("*.kra"), key = lambda file: Path(file).stat().st_mtime)
        for file in sorted_list:
            file_base = base_stem_and_version_number_for_versioned_file(file)[0]
            if not file_base.endswith(".kra-autosave"):
                add_base_to_tree(folder_path / file_base)
    
    elif result == ac_remove_unconfigured_in_folder:
        row_item = source_model.itemFromIndex(model.mapToSource(rows[0]))
        for child_idx in reversed(range(row_item.rowCount())):
            child = row_item.child(child_idx)
            child_path = child.data(PathRole)
            if child_path in store:
                continue
            model.removeRow(child.row(), rows[0])
    
    elif result == ac_show_in_file_browser:
        open_folder_in_file_browser(folder_path)
    
    elif result == ac_copy_config:
        config_clipboard = deepcopy(store[path])
        #print(store[path])
        print(f"copied from {path}:")
        print(config_clipboard)
    
    elif result == ac_paste_config:
        print("- - - - -")
        print("ac_paste_config start")
        
        paste_dialog = PasteDialog(dialog)
        paste_settings = paste_dialog.run()
        
        if not paste_settings:
            return
        
        #for k,v in store.items():
        #    print("  ",k,":",v)
        
        cc = config_clipboard
        
        for row_index in rows:
            source_index = model.mapToSource(row_index)
            
            path = source_index.data(PathRole)
            
            if path not in store:
                # add to store first.
                source_index2 = source_index.siblingAtColumn(source_index.column()+1)
                index2 = model.mapFromSource(source_index2)
                btns = tree.indexWidget(index2)
                del_btn = btns.findChild(TreeButton, "StoreAddDeleteButton")
                del_btn.click()
            
            print(f"paste to {path}")
            bes = store[path]["basic_export_settings"]
            ccbes = cc["basic_export_settings"]
            if paste_settings["name"]:
                #print(" - paste name settings")
                bes["file_name_src"] = ccbes["file_name_src"]
                bes["file_name_cust"] = ccbes["file_name_cust"] if "file_name_cust" in ccbes else ""
            if paste_settings["type"]:
                #print(" - paste type setting")
                bes["type"] = ccbes["type"]
            if paste_settings["location"]:
                #print(" - paste location settings")
                bes["location"] = ccbes["location"]
                bes["folder_name_src"] = ccbes["folder_name_src"] if "folder_name_src" in ccbes else "proj"
                bes["location_cust"] = ccbes["location_cust"] if "location_cust" in ccbes else ""
            if paste_settings["export_settings"]:
                for ext in paste_settings["type_export_settings"]:
                    if paste_settings["type_export_settings"][ext] and ext in cc["type_export_settings"]:
                        #print(f" - paste {ext} export config")
                        store[path]["type_export_settings"][ext] = deepcopy(cc["type_export_settings"][ext])
            #store[path] = deepcopy(config_clipboard)
            
        _on_tree_selection_changed(None, None)
            
        #for k,v in store.items():
        #    print("  ",k,":",v)
            
        print("ac_paste_config end")
        print("- - - - -")
    
    elif result == ac_relocate:
        
        start_path = folder_path
        while not start_path.exists():
            start_path = start_path.parent
            if start_path == Path():
                start_path = Path.home()
                break
        
        if (target_folder_path := Path(FileDialog.getExistingDirectory(dialog, "Locate folder", str(start_path)))) == Path():
            return
        
        relocate_rows_in_tree(target_folder_path, rows)
        
    elif result == ac_remove:
        print("- - - - -")
        print("ac_remove start")
        
        for k,v in store.items():
            print("  ",k,":",v)
            
        # gather items to be removed, excluding projects inside folders that are being removed, as they'll be removed with the folder anyway.
        print("building list of rows to remove...")
        row_items = []
        for row_index in rows:
            row_item = source_model.itemFromIndex(model.mapToSource(row_index))
            if row_index.data(ItemTypeRole) == "folder":
                print(f" - add folder {row_index.data(PathRole)}.")
                row_items.append(row_item)
            else:
                if not row_index.parent() in rows:
                    print(f" - add project {row_index.data(PathRole)}.")
                    row_items.append(row_item)
        
        print("removing...")
        for item in row_items:
            path = item.data(PathRole)
            item_type = item.data(ItemTypeRole)
            if item_type == "folder":
                for child_idx in range(item.rowCount()):
                    child = item.child(child_idx)
                    child_path = child.data(PathRole)
                    print(f" - {child_path=}")
                    if child_path in store:
                        del store[child_path]
            print(f" - {path=}")
            model.removeRow(item.row(), model.mapFromSource((item.parent() or source_model.invisibleRootItem()).index()))
            if path in store:
                del store[path]
        
        print("done")
        for k,v in store.items():
            print("  ",k,":",v)
        print("ac_remove end")
        print("- - - - -")

class PasteDialog(QDialog):
    last_used = {"name":False, "type":False, "location":False, "export_settings":True, "type_export_settings":{}}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from PyQt5.QtWidgets import QGroupBox, QHBoxLayout

        layout = QVBoxLayout(self)
        
        print(f"{self.last_used=}")
        
        self.cb_name = QCheckBox("Name")
        self.cb_name.setCheckState(Qt.Checked if self.last_used["name"] else Qt.Unchecked)
        layout.addWidget(self.cb_name)
        
        self.cb_type = QCheckBox("Type")
        self.cb_type.setCheckState(Qt.Checked if self.last_used["type"] else Qt.Unchecked)
        layout.addWidget(self.cb_type)
        
        self.cb_location = QCheckBox("Location")
        self.cb_location.setCheckState(Qt.Checked if self.last_used["location"] else Qt.Unchecked)
        layout.addWidget(self.cb_location)
        
        cb_export_layout = QHBoxLayout()
        self.cb_export = QCheckBox("Export settings")
        self.cb_export.setCheckState(Qt.Checked if self.last_used["export_settings"] else Qt.Unchecked)
        cb_export_layout.addWidget(self.cb_export)
        cb_export_layout.addStretch()
        cb_export_none = QToolButton()
        cb_export_none.setAutoRaise(True)
        cb_export_none.setText("none")
        cb_export_layout.addWidget(cb_export_none)
        cb_export_all = QToolButton()
        cb_export_all.setAutoRaise(True)
        cb_export_all.setText("all")
        cb_export_layout.addWidget(cb_export_all)
        layout.addLayout(cb_export_layout)
        
        self.cb_type_frame = QGroupBox()
        cb_type_layout = QVBoxLayout(self.cb_type_frame)
        self.cb_ext = {}
        global config_clipboard
        clipboard_has_any_type_settings = False
        for ext in (".png", ".jpg", ".jxl"):
            if not ext in self.last_used["type_export_settings"]:
                self.last_used["type_export_settings"][ext] = True
            if ext in config_clipboard["type_export_settings"]:
                clipboard_has_any_type_settings = True
                self.cb_ext[ext] = QCheckBox(ext)
                self.cb_ext[ext].setCheckState(Qt.Checked if self.last_used["type_export_settings"][ext] else Qt.Unchecked)
                cb_type_layout.addWidget(self.cb_ext[ext])
        layout.addWidget(self.cb_type_frame)
        
        if not clipboard_has_any_type_settings:
            self.cb_type_frame.hide()
            self.cb_export.setEnabled(False)
            cb_export_none.setEnabled(False)
            cb_export_all.setEnabled(False)
        
        self.cb_type_frame.setEnabled(self.cb_export.checkState() == Qt.Checked)
        
        self.cb_export.stateChanged.connect(self._on_export_settings_checkbox_state_changed)
        
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(dialog_buttons)
        
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        
        cb_export_none.clicked.connect(self._on_export_settings_none_button_clicked)
        cb_export_all.clicked.connect(self._on_export_settings_all_button_clicked)
    
    def _on_export_settings_checkbox_state_changed(self, state):
        self.cb_type_frame.setEnabled(state == Qt.Checked)
    
    def _on_export_settings_none_button_clicked(self):
        for cb in self.cb_ext.values():
            cb.setCheckState(Qt.Unchecked)
    
    def _on_export_settings_all_button_clicked(self):
        for cb in self.cb_ext.values():
            cb.setCheckState(Qt.Checked)
    
    def run(self):
        if self.exec() == QDialog.Rejected:
            return None
        
        self.last_used["name"] = self.cb_name.checkState() == Qt.Checked
        self.last_used["type"] = self.cb_type.checkState() == Qt.Checked
        self.last_used["location"] = self.cb_location.checkState() == Qt.Checked
        self.last_used["export_settings"] = self.cb_export.checkState() == Qt.Checked
        
        for ext,cb in self.cb_ext.items():
            self.last_used["type_export_settings"][ext] = cb.checkState() == Qt.Checked
        
        return self.last_used

def relocate_rows_in_tree(target_folder_path, rows=None):
    print("- - - - -")
    print("relocate_rows_in_tree: start")
    
    for k,v in store.items():
        print("  ",k,":",v)

    if not rows:
        rows = tree.selectionModel().selectedRows()
    
    target_folder_exists_in_tree = False
    for i in range(source_model.rowCount()):
        check_index = source_model.index(i, 0)
        if source_model.data(check_index, PathRole) == target_folder_path:
            target_folder_exists_in_tree = True
            target_folder_item = source_model.itemFromIndex(check_index)
            break
    
    # gather items to be moved, excluding projects inside folders that are being moved, as they'll be moved with the folder anyway.
    # also exclude the target folder item and its children if for some reason they're also selected.
    row_items = []
    for row_index in rows:
        row_item = source_model.itemFromIndex(model.mapToSource(row_index))
        if row_index.data(ItemTypeRole) == "folder":
            if row_index.data(PathRole) == target_folder_path:
                continue
            row_items.append(row_item)
        else:
            if not row_index.parent() in rows:
                row_items.append(row_item)
    
    for selected_row_item in row_items:
        path = selected_row_item.data(PathRole)
        item_type = selected_row_item.data(ItemTypeRole)
        print("- -")
        print(f"relocating {path} to {target_folder_path}")
        
        selected_row_index = selected_row_item.index()
    
        if not target_folder_exists_in_tree:
            print("Target folder item doesn't exist in tree yet.")
            target_folder_exists_in_tree = True
            if item_type == "folder":
                print("This folder item will become the target folder item.")
                change_store_path_for_item(selected_row_item, target_folder_path)
                selected_row_item2_source_index = source_model.sibling(selected_row_item.row(), selected_row_item.column()+1, selected_row_index)
                selected_row_item2_index = model.mapFromSource(selected_row_item2_source_index)
                tree.setIndexWidget(selected_row_item2_index, None)
                add_buttons_for_row(selected_row_item.data(PathRole), selected_row_item.data(ItemTypeRole), selected_row_item, source_model.itemFromIndex(selected_row_item2_source_index))
                for child_idx in range(selected_row_item.rowCount()):
                    child_item = selected_row_item.child(child_idx)
                    change_store_path_for_item(child_item, target_folder_path)
                    populate_base_item_with_file_items(child_item, child_item.data(PathRole))
                target_folder_item = selected_row_item
                continue
            else:
                print("A new target folder item will be added to tree.")
                target_folder_item = add_folder_to_tree(target_folder_path)
                tree.setExpanded(model.mapFromSource(target_folder_item.index()), True)
    
        if item_type == "folder":
            print("Projects in this folder will be moved to the target folder item.")
            while selected_row_item.child(0):
                reparent_base_row_in_tree(selected_row_item, 0, target_folder_item, target_folder_path)
        else:
            print("This project will be moved to the target folder item.")
            reparent_base_row_in_tree(selected_row_item.parent(), selected_row_item.row(), target_folder_item, target_folder_path)
    
    print("done")
    for k,v in store.items():
        print("  ",k,":",v)
    print("relocate_rows_in_tree: end")
    print("- - - - -")

def reparent_base_row_in_tree(source_parent_item, source_child_index, target_parent, target_folder_path): 
    row_items = source_parent_item.takeRow(source_child_index)
    change_store_path_for_item(row_items[0], target_folder_path)
    target_parent.appendRow(row_items)
    add_buttons_for_row(row_items[0].data(PathRole), row_items[0].data(ItemTypeRole), *row_items)
    populate_base_item_with_file_items(row_items[0])#, row_new_path)

def change_store_path_for_item(item, target_folder_path):
    old_path = item.data(PathRole)
    item_type = item.data(ItemTypeRole)
    new_path = target_folder_path / old_path.name if item_type != "folder" else target_folder_path
    if old_path in store:
        store_temp_copy = store[old_path]
        del store[old_path]
        store[new_path] = store_temp_copy
    if item_type == "folder":
        item.setData(str(new_path), Qt.DisplayRole)
    item.setData(new_path, PathRole)

tree.setContextMenuPolicy(Qt.CustomContextMenu)
tree.customContextMenuRequested.connect(_on_tree_custom_context_menu_requested)

tree.setDragEnabled(True)
tree.setAcceptDrops(True)

add_button = QToolButton()
add_button.setIcon(app.icon("list-add"))
add_button.setPopupMode(QToolButton.InstantPopup)

add_button_menu = QMenu()
add_folder_action = add_button_menu.addAction("Add folder...")
add_project_action = add_button_menu.addAction("Add project...")
add_button.setMenu(add_button_menu)

def _on_add_folder_action_triggered(start_path = None, force_use_start_path = False):
    start_path = start_path or Path(app.activeDocument().fileName()).parent
    print("add folder at start_path =", start_path)
    result = FileDialog.getExistingDirectory(dialog, "Locate folder", str(start_path), "QE_AddFolderToTree" if not force_use_start_path else None)
    if not result:
        return
    item = add_folder_to_tree(Path(result))

def _on_add_project_action_triggered(start_path = None, force_use_start_path = False):
    start_path = start_path or Path(app.activeDocument().fileName()).parent
    print("add project at start_path =", start_path)

    file = FileDialog.getOpenFileName(dialog, "locate file", str(start_path), "Krita document (*.kra)", None, "QE_AddProjectToTree" if not force_use_start_path else None)
    print(f"{file=}")
    if not file:
        return
    file = Path(file)
    base = base_stem_and_version_number_for_versioned_file(file)[0]
    path = file.parent / base
    item = add_base_to_tree(path)

add_folder_action.triggered.connect(_on_add_folder_action_triggered)
add_project_action.triggered.connect(_on_add_project_action_triggered)

dialog_layout.addWidget(add_button)

dialog.resize(512, 640)
dialog.open()
