from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from krita import *
app = Krita.instance()

import xml.etree.ElementTree as ET

if False:
    # Assuming 'xml_data' contains your XML string
    xml_data = app.readSetting("gaussian blur_filter_bookmarks", "20px blur", "")
    print(xml_data)
    root = ET.fromstring(xml_data)
    for param in root.iter('param'):
        #print(dir(param))
        #print(param.attrib, param.items(), param.keys(), param.tag, param.text)#param.tail)#, param.text)
        print(f"parameter {param.attrib['name']} (of type {param.attrib['type']}) has value {param.text}.")
        #STOP
        #print(param.name, param.text)
    STOP

if False:
    for f in app.filters():
        filter = app.filter(f)
        print(f"{filter.name()}")
        for p in filter.configuration().properties():
            pass#print(f"   {p}")
    #STOP

    a = app.action("krita_filter_gaussian blur")
    #a.trigger()
    #FAIL

    for action in app.actions():
        if "filter" in action.objectName().lower():
            print(f"{action.objectName()} ({action.text()})")
    FAIL

class SpinBox(QSpinBox):
    def __init__(self, value_=1, min_=1, max_=100, suffix_=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setRange(min_, max_)
        self.setValue(value_)
        if suffix_:
            self.setSuffix(suffix_)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        
        self.setContentsMargins(0,0,0,0)
        self.setFrame(False)
        self.lineEdit().setContentsMargins(0,0,0,0)
        self.lineEdit().setTextMargins(0,0,0,0)
        self.lineEdit().setFrame(False)
        
        self.lineEdit().textChanged.connect(self._on_lineedit_text_changed)
    
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.updateGeometry()
    
    def _on_lineedit_text_changed(self, text):
        self.updateGeometry()
    
    def sizeHint(self):
        size = super().sizeHint()
        
        fm = QFontMetrics(self.font())
        size.setWidth(fm.horizontalAdvance(self.lineEdit().text()+" ") + 2)
        return size
    
    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        
        fm = QFontMetrics(self.font())
        size.setWidth(fm.horizontalAdvance("0 ") + 2)
        return size

dialog = QDialog(app.activeWindow().qwindow())
#dialog.setWindowModality(Qt.WindowModal)
layout = QVBoxLayout(dialog)

class Tree(QTreeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, event):
        item = self.indexAt(event.pos())

        if item.isValid():
            super().mousePressEvent(event)
        else:
            self.clearSelection()
            self.selectionModel().setCurrentIndex(QModelIndex(), QItemSelectionModel.Select)

    def rowsAboutToBeRemoved(self, parent, start, end):
        par_item = self.itemFromIndex(parent)
        if par_item:
            item = par_item.child(start)
        else:
            item = self.topLevelItem(start)
        print("rowsAboutToBeRemoved", parent, par_item, item.text(0), start, end)
        super().rowsAboutToBeRemoved(parent, start, end)
    
    def rowsInserted(self, parent, start, end):
        par_item = self.itemFromIndex(parent)
        if par_item:
            item = par_item.child(start)
        else:
            item = self.topLevelItem(start)
        print("rowsInserted", parent, par_item, item.text(0), start, end)
        super().rowsInserted(parent, start, end)
        print(f"{item.childCount()=}")
        
        self.postRowInserted(item)
        self.setCurrentItem(item)
    
    def postRowInserted(self, item):
        if item.data(0, Qt.UserRole) == "ApplyComposition":
            addApplyCompositionItem(item.parent(), item)
        elif item.data(0, Qt.UserRole) == "SliceImage":
            addSliceImageItem(item.parent(), item)
        elif item.data(0, Qt.UserRole) == "CropImage":
            addCropImageItem(item.parent(), item)
        elif item.data(0, Qt.UserRole) == "SetLayerVisibility":
            addSetLayerVisibilityItem(item.parent(), item)
        elif item.data(0, Qt.UserRole) == "ApplyFilter":
            addApplyFilterItem(item.parent(), item)
        elif item.data(0, Qt.UserRole) == "FlattenImage":
            addFlattenImageItem(item.parent(), item)
        
        item.setExpanded(True)
        
        for index in range(item.childCount()):
            self.postRowInserted(item.child(index))
    
    def dropEvent(self, event):
        print('dropEvent happened')
        widgetItemThatMoved = event.source().currentItem()
        parentThatReceivedIt = self.itemAt(event.pos())
        #self.theFunc(parentThatReceivedIt,widgetItemThatMoved)
        #print(f"{widgetItemThatMoved=} '{widgetItemThatMoved.text(0)}' {parentThatReceivedIt=} '{parentThatReceivedIt.text(0)}'")
        #event.acceptProposedAction()
        super().dropEvent(event)
        
        if False:
            droppedIndex = self.indexAt(event.pos())
            if not (droppedIndex.isValid() or droppedIndex.parent().isValid()):
                pass#return
            super().dropEvent(event)
        
            mime_data = event.mimeData()
            drop_action = event.dropAction()
        
            #dmd = self.dropMimeData(self.itemFromIndex(droppedIndex.parent()), droppedIndex.row(), mime_data, drop_action)
            #print(f"{dmd=}")
            #super().dropEvent(event)
            print(event.mimeData().formats())
            print(event.mimeData().data("application/x-qabstractitemmodeldatalist"))
            #print(event.mimeData().retrieveData("application/x-qabstractitemmodeldatalist", QVariant.))

tree = Tree()#QTreeWidget()
tree.setColumnCount(3)
tree.header().setFirstSectionMovable(True)
tree.header().moveSection(2, 0)
tree.resizeColumnToContents(2)
layout.addWidget(tree)

def addTreeItem(parent, text):
    item_ = QTreeWidgetItem(parent)
    item_.setText(0, text)
    return item_

def addApplyCompositionItem(parent, item_=None):
    data = None
    if not item_:
        item_ = addTreeItem(parent, "Apply composition")
        item_.setData(0, Qt.UserRole, "ApplyComposition")
        data = {"name":""}
        print(f"set {data=}")
    else:
        data = item_.data(1, Qt.UserRole)
        print(f"{data=}")
    
    def _on_name_edit_text_changed(text):
        data = item_.data(1, Qt.UserRole)
        data["name"] = text
        item_.setData(1, Qt.UserRole, data)
    
    edit_ = QLineEdit()
    edit_.setPlaceholderText("Composition name")
    edit_.setText(data["name"])
    edit_.textChanged.connect(_on_name_edit_text_changed)
    tree.setItemWidget(item_, 1, edit_)
    item_.setData(1, Qt.UserRole, data)
    return item_

def addSliceImageItem(parent, item_=None):
    data = None
    if not item_:
        item_ = addTreeItem(parent, "Slice image")
        item_.setData(0, Qt.UserRole, "SliceImage")
        data = {"count":[2,2], "pixels":[32,32], "mode":"count"}
        print(f"set {data=}")
    else:
        data = item_.data(1, Qt.UserRole)
        print(f"{data=}")
    
    w_ = QWidget()
    wl_ = QHBoxLayout(w_)
    sw_ = QStackedWidget()
    
    def _on_count_value_changed(value, index):
        data = item_.data(1, Qt.UserRole)
        data["count"][index] = value
        item_.setData(1, Qt.UserRole, data)
    
    p0_ = QWidget()
    p0l_ = QHBoxLayout(p0_)
    p0l_.setSpacing(0)
    p0l_.addWidget(QLabel("into"))
    p0_edit_x_ = SpinBox(value_=data["count"][0], min_=1, max_=256)
    p0_edit_x_.valueChanged.connect(lambda value: _on_count_value_changed(value, 0))
    p0l_.addWidget(p0_edit_x_)
    p0l_.addWidget(QLabel("x"))
    p0_edit_y_ = SpinBox(value_=data["count"][1], min_=1, max_=256)
    p0_edit_y_.valueChanged.connect(lambda value: _on_count_value_changed(value, 1))
    p0l_.addWidget(p0_edit_y_)
    p0l_.addWidget(QLabel("slices"))
    p0l_.addStretch()
    sw_.addWidget(p0_)
    
    def _on_pixel_value_changed(value, index):
        data = item_.data(1, Qt.UserRole)
        data["pixels"][index] = value
        item_.setData(1, Qt.UserRole, data)
    
    p1_ = QWidget()
    p1l_ = QHBoxLayout(p1_)
    p1l_.addWidget(QLabel("into"))
    p1_edit_x_ = SpinBox(value_=data["pixels"][0], min_=1, max_=4096, suffix_="px")
    p1_edit_x_.valueChanged.connect(lambda value: _on_pixel_value_changed(value, 0))
    p1l_.addWidget(p1_edit_x_)
    p1l_.addWidget(QLabel("by"))
    p1_edit_y_ = SpinBox(value_=data["pixels"][1], min_=1, max_=4096, suffix_="px")
    p1_edit_y_.valueChanged.connect(lambda value: _on_pixel_value_changed(value, 1))
    p1l_.addWidget(p1_edit_y_)
    p1l_.addWidget(QLabel("slices"))
    p1l_.addStretch()
    sw_.addWidget(p1_)
    
    p2_ = QLabel("at guides")
    sw_.addWidget(p2_)
    
    def _on_mode_menu_action_triggered(action):
        index = 0 if action==a0 else 1 if action==a1 else 2
        sw_.setCurrentIndex(index)
        data = item_.data(1, Qt.UserRole)
        data["mode"] = ("count", "pixels", "guides")[index]
        item_.setData(1, Qt.UserRole, data)
    
    cb_ = QToolButton()
    cb_.setAutoRaise(True)
    cbm_ = QMenu()
    a0 = cbm_.addAction("into x-count by y-count slices")
    a1 = cbm_.addAction("into w-px by h-px slices")
    a2 = cbm_.addAction("at guides")
    cbm_.triggered.connect(_on_mode_menu_action_triggered)
    cb_.setMenu(cbm_)
    cb_.setPopupMode(QToolButton.InstantPopup)
    cb_.setStyleSheet("QToolButton::menu-indicator {image: none;}")
    cb_.setArrowType(Qt.DownArrow)
    
    sw_.setCurrentIndex(0 if data["mode"]=="count" else 1 if data["mode"]=="pixels" else 2)
    
    wl_.addWidget(sw_)
    wl_.addWidget(cb_)
    
    w_.setContentsMargins(0,0,0,0)
    wl_.setContentsMargins(0,0,0,0)
    sw_.setContentsMargins(0,0,0,0)
    p0_.setContentsMargins(0,0,0,0)
    p0l_.setContentsMargins(0,0,0,0)
    p1_.setContentsMargins(0,0,0,0)
    p1l_.setContentsMargins(0,0,0,0)
    
    tree.setItemWidget(item_, 1, w_)
    item_.setData(1, Qt.UserRole, data)
    return item_

def addCropImageItem(parent, item_=None):
    data = None
    if not item_:
        item_ = addTreeItem(parent, "Crop image")
        item_.setData(0, Qt.UserRole, "CropImage")
        data = {"pixels":[0,0,1024,1024], "mode":"pixels"}
        print(f"set {data=}")
    else:
        data = item_.data(1, Qt.UserRole)
        print(f"{data=}")
    
    w_ = QWidget()
    wl_ = QHBoxLayout(w_)
    sw_ = QStackedWidget()
    
    def _on_pixel_value_changed(value, index):
        data = item_.data(1, Qt.UserRole)
        data["pixels"][index] = value
        item_.setData(1, Qt.UserRole, data)
    
    p0_ = QWidget()
    p0l_ = QHBoxLayout(p0_)
    p0l_.setSpacing(0)
    p0l_.addWidget(QLabel("from (left"))
    p0_edit_l_ = SpinBox(value_=data["pixels"][0], min_=0, max_=65536)
    p0_edit_l_.valueChanged.connect(lambda value: _on_pixel_value_changed(value, 0))
    p0l_.addWidget(p0_edit_l_)
    p0l_.addWidget(QLabel(", top"))
    p0_edit_t_ = SpinBox(value_=data["pixels"][1], min_=0, max_=65536)
    p0_edit_t_.valueChanged.connect(lambda value: _on_pixel_value_changed(value, 1))
    p0l_.addWidget(p0_edit_t_)
    p0l_.addWidget(QLabel(") to (right"))
    p0_edit_r_ = SpinBox(value_=data["pixels"][2], min_=0, max_=65536)
    p0_edit_r_.valueChanged.connect(lambda value: _on_pixel_value_changed(value, 2))
    p0l_.addWidget(p0_edit_r_)
    p0l_.addWidget(QLabel(", bottom"))
    p0_edit_b_ = SpinBox(value_=data["pixels"][3], min_=0, max_=65536)
    p0_edit_b_.valueChanged.connect(lambda value: _on_pixel_value_changed(value, 3))
    p0l_.addWidget(p0_edit_b_)
    p0l_.addWidget(QLabel(") pixels"))
    p0l_.addStretch()
    sw_.addWidget(p0_)
    
    p1_ = QWidget()
    p1l_ = QHBoxLayout(p1_)
    p1l_.addWidget(QLabel("into"))
    p1_edit_x_ = SpinBox(value_=32, min_=1, max_=4096, suffix_="px")
    p1l_.addWidget(p1_edit_x_)
    p1l_.addWidget(QLabel("by"))
    p1_edit_y_ = SpinBox(value_=32, min_=1, max_=4096, suffix_="px")
    p1l_.addWidget(p1_edit_y_)
    p1l_.addWidget(QLabel("slices"))
    p1l_.addStretch()
    sw_.addWidget(p1_)
    
    p2_ = QLabel("at guides")
    sw_.addWidget(p2_)
    
    def _on_mode_menu_action_triggered(action):
        index = 0 if action==a0 else 1 if action==a1 else 2
        sw_.setCurrentIndex(index)
        data = item_.data(1, Qt.UserRole)
        data["mode"] = ("pixels", "???", "guides")[index]
        item_.setData(1, Qt.UserRole, data)
    
    cb_ = QToolButton()
    cb_.setAutoRaise(True)
    cbm_ = QMenu()
    a0 = cbm_.addAction("from (left, top) to (right, bottom) (pixels)")
    a1 = cbm_.addAction("into w-px by h-px slices")
    a2 = cbm_.addAction("at guides")
    cbm_.triggered.connect(_on_mode_menu_action_triggered)
    cb_.setMenu(cbm_)
    cb_.setPopupMode(QToolButton.InstantPopup)
    cb_.setStyleSheet("QToolButton::menu-indicator {image: none;}")
    cb_.setArrowType(Qt.DownArrow)
    
    sw_.setCurrentIndex(0 if data["mode"]=="pixels" else 1 if data["mode"]=="???" else 2)
    
    wl_.addWidget(sw_)
    wl_.addWidget(cb_)
    
    w_.setContentsMargins(0,0,0,0)
    wl_.setContentsMargins(0,0,0,0)
    sw_.setContentsMargins(0,0,0,0)
    p0_.setContentsMargins(0,0,0,0)
    p0l_.setContentsMargins(0,0,0,0)
    p1_.setContentsMargins(0,0,0,0)
    p1l_.setContentsMargins(0,0,0,0)
    
    tree.setItemWidget(item_, 1, w_)
    item_.setData(1, Qt.UserRole, data)
    return item_

def addApplyFilterItem(parent, item_=None):
    data = None
    if not item_:
        item_ = addTreeItem(parent, "Apply filter")
        item_.setData(0, Qt.UserRole, "ApplyFilter")
        data = {"filter":"gaussian blur", "preset_name":""}
        print(f"set {data=}")
    else:
        data = item_.data(1, Qt.UserRole)
        print(f"{data=}")
    
    edit_ = QPlainTextEdit()
    
    w_ = QWidget()
    wl_ = QVBoxLayout(w_)
    
    wl_top_ = QHBoxLayout()
    wl_.addLayout(wl_top_)
    
    cb_ = QComboBox()
    for f in app.filters():
        filter = app.filter(f)
        cb_.addItem(filter.name())
    
    cb_.setCurrentText(data["filter"])
    
    def _on_cb_current_index_changed(combobox, edit):
        f = combobox.currentText()
        data = item_.data(1, Qt.UserRole)
        data["filter"] = f
        item_.setData(1, Qt.UserRole, data)
        filter = app.filter(f)
    
    cb_.currentIndexChanged.connect(lambda index, c=cb_, e=edit_: _on_cb_current_index_changed(c, e))
    wl_top_.addWidget(cb_)
    
    preset_name_ = QLineEdit()
    preset_name_.setPlaceholderText("Preset Name (default if empty)")
    
    def _on_preset_name_text_changed(text, edit, conf_edit, combobox):
        data = item_.data(1, Qt.UserRole)
        data["preset_name"] = text
        item_.setData(1, Qt.UserRole, data)
        f = combobox.currentText()
        preset_conf = app.readSetting("{0}_filter_bookmarks".format(f), text, "")
        if text != "" and preset_conf == "":
            p = edit.palette()
            p.setColor(QPalette.Base, QColor(255,0,0,32))
            edit.setPalette(p)
        else:
            p = edit.palette()
            p.setColor(QPalette.Base, dialog.palette().color(QPalette.Base))
            edit.setPalette(p)
            conf_edit.setPlainText(preset_conf)
    
    preset_name_.textChanged.connect(lambda text, pn=preset_name_, e=edit_, c=cb_: _on_preset_name_text_changed(text, pn, e, c))
    
    preset_name_.setText(data["preset_name"])
    
    wl_top_.addWidget(preset_name_)
    
    w_.setContentsMargins(0,0,0,0)
    wl_.setContentsMargins(0,0,0,0)
    
    edit_.setFont(QFont("monospace"))
    edit_.setPlainText("hi")
    edit_.setMaximumHeight(96)
    #wl_.addWidget(edit_)
    
    tree.setItemWidget(item_, 1, w_)
    item_.setData(1, Qt.UserRole, data)
    return item_

def addSetLayerVisibilityItem(parent, item_=None):
    data = None
    if not item_:
        item_ = addTreeItem(parent, "Set layer visibility")
        item_.setData(0, Qt.UserRole, "SetLayerVisibility")
        data = {"visible":True, "layer_name":""}
        print(f"set {data=}")
    else:
        data = item_.data(1, Qt.UserRole)
        print(f"{data=}")
    
    w_ = QWidget()
    wl_ = QHBoxLayout(w_)
    
    btn_ = QToolButton()
    btn_.setIcon(app.icon("visible" if data["visible"] else "novisible"))
    btn_.setCheckable(True)
    btn_.setChecked(data["visible"])
    btn_.setStyleSheet("border: none")
    wl_.addWidget(btn_)
    
    def _on_btn_toggled(checked):
        btn_.setIcon(app.icon("visible" if checked else "novisible"))
        data = item_.data(1, Qt.UserRole)
        data["visible"] = checked
        item_.setData(1, Qt.UserRole, data)
    
    btn_.toggled.connect(_on_btn_toggled)
    
    edit_ = QLineEdit()
    edit_.setPlaceholderText("Layer Name (all if empty)")
    edit_.setText(data["layer_name"])
    wl_.addWidget(edit_)
    wl_.addStretch()
    
    def _on_edit_text_editing_finished():
        data = item_.data(1, Qt.UserRole)
        data["layer_name"] = edit_.text()
        item_.setData(1, Qt.UserRole, data)
    
    edit_.editingFinished.connect(_on_edit_text_editing_finished)
    
    w_.setContentsMargins(0,0,0,0)
    wl_.setContentsMargins(0,0,0,0)
    
    tree.setItemWidget(item_, 1, w_)
    item_.setData(1, Qt.UserRole, data)
    return item_

def addFlattenImageItem(parent, item_=None):
    data = None
    if not item_:
        item_ = addTreeItem(parent, "Flatten image")
        item_.setData(0, Qt.UserRole, "FlattenImage")

#    tree.setItemWidget(item_, 1, edit_)
#    item_.setData(1, Qt.UserRole, data)
    return item_

item1 = addApplyCompositionItem(tree)
item2 = addCropImageItem(tree)
item3 = addSliceImageItem(tree)
item3_0 = addTreeItem(item3, "For each slice:")
item3_0_0 = addApplyFilterItem(item3_0)
item3_0_1 = addTreeItem(item3_0, "Export")
item4 = addTreeItem(tree, "Scale image")
item5 = addSetLayerVisibilityItem(tree)
item5 = addFlattenImageItem(tree)
item6 = addTreeItem(tree, "Export")

tree.expandAll()
#tree.setUniformRowHeights(True)
tree.setDragDropMode(QAbstractItemView.InternalMove)
tree.setDragEnabled(True)
tree.setDropIndicatorShown(True)

tree.resizeColumnToContents(0)

tree.update()
tree.updateGeometries()
tree.scheduleDelayedItemsLayout()

controls_layout = QHBoxLayout()
layout.addLayout(controls_layout)

add_item_button = QToolButton()
add_item_button.setIcon(app.icon("list-add"))
add_item_button.setPopupMode(QToolButton.InstantPopup)

add_item_menu = QMenu()
add_apply_composition_action = add_item_menu.addAction("Apply composition")
add_crop_image_action = add_item_menu.addAction("Crop image")
add_slice_image_action = add_item_menu.addAction("Slice image")
add_apply_filter_action = add_item_menu.addAction("Apply filter")
add_set_layer_visibility_action = add_item_menu.addAction("Set layer visibility")
add_flatten_image_action = add_item_menu.addAction("Flatten image")
add_scale_action = add_item_menu.addAction("Scale")
add_export_action = add_item_menu.addAction("Export")

def _on_add_item_menu_action_triggered(action):
    print(f"add item menu: {action.text()=}")
    parent = tree.currentItem() if tree.selectedItems() else tree
    if action == add_apply_composition_action:
        addApplyCompositionItem(parent)
    elif action == add_crop_image_action:
        addCropImageItem(parent)
    elif action == add_slice_image_action:
        addSliceImageItem(parent)
    elif action == add_apply_filter_action:
        addApplyFilterItem(parent)
    elif action == add_set_layer_visibility_action:
        addSetLayerVisibilityItem(parent)
    elif action == add_flatten_image_action:
        addFlattenImageItem(parent)
    elif action == add_scale_action:
        addTreeItem(parent, "Scale")
    elif action == add_export_action:
        addTreeItem(parent, "Export")
    if isinstance(parent, QTreeWidgetItem):
        parent.setExpanded(True)

add_item_menu.triggered.connect(_on_add_item_menu_action_triggered)
add_item_button.setMenu(add_item_menu)

remove_item_button = QToolButton()
remove_item_button.setIcon(app.icon("list-remove"))

def _on_remove_item_button_clicked(checked):
    item = tree.currentItem() if tree.selectedItems() else None
    if not item:
        return
    top_level_index = tree.indexOfTopLevelItem(item)
    print(top_level_index)
    if top_level_index != -1:
        tree.takeTopLevelItem(top_level_index)
    else:
        parent = item.parent()
        child_index = parent.indexOfChild(item)
        parent.takeChild(child_index)

remove_item_button.clicked.connect(_on_remove_item_button_clicked)

def _on_run_button_clicked(checked):
    doc = app.activeDocument()
    node = doc.activeNode()
    print(f"{doc.fileName()=}, {node.name()=}")
    
    doc.setBatchmode(True)
    
    iter = QTreeWidgetItemIterator(tree)
    while iter.value():
        item = iter.value()
        data = item.data(1, Qt.UserRole)
        
        if item.data(0, Qt.UserRole) == "ApplyComposition":
            node.setVisible(data["visible"])
            doc.refreshProjection()
        
        elif item.data(0, Qt.UserRole) == "SetLayerVisibility":
            node.setVisible(data["visible"])
            doc.refreshProjection()
            
        elif item.data(0, Qt.UserRole) == "CropImage":
            w = data["pixels"][2] - data["pixels"][0]
            h = data["pixels"][3] - data["pixels"][1]
            doc.crop(data["pixels"][0], data["pixels"][1], w, h)
            
        elif item.data(0, Qt.UserRole) == "ApplyFilter":
            filter_name = data["filter"]
            filter = app.filter(filter_name)
            preset_name = data["preset_name"]
            preset_xml = app.readSetting("{0}_filter_bookmarks".format(filter_name), preset_name, "")
            if preset_xml:
                config = filter.configuration()

                root = ET.fromstring(preset_xml)
                for param in root.iter('param'):
                    param_name = param.attrib['name']
                    print(f"parameter {param_name} (of type {param.attrib['type']}) has value {param.text}.")
                    value = param.text
                    if value in ("true", "false"):
                        value = True if value=="true" else False
                    else:
                        try:
                            value = int(value)
                        except ValueError:
                            print("not an int")
                            try:
                                value = float(value)
                            except ValueError:
                                print("not a float")
                    config.setProperty(param_name, value)
                
                filter.setConfiguration(config)
            
            print(f"apply filter {filter_name} with config {filter.configuration().properties()}.")
            filter.startFilter(node, 0, 0, doc.width(), doc.height())
        
        elif item.data(0, Qt.UserRole) == "FlattenImage":
            doc.flatten()
        
        item.setIcon(2, app.icon("dialog-ok"))
        iter += 1
    
    doc.setBatchmode(False)

run_button = QToolButton()
run_button.setIcon(app.icon("animation_play"))
run_button.clicked.connect(_on_run_button_clicked)

controls_layout.addWidget(add_item_button)
controls_layout.addWidget(remove_item_button)
controls_layout.addWidget(run_button)
controls_layout.addStretch()

dialog.resize(680,420)
dialog.show()
