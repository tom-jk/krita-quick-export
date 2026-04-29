from PyQt5.QtWidgets import (QLabel, QHBoxLayout, QVBoxLayout, QLineEdit, QStyle, QCompleter, QTreeWidget,
                             QTreeWidgetItem, QHBoxLayout, QVBoxLayout, QPushButton, QCheckBox, QWidget, QToolButton,
                             QStyleOption, QStyleOptionButton, QAbstractItemView, QTreeWidgetItemIterator)
from PyQt5.QtCore import Qt, QSize, QPoint, QObject, QModelIndex, pyqtSignal, QEvent, QTimer
from PyQt5.QtGui import QFontMetrics, QIcon, QPixmap, QColor, QPainter, QPalette
from pathlib import Path
import krita

app = Krita.instance()

class CheckBox(QCheckBox):
    def nextCheckState(self):
        self.setCheckState(Qt.Checked if self.checkState() in (Qt.Unchecked, Qt.PartiallyChecked) else Qt.Unchecked)

class FolderFilterButton(QPushButton):
    filterChanged = pyqtSignal()
    
    TextRole = Qt.UserRole
    CheckedRole = Qt.UserRole+1
    UsedRole = Qt.UserRole+2
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        layout = QHBoxLayout(self)
        m = self.style().pixelMetric(QStyle.PM_ButtonMargin)
        layout.setContentsMargins(m, m, m, m)
        layout.setSpacing(round(m/2))
        
        icon_label = QLabel()
        icon_size = self.style().pixelMetric(QStyle.PM_ButtonIconSize)
        icon_label.setPixmap(app.icon("document-open").pixmap(QSize(icon_size, icon_size)))
        
        layout.addWidget(icon_label)
        
        self.label_text = "Filter by folder..."
        
        fm = QFontMetrics(self.font())
        w = fm.horizontalAdvance(self.label_text)
        self.setMinimumWidth(icon_size + round(m/2) + w + m*2)
        
        self.clicked.connect(self._on_clicked)
        
        self.included_folders = []
        
        self.popup = QWidget(self)
        self.popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.popup.setMinimumSize(480,640)
        popup_layout = QVBoxLayout(self.popup)
        popup_layout.setSpacing(round(popup_layout.spacing()/2))

        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setItemsExpandable(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.tree_item_checkbox_state_changed_recursing = False
        
        popup_layout.addWidget(self.tree)
        
        self.temp_show_all_checkbox = QCheckBox("Show all temporarily")
        self.temp_show_all_checkbox.toggled.connect(self._on_temp_show_all_checkbox_toggled)
        
        self.check_selected_button = QToolButton()
        self.check_selected_button.setText("Check")
        self.check_selected_button.setAutoRaise(True)
        self.check_selected_button.clicked.connect(self._on_check_selected_button_clicked)
        
        self.uncheck_selected_button = QToolButton()
        self.uncheck_selected_button.setText("Uncheck")
        self.uncheck_selected_button.setAutoRaise(True)
        self.uncheck_selected_button.clicked.connect(self._on_uncheck_selected_button_clicked)
        
        self.clear_button = QToolButton()
        self.clear_button.setText("Clear")
        self.clear_button.setAutoRaise(True)
        self.clear_button.clicked.connect(self._on_clear_button_clicked)
        
        popup_controls_layout = QHBoxLayout()
        popup_layout.addLayout(popup_controls_layout)
        popup_controls_layout.addWidget(self.temp_show_all_checkbox)
        popup_controls_layout.addWidget(self.check_selected_button)
        popup_controls_layout.addWidget(self.uncheck_selected_button)
        popup_controls_layout.addWidget(self.clear_button)
    
    def _on_temp_show_all_checkbox_toggled(self, checked):
        self.tree.setDisabled(checked)
        self.update_label()
        self.filterChanged.emit()
    
    def _on_clear_button_clicked(self, checked):
        print("_on_clear_button_clicked")
        self.tree_item_checkbox_state_changed_recursing = True
        iter = QTreeWidgetItemIterator(self.tree)
        while iter.value():
            item = iter.value()
            checkbox = self.tree.itemWidget(item, 0).layout().itemAt(0).widget()
            checkbox.setCheckState(Qt.Unchecked)
            item.setData(0, self.CheckedRole, Qt.Unchecked)
            iter += 1
        self.included_folders.clear()
        self.tree_item_checkbox_state_changed_recursing = False
        self.update_label()
        self.filterChanged.emit()
    
    def _on_check_selected_button_clicked(self, checked):
        self.set_selected(Qt.Checked)
    
    def _on_uncheck_selected_button_clicked(self, checked):
        self.set_selected(Qt.Unchecked)
    
    def set_selected(self, check_state):
        print("_on_check_selected_button_clicked")
        self.tree_item_checkbox_state_changed_recursing = True
        iter = QTreeWidgetItemIterator(self.tree)
        while iter.value():
            item = iter.value()
            if item.isSelected():
                checkbox = self.tree.itemWidget(item, 0).layout().itemAt(0).widget()
                checkbox.setCheckState(check_state)
                item.setData(0, self.CheckedRole, check_state)
                if check_state == Qt.Unchecked and item in self.included_folders:
                    self.included_folders.pop(self.included_folders.index(item))
                if check_state != Qt.Unchecked and item not in self.included_folders:
                    self.included_folders.append(item)
            iter += 1
        self.tree_item_checkbox_state_changed_recursing = False
        self.update_label()
        self.filterChanged.emit()
    
    def add_item_to_tree(self, parent, text):
        item = QTreeWidgetItem(parent)
        wgt = QWidget()
        l = QHBoxLayout(wgt)
        l.setContentsMargins(0,0,0,0)
        checkbox = CheckBox(text)
        checkbox.setStyleSheet("QCheckBox::indicator:unchecked {border: 1px solid rgba(255,255,255,0.1);}")
        checkbox.setTristate(True)
        checkbox.setCheckState(Qt.Unchecked)
        checkbox.stateChanged.connect(lambda state, cb=checkbox, i=item: self._on_tree_item_checkbox_state_changed(state, cb, i))
        l.addWidget(checkbox)
        self.tree.setItemWidget(item, 0, wgt)
        item.setData(0, self.TextRole, text)
        item.setData(0, self.CheckedRole, Qt.Unchecked)
        item.setData(0, self.UsedRole, True)
        item.setExpanded(True)
        return item
    
    def _on_tree_item_checkbox_state_changed(self, state, checkbox, item):
        #print(f"_on_tree_item_checkbox_state_changed: {state} {checkbox} {item}")
        
        if self.tree_item_checkbox_state_changed_recursing:
            return

        self.tree_item_checkbox_state_changed_recursing = True
        
        if state == Qt.Checked:
            if not item in self.included_folders:
                self.included_folders.append(item)
                item.setData(0, self.CheckedRole, Qt.Checked)
            #print(f"added {item.data(0, self.TextRole)}")
        else:
            try:
                item.setData(0, self.CheckedRole, Qt.Unchecked)
                self.included_folders.pop(self.included_folders.index(item))
                #print(f"removed {item.data(0, self.TextRole)}")
            except ValueError as e:
                print(f"item {item.data(0, self.TextRole)}:", e)
    
        stack = [item]
        numloops = 0
        while stack and numloops < 9999:
            numloops += 1
            item_ = stack.pop()
            if item_ == item or item_.data(0, self.CheckedRole) != Qt.Checked:
                if item_.childCount() > 0:
                    for idx in range(item_.childCount()):
                        stack.append(item_.child(idx))
            if item_ == item:
                continue
            checkbox = self.tree.itemWidget(item_, 0).layout().itemAt(0).widget()
            if state == Qt.Checked and item_.data(0, self.CheckedRole) == Qt.Unchecked:
                checkbox.setCheckState(Qt.PartiallyChecked)
                item_.setData(0, self.CheckedRole, Qt.PartiallyChecked)
                self.included_folders.append(item_)
                #print(f"added {item_.data(0, self.TextRole)}")
            if not state == Qt.Checked and item_.data(0, self.CheckedRole) == Qt.PartiallyChecked:
                checkbox.setCheckState(Qt.Unchecked)
                item_.setData(0, self.CheckedRole, Qt.Unchecked)
                try:
                    self.included_folders.pop(self.included_folders.index(item_))
                    #print(f"removed {item_.data(0, self.TextRole)}")
                except ValueError as e:
                    print(f"item {item.data(0, self.TextRole)}:", e)
        if numloops==9999: print("bailed at numloops==9999")
    
        self.tree_item_checkbox_state_changed_recursing = False
        
        #print(f"{[i.data(0, self.TextRole) for i in self.included_folders]}")
        
        self.update_label()
        self.filterChanged.emit()
        
    def update_label(self):
        inc_count = len(self.included_folders)
        
        # TODO: when many, show highest common ancestor (eg. "Documents") if there is one with all descendents checked.
        if not self.temp_show_all_checkbox.isChecked() and inc_count > 0:
            if False:#inc_count == 1:
                self.label_text = self.included_folders[0].data(0, self.TextRole)
            else:
                self.label_text = f"Filter {inc_count} folder{'s' if inc_count>1 else ''}"
        else:
            self.label_text = "Filter by folder..."
        self.update()
    
    def includedFolders(self):
        if self.temp_show_all_checkbox.isChecked() or len(self.included_folders) == 0:
            return None
        
        paths = []
        iter_queue = [self.tree.topLevelItem(idx) for idx in range(self.tree.topLevelItemCount())]
        stack = []
        while iter_queue:
            item = iter_queue.pop(0)
            if item == -1:
                stack.pop()
                continue
            stack.append(item.data(0, self.TextRole))
            #print(stack)
            if item.data(0, self.CheckedRole) != Qt.Unchecked:
                paths.append(stack.copy())
            if item.childCount() > 0:
                l = []
                for idx in range(item.childCount()):
                    l.append(item.child(idx))
                l.append(-1)
                iter_queue[0:0] = l
            else:
                stack.pop()
        
        for i, path in enumerate(paths):
            p = Path(path[0]).joinpath(*path[1:])
            paths[i] = p
        
        #print("includedFolders:", paths)
        return paths
    
    def add_folder_to_tree(self, path):
        path_parts = path.parts
        #print(f"{path_parts=}")
        
        tree = self.tree
        
        item = None
        for item_idx in range(tree.topLevelItemCount()):
            item_ = tree.topLevelItem(item_idx)
            if item_.data(0, self.TextRole) == path_parts[0]:
                item = item_
                break
        
        if not item:
            #print("New root item:", path_parts[0])
            item = self.add_item_to_tree(tree, path_parts[0])
            print(item.data(0, self.TextRole), item.data(0, self.CheckedRole))
        
        self.tree_item_checkbox_state_changed_recursing = True
        
        print(path_parts[1:])
        for part in path_parts[1:]:
            already_exists = False
            for child_idx in range(item.childCount()):
                child = item.child(child_idx)
                #print("compare:", child.text(0), part)
                if child.data(0, self.TextRole) == part:
                    #print("Already exists")
                    already_exists = True
                    break
            if already_exists:
                item = child
                continue
            print("adding", part)
            new_item = self.add_item_to_tree(item, part)
            if item.data(0, self.CheckedRole) in (Qt.Checked, Qt.PartiallyChecked):
                # propagate checked state.
                cb = tree.itemWidget(new_item, 0).findChild((QCheckBox,))
                cb.setCheckState(Qt.PartiallyChecked)
                new_item.setData(0, self.CheckedRole, Qt.PartiallyChecked)
                self.included_folders.append(new_item)
            item = new_item
        
        self.tree_item_checkbox_state_changed_recursing = False
        
        item.setData(0, self.UsedRole, True)
        
        self.update_label()
        self.filterChanged.emit()
    
    def remove_folder_from_tree(self, path):
        path_parts = path.parts
        tree = self.tree
        
        item = None
        for item_idx in range(tree.topLevelItemCount()):
            item_ = tree.topLevelItem(item_idx)
            if item_.data(0, self.TextRole) == path_parts[0]:
                item = item_
                break
        
        if not item:
            print(f"failed to remove folder {path=} (root not in tree).")
            return
        
        for part in path_parts[1:]:
            ancestor_exists = False
            for child_idx in range(item.childCount()):
                child = item.child(child_idx)
                if child.data(0, self.TextRole) == part:
                    ancestor_exists = True
                    break
            if ancestor_exists:
                item = child
                continue
            print(f"failed to remove folder {path=} (ancestor {part} not in tree).")
        
        item.setData(0, self.UsedRole, False)
        
        # look at all folders under this one, and cascade up through ancestors.
        
        def is_any_descendent_used(itm):
            for child_idx in range(itm.childCount()):
                child = itm.child(child_idx)
                if child.data(0, self.UsedRole):
                    return True
                if child.childCount() > 0:
                    if is_any_descendent_used(child):
                        return True
            return False
        
        while True:
            if is_any_descendent_used(item):
                return
            
            parent = item.parent()
            if not parent:
                return
            
            cb = tree.itemWidget(item, 0).findChild((QCheckBox,))
            cb.setCheckState(Qt.Unchecked)
            parent.removeChild(item)
            item = parent
    
    def setAllFoldersUnused(self, item=None):
        if not item:
            item = self.tree.invisibleRootItem()
        
        for child_idx in range(item.childCount()):
            child = item.child(child_idx)
            child.setData(0, self.UsedRole, False)
            if child.childCount() > 0:
                self.setAllFoldersUnused(child)
    
    def purgeUnusedFolders(self, item=None):
        if not item:
            item = self.tree.invisibleRootItem()
        
        any_child_used = False
        
        for child_idx in reversed(range(item.childCount())):
            child = item.child(child_idx)
            if child.childCount() > 0:
                any_child_used |= self.purgeUnusedFolders(child)
            else:
                if child.data(0, self.UsedRole):
                    any_child_used |= True
                else:
                    cb = self.tree.itemWidget(child, 0).findChild((QCheckBox,))
                    cb.setCheckState(Qt.Unchecked)
                    item.removeChild(child)
        
        if any_child_used:
            return True
        
        if item.data(0, self.UsedRole):
            return True
        
        parent = item.parent()
        if not parent:
            return True
        
        cb = self.tree.itemWidget(item, 0).findChild((QCheckBox,))
        cb.setCheckState(Qt.Unchecked)
        parent.removeChild(item)
        return False
    
    def _on_clicked(self, checked):
        popup = self.popup
        rect = self.rect()
        popup.move(self.mapToGlobal(rect.bottomLeft()))
        #print(popup.geometry(), popup.screen().size())
        if popup.geometry().bottom() > popup.screen().size().height():
            popup.move(self.mapToGlobal(rect.topLeft() - QPoint(0, popup.rect().height())))
        popup.show()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)
        opt = QStyleOptionButton()
        opt.initFrom(self)
        
        if self.temp_show_all_checkbox.isChecked() or len(self.included_folders) == 0:
            painter.setPen(self.palette().placeholderText().color())
        
        m = self.style().pixelMetric(QStyle.PM_ButtonMargin)
        icon_size = self.style().pixelMetric(QStyle.PM_ButtonIconSize)
        opt.rect.setLeft(m + icon_size + round(m/2))
        opt.rect.setRight(opt.rect.right() - m)
        painter.drawText(opt.rect, Qt.AlignLeft | Qt.AlignVCenter, self.label_text)

class FilterLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.setPlaceholderText("Filter by name...")
        self.setClearButtonEnabled(True)
        self.completer = QCompleter()
        self.completer_popup_width_set = False
        
        self.textChanged.connect(self._on_text_changed)
    
    def mouseDoubleClickEvent(self, event):
        #print(f"mouseDoubleClickEvent: ")
        popup = self.completer.popup()
        
        if popup.isVisible():
            return

        if self.text() == "":
            self.completer.setCompletionPrefix("")
            self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
            popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        else:
            self.completer.setCompletionMode(QCompleter.PopupCompletion)

        self.set_completer_popup_width_from_widest_item()
        #popup.show()
        self.completer.complete()
    
    def _on_text_changed(self, text):
        popup = self.completer.popup()
        
        if text == "":
            self.completer.setCompletionPrefix("")
            self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
            popup.move(self.mapToGlobal(self.rect().bottomLeft()))
            QTimer.singleShot(0, popup.show) # popup auto-hides, so force it visible again.
        else:
            self.completer.setCompletionMode(QCompleter.PopupCompletion)
            
        self.set_completer_popup_width_from_widest_item()
        #popup.show()
        self.completer.complete()
    
    def set_completer_popup_width_from_widest_item(self):
        popup = self.completer.popup()
        
        if popup.isVisible() or self.completer_popup_width_set:
            return
        
        model = self.completer.model()
        column = self.completer.completionColumn()
        max_w = 0
        for i in range(model.rowCount()):
            w = model.data(model.index(i, column), Qt.SizeHintRole).width()
            max_w = max(max_w, w)
            #print(i, "->", w)
        
        cm = popup.contentsMargins()
        s = popup.style()
        smpw = s.pixelMetric(QStyle.PM_MenuPanelWidth)
        smhm = s.pixelMetric(QStyle.PM_MenuHMargin)
        smdfw = s.pixelMetric(QStyle.PM_MenuDesktopFrameWidth)
        sdfw = s.pixelMetric(QStyle.PM_DefaultFrameWidth)
        
        #print(s, smpw, smhm, smdfw, sdfw, popup.width()-popup.viewport().width())
        w_pad = cm.left()+cm.right() + 2*smpw + 2*smhm + 2*smdfw + 2*sdfw + popup.width()-popup.viewport().width()
        w_kludge = 4
        w = max(self.rect().width(), max_w + w_pad + w_kludge)
        
        popup.setMinimumWidth(w)
        self.completer_popup_width_set = True
