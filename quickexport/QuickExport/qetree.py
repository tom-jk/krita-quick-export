from PyQt5.QtWidgets import (QWidget, QSizePolicy, QDialog, QDialogButtonBox, QMessageBox, QFileDialog,
                             QMenu, QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox, QLineEdit, QCheckBox,
                             QPushButton, QAbstractItemView, QTreeView, QLabel, QStyledItemDelegate,
                             QStyle, QHeaderView, QToolButton, QGraphicsOpacityEffect, QApplication)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QPixmap, QImage, QBrush, QPainter, QWindow
from PyQt5.QtCore import Qt, QModelIndex, QSortFilterProxyModel, QRegExp, QRect, QTimer, QItemSelection
import zipfile
import re
from copy import deepcopy
from pathlib import Path
from krita import Krita, InfoObject, FileDialog
from .utils import *
app = Krita.instance()

tree_icon_size = QApplication.style().pixelMetric(QStyle.PM_SmallIconSize)


# borrowed from the Last Documents Docker.
def _make_thumbnail_for_file(path):
    if not str2bool(readSetting("show_thumbnails_for_unopened")):
        if path.exists():
            thumbnail = app.icon('view-preview').pixmap(64,64)
        else:
            thumbnail = app.icon('window-close').pixmap(64,64)
        return thumbnail
    
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


class PasteDialog(QDialog):
    last_used = {"overwrite_only":True, "name":False, "type":False, "location":False, "scale":False, "export_settings":True, "type_export_settings":{}}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QVBoxLayout(self)
        
        print(f"{self.last_used=}")
        
        self.cb_name = QCheckBox("Name settings")
        self.cb_name.setToolTip("Exported file name source and custom name.")
        self.cb_name.setCheckState(Qt.Checked if self.last_used["name"] else Qt.Unchecked)
        layout.addWidget(self.cb_name)
        
        self.cb_type = QCheckBox("Type")
        self.cb_type.setToolTip("Active export type.")
        self.cb_type.setCheckState(Qt.Checked if self.last_used["type"] else Qt.Unchecked)
        layout.addWidget(self.cb_type)
        
        self.cb_location = QCheckBox("Location settings")
        self.cb_location.setToolTip("Location, folder name source, custom name and custom path.")
        self.cb_location.setCheckState(Qt.Checked if self.last_used["location"] else Qt.Unchecked)
        layout.addWidget(self.cb_location)
        
        self.cb_scale = QCheckBox("Scale settings")
        self.cb_scale.setToolTip("Whether scaling is enabled, and scale side, size and units, proportions constraint and filter strategy.")
        self.cb_scale.setCheckState(Qt.Checked if self.last_used["scale"] else Qt.Unchecked)
        layout.addWidget(self.cb_scale)
        
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
        clipboard_has_any_type_settings = False
        for ext in supported_extensions():
            if not ext in self.last_used["type_export_settings"]:
                self.last_used["type_export_settings"][ext] = True
            if ext[1:] in config_clipboard["default"]["export"]:
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
        
        self.bg_overwrite_only = QButtonGroup(self)
        rb_overwrite_only_off = QRadioButton("Create settings if they don't exist")
        rb_overwrite_only_on = QRadioButton("Paste over existing settings only")
        
        self.bg_overwrite_only.addButton(rb_overwrite_only_off, 0)
        self.bg_overwrite_only.addButton(rb_overwrite_only_on, 1)
        
        rb_overwrite_only_off.setChecked(self.last_used["overwrite_only"] == False)
        rb_overwrite_only_on.setChecked(self.last_used["overwrite_only"] == True)
        
        cb_type_layout.addWidget(rb_overwrite_only_off)
        cb_type_layout.addWidget(rb_overwrite_only_on)
        
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
        
        self.last_used["overwrite_only"] = self.bg_overwrite_only.checkedId() == 1
        self.last_used["name"] = self.cb_name.checkState() == Qt.Checked
        self.last_used["type"] = self.cb_type.checkState() == Qt.Checked
        self.last_used["location"] = self.cb_location.checkState() == Qt.Checked
        self.last_used["scale"] = self.cb_scale.checkState() == Qt.Checked
        self.last_used["export_settings"] = self.cb_export.checkState() == Qt.Checked
        
        for ext,cb in self.cb_ext.items():
            self.last_used["type_export_settings"][ext] = cb.checkState() == Qt.Checked
        
        print(self.last_used)
        return self.last_used


class TreeButton(QToolButton):
    def __init__(self, role, path, item_type, icon, item=None, item2=None, tree=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        self.path = path
        self.item_type = item_type
        self.item = item
        self.item2 = item2
        self.tree = tree
        self.setIcon(icon)
        self.setAutoRaise(True)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        print("clicked", self.role, self.path)
        
        if self.role == "del":
            if self.path not in qe_settings:
                qe_settings[self.path] = default_settings(path=self.path, node_type=self.item_type)
                # ~ qe_settings[self.path]["config_file_index"] = 0
                #add_default_store_for_path(self.path, self.item_type)
                self.setIcon(app.icon("edit-delete"))
                l = self.parent().layout()
                l.itemAt(1).widget().show()
            else:
                del qe_settings[self.path]
                self.setIcon(app.icon("list-add"))
                l = self.parent().layout()
                l.itemAt(1).widget().hide()
            
            self.item.model().dataChanged.emit(self.item.index(), self.item2.index())
            self.tree.selectionModel().selectionChanged.emit(QItemSelection(), QItemSelection())
        
        elif self.role == "opn":
            if self.item_type == QEItemType.FOLDER:
                open_folder_in_file_browser(self.path)
            else:
                path = self.path
                if self.item_type == QEItemType.PROJECT:
                    if self.item.rowCount() > 0:
                        item_of_latest_file = self.item.child(self.item.rowCount()-1)
                        path = item_of_latest_file.data(PathRole)
                
                if (doc := app.openDocument(str(path))):
                    app.activeWindow().addView(doc)
                    doc.waitForDone()
        
        elif self.role == "cfg":
            extension = qe_settings[self.path]["basic"]["ext"]
            
            if extension in configless_extensions():
                self.tree.requestShowMessage.emit(f"Exports to {extension} don't require a config.", 2000)
                return
            
            ext_key = extension[1:]
            
            if ext_key in config_aliases():
                ext_key = config_aliases()[ext_key]
            
            plugin_dir = Path(app.getAppDataLocation()) / "pykrita" / "QuickExport"

            doc = app.createDocument(2,2,"QuickExportDummyDoc","RGBA","U8","",72.0)
            
            dummy_file_name = "ExportDummy" + extension
            
            info = InfoObject()
            
            s_export = qe_settings[self.path]["export"]
            if ext_key in s_export:
                for k,v in s_export[ext_key].items():
                    info.setProperty(k, v)
            
            result = doc.exportImage(str(plugin_dir / dummy_file_name), info)
            print(f"{result=}, {info=}, {info.properties()=}")
            
            if result:
                #print("BEFORE:")
                #print(qe_settings[self.path])
                
                qe_settings[self.path]["export"][ext_key] = info.properties()
                
                #print("AFTER:")
                #print(qe_settings[self.path])
                
                self.item.model().dataChanged.emit(self.item.index(), self.item2.index())

            doc.waitForDone()
            doc.close()
            print(doc)


row_height = -1

class ItemDelegate(QStyledItemDelegate):
    """
        QModelIndex: source model index of item.
        QStandardItem: the renamed item.
        str: new name.
    """
    commitItemRename = pyqtSignal(QModelIndex, QStandardItem, str)
    
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
        if index.data(PathRole) not in qe_settings:
            painter.setOpacity(0.5)
        super().paint(painter, option, index)
        painter.restore()
    
    def setModelData(self, editor, model, index):
        print(f"setModelData {editor=} {model=} {index=}")
        
        source_model = model.sourceModel()
        
        source_index = model.mapToSource(index)
        item = source_model.itemFromIndex(source_index)
        
        old_text = item.data(Qt.DisplayRole)
        new_text = editor.text()
        
        if new_text == "":
            return
        
        print(f"{old_text=} {new_text=}")
        
        if not index.data(PathRole):
            return
        
        item_type = index.data(ItemTypeRole)
        if old_text == new_text or (item_type == QEItemType.FOLDER and Path(new_text) == index.data(PathRole)):
            print("no change.")
            return
        
        if item_type == QEItemType.FOLDER:
            if str(Path(new_text).resolve()) != new_text:
                print("tried to set folder path containing '.' or '..' parts, or which was not an absolute path, which isn't allowed.")
                return
        else:
            if len(Path(new_text).parts) > 1:
                print("tried to set project name to a path, which isn't allowed.")
                return
        
        self.commitItemRename.emit(source_index, item, new_text)


class MySortFilterProxyModel(QSortFilterProxyModel):
    def setIncludedFolders(self, paths):
        self.includedFolders_ = paths
    
    def includedFolders(self):
        if hasattr(self, "includedFolders_"):
            return self.includedFolders_
        return None
    
    def filterAcceptsRow(self, source_row, source_parent):
        #print(f"{self.includedFolders()=}")
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        path = source_model.data(index, PathRole)
        #print(f"{sp}{source_row=} {source_parent=} {source_parent.model()=} {path=}")
        item_type = source_model.data(index, ItemTypeRole)
        
        if not path:
            return False
        
        if (folders := self.includedFolders()):
            folder = path if item_type == QEItemType.FOLDER else path.parent
            if folder not in folders:
                print(f" {path} was not displayed.")
                return False
        
        if not self.filterRegExp().pattern():
            return True
        
        matched = self.filterRegExp().indexIn(str(path))
        #print(f"{sp} filterAcceptsRow: pattern={self.filterRegExp().pattern()}, {matched=} (length {self.filterRegExp().matchedLength()})")
    
        if (type(matched) == int and matched > -1) or (type(matched) == bool and matched): # handles fixedstring or wildcard filtering.
            return True
    
        if self.filterRegExp().matchedLength() > 0:
            return True
        
        return False


class QETree(QTreeView):
    requestConfigWidgetsRefreshForPath = pyqtSignal(Path)
    requestAddFolderAtPath = pyqtSignal(Path)
    requestAddProjectAtPath = pyqtSignal(Path)
    requestShowMessage = pyqtSignal(str, int)
    addingFolder = pyqtSignal(Path)
    removingFolder = pyqtSignal(Path)
    
    def setup(self):
        item_delegate = ItemDelegate()
        self.setItemDelegate(item_delegate)
        item_delegate.commitItemRename.connect(self._on_delegate_commit_item_rename)
        self.setUniformRowHeights(True)
        self.source_model = QStandardItemModel(0, 2)
        self.model = MySortFilterProxyModel()
        self.model.setSourceModel(self.source_model)
        self.model.setFilterRole(PathRole)
        self.model.setFilterKeyColumn(0)
        self.model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.model.setRecursiveFilteringEnabled(True)
        self.setModel(self.model)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)

        model_root = self.source_model.invisibleRootItem()

        for path in qe_settings:
            if qe_settings[path]["node_type"] == QEItemType.FOLDER:
                item = self.add_folder_to_tree(path)
            else:
                item = self.add_base_to_tree(path)
        
        for doc in app.documents():
            file = Path(doc.fileName())
            print(file, file.suffix)
            if not file:
                continue
            if not file.suffix == ".kra":
                continue
            base = base_stem_and_version_number_for_versioned_file(file)[0]
            path = file.parent / base
            item = self.add_base_to_tree(path)

        for i in range(self.source_model.rowCount()):
            index = self.model.mapFromSource(self.source_model.index(i, 0))
            self.setExpanded(index, True)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_custom_context_menu_requested)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)

    def dropEvent(self, event):
        if event.source() != self:
            return
        
        dropped_on_source_index = self.model.mapToSource(self.indexAt(event.pos()))
        if dropped_on_source_index.column() != 0:
            dropped_on_source_index = dropped_on_source_index.siblingAtColumn(0)
        dropped_on_item = self.source_model.itemFromIndex(dropped_on_source_index)
        
        if not dropped_on_item:
            return
        
        print(f"dropEvent: source: {event.source()}, mimeData.formats: {event.mimeData().formats()}, dropAction: {event.dropAction()}, dropped on: {dropped_on_item.data(PathRole)}")
        
        if dropped_on_item.data(ItemTypeRole) == QEItemType.FILE:
            dropped_on_item = dropped_on_item.parent()
            print(f"dropped on file -> project: {dropped_on_item.data(PathRole)}")
        
        if dropped_on_item.data(ItemTypeRole) == QEItemType.PROJECT:
            dropped_on_item = dropped_on_item.parent()
            print(f"dropped on project -> folder: {dropped_on_item.data(PathRole)}")
        
        self.relocate_rows_in_tree(dropped_on_item.data(PathRole))

    def add_item_to_tree(self, parent, path, text, icon, item_type, selectable=True):
        item = QStandardItem()
        item2 = QStandardItem()
        parent.appendRow([item, item2])
        item.setData(path, PathRole)
        item.setData(item_type, ItemTypeRole)
        item.setData(text, Qt.DisplayRole)
        item.setIcon(icon)
        item.setSelectable(selectable)
        item2.setSelectable(False)#selectable)
        item.setEditable(selectable)
        item2.setEditable(False)
        item.setDropEnabled(selectable)
        item2.setDropEnabled(False)
        
        self.add_buttons_for_row(path, item_type, item, item2)
        
        return item

    def add_buttons_for_row(self, path, item_type, item, item2):
        global row_height
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_widget.setContentsMargins(0,0,0,0)
        buttons_layout.setContentsMargins(0,0,0,0)
        buttons_layout.setSpacing(0)
        del_button = TreeButton(role="del", path=path, item_type=item_type, icon=app.icon("edit-delete"), item=item, item2=item2, tree=self)
        row_height = del_button.sizeHint().height()
        cfg_button = TreeButton(role="cfg", path=path, item_type=item_type, icon=app.icon("configure"), item=item, item2=item2, tree=self)
        exp_button = TreeButton(role="exp", path=path, item_type=item_type, icon=app.icon("document-export"))
        opn_button = TreeButton(role="opn", path=path, item_type=item_type, icon=app.icon("document-open"), item=item, item2=item2)
        sp = del_button.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        for btn in del_button, cfg_button, opn_button:
            btn.setSizePolicy(sp)
            buttons_layout.addWidget(btn)
        buttons_layout.addStretch()
        
        del_button.setObjectName("StoreAddDeleteButton")
        
        if item_type == QEItemType.FILE:
            del_button.hide()
            cfg_button.hide()
        
        if path not in qe_settings:
            del_button.setIcon(app.icon("list-add"))
            cfg_button.hide()
            exp_button.hide()
        
        index = self.model.mapFromSource(item2.index())
        self.setIndexWidget(index, buttons_widget)

    def add_base_to_tree(self, path):
        #print(path)
        folder = path.parent
        folder_item = self.add_folder_to_tree(folder)
        
        for i in range(folder_item.rowCount()):
            item = folder_item.child(i, 0)
            #print(i, index, folder_item.data(index, PathRole))
            if item.data(PathRole) == path:
                return item
        
        thumb = _make_thumbnail_for_file(path)
        icon = QIcon(square_thumbnail(thumb, tree_icon_size))
        
        item = self.add_item_to_tree(folder_item, path, path.name, icon, QEItemType.PROJECT)
        
        self.populate_base_item_with_file_items(item, path)

    def populate_base_item_with_file_items(self, item, path=None):
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
                    self.add_file_to_tree(file)
                    latest_file = file
            if latest_file:
                thumb = _make_thumbnail_for_file(latest_file)
                icon = QIcon(square_thumbnail(thumb, tree_icon_size))
                item.setIcon(icon)
        
        if not latest_file:
            # fallback to file-not-found icon.
            thumb = _make_thumbnail_for_file(path)
            icon = QIcon(square_thumbnail(thumb, tree_icon_size))
            item.setIcon(icon)

    def add_file_to_tree(self, path):
        base = base_stem_and_version_number_for_versioned_file(path)[0]
        base_item = self.add_base_to_tree(path.parent / base)
        
        for i in range(base_item.rowCount()):
            item = base_item.child(i, 0)
            #print(i, index, folder_item.data(index, PathRole))
            if item.data(PathRole) == path:
                return item
        
        thumb = _make_thumbnail_for_file(path)
        icon = QIcon(square_thumbnail(thumb, tree_icon_size))
        
        return self.add_item_to_tree(base_item, path, path.name, icon, QEItemType.FILE, selectable=False)

    def add_folder_to_tree(self, path):
        for i in range(self.source_model.rowCount()):
            index = self.source_model.index(i, 0)
            if self.source_model.data(index, PathRole) == path:
                return self.source_model.item(i)
        
        self.addingFolder.emit(path)
        return self.add_item_to_tree(self.source_model, path, str(path), app.icon("folder"), QEItemType.FOLDER)

    def _on_custom_context_menu_requested(self, pos):
        # Defer context menu until after tree selection has updated.
        # otherwise, closing a context menu and reopening one on another item by rapidly right-clicking
        # twice will show the menu with the old selection, both visually and in selection model.
        QTimer.singleShot(0, lambda: self._on_custom_context_menu_requested_main(pos))
        
    def _on_custom_context_menu_requested_main(self, pos):
        print("context menu", pos, self.indexAt(pos), self.indexAt(pos).data(PathRole))
        
        dialog = self.window()
        
        rows = self.selectionModel().selectedRows()
        
        if len(rows) == 0:
            return
        
        selection_folder_count = 0
        selection_project_count = 0
        selection_contains_stored_paths = False
        selection_contains_children_of_other_selected = False
        print("selected rows:")
        for i, row_index in enumerate(rows):
            if row_index.data(PathRole) in qe_settings:
                selection_contains_stored_paths = True
            if row_index.data(ItemTypeRole) == QEItemType.FOLDER:
                selection_folder_count += 1
            else:
                selection_project_count += 1
                if row_index.parent() in rows:
                    selection_contains_children_of_other_selected = True
            print("   ",i,":", row_index.data(PathRole))    
        
        print(f"Selection contains {selection_folder_count} Folders and {selection_project_count} Projects.")
        if selection_contains_children_of_other_selected:
            print("Some selected projects are inside folders that are also selected.")
        
        index = self.indexAt(pos)
        print(index.row(), index.column(), index.data(PathRole), index.data(ItemTypeRole), index.model())
        
        path = index.data(PathRole)
        item_type = index.data(ItemTypeRole)
        
        if not path:
            return
        
        #print(f"{qe_settings=}")
        #print(f"{config_clipboard=}")
        
        menu = QMenu(dialog)
        ac_add_folder = ac_add_project = ac_relocate = ac_remove = ac_add_all_projects_in_folder = ac_remove_unconfigured_in_folder = ac_show_in_file_browser = None
        ac_copy_config = ac_paste_config = ac_prune = None
        if len(rows) == 1:
            ac_add_folder = menu.addAction("Add folder...")
            ac_add_project = menu.addAction("Add project...")
            if item_type == QEItemType.FOLDER:
                menu.addSeparator()
                ac_add_all_projects_in_folder = menu.addAction("Add all projects in folder")
                ac_remove_unconfigured_in_folder = menu.addAction("Remove unconfigured projects")
                menu.addSeparator()
                ac_show_in_file_browser = menu.addAction("Show in file browser")
            menu.addSeparator()
        ac_copy_config = menu.addAction(app.icon("edit-copy"), "Copy")
        ac_paste_config = menu.addAction(app.icon("edit-paste"), "Paste...")
        if not (len(rows) == 1 and path in qe_settings):
            ac_copy_config.setDisabled(True)
        if not config_clipboard["default"]:
            ac_paste_config.setDisabled(True)
        menu.addSeparator()
        if item_type != QEItemType.FILE:
            ac_relocate = menu.addAction("Relocate...")
            menu.addSeparator()
            if selection_contains_stored_paths:
                ac_prune = menu.addAction("Prune export settings...")
            ac_remove = menu.addAction(app.icon("list-remove"), "Remove")
        
        result = menu.exec(self.viewport().mapToGlobal(pos))
        
        if not result:
            return
        
        folder_path = path if item_type == QEItemType.FOLDER else path.parent
        
        if result == ac_add_folder:
            self.requestAddFolderAtPath.emit(folder_path)
            
        elif result == ac_add_project:
            self.requestAddProjectAtPath.emit(folder_path)
            
        elif result == ac_add_all_projects_in_folder:
            if not folder_path.exists():
                print(f"Folder not found at {path}")
                return

            sorted_list = sorted(folder_path.glob("*.kra"), key = lambda file: Path(file).stat().st_mtime)
            for file in sorted_list:
                file_base = base_stem_and_version_number_for_versioned_file(file)[0]
                if not file_base.endswith(".kra-autosave"):
                    self.add_base_to_tree(folder_path / file_base)
        
        elif result == ac_remove_unconfigured_in_folder:
            row_item = self.source_model.itemFromIndex(self.model.mapToSource(rows[0]))
            for child_idx in reversed(range(row_item.rowCount())):
                child = row_item.child(child_idx)
                child_path = child.data(PathRole)
                if child_path in qe_settings:
                    continue
                self.model.removeRow(child.row(), rows[0])
        
        elif result == ac_show_in_file_browser:
            open_folder_in_file_browser(folder_path)
        
        elif result == ac_copy_config:
            config_clipboard["default"] = deepcopy(qe_settings[path])
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
            
            cc = config_clipboard["default"]
            
            for row_index in rows:
                source_index = self.model.mapToSource(row_index)
                
                path = source_index.data(PathRole)
                
                if path not in qe_settings:
                    # add to store first.
                    source_index2 = source_index.siblingAtColumn(source_index.column()+1)
                    index2 = self.model.mapFromSource(source_index2)
                    btns = self.indexWidget(index2)
                    del_btn = btns.findChild(TreeButton, "StoreAddDeleteButton")
                    del_btn.click()
                
                print(f"paste to {path}")
                bes = qe_settings[path]["basic"]
                ccbes = cc["basic"]
                if paste_settings["name"]:
                    #print(" - paste name settings")
                    bes["file_name_source"] = ccbes["file_name_source"]
                    bes["file_name_custom"] = ccbes["file_name_custom"]
                if paste_settings["type"]:
                    #print(" - paste type setting")
                    bes["ext"] = ccbes["ext"]
                if paste_settings["location"]:
                    #print(" - paste location settings")
                    bes["location"] = ccbes["location"]
                    bes["location_name_source"] = ccbes["location_name_source"]
                    bes["location_name_custom"] = ccbes["location_name_custom"]
                    bes["location_custom"] = ccbes["location_custom"]
                if paste_settings["scale"]:
                    #print(" - paste scale settings")
                    bes["scale"] = ccbes["scale"]
                    bes["scale_side"] = ccbes["scale_side"]
                    bes["scale_width"] = ccbes["scale_width"]
                    bes["scale_width_mode"] = ccbes["scale_width_mode"]
                    bes["scale_height"] = ccbes["scale_height"]
                    bes["scale_height_mode"] = ccbes["scale_height_mode"]
                    bes["scale_keep_aspect"] = ccbes["scale_keep_aspect"]
                    bes["scale_filter"] = ccbes["scale_filter"]
                if paste_settings["export_settings"]:
                    overwrite_only = paste_settings["overwrite_only"]
                    for ext in paste_settings["type_export_settings"]:
                        if paste_settings["type_export_settings"][ext] and ext[1:] in cc["export"]:
                            if overwrite_only and ext[1:] not in qe_settings[path]["export"]:
                                continue
                            #print(f" - paste {ext} export config")
                            qe_settings[path]["export"][ext[1:]] = deepcopy(cc["export"][ext[1:]])
            
            #self._on_selection_changed(None, None)
            # TODO: this is badly done (indeces passes to dataChanged must all have same parent; that's not guaranteed here).
            self.source_model.dataChanged.emit(rows[0], rows[-1])
            self.requestConfigWidgetsRefreshForPath.emit(path)
                
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
            
            self.relocate_rows_in_tree(target_folder_path, rows)
            
        elif result == ac_prune:
            prune_msgbox_details = []
            settings_to_delete = []
            for row_index in rows:
                path = row_index.data(PathRole)
                if not path in qe_settings:
                    continue
                row_active_type = qe_settings[path]["basic"]["ext"]
                row_es = qe_settings[path]["export"]
                if not row_es:
                    continue
                row_unused_types = []
                for ext in row_es:
                    if "." + ext != row_active_type:
                        settings_to_delete.append({"path":path, "ext":ext})
                        row_unused_types.append(ext)
                if not row_unused_types:
                    continue
                prune_msgbox_details.append(f"{path}: {', '.join(row_unused_types)}")
            if not prune_msgbox_details:
                QMessageBox.information(dialog, "Prune export settings", "There are no unused export settings on the selected items to delete.")
                return
            prune_msgbox = QMessageBox(QMessageBox.Question,
                                       "Prune export settings",
                                       "For each selected item, export settings for file types other than the active export type will be deleted.",
                                       QMessageBox.Ok | QMessageBox.Cancel,
                                       dialog
            )
            prune_msgbox.setDetailedText("Settings to be deleted:\n" + "\n".join(prune_msgbox_details))
            if prune_msgbox.exec() != QMessageBox.Ok:
                return
            
            print("pruning export settings...")
            
            for setting_to_delete in settings_to_delete:
                path = setting_to_delete["path"]
                ext = setting_to_delete["ext"]
                print(f" - deleting {ext} from {path}")
                del qe_settings[path]["export"][ext]
                if f"config_export_{ext}_string" in qe_settings[path]:
                    del qe_settings[path][f"config_export_{ext}_string"]
            
            # TODO: this is badly done (indeces passes to dataChanged must all have same parent; that's not guaranteed here).
            self.source_model.dataChanged.emit(rows[0], rows[-1])
            
            print("done.")
        
        elif result == ac_remove:
            print("- - - - -")
            print("ac_remove start")
            
            #for k,v in qe_settings.items():
                #print("  ",k,":",v)
                
            # gather items to be removed, excluding projects inside folders that are being removed, as they'll be removed with the folder anyway.
            print("building list of rows to remove...")
            row_items = []
            folder_paths_being_removed = []
            for row_index in rows:
                row_item = self.source_model.itemFromIndex(self.model.mapToSource(row_index))
                if row_index.data(ItemTypeRole) == QEItemType.FOLDER:
                    print(f" - add folder {row_index.data(PathRole)}.")
                    folder_paths_being_removed.append(row_index.data(PathRole))
                    row_items.append(row_item)
                else:
                    if not row_index.parent() in rows:
                        print(f" - add project {row_index.data(PathRole)}.")
                        row_items.append(row_item)
            
            print("removing...")
            for item in row_items:
                path = item.data(PathRole)
                item_type = item.data(ItemTypeRole)
                if item_type == QEItemType.FOLDER:
                    for child_idx in range(item.rowCount()):
                        child = item.child(child_idx)
                        child_path = child.data(PathRole)
                        print(f" - {child_path=} (row:{child.row()})")
                        if child_path in qe_settings:
                            del qe_settings[child_path]
                print(f" - {path=} (row:{item.row()})")
                self.source_model.removeRow(item.row(), (item.parent() or self.source_model.invisibleRootItem()).index())
                if path in qe_settings:
                    del qe_settings[path]
            
            # TODO: this is badly done (indeces passes to dataChanged must all have same parent; that's not guaranteed here).
            self.source_model.dataChanged.emit(rows[0], rows[-1])
            
            for folder_path in folder_paths_being_removed:
                self.removingFolder.emit(path)
            
            print("done")
            #for k,v in qe_settings.items():
                #print("  ",k,":",v)
            print("ac_remove end")
            print("- - - - -")

    def relocate_rows_in_tree(self, target_folder_path, rows=None):
        print("- - - - -")
        print("relocate_rows_in_tree: start")
        
        #for k,v in qe_settings.items():
            #print("  ",k,":",v)

        if not rows:
            rows = self.selectionModel().selectedRows()
        
        target_folder_exists_in_tree = False
        for i in range(self.source_model.rowCount()):
            check_index = self.source_model.index(i, 0)
            if self.source_model.data(check_index, PathRole) == target_folder_path:
                target_folder_exists_in_tree = True
                target_folder_item = self.source_model.itemFromIndex(check_index)
                break
        
        # gather items to be moved, excluding projects inside folders that are being moved, as they'll be moved with the folder anyway.
        # also exclude the target folder item and its children if for some reason they're also selected.
        row_items = []
        for row_index in rows:
            row_item = self.source_model.itemFromIndex(self.model.mapToSource(row_index))
            if row_index.data(ItemTypeRole) == QEItemType.FOLDER:
                if row_index.data(PathRole) == target_folder_path:
                    continue
                row_items.append(row_item)
            elif row_index.data(ItemTypeRole) == QEItemType.FILE:
                continue
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
                if item_type == QEItemType.FOLDER:
                    print("This folder item will become the target folder item.")
                    self.change_settings_path_for_item(selected_row_item, target_folder_path)
                    selected_row_item2_source_index = self.source_model.sibling(selected_row_item.row(), selected_row_item.column()+1, selected_row_index)
                    selected_row_item2_index = self.model.mapFromSource(selected_row_item2_source_index)
                    self.setIndexWidget(selected_row_item2_index, None)
                    self.add_buttons_for_row(selected_row_item.data(PathRole), selected_row_item.data(ItemTypeRole), selected_row_item, self.source_model.itemFromIndex(selected_row_item2_source_index))
                    for child_idx in range(selected_row_item.rowCount()):
                        child_item = selected_row_item.child(child_idx)
                        self.change_settings_path_for_item(child_item, target_folder_path)
                        self.populate_base_item_with_file_items(child_item, child_item.data(PathRole))
                    target_folder_item = selected_row_item
                    continue
                else:
                    print("A new target folder item will be added to tree.")
                    target_folder_item = self.add_folder_to_tree(target_folder_path)
                    self.setExpanded(self.model.mapFromSource(target_folder_item.index()), True)
        
            if item_type == QEItemType.FOLDER:
                print("Projects in this folder will be moved to the target folder item.")
                while selected_row_item.child(0):
                    self.reparent_base_row_in_tree(selected_row_item, 0, target_folder_item, target_folder_path)
            else:
                print("This project will be moved to the target folder item.")
                self.reparent_base_row_in_tree(selected_row_item.parent(), selected_row_item.row(), target_folder_item, target_folder_path)
        
        print("done")
        #for k,v in qe_settings.items():
            #print("  ",k,":",v)
        print("relocate_rows_in_tree: end")
        print("- - - - -")

    def reparent_base_row_in_tree(self, source_parent_item, source_child_index, target_parent, target_folder_path):
        if source_parent_item == target_parent:
            return
        row_items = source_parent_item.takeRow(source_child_index)
        self.change_settings_path_for_item(row_items[0], target_folder_path, new_parent_item = target_parent)
        target_parent.appendRow(row_items)
        self.add_buttons_for_row(row_items[0].data(PathRole), row_items[0].data(ItemTypeRole), *row_items)
        self.populate_base_item_with_file_items(row_items[0])

    def change_settings_path_for_item(self, item, target_folder_path, new_name="", new_parent_item=None):
        print(f"change_settings_path_for_item: {item=} {item.data(PathRole)=} {target_folder_path=} {new_name=} {new_parent_item=}")
        old_path = item.data(PathRole)
        item_type = item.data(ItemTypeRole)
        new_name = new_name or old_path.name
        new_path = target_folder_path / new_name if item_type != QEItemType.FOLDER else target_folder_path
        
        if not new_parent_item:
            if item_type == QEItemType.FOLDER:
                print(f"set new_parent_item to model root")
                new_parent_item = self.source_model.invisibleRootItem()
                print(new_parent_item)
            else:
                if old_path.parent == target_folder_path:
                    new_parent_item = item.parent()
                else:
                    root_item = self.source_model.invisibleRootItem()
                    for row in range(root_item.rowCount()):
                        if root_item.child(row).data(PathRole) == target_folder_path:
                            new_parent_item = root_item.child(row)
                            break
        
        # keep checking all items under same parent until name doesn't collide.
        dupe_num = 0
        test_path = new_path
        while True:
            collision = False
            for row in range(new_parent_item.rowCount()):
                check_item = new_parent_item.child(row)
                if check_item == item:
                    continue
                if check_item.data(PathRole) == test_path:
                    dupe_num += 1
                    print(f"new path {test_path} collides with existing.")
                    test_path = new_path.with_stem(new_path.stem + f" ({dupe_num})")
                    collision = True
                    break
            if not collision:
                break
        new_path = test_path
        
        if old_path in qe_settings:
            store_temp_copy = qe_settings[old_path]
            del qe_settings[old_path]
            qe_settings[new_path] = store_temp_copy
        
        if item_type == QEItemType.FOLDER:
            self.removingFolder.emit(old_path)
            self.addingFolder.emit(new_path)
        
        item.setData(str(new_path) if item_type == QEItemType.FOLDER else new_path.name, Qt.DisplayRole)
        item.setData(new_path, PathRole)

    def tree_iter(self, index, callback):
        #print(f"tree_iter: {index.data(PathRole)}")
        callback(self.model.mapToSource(index))
        for row in range(self.model.rowCount(index)):
            self.tree_iter(self.model.index(row, 0, index), callback)

    def _on_filter_edit_text_changed(self, text):
        print(text)
        self.model.setFilterFixedString(text)
        if text != "":
            self.expandAll()
        
        self.add_buttons_for_all_rows()
    
    def add_buttons_for_all_rows(self):
        def callback_method(index):
            item = self.source_model.itemFromIndex(index)
            item2_source_index = index.siblingAtColumn(index.column()+1)
            item2 = self.source_model.itemFromIndex(item2_source_index)
            #print(f"{item2_source_index=}, row:{item2_source_index.row()}, col:{item2_source_index.column()}, model:{item2_source_index.model()}, {item2=}")
            if item2:
                self.add_buttons_for_row(item.data(PathRole), item.data(ItemTypeRole), item, item2)
        
        self.tree_iter(QModelIndex(), callback_method)
    
    def _on_delegate_commit_item_rename(self, source_index, item, new_name):
        suppress_store_on_widget_edit = True
        
        source_model = self.source_model
        item_type = item.data(ItemTypeRole)
        
        if item_type == QEItemType.FOLDER:
            self.change_settings_path_for_item(item, Path(new_name))
            self.add_buttons_for_row(item.data(PathRole), item.data(ItemTypeRole), item, source_model.itemFromIndex(source_index.siblingAtColumn(source_index.column()+1)))
            
            for row in range(item.rowCount()):
                child_item = item.child(row)
                child_source_index = child_item.index()
                self.change_settings_path_for_item(child_item, source_index.data(PathRole))
                self.add_buttons_for_row(child_item.data(PathRole), child_item.data(ItemTypeRole), child_item, source_model.itemFromIndex(child_source_index.siblingAtColumn(child_source_index.column()+1)))
                self.populate_base_item_with_file_items(child_item)
        else:
            self.change_settings_path_for_item(item, source_index.data(PathRole).parent, new_name)
            self.add_buttons_for_row(item.data(PathRole), item.data(ItemTypeRole), item, source_model.itemFromIndex(source_index.siblingAtColumn(source_index.column()+1)))
            self.populate_base_item_with_file_items(item)
        
        self.requestConfigWidgetsRefreshForPath.emit(source_index.data(PathRole))
        
        self.source_model.dataChanged.emit(source_index, source_index)
        
        suppress_store_on_widget_edit = False
