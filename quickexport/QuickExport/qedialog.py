from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate, QMenu,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup,
                             QActionGroup, QToolButton, QComboBox, QStackedWidget, QStyle, QStyleOption,
                             QStyleOptionButton, QSpinBox, QStyleOptionSpinBox, QGraphicsOpacityEffect,
                             QFileDialog, QSplitter, QSplitterHandle)
from PyQt5.QtCore import Qt, QObject, QRegExp, QModelIndex, pyqtSignal, QEvent
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor, QPainter, QPalette, QMouseEvent, QTabletEvent
import zipfile
from pathlib import Path
from functools import partial
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita
from .utils import *
from .qewidgets import QEMenu, SnapSlider, SpinBoxSlider, QEComboBox, CheckToolButton, ResizingPixmapLabel
from .qefilterwidgets import FilterLineEdit, FolderFilterButton
from .qetree import QETree#QECols, QETree
from .multilineelidedbutton import MultiLineElidedText, MultiLineElidedButton
from .filenameedit import FileNameEdit

app = Krita.instance()

suppress_store_on_widget_edit = False

class SplitterHandle(QSplitterHandle):
    """
    Snapping SplitterHandle for big thumbnail.
    """
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        super().mouseMoveEvent(event)
        self.splitter().user_interacting = True

    def mouseMoveEvent(self, event):
        if not event.buttons() & Qt.LeftButton:
            return
        splitter = self.splitter()
        pos_x = self.mapToParent(event.pos()).x()
        snap_x = QEDialog.instance.preferred_big_thumbnail_height
        if pos_x < 16:
            splitter.moveSplitter(0, 1)
            splitter.user_set_position = 0
        elif abs(snap_x - pos_x) < 8:
            splitter.moveSplitter(snap_x, 1)
            splitter.user_set_position = snap_x
        elif abs(snap_x//2 - pos_x) < 8:
            splitter.moveSplitter(snap_x//2, 1)
            splitter.user_set_position = snap_x//2
        else:
            super().mouseMoveEvent(event)
            splitter.user_set_position = pos_x

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.splitter().user_interacting = False
        super().mouseReleaseEvent(event)


class Splitter(QSplitter):
    """
    Splitter that keeps user-set pixel size of left-side widget, for
    big thumbnail/basic export settings box.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_interacting = False
        self.user_set_position = -1

    def createHandle(self):
        return SplitterHandle(self.orientation(), self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.user_interacting:
            return
        total_size = sum(self.sizes())
        self.setSizes([self.user_set_position, total_size - self.user_set_position])


class QEDialog(QDialog):
    instance = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.__class__.instance = self

        self.first_setup()
        self.installEventFilter(self)

    def eventFilter(self, object, event):
        if event.type() == QEvent.WindowDeactivate:
            extension().update_quick_export_display()
        return False

    def setup(self, msg="", doc=None):
        
        self.highlighted_doc = doc
        
        layout = self.layout()
        
        # TODO: save user changes to tree column sizes and retrieve at each start.
        self.tree_is_ready = False
        self.tree = QETree(self)
        self.tree.addingFolder.connect(self._on_tree_adding_folder)
        self.tree.removingFolder.connect(self._on_tree_removing_folder)
        self.folder_filter_button.setAllFoldersUnused()
        self.tree.setup()
        self.folder_filter_button.purgeUnusedFolders()
        self.tree.source_model.dataChanged.connect(self._on_tree_source_model_data_changed)
        self.tree.selectionModel().selectionChanged.connect(self._on_tree_selection_changed)
        self.tree.requestConfigWidgetsRefreshForPath.connect(self._on_tree_request_config_widgets_refresh_for_path)
        self.tree.requestAddFolderAtPath.connect(self._on_tree_request_add_folder_at_path)
        self.tree.requestAddProjectAtPath.connect(self._on_tree_request_add_project_at_path)
        self.tree.requestShowMessage.connect(self._on_tree_request_show_message)
        self.filter_edit.textChanged.connect(self.tree._on_filter_edit_text_changed)
        
        self.basic_export_settings_container.setDisabled(True)
        self.basic_export_settings_output_path.setText("export path preview")
        self.basic_export_settings_output_path.setDisabled(True)
        
        # TODO: disallow sorting by thumbnail and action button columns.
        #self.tree.setSortingEnabled(True)
        #self.tree.sortByColumn(QECols.OPEN_FILE_COLUMN, Qt.AscendingOrder)
        
        if self.filter_edit.text():
            self.tree._on_filter_edit_text_changed(self.filter_edit.text())
        
        if (included_folders := self.folder_filter_button.includedFolders()):
            self._on_folder_filter_button_filter_changed()
        
        self.tree_container_layout.addWidget(self.tree)
        self.tree_is_ready = True
        
        update_qe_settings_last_load()
        
        self.update_save_button()
        
        #self.tree.set_settings_display_mode()
        
        #self.tree.setup_filter_completer()
        
        if (doc := app.activeDocument()):
            if (filename := doc.fileName()):
                filepath = Path(filename)
                self.tree.select_for_file_path(filepath)
        
        #if self.tree.focused_item:
        #    self.tree.scrollToItem(self.tree.focused_item, QAbstractItemView.PositionAtCenter)
        
        self.update_show_extensions_in_list_for_all_types()
        
        # refresh options button icon, make sure isn't stuck on outdated theme.
        self.options_button.setIcon(app.icon('view-choose'))
        
        # status bar.
        self.sbar_ready_label.setText(" Ready." if msg == "" else " "+msg) # extra space to align with showmessage.
        
        # TODO: inform user about having multiple copies of same file open.
        #if len(self.tree.dup_counts) == 1:
        #    self.sbar_ready_label.setText(f"Note: Multiple copies of '{list(self.tree.dup_counts.keys())[0]}' are currently open in Krita.")
        #elif len(self.tree.dup_counts) > 1:
        #    self.sbar_ready_label.setText(f"Note: Multiple copies of multiple files (hover mouse here to see) are currently open in Krita.")
        #    self.sbar_ready_label.setToolTip("\n".join(self.tree.dup_counts.keys()))

    def first_setup(self):
        layout = QVBoxLayout(self)
        
        view_buttons = QWidget()
        view_buttons_layout = QHBoxLayout()
        
        self.add_button = QToolButton()
        self.add_button.setIcon(app.icon("list-add"))
        self.add_button.setPopupMode(QToolButton.InstantPopup)

        add_button_menu = QMenu()
        add_folder_action = add_button_menu.addAction("Add folder...")
        add_project_action = add_button_menu.addAction("Add project...")
        self.add_button.setMenu(add_button_menu)

        add_folder_action.triggered.connect(self._on_add_folder_action_triggered)
        add_project_action.triggered.connect(self._on_add_project_action_triggered)

        view_buttons_layout.addWidget(self.add_button)
        
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter tree...")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.addAction(app.icon("tool_zoom"), QLineEdit.LeadingPosition)
        view_buttons_layout.addWidget(self.filter_edit)
        
        self.folder_filter_button = FolderFilterButton()
        self.folder_filter_button.setAutoDefault(False)
        self.folder_filter_button.filterChanged.connect(self._on_folder_filter_button_filter_changed)
        
        view_buttons_layout.addWidget(self.folder_filter_button)
        
        view_buttons_layout.setContentsMargins(0,0,0,0)
        view_buttons.setLayout(view_buttons_layout)
        layout.addWidget(view_buttons)

        self.tree_container_layout = QVBoxLayout()
        layout.addLayout(self.tree_container_layout)

        visible_extensions = readSetting("visible_types").split(" ")
        
        if len(visible_extensions) == 0 or not any(test in supported_extensions() for test in visible_extensions):
            # bad config, reset to default.
            writeSetting("visible_types", setting_defaults["visible_types"])
            visible_extensions = readSetting("visible_types").split(" ")

        basic_export_settings_splitter = Splitter()
        
        self.preferred_big_thumbnail_height = 32
        self.big_thumbnail = ResizingPixmapLabel()
        self.big_thumbnail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        basic_export_settings_splitter.addWidget(self.big_thumbnail)

        self.basic_export_settings_container = QGroupBox()
        self.basic_export_settings_container.setDisabled(True)
        basic_export_settings_container_layout = QVBoxLayout(self.basic_export_settings_container)
        self.basic_export_settings_container.setContentsMargins(self.basic_export_settings_container.contentsMargins() / 2)
        basic_export_settings_container_layout.setContentsMargins(basic_export_settings_container_layout.contentsMargins() / 2)

        basic_export_settings_file_container = QWidget()
        basic_export_settings_file_container_layout = QHBoxLayout(basic_export_settings_file_container)
        basic_export_settings_file_container.setContentsMargins(0,0,0,0)
        basic_export_settings_file_container_layout.setContentsMargins(0,0,0,0)

        self.basic_export_settings_file_name = QComboBox()
        self.basic_export_settings_file_name.addItems(["Project name", "File name", "Custom name"])
        basic_export_settings_file_container_layout.addWidget(self.basic_export_settings_file_name)
        self.basic_export_settings_file_name_custom = QLineEdit("Hello")
        sp = self.basic_export_settings_file_name_custom.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.basic_export_settings_file_name_custom.setSizePolicy(sp)
        self.basic_export_settings_file_name_custom.hide()
        basic_export_settings_file_container_layout.addWidget(self.basic_export_settings_file_name_custom)
        
        self.basic_export_settings_file_type = QComboBox()
        self.basic_export_settings_file_type.addItems(supported_extensions())
        for ext in supported_extensions():
            self.update_show_extensions_in_list_for_type(ext, ext in visible_extensions)
        self.basic_export_settings_file_type.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        basic_export_settings_file_container_layout.addWidget(self.basic_export_settings_file_type)

        basic_export_settings_folder_container = QWidget()
        basic_export_settings_folder_container_layout = QHBoxLayout(basic_export_settings_folder_container)
        basic_export_settings_folder_container_layout.setAlignment(Qt.AlignLeft)
        basic_export_settings_folder_container.setContentsMargins(0,0,0,0)
        basic_export_settings_folder_container_layout.setContentsMargins(0,0,0,0)

        self.basic_export_settings_folder_location = QComboBox()
        self.basic_export_settings_folder_location.addItems(["In same folder", "In subfolder", "In parent of folder", "In sibling of folder", "In another folder"])
        self.basic_export_settings_folder_location.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        basic_export_settings_folder_container_layout.addWidget(self.basic_export_settings_folder_location)
        self.basic_export_settings_folder_name = QComboBox()
        self.basic_export_settings_folder_name.addItems(["with project name", "with custom name"])
        self.basic_export_settings_folder_name.hide()
        basic_export_settings_folder_container_layout.addWidget(self.basic_export_settings_folder_name)
        self.basic_export_settings_folder_name_custom = QLineEdit("Folder Name Custom")
        self.basic_export_settings_folder_name_custom.hide()
        basic_export_settings_folder_container_layout.addWidget(self.basic_export_settings_folder_name_custom)
        self.basic_export_settings_location_custom = QLineEdit("Location Custom")
        action = self.basic_export_settings_location_custom.addAction(app.icon("system-help"), QLineEdit.TrailingPosition)
        action.setToolTip("Can be specified relative to source folder:\n 'subfolder'\n 'subfolder/subsubfolder'\n '../parentsiblingfolder'\n '../../grandparentsiblingfolder'\n etc.\n\n"
                          "Or absolute:\n '/home/user/folder' (Unix)\n 'c:/users/user/folder' (Windows).\n\n"
                          "Rather than a fixed path for a specific user,\nprefer '~' for the current user's home folder:\n '~/folder' is '/home/(user)/folder' (Unix)\n '~/folder' is 'c:/users/(user)/folder' (Windows).\n\n"
                          "Relative paths are the most portable: if the source file is moved, a relative path 'moves' with it.\nPrefer to use relative paths.")
        self.basic_export_settings_location_custom.hide()
        basic_export_settings_folder_container_layout.addWidget(self.basic_export_settings_location_custom)
        self.basic_export_settings_folder_custom_switch_type = QToolButton()
        self.basic_export_settings_folder_custom_switch_type.setIcon(app.icon("view-refresh"))
        self.basic_export_settings_folder_custom_switch_type.setToolTip("Swap between absolute and relative paths.")
        self.basic_export_settings_folder_custom_switch_type.hide()
        basic_export_settings_folder_container_layout.addWidget(self.basic_export_settings_folder_custom_switch_type)
        self.basic_export_settings_folder_pick_custom = QToolButton()
        self.basic_export_settings_folder_pick_custom.setIcon(app.icon("folder"))
        self.basic_export_settings_folder_pick_custom.hide()
        basic_export_settings_folder_container_layout.addWidget(self.basic_export_settings_folder_pick_custom)

        basic_export_settings_scale_container = QWidget()
        basic_export_settings_scale_container_layout = QHBoxLayout(basic_export_settings_scale_container)
        basic_export_settings_scale_container_layout.setAlignment(Qt.AlignLeft)
        basic_export_settings_scale_container_layout.setSpacing(0)
        basic_export_settings_scale_container.setContentsMargins(0,0,0,0)
        basic_export_settings_scale_container_layout.setContentsMargins(0,0,0,0)

        self.basic_export_settings_scale_enabled = QCheckBox("Scale")
        basic_export_settings_scale_container_layout.addWidget(self.basic_export_settings_scale_enabled)

        self.basic_export_settings_scale_subcontainer = QWidget()
        basic_export_settings_scale_subcontainer_layout = QHBoxLayout(self.basic_export_settings_scale_subcontainer)
        basic_export_settings_scale_subcontainer_layout.setAlignment(Qt.AlignLeft)
        self.basic_export_settings_scale_subcontainer.setContentsMargins(0,0,0,0)
        basic_export_settings_scale_subcontainer_layout.setContentsMargins(0,0,0,0)

        sp = self.basic_export_settings_scale_subcontainer.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.basic_export_settings_scale_subcontainer.setSizePolicy(sp)

        self.basic_export_settings_scale_side = QComboBox()
        self.basic_export_settings_scale_side.setToolTip("Set the side(s) of the image to be scaled.\n\n"
                                                         "Short and long automatically pick the shortest/longest side of the image.\n"
                                                         "(If the image is square, both sides will be scaled equally.)")
        self.basic_export_settings_scale_side.addItems(["width", "height", "short", "long", "both"])
        basic_export_settings_scale_subcontainer_layout.addWidget(self.basic_export_settings_scale_side)

        basic_export_settings_scale_subcontainer_layout.addWidget(QLabel("to"))

        self.basic_export_settings_scale_w_subcontainer = QWidget()
        basic_export_settings_scale_w_subcontainer_layout = QHBoxLayout(self.basic_export_settings_scale_w_subcontainer)
        basic_export_settings_scale_w_subcontainer_layout.setSpacing(0)
        self.basic_export_settings_scale_w_subcontainer.setContentsMargins(0,0,0,0)
        basic_export_settings_scale_w_subcontainer_layout.setContentsMargins(0,0,0,0)

        self.basic_export_settings_scale_w_size = DoubleParseSpinBox().widget()
        self.basic_export_settings_scale_w_size.setRange(1, 65536)
        self.basic_export_settings_scale_w_size.setDecimals(0)
        self.basic_export_settings_scale_w_size.setButtonSymbols(QSpinBox.NoButtons)
        basic_export_settings_scale_w_subcontainer_layout.addWidget(self.basic_export_settings_scale_w_size)

        self.basic_export_settings_scale_w_mode = QComboBox()
        self.basic_export_settings_scale_w_mode.addItems(("px","%"))
        basic_export_settings_scale_w_subcontainer_layout.addWidget(self.basic_export_settings_scale_w_mode)

        basic_export_settings_scale_subcontainer_layout.addWidget(self.basic_export_settings_scale_w_subcontainer)

        self.basic_export_settings_scale_x_label = QLabel("\u00D7")
        self.basic_export_settings_scale_x_label.hide()
        basic_export_settings_scale_subcontainer_layout.addWidget(self.basic_export_settings_scale_x_label)

        self.basic_export_settings_scale_h_subcontainer = QWidget()
        basic_export_settings_scale_h_subcontainer_layout = QHBoxLayout(self.basic_export_settings_scale_h_subcontainer)
        basic_export_settings_scale_h_subcontainer_layout.setSpacing(0)
        self.basic_export_settings_scale_h_subcontainer.setContentsMargins(0,0,0,0)
        basic_export_settings_scale_h_subcontainer_layout.setContentsMargins(0,0,0,0)

        self.basic_export_settings_scale_h_size = DoubleParseSpinBox().widget()
        self.basic_export_settings_scale_h_size.setRange(1, 65536)
        self.basic_export_settings_scale_h_size.setDecimals(0)
        self.basic_export_settings_scale_h_size.setButtonSymbols(QSpinBox.NoButtons)
        basic_export_settings_scale_h_subcontainer_layout.addWidget(self.basic_export_settings_scale_h_size)

        self.basic_export_settings_scale_h_mode = QComboBox()
        self.basic_export_settings_scale_h_mode.addItems(("px","%"))
        basic_export_settings_scale_h_subcontainer_layout.addWidget(self.basic_export_settings_scale_h_mode)

        self.basic_export_settings_scale_h_subcontainer.hide()
        basic_export_settings_scale_subcontainer_layout.addWidget(self.basic_export_settings_scale_h_subcontainer)

        self.basic_export_settings_scale_keep_proportions = QCheckBox("Keep proportions")
        self.basic_export_settings_scale_keep_proportions.setToolTip("When enabled, automatically scale the other side of the image to preserve aspect ratio.\n"
                                                                     "When disabled, the other side will not be scaled.")
        self.basic_export_settings_scale_keep_proportions.setChecked(True)
        basic_export_settings_scale_subcontainer_layout.addWidget(self.basic_export_settings_scale_keep_proportions)
        
        self.basic_export_settings_scale_filter = QComboBox()
        self.basic_export_settings_scale_filter.setToolTip("Filtering strategy to use when scaling.")
        self.basic_export_settings_scale_filter.addItems(filter_strategy_display_strings)
        basic_export_settings_scale_subcontainer_layout.addWidget(self.basic_export_settings_scale_filter)

        basic_export_settings_scale_container_layout.addWidget(self.basic_export_settings_scale_subcontainer)
        
        self.basic_export_settings_scale_subcontainer.hide()

        self.basic_export_settings_output_path = QLabel("export path preview")
        self.basic_export_settings_output_path.setDisabled(True)
        self.basic_export_settings_output_path.setWordWrap(True)
        self.basic_export_settings_output_path.setTextFormat(Qt.PlainText)
        self.basic_export_settings_output_path.setAlignment(Qt.AlignHCenter)

        self.basic_export_settings_file_name.currentIndexChanged.connect(self._on_basic_export_settings_file_name_current_index_changed)
        self.basic_export_settings_file_name_custom.textChanged.connect(self.update_basic_export_settings_output_path_label)
        self.basic_export_settings_file_type.currentIndexChanged.connect(self.update_basic_export_settings_output_path_label)
        self.basic_export_settings_folder_location.currentIndexChanged.connect(self._on_basic_export_settings_folder_location_current_index_changed)
        self.basic_export_settings_folder_name.currentIndexChanged.connect(self._on_basic_export_settings_folder_name_current_index_changed)
        self.basic_export_settings_folder_name_custom.textChanged.connect(self.update_basic_export_settings_output_path_label)
        self.basic_export_settings_location_custom.textChanged.connect(self.update_basic_export_settings_output_path_label)
        self.basic_export_settings_folder_custom_switch_type.clicked.connect(self._on_basic_export_settings_folder_custom_switch_type_clicked)
        self.basic_export_settings_folder_pick_custom.clicked.connect(self._on_basic_export_settings_folder_pick_custom_clicked)
        self.basic_export_settings_scale_enabled.toggled.connect(self._on_basic_export_settings_scale_enabled_toggled)
        self.basic_export_settings_scale_side.currentIndexChanged.connect(self._on_basic_export_settings_scale_side_current_index_changed)
        self.basic_export_settings_scale_w_size.valueChanged.connect(self.update_export_settings_from_widgets_no_args)
        self.basic_export_settings_scale_w_mode.currentIndexChanged.connect(self._on_basic_export_settings_scale_w_mode_current_index_changed)
        self.basic_export_settings_scale_h_size.valueChanged.connect(self.update_export_settings_from_widgets_no_args)
        self.basic_export_settings_scale_h_mode.currentIndexChanged.connect(self._on_basic_export_settings_scale_h_mode_current_index_changed)
        self.basic_export_settings_scale_keep_proportions.toggled.connect(self.update_export_settings_from_widgets_no_args)
        self.basic_export_settings_scale_filter.currentIndexChanged.connect(self.update_export_settings_from_widgets_no_args)

        basic_export_settings_container_layout.addWidget(basic_export_settings_file_container)
        basic_export_settings_container_layout.addWidget(basic_export_settings_folder_container)
        basic_export_settings_container_layout.addWidget(basic_export_settings_scale_container)
        basic_export_settings_splitter.addWidget(self.basic_export_settings_container)
        layout.addWidget(basic_export_settings_splitter)
        layout.addWidget(self.basic_export_settings_output_path)
        
        basic_export_settings_splitter.setCollapsible(1, False)
        
        # set thumbnail/basic settings splitter to reasonable initial position, then a better one once initial layout is done.
        basic_export_settings_splitter.moveSplitter(64, 1)
        
        def move_splitter():
            h = round(self.basic_export_settings_container.sizeHint().height() * 0.9)
            self.preferred_big_thumbnail_height = h
            basic_export_settings_splitter.moveSplitter(h, 1)
            basic_export_settings_splitter.user_set_position = h
            self.big_thumbnail.setMaximumSize(h*2, h*2)
            # refresh thumbnail.
            index = self.tree.selectionModel().currentIndex()
            if index.isValid():
                index = self.tree.model.mapToSource(index)
                self.set_big_thumbnail(index.data(PathRole))
        QTimer.singleShot(0, lambda: move_splitter())
        
        self.save_buttons_container = QWidget()
        self.save_buttons_container_layout = QHBoxLayout(self.save_buttons_container)
        self.save_buttons_container_layout.setSpacing(0)
        self.save_buttons_container.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.save_buttons_container.setContentsMargins(0,0,0,0)
        self.save_buttons_container_layout.setContentsMargins(0,0,0,0)
        
        self.save_buttons_container_opacity = QGraphicsOpacityEffect(self.save_buttons_container)
        self.save_buttons_container.setGraphicsEffect(self.save_buttons_container_opacity)
        self.save_buttons_container_opacity.setOpacity(0.5)
        self.save_buttons_container.setDisabled(True)
        
        # revert button.
        self.revert_button = QToolButton()
        self.revert_button.setToolTip("Revert settings to last save.")
        self.revert_button.setAutoRaise(True)
        self.revert_button.setIcon(app.icon("edit-undo"))
        self.revert_button.clicked.connect(self._on_revert_button_clicked)
        self.save_buttons_container_layout.addWidget(self.revert_button)

        # save button.
        self.save_button = QToolButton()
        self.save_button.setToolTip("Save settings now.")
        self.save_button.setAutoRaise(True)
        self.save_button.setIcon(app.icon("document-save"))
        self.save_button.clicked.connect(self._on_save_button_clicked)
        self.save_buttons_container_layout.addWidget(self.save_button)
        
        # status bar area.
        status_widget = QWidget()
        status_layout = QHBoxLayout()
        
        # qe options menu.
        self.options_button = QToolButton()
        self.options_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.options_button.setAutoRaise(True)
        self.options_button.setStyleSheet("QToolButton::menu-indicator {image: none;}")
        self.options_button.setPopupMode(QToolButton.InstantPopup)
        status_layout.addWidget(self.options_button)
        
        options_menu = QEMenu()

        custom_icons_menu = QEMenu()

        use_custom_icons_action = custom_icons_menu.addAction("Use custom icons")
        use_custom_icons_action.setCheckable(True)
        use_custom_icons_action.setChecked(str2qtcheckstate(readSetting("use_custom_icons")))
        use_custom_icons_action.toggled.connect(self._on_use_custom_icons_action_toggled)

        custom_icons_menu.addSeparator()

        custom_icons_theme_action_group = QActionGroup(custom_icons_menu)
        custom_icons_theme_action_group.triggered.connect(lambda action, grp=custom_icons_theme_action_group: self._on_custom_icons_theme_action_group_triggered(action, grp))

        icons_follow_theme_action = custom_icons_menu.addAction("Try to follow theme")
        icons_follow_theme_action.setToolTip("If using one of the themes bundled with Krita, the correct icons will be used.\n" \
                                             "If not, guesses which icons to use based on keywords in the theme name ('dark', 'black', etc.)\n" \
                                             "If there are no such keywords, assumes light theme. You can force a theme if the guess is wrong.")
        icons_follow_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_follow_theme_action.setCheckable(True)
        icons_follow_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme"), "follow"))

        icons_light_theme_action = custom_icons_menu.addAction("Use light theme icons")
        icons_light_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_light_theme_action.setCheckable(True)
        icons_light_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme"), "light"))

        icons_dark_theme_action = custom_icons_menu.addAction("Use dark theme icons")
        icons_dark_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_dark_theme_action.setCheckable(True)
        icons_dark_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme"), "dark"))

        custom_icons_action = options_menu.addAction("Custom icons")
        custom_icons_action.setMenu(custom_icons_menu)

        options_menu.addSeparator()
        
        show_export_name_in_menu_action = options_menu.addAction("Show export name in File menu")
        show_export_name_in_menu_action.setToolTip("When possible, show in the File menu as 'Quick Export to 'myImageName.png'.\n" \
                                                   "Otherwise show as 'Quick Export' only.")
        show_export_name_in_menu_action.setCheckable(True)
        show_export_name_in_menu_action.setChecked(str2qtcheckstate(readSetting("show_export_name_in_menu")))
        show_export_name_in_menu_action.toggled.connect(self._on_show_export_name_in_menu_action_toggled)
        
        default_export_unsaved_action = options_menu.addAction("Default export for unsaved images")
        default_export_unsaved_action.setToolTip("Run the normal Krita exporter when you press Quick Export for not-yet-saved images.\n" \
                                                 "Otherwise don't export, just show a reminder to save the file.")
        default_export_unsaved_action.setCheckable(True)
        default_export_unsaved_action.setChecked(str2qtcheckstate(readSetting("default_export_unsaved")))
        default_export_unsaved_action.toggled.connect(self._on_default_export_unsaved_action_toggled)
        
        options_menu.addSeparator()
        
        create_export_folders_menu = QEMenu()

        create_export_folders_action_group = QActionGroup(create_export_folders_menu)
        create_export_folders_action_group.triggered.connect(lambda action, grp=create_export_folders_action_group: self._on_create_export_folders_action_group_triggered(action, grp))

        create_export_folders_never_action = create_export_folders_menu.addAction("Never")
        create_export_folders_never_action.setToolTip("When trying to export to a folder that doesn't exist, the export will fail.")
        create_export_folders_never_action.setActionGroup(create_export_folders_action_group)
        create_export_folders_never_action.setCheckable(True)
        create_export_folders_never_action.setChecked(str2qtcheckstate(readSetting("create_missing_folders_at_export"), "never"))

        create_export_folders_ask_action = create_export_folders_menu.addAction("Ask")
        create_export_folders_ask_action.setToolTip("When trying to export to a folder that doesn't exist, you will be asked if you want to create the missing folder(s).")
        create_export_folders_ask_action.setActionGroup(create_export_folders_action_group)
        create_export_folders_ask_action.setCheckable(True)
        create_export_folders_ask_action.setChecked(str2qtcheckstate(readSetting("create_missing_folders_at_export"), "ask"))

        create_export_folders_always_action = create_export_folders_menu.addAction("Always")
        create_export_folders_always_action.setToolTip("When trying to export to a folder that doesn't exist, the missing folder(s) will first be created, then the export will continue.")
        create_export_folders_always_action.setActionGroup(create_export_folders_action_group)
        create_export_folders_always_action.setCheckable(True)
        create_export_folders_always_action.setChecked(str2qtcheckstate(readSetting("create_missing_folders_at_export"), "always"))

        create_export_folders_action = options_menu.addAction("Create missing folders at export")
        create_export_folders_action.setMenu(create_export_folders_menu)
        
        options_menu.addSeparator()
        
        # auto save settings on close button.
        autosave_on_close_action = options_menu.addAction("Autosave on dialog close")
        autosave_on_close_action.setToolTip("Automatically save changes to settings without asking when you close the dialog.\n" \
                                            "If disabled, unsaved settings will be lost when you close the dialog.")
        autosave_on_close_action.setCheckable(True)
        autosave_on_close_action.setChecked(str2qtcheckstate(readSetting("auto_save_on_close")))
        autosave_on_close_action.toggled.connect(self._on_auto_save_on_close_action_toggled)
        
        show_thumbnails_for_unopened_images_action = options_menu.addAction("Load thumbnails")
        show_thumbnails_for_unopened_images_action.setToolTip("Changing this setting will not affect existing thumbnails.")
        show_thumbnails_for_unopened_images_action.setCheckable(True)
        show_thumbnails_for_unopened_images_action.setChecked(str2qtcheckstate(readSetting("show_thumbnails_for_unopened")))
        show_thumbnails_for_unopened_images_action.toggled.connect(lambda checked: writeSetting("show_thumbnails_for_unopened", bool2str(checked)))
        
        self.show_extensions_in_list_menu = QEMenu()
        
        for ext in supported_extensions():
            action = self.show_extensions_in_list_menu.addAction(ext)
            action.setCheckable(True)
            action.setChecked(ext in visible_extensions)
        
        self.show_extensions_in_list_menu.triggered.connect(self._on_show_extensions_in_list_menu_triggered)
        show_extensions_in_list_action = options_menu.addAction("Visible file types")
        show_extensions_in_list_action.setMenu(self.show_extensions_in_list_menu)
        self.post_update_show_extensions_in_list()
                
        options_menu.addSeparator()
        
        if False:
            wide_column_resize_grabber_action = options_menu.addAction("Wider grabber for resizing columns")
            wide_column_resize_grabber_action.setToolTip("The regions in the header where you can click and drag to resize columns will be twice as wide.\n" \
                                                         "Try this option if you frequently sort or move columns by accident.")
            wide_column_resize_grabber_action.setCheckable(True)
            wide_column_resize_grabber_action.setChecked(str2qtcheckstate(readSetting("wide_column_resize_grabber")))
            wide_column_resize_grabber_action.toggled.connect(self._on_wide_column_resize_grabber_action_toggled)
        
        self.options_button.setMenu(options_menu)
        
        # status bar.
        # TODO: allow custom prompt messages on startup to be reset once eg. an image has been exported?
        self.sbar = QStatusBar()
        self.sbar_ready_label = QLabel()
        self.sbar.insertWidget(0, self.sbar_ready_label)
        
        # statistics (number of items, of which hidden).
        self.statistics_label = QLabel("")
        self.statistics_label_opacity = QGraphicsOpacityEffect(self.statistics_label)
        self.statistics_label_opacity.setOpacity(0.5)
        self.statistics_label.setGraphicsEffect(self.statistics_label_opacity)
        self.sbar.addPermanentWidget(self.statistics_label)
        
        self.sbar.addPermanentWidget(self.save_buttons_container)
        
        status_layout.addWidget(self.sbar)
        
        status_layout.setContentsMargins(0,0,0,0)
        status_widget.setContentsMargins(0,0,0,0)
        status_widget.setLayout(status_layout)
        layout.addWidget(status_widget)
        
        cm = layout.contentsMargins()
        layout.setContentsMargins(2,2,2,2)
        
        layout.setSpacing(2)

        # setup dialog window.
        self.setLayout(layout)
        self.setWindowTitle("Quick Export")
        dialog_width = int(readSetting("dialogWidth"))
        dialog_height = int(readSetting("dialogHeight"))
        self.resize(dialog_width, dialog_height)

    def OLD_first_setup(self):

        layout = QVBoxLayout()

        view_buttons = QWidget()
        view_buttons_layout = QHBoxLayout()

        # TODO: inform user that some items are currently hidden, and how many.

        # show unstored button.
        tooltip = "Show unstored\n" \
                  "Enable this to pick the images you're interested in exporting, then disable it to hide the rest."
        self.show_unstored_button = CheckToolButton(icon_name="show_unstored", checked=str2bool(readSetting("show_unstored")), tooltip=tooltip)
        self.show_unstored_button.clicked.connect(self._on_show_unstored_button_clicked)

        # show unopened button.
        tooltip = "Show unopened\n" \
                  "Show the export settings of every file - currently open or not - for which settings have been saved."
        self.show_unopened_button = CheckToolButton(icon_name="show_unopened", checked=str2bool(readSetting("show_unopened")), tooltip=tooltip)
        self.show_unopened_button.clicked.connect(self._on_show_unopened_button_clicked)

        # show non-kra files button.
        tooltip = "Show non-kra\n" \
                  "Show export settings for files of usually exported types, such as .png and .jpg. Disabled by default because it's kind of redundant."
        self.show_non_kra_button = CheckToolButton(icon_name="show_non_kra", checked=str2bool(readSetting("show_non_kra")), tooltip=tooltip)
        self.show_non_kra_button.clicked.connect(self._on_show_non_kra_button_clicked)

        self.settings_display_mode_combobox = QEComboBox(flat=False)
        self.settings_display_mode_combobox.addItem("Minimized", "minimized", "All rows are minimized.")
        self.settings_display_mode_combobox.addItem("Compact", "compact", "All rows are compact.")
        self.settings_display_mode_combobox.addItem("Focused", "focused", "The focused row is expanded, all others are compact or minimized.\nDouble-click a row to focus it.")
        self.settings_display_mode_combobox.addItem("Expanded", "expanded", "All rows are expanded.")
        self.settings_display_mode_combobox.setCurrentIndex(self.settings_display_mode_combobox.findData(readSetting("settings_display_mode")))
        self.settings_display_mode_combobox.currentIndexChanged.connect(self._on_settings_display_mode_combobox_current_index_changed)

        self.settings_minimize_unfocused_button = QCheckBox("minimize")
        self.settings_minimize_unfocused_button.setToolTip("In focused display mode, reduce the size of the unfocused rows.")
        self.settings_minimize_unfocused_button.setCheckState(str2qtcheckstate(readSetting("minimize_unfocused")))
        self.settings_minimize_unfocused_button.setVisible(readSetting("settings_display_mode") == "focused")
        self.settings_minimize_unfocused_button.clicked.connect(self._on_settings_minimize_unfocused_button_clicked)

        self.filter_edit = FilterLineEdit()
        
        self.folder_filter_button = FolderFilterButton()
        self.folder_filter_button.setAutoDefault(False)
        self.folder_filter_button.filterChanged.connect(self._on_folder_filter_button_filter_changed)

        self.fade_button = QToolButton()
        self.fade_button.setText("Fade")
        self.fade_button.setAutoRaise(True)
        self.fade_button.clicked.connect(self._on_fade_button_clicked)

        self.alt_row_contrast_slider = SpinBoxSlider("Contrast", "%", 0, 100, 2, "")
        self.alt_row_contrast_slider.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.alt_row_contrast_slider.setValue(int(readSetting("alt_row_contrast")))
        self.alt_row_contrast_slider.valueChanged.connect(self._on_alt_row_contrast_slider_value_changed)

        self.unhovered_fade_slider = SpinBoxSlider("Settings", "%", 0, 100, 5, "")
        self.unhovered_fade_slider.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.unhovered_fade_slider.setValue(int(readSetting("unhovered_fade")))
        self.unhovered_fade_slider.valueChanged.connect(self._on_unhovered_fade_slider_value_changed)

        self.stored_highlight_slider = SpinBoxSlider("Stored", "%", 0, 100, 5, "")
        self.stored_highlight_slider.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.stored_highlight_slider.setValue(int(readSetting("highlight_alpha")))
        self.stored_highlight_slider.valueChanged.connect(self._on_stored_highlight_slider_value_changed)
        
        self.update_fade_sliders_visibility(str2bool(readSetting("show_fade_sliders")))

        view_buttons_layout.addWidget(QLabel("Show:"))
        view_buttons_layout.addWidget(self.show_non_kra_button)
        view_buttons_layout.addWidget(self.show_unopened_button)
        view_buttons_layout.addWidget(self.show_unstored_button)
        view_buttons_layout.addWidget(self.settings_display_mode_combobox)
        view_buttons_layout.addWidget(self.settings_minimize_unfocused_button)
        view_buttons_layout.addWidget(self.filter_edit)
        view_buttons_layout.addWidget(self.folder_filter_button)
        view_buttons_layout.addWidget(self.fade_button)
        view_buttons_layout.addWidget(self.alt_row_contrast_slider)
        view_buttons_layout.addWidget(self.unhovered_fade_slider)
        view_buttons_layout.addWidget(self.stored_highlight_slider)

        view_buttons_layout.setContentsMargins(0,0,0,0)
        view_buttons.setLayout(view_buttons_layout)
        layout.addWidget(view_buttons)

        config_buttons = QWidget()
        config_buttons_layout = QHBoxLayout()

        # advanced mode button.
        self.advanced_mode_button = QCheckBox("Advanced")
        self.advanced_mode_button.setToolTip("Basic mode: export settings are saved by default (recommended).\nAdvanced mode: configure how settings are stored.")
        self.advanced_mode_button.setCheckState(str2qtcheckstate(readSetting("advanced_mode")))
        self.advanced_mode_button.clicked.connect(self._on_advanced_mode_button_clicked)

        self.auto_store_label = QLabel("Store on:")

        # auto store for modified button.
        self.auto_store_on_modify_button = QCheckBox("modify")
        self.auto_store_on_modify_button.setToolTip("Automatically check the store button for a file when you modify any of its export settings.")
        self.auto_store_on_modify_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_modify")))
        self.auto_store_on_modify_button.clicked.connect(self._on_auto_store_on_modify_button_clicked)

        # auto store for exported button.
        self.auto_store_on_export_button = QCheckBox("export")
        self.auto_store_on_export_button.setToolTip("Automatically check the store button for a file when you export it.")
        self.auto_store_on_export_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_export")))
        self.auto_store_on_export_button.clicked.connect(self._on_auto_store_on_export_button_clicked)

        # auto save settings on close button.
        self.auto_save_on_close_button = QCheckBox("Autosave on close")
        self.auto_save_on_close_button.setToolTip("Automatically save changes to settings without asking when you close the dialog.")
        self.auto_save_on_close_button.setCheckState(str2qtcheckstate(readSetting("auto_save_on_close")))
        self.auto_save_on_close_button.clicked.connect(self._on_auto_save_on_close_button_clicked)

        # save button.
        self.save_button = QPushButton("Save Settings*")
        self.save_button.setMinimumWidth(self.save_button.sizeHint().width())
        self.save_button.setText("Save Settings")
        self.save_button.setDisabled(True)
        self.save_button.clicked.connect(self._on_save_button_clicked)

        config_buttons_layout.addWidget(self.auto_store_label)
        config_buttons_layout.addWidget(self.auto_store_on_modify_button)
        config_buttons_layout.addWidget(self.auto_store_on_export_button)
        config_buttons_layout.addStretch()
        config_buttons_layout.addWidget(self.auto_save_on_close_button)
        config_buttons_layout.addWidget(self.save_button)

        config_buttons_layout.setContentsMargins(0,0,0,0)
        config_buttons.setLayout(config_buttons_layout)
        layout.addWidget(config_buttons)

        # status bar area.
        status_widget = QWidget()
        status_layout = QHBoxLayout()
        
        # qe options menu.
        self.options_button = QToolButton()
        self.options_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.options_button.setAutoRaise(True)
        self.options_button.setStyleSheet("QToolButton::menu-indicator {image: none;}")
        self.options_button.setPopupMode(QToolButton.InstantPopup)
        status_layout.addWidget(self.options_button)
        
        options_menu = QEMenu()

        custom_icons_menu = QEMenu()

        use_custom_icons_action = custom_icons_menu.addAction("Use custom icons")
        use_custom_icons_action.setCheckable(True)
        use_custom_icons_action.setChecked(str2qtcheckstate(readSetting("use_custom_icons")))
        use_custom_icons_action.toggled.connect(self._on_use_custom_icons_action_toggled)

        custom_icons_menu.addSeparator()

        custom_icons_theme_action_group = QActionGroup(custom_icons_menu)
        custom_icons_theme_action_group.triggered.connect(lambda action, grp=custom_icons_theme_action_group: self._on_custom_icons_theme_action_group_triggered(action, grp))

        icons_follow_theme_action = custom_icons_menu.addAction("Try to follow theme")
        icons_follow_theme_action.setToolTip("If using one of the themes bundled with Krita, the correct icons will be used.\n" \
                                             "If not, guesses which icons to use based on keywords in the theme name ('dark', 'black', etc.)\n" \
                                             "If there are no such keywords, assumes light theme. You can force a theme if the guess is wrong.")
        icons_follow_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_follow_theme_action.setCheckable(True)
        icons_follow_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme"), "follow"))

        icons_light_theme_action = custom_icons_menu.addAction("Use light theme icons")
        icons_light_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_light_theme_action.setCheckable(True)
        icons_light_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme"), "light"))

        icons_dark_theme_action = custom_icons_menu.addAction("Use dark theme icons")
        icons_dark_theme_action.setActionGroup(custom_icons_theme_action_group)
        icons_dark_theme_action.setCheckable(True)
        icons_dark_theme_action.setChecked(str2qtcheckstate(readSetting("custom_icons_theme"), "dark"))

        custom_icons_action = options_menu.addAction("Custom icons")
        custom_icons_action.setMenu(custom_icons_menu)

        options_menu.addSeparator()
        
        show_export_name_in_menu_action = options_menu.addAction("Show export name in File menu")
        show_export_name_in_menu_action.setToolTip("When possible, show in the File menu as 'Quick Export to 'myImageName.png'.\n" \
                                                   "Otherwise show as 'Quick Export' only.")
        show_export_name_in_menu_action.setCheckable(True)
        show_export_name_in_menu_action.setChecked(str2qtcheckstate(readSetting("show_export_name_in_menu")))
        show_export_name_in_menu_action.toggled.connect(self._on_show_export_name_in_menu_action_toggled)
        
        default_export_unsaved_action = options_menu.addAction("Default export for unsaved images")
        default_export_unsaved_action.setToolTip("Run the normal Krita exporter when you press Quick Export for not-yet-saved images.\n" \
                                                 "Otherwise don't export, just show a reminder to save the file.")
        default_export_unsaved_action.setCheckable(True)
        default_export_unsaved_action.setChecked(str2qtcheckstate(readSetting("default_export_unsaved")))
        default_export_unsaved_action.toggled.connect(self._on_default_export_unsaved_action_toggled)
        
        options_menu.addSeparator()
        
        show_thumbnails_for_unopened_images_action = options_menu.addAction("Show thumbnails for unopened images")
        show_thumbnails_for_unopened_images_action.setToolTip("Will take effect when this dialog next runs.")
        show_thumbnails_for_unopened_images_action.setCheckable(True)
        show_thumbnails_for_unopened_images_action.setChecked(str2qtcheckstate(readSetting("show_thumbnails_for_unopened")))
        show_thumbnails_for_unopened_images_action.toggled.connect(lambda checked: writeSetting("show_thumbnails_for_unopened", bool2str(checked)))
        
        self.show_extensions_in_list_menu = QEMenu()
        visible_extensions = readSetting("visible_types").split(" ")
        
        if len(visible_extensions) == 0 or not any(test in supported_extensions() for test in visible_extensions):
            # bad config, reset to default.
            writeSetting("visible_types", setting_defaults["visible_types"])
            visible_extensions = (".jpg", ".jpeg", ".png")
        
        for ext in supported_extensions():
            action = self.show_extensions_in_list_menu.addAction(ext)
            action.setCheckable(True)
            action.setChecked(ext in visible_extensions)
        
        self.show_extensions_in_list_menu.triggered.connect(self._on_show_extensions_in_list_menu_triggered)
        show_extensions_in_list_action = options_menu.addAction("Visible file types")
        show_extensions_in_list_action.setMenu(self.show_extensions_in_list_menu)
        
        options_menu.addSeparator()
        
        wide_column_resize_grabber_action = options_menu.addAction("Wider grabber for resizing columns")
        wide_column_resize_grabber_action.setToolTip("The regions in the header where you can click and drag to resize columns will be twice as wide.\n" \
                                                     "Try this option if you frequently sort or move columns by accident.")
        wide_column_resize_grabber_action.setCheckable(True)
        wide_column_resize_grabber_action.setChecked(str2qtcheckstate(readSetting("wide_column_resize_grabber")))
        wide_column_resize_grabber_action.toggled.connect(self._on_wide_column_resize_grabber_action_toggled)
        
        self.options_button.setMenu(options_menu)
        
        status_layout.addWidget(self.advanced_mode_button)
        
        # status bar.
        # TODO: allow custom prompt messages on startup to be reset once eg. an image has been exported?
        self.sbar = QStatusBar()
        self.sbar_ready_label = QLabel()
        self.sbar.insertWidget(0, self.sbar_ready_label)
        status_layout.addWidget(self.sbar)
        
        # statistics (number of items, of which hidden).
        self.statistics_label = QLabel("")
        self.statistics_label_opacity = QGraphicsOpacityEffect(self.statistics_label)
        self.statistics_label_opacity.setOpacity(0.5)
        self.statistics_label.setGraphicsEffect(self.statistics_label_opacity)
        self.sbar.addPermanentWidget(self.statistics_label)
        
        status_layout.setContentsMargins(0,0,0,0)
        status_widget.setLayout(status_layout)
        layout.addWidget(status_widget)

        # setup dialog window.
        self.setLayout(layout)
        self.setWindowTitle("Quick Export")
        dialog_width = int(readSetting("dialogWidth"))
        dialog_height = int(readSetting("dialogHeight"))
        self.resize(dialog_width, dialog_height)
    
    def reject(self):
        self.close()
    
    def closeEvent(self, event):
        # TODO: export file name not set if user doesn't unfocus lineedit before closing.
        ret = QMessageBox.Discard
        
        if str2bool(readSetting("auto_save_on_close")):
            # save without asking.
            ret = QMessageBox.Save
        elif self.save_buttons_container.isEnabled():
            # ask user.
            msgBox = QMessageBox(self)
            msgBox.setText("There are unsaved changes to export settings.")
            msgBox.setInformativeText("Do you want to save your changes?")
            msgBox.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msgBox.setDefaultButton(QMessageBox.Save)
            ret = msgBox.exec()
        
        if ret == QMessageBox.Cancel:
            event.ignore()
            return
        
        self.sbar.clearMessage()
        
        writeSetting("dialogWidth", str(self.size().width()))
        writeSetting("dialogHeight", str(self.size().height()))
        
        if False:
            self.tree.thumbnail_worker.close()
            
            if len(self.tree.items) > 0:
                # only write columns state if they've been fit to any items.
                state = self.tree.header().saveState()
                state_str = str(state.toBase64()).lstrip("b'").rstrip("'")
                writeSetting("columns_state", state_str)
        
        self.tree_container_layout.removeWidget(self.tree)
        WidgetBin.addWidget(self.tree)
        QETree.instance = None
        self.tree = None
        
        if ret == QMessageBox.Save:
            save_settings_to_config()
        else:
            load_settings_from_config(suppress_version_warning=True)
        
        extension().update_quick_export_display()
        event.accept()

    def update_save_button(self):
        if is_any_qe_setting_modified():
            if not self.save_buttons_container.isEnabled():
                self.save_buttons_container.setDisabled(False)
                self.save_buttons_container_opacity.setOpacity(1.0)
        else:
            if self.save_buttons_container.isEnabled():
                self.save_buttons_container.setDisabled(True)
                self.save_buttons_container_opacity.setOpacity(0.5)

    def _on_show_unstored_button_clicked(self, checked):
        writeSetting("show_unstored", bool2str(checked))
        self.tree.refilter()

    def _on_show_unopened_button_clicked(self, checked):
        writeSetting("show_unopened", bool2str(checked))
        self.tree.refilter()

    def _on_show_non_kra_button_clicked(self, checked):
        writeSetting("show_non_kra", bool2str(checked))
        self.tree.refilter()
    
    def _on_folder_filter_button_filter_changed(self):
        self.tree.model.setIncludedFolders(self.folder_filter_button.includedFolders())
        self.tree.model.invalidateFilter()
        self.tree.add_buttons_for_all_rows()

    def _on_auto_save_on_close_action_toggled(self, checked):
        writeSetting("auto_save_on_close", bool2str(checked))

    def _on_use_custom_icons_action_toggled(self, checked):
        writeSetting("use_custom_icons", bool2str(checked))
        extension().update_action_icons()

    def _on_custom_icons_theme_action_group_triggered(self, action, group):
        writeSetting("custom_icons_theme", ["follow","light","dark"][group.actions().index(action)])
        extension().update_action_icons()
    
    def _on_create_export_folders_action_group_triggered(self, action, group):
        writeSetting("create_missing_folders_at_export", ("never","ask","always")[group.actions().index(action)])
    
    def _on_show_export_name_in_menu_action_toggled(self, checked):
        writeSetting("show_export_name_in_menu", bool2str(checked))
        extension().update_quick_export_display()
    
    def _on_default_export_unsaved_action_toggled(self, checked):
        writeSetting("default_export_unsaved", bool2str(checked))
        extension().update_quick_export_display()

    def update_show_extensions_in_list_for_all_types(self):
        return
        for action in self.show_extensions_in_list_menu.actions():
            self.update_show_extensions_in_list_for_type(action.text(), action.isChecked())
        self.post_update_show_extensions_in_list()

    def _on_show_extensions_in_list_menu_triggered(self, action):
        self.update_show_extensions_in_list_for_type(action.text(), action.isChecked())
        self.post_update_show_extensions_in_list()

    def post_update_show_extensions_in_list(self):
        last_checked = None
        last_disabled = None
        visible_types = []
        checked_count = 0
        for a in self.show_extensions_in_list_menu.actions():
            if not a.isEnabled():
                last_disabled = a
            if a.isChecked():
                visible_types.append(a.text())
                checked_count += 1
                last_checked = a
        
        if checked_count < 2:
            last_checked.setDisabled(True)
        else:
            if last_disabled:
                last_disabled.setDisabled(False)
        
        writeSetting("visible_types", " ".join(visible_types))

    def update_show_extensions_in_list_for_type(self, ext, show):
        combobox = self.basic_export_settings_file_type    
        model = combobox.model()
        for item_idx in range(combobox.count()):
            t = combobox.itemText(item_idx)
            #print(f"{item_idx=}, {t=}, {ext=}, {show=}")
            if t != ext:
                continue
            combobox.view().setRowHidden(item_idx, not show)
            item = model.item(item_idx)
            flags = item.flags()
            item.setFlags((flags & ~Qt.ItemIsEnabled) if not show else (flags | Qt.ItemIsEnabled))

    def _on_wide_column_resize_grabber_action_toggled(self, checked):
        writeSetting("wide_column_resize_grabber", bool2str(checked))
        self.tree.header().setStyle(self.tree.wide_header_style if checked else self.tree.style())

    def _on_revert_button_clicked(self, checked):
        self.tree_container_layout.removeWidget(self.tree)
        WidgetBin.addWidget(self.tree)
        QETree.instance = None
        self.tree = None
        
        load_settings_from_config(suppress_version_warning=True)
        
        extension().update_quick_export_display()
        
        # TODO: verify highlighted_doc still exists before passing it.
        self.setup()
        self.sbar.showMessage("Settings reverted.", 2500)

    def _on_save_button_clicked(self, checked):
        save_settings_to_config()
        self.save_buttons_container.setDisabled(True)
        self.save_buttons_container_opacity.setOpacity(0.5)
        self.sbar.showMessage("Settings saved.", 2500)

    def _on_add_folder_action_triggered(self, start_path = None, force_use_start_path = False):
        start_path = start_path or Path(app.activeDocument().fileName()).parent if app.activeDocument() else Path.home()
        print("add folder at start_path =", start_path)
        result = FileDialog.getExistingDirectory(self, "Locate folder", str(start_path), "QE_AddFolderToTree" if not force_use_start_path else None)
        if not result:
            return
        item = self.tree.add_folder_to_tree(Path(result))
        self.tree.selectionModel().select(self.tree.model.mapFromSource(item.index()), QItemSelectionModel.ClearAndSelect)

    def _on_add_project_action_triggered(self, start_path = None, force_use_start_path = False):
        start_path = start_path or Path(app.activeDocument().fileName()).parent if app.activeDocument() else Path.home()
        print("add project at start_path =", start_path)

        file = FileDialog.getOpenFileName(self, "locate file", str(start_path), "Krita document (*.kra)", None, "QE_AddProjectToTree" if not force_use_start_path else None)
        print(f"{file=}")
        if not file:
            return
        file = Path(file)
        base = base_stem_and_version_number_for_versioned_file(file)[0]
        path = file.parent / base
        item = self.tree.add_base_to_tree(path)
        self.tree.expand(self.tree.model.mapFromSource(item.parent().index()))
        self.tree.selectionModel().select(self.tree.model.mapFromSource(item.index()), QItemSelectionModel.ClearAndSelect)

    def _on_tree_source_model_data_changed(self, topLeft, bottomRight, roles):
        # TODO: restrict save string update to affected items.
        for path in qe_settings.keys():
            generate_save_string(path)
        self.update_save_button()

    def _on_tree_selection_changed(self, selected, deselected):
        #print(len(selected), "selected", selected)
        #print(len(deselected), "deselected", deselected)
        
        rows = self.tree.selectionModel().selectedRows()
        
        model = self.tree.model
        
        if len(rows) == 1:
            self.basic_export_settings_container.setDisabled(False)
            
            index = rows[0]
            index = model.mapToSource(index)
            path = index.data(PathRole)
            #print("_on_tree_selection_changed:", index.row(), index.column(), index.parent(), index.model(), index.data(PathRole))
            self.set_basic_export_settings_controls_for_path(path)
            
            self.set_big_thumbnail(path)
            
        else:
            self.basic_export_settings_container.setDisabled(True)
            self.basic_export_settings_output_path.setText("export path preview")
            self.basic_export_settings_output_path.setDisabled(True)
            
            if len(rows) == 0 and self.tree.selectionModel().currentIndex().isValid():
                global suppress_store_on_widget_edit
                suppress_store_on_widget_edit = True
                self.update_basic_export_settings_output_path_label()
                suppress_store_on_widget_edit = False
                
                index = self.tree.selectionModel().currentIndex()
                index = model.mapToSource(index)
                self.set_big_thumbnail(index.data(PathRole))
            else:
                self.set_big_thumbnail(None)

    def set_big_thumbnail(self, path=Path()):
        if not path:
            self.big_thumbnail.setPixmap(None)
            return
        
        file_to_use = None
        
        if path.exists() and path.is_file():
            # file.
            file_to_use = path
        elif path.parent.exists():
            # project.
            sorted_list = sorted(path.parent.glob(f"{path.name}*.kra"), key = lambda file: Path(file).stat().st_mtime)
            for file in sorted_list:
                file_base = base_stem_and_version_number_for_versioned_file(file)[0]
                if path.stem == file_base:
                    file_to_use = file
        
        if file_to_use:
            print(f"set_big_thumbnail from {file_to_use} at {self.preferred_big_thumbnail_height*2}px")
            thumb = _make_thumbnail_for_file(file_to_use)
            icon = square_thumbnail(thumb, self.preferred_big_thumbnail_height*2)
            self.big_thumbnail.setPixmap(icon)
        else:
            self.big_thumbnail.setPixmap(None)

    def update_basic_export_settings_output_path_label(self):
        sel_rows = self.tree.selectionModel().selectedRows()
        
        if len(sel_rows) == 0:
            if self.tree.selectionModel().currentIndex().isValid():
                sel_rows = [self.tree.selectionModel().currentIndex()]
        
        if len(sel_rows) != 1:
            return
        
        model = self.tree.model
        
        index = sel_rows[0]
        index = model.mapToSource(index)
        
        path = index.data(PathRole)
        item_type = index.data(ItemTypeRole)
        
        settings = None
        
        if path in qe_settings:
            settings = qe_settings[path]
            
            self.update_export_settings_from_widgets(path, settings)
        
        if not settings:
            settings_path = find_settings_path_for_file(path)
            if not settings_path:
                return
            settings = qe_settings[settings_path]
        
        output_path = export_file_path(settings, path, item_type=item_type)
        
        self.basic_export_settings_output_path.setText(str(output_path))
        self.basic_export_settings_output_path.setDisabled(False)

        #print("--update_basic_export_settings_output_path_label--")
        #for x,y in enumerate(qe_settings):
            #print(x, y, qe_settings[y])
        #print("--")

    def update_export_settings_from_widgets_no_args(self):
        # can be connected to by signals to call update_export_settings_from_widgets
        # without passing parameters like checked, index, text etc. on to it
        # (which would end up as path and settings args, which is bad).
        self.update_export_settings_from_widgets()

    def update_export_settings_from_widgets(self, path=None, settings=None):
        #print(f"update_export_settings_from_widgets: {path=} {settings=}")
        global suppress_store_on_widget_edit
        if suppress_store_on_widget_edit:
            #print("suppressed store on widget edit")
            return
        
        if not (path and settings):
            print("no path and setting")
            if not path:
                index = self.tree.selectionModel().currentIndex()
                if not index.isValid():
                    print("invalid index")
                    return
                model = self.tree.model
                index = model.mapToSource(index)
                path = index.data(PathRole)
            if path not in qe_settings:
                print(f"{path=} not in settings")
                return
            settings = qe_settings[path]
        
        file_name_source_index = self.basic_export_settings_file_name.currentIndex()
        file_name_custom = self.basic_export_settings_file_name_custom.text()
        output_extension = self.basic_export_settings_file_type.currentText()
        location_index = self.basic_export_settings_folder_location.currentIndex()
        location_name_source_index = self.basic_export_settings_folder_name.currentIndex()
        location_name_custom = self.basic_export_settings_folder_name_custom.text()
        location_custom = Path(self.basic_export_settings_location_custom.text())
        scale_enabled = self.basic_export_settings_scale_enabled.isChecked()
        scale_side = self.basic_export_settings_scale_side.currentIndex()
        scale_w_size = self.basic_export_settings_scale_w_size.value()
        scale_w_mode = self.basic_export_settings_scale_w_mode.currentIndex()
        scale_h_size = self.basic_export_settings_scale_h_size.value()
        scale_h_mode = self.basic_export_settings_scale_h_mode.currentIndex()
        scale_keep_aspect = self.basic_export_settings_scale_keep_proportions.isChecked()
        scale_filter = self.basic_export_settings_scale_filter.currentIndex()
        
        s_basic = settings["basic"]
        s_basic["file_name_source"] = file_name_source_index
        s_basic["file_name_custom"] = file_name_custom
        s_basic["ext"] = output_extension
        s_basic["location"] = location_index
        s_basic["location_name_source"] = location_name_source_index
        s_basic["location_name_custom"] = location_name_custom
        s_basic["location_custom"] = location_custom
        s_basic["scale"] = scale_enabled
        s_basic["scale_side"] = scale_side
        s_basic["scale_width"] = scale_w_size
        s_basic["scale_width_mode"] = scale_w_mode
        s_basic["scale_height"] = scale_h_size
        s_basic["scale_height_mode"] = scale_h_mode
        s_basic["scale_keep_aspect"] = scale_keep_aspect
        s_basic["scale_filter"] = scale_filter
        
        print(path)
        print(s_basic)
        
        generate_save_string(path)
        self.update_save_button()

    def _on_basic_export_settings_file_name_current_index_changed(self, index):
        self.basic_export_settings_file_name_custom.setVisible(index == QEFileNameSource.CUSTOM)
        self.update_basic_export_settings_output_path_label()

    def _on_basic_export_settings_folder_location_current_index_changed(self, index):
        show_name = index in (QELocation.IN_SUBFOLDER, QELocation.IN_SIBLING_OF_FOLDER)
        self.basic_export_settings_folder_name.setVisible(show_name)
        self.basic_export_settings_folder_name_custom.setVisible(show_name and self.basic_export_settings_folder_name.currentIndex() == QEFolderNameSource.CUSTOM)
        self.basic_export_settings_location_custom.setVisible(index == QELocation.CUSTOM)
        self.basic_export_settings_folder_custom_switch_type.setVisible(index == QELocation.CUSTOM)
        self.basic_export_settings_folder_pick_custom.setVisible(index == QELocation.CUSTOM)
        self.update_basic_export_settings_output_path_label()

    def _on_basic_export_settings_folder_name_current_index_changed(self, index):
        self.basic_export_settings_folder_name_custom.setVisible(self.basic_export_settings_folder_location.currentIndex() in (QELocation.IN_SUBFOLDER, QELocation.IN_SIBLING_OF_FOLDER) and index == QEFolderNameSource.CUSTOM)
        self.basic_export_settings_location_custom.setVisible(self.basic_export_settings_folder_location.currentIndex() == QELocation.CUSTOM)
        self.update_basic_export_settings_output_path_label()

    def _on_basic_export_settings_folder_custom_switch_type_clicked(self):
        path = Path(self.basic_export_settings_location_custom.text())
        path = path.expanduser()
        
        sel_rows = self.tree.selectionModel().selectedRows()
        index = self.tree.model.mapToSource(sel_rows[0])
        
        row_path = index.data(PathRole)
        item_type = index.data(ItemTypeRole)
        source_path = row_path if item_type == QEItemType.FOLDER else row_path.parent
        
        if path.is_absolute():
            path = path.relative_to(source_path, walk_up=True)
        else:
            path = (source_path / path).resolve()
            try:
                path = Path("~") / (path.relative_to(Path.home()))
            except ValueError:
                pass
        
        self.basic_export_settings_location_custom.setText(str(path))
        self.update_basic_export_settings_output_path_label()

    def _on_basic_export_settings_folder_pick_custom_clicked(self):
        start_path = Path()
        
        if self.basic_export_settings_location_custom.text():
            start_path = Path(self.basic_export_settings_location_custom.text())
        
        if not start_path.exists():
            sel_rows = self.tree.selectionModel().selectedRows()
            index = self.tree.model.mapToSource(sel_rows[0])
            
            path = index.data(PathRole)
            item_type = index.data(ItemTypeRole)
            start_path = path if item_type == QEItemType.FOLDER else path.parent
        
        if not start_path.exists():
            start_path = Path.home()
        
        # TODO: remove dialog name to force start folder?
        result = FileDialog.getExistingDirectory(self, "Locate folder", str(start_path), "QE_CustomExportFolder")
        if not result:
            return
        self.basic_export_settings_location_custom.setText(result)
        self.update_basic_export_settings_output_path_label()

    def set_basic_export_settings_controls_for_path(self, path):
        global suppress_store_on_widget_edit
        
        if not path in qe_settings:
            self.basic_export_settings_container.setDisabled(True)
            path = find_settings_path_for_file(path)
            if not path:
                self.basic_export_settings_output_path.setText("export path preview")
                self.basic_export_settings_output_path.setDisabled(True)
                return
        
        s_basic = qe_settings[path]["basic"]
        
        suppress_store_on_widget_edit = True
        
        self.basic_export_settings_file_name.setCurrentIndex(s_basic["file_name_source"])
        self.basic_export_settings_file_name_custom.setText(s_basic["file_name_custom"])
        self.basic_export_settings_file_type.setCurrentText(s_basic["ext"])
        self.basic_export_settings_folder_location.setCurrentIndex(s_basic["location"])
        self.basic_export_settings_folder_name.setCurrentIndex(s_basic["location_name_source"])
        self.basic_export_settings_folder_name_custom.setText(s_basic["location_name_custom"])
        self.basic_export_settings_location_custom.setText(str(s_basic["location_custom"]))
        self.basic_export_settings_scale_enabled.setChecked(s_basic["scale"])
        self.basic_export_settings_scale_side.setCurrentIndex(s_basic["scale_side"])
        self.basic_export_settings_scale_w_size.setValue(s_basic["scale_width"])
        self.basic_export_settings_scale_w_mode.setCurrentIndex(s_basic["scale_width_mode"])
        self.basic_export_settings_scale_h_size.setValue(s_basic["scale_height"])
        self.basic_export_settings_scale_h_mode.setCurrentIndex(s_basic["scale_height_mode"])
        self.basic_export_settings_scale_keep_proportions.setChecked(s_basic["scale_keep_aspect"])
        self.basic_export_settings_scale_filter.setCurrentIndex(s_basic["scale_filter"])
        
        #print("--set_basic_export_settings_controls_for_path--")
        #for x,y in enumerate(qe_settings):
            #print(x, y, qe_settings[y])
        #print("--")
        
        self.update_basic_export_settings_output_path_label()
        
        suppress_store_on_widget_edit = False
    
    def _on_basic_export_settings_scale_enabled_toggled(self, checked):
        self.basic_export_settings_scale_subcontainer.setVisible(checked)
        self.update_export_settings_from_widgets()

    def _on_basic_export_settings_scale_side_current_index_changed(self, index):
        self.basic_export_settings_scale_subcontainer.layout().setEnabled(False)
        self.basic_export_settings_scale_w_subcontainer.setVisible(index in (0,2,3,4))
        self.basic_export_settings_scale_h_subcontainer.setVisible(index in (1,4))
        self.basic_export_settings_scale_x_label.setVisible(index == 4)
        self.basic_export_settings_scale_keep_proportions.setVisible(index in (0,1,2,3))
        self.basic_export_settings_scale_subcontainer.layout().setEnabled(True)
        self.update_export_settings_from_widgets()

    def _on_basic_export_settings_scale_w_mode_current_index_changed(self, index):
        if index == 0:
            self.basic_export_settings_scale_w_size.setDecimals(0)
            self.basic_export_settings_scale_w_size.setRange(1, 65536)
        else:
            self.basic_export_settings_scale_w_size.setDecimals(3)
            self.basic_export_settings_scale_w_size.setRange(0.001, 1000)
        self.update_export_settings_from_widgets()

    def _on_basic_export_settings_scale_h_mode_current_index_changed(self, index):
        if index == 0:
            self.basic_export_settings_scale_h_size.setDecimals(0)
            self.basic_export_settings_scale_h_size.setRange(1, 65536)
        else:
            self.basic_export_settings_scale_h_size.setDecimals(3)
            self.basic_export_settings_scale_h_size.setRange(0.001, 1000)
        self.update_export_settings_from_widgets()
    
    def _on_tree_request_config_widgets_refresh_for_path(self, path):
        self.set_basic_export_settings_controls_for_path(path)
    
    def _on_tree_request_add_folder_at_path(self, path):
        self._on_add_folder_action_triggered(start_path = path, force_use_start_path = True)
    
    def _on_tree_request_add_project_at_path(self, path):
        self._on_add_project_action_triggered(start_path = path, force_use_start_path = True)
    
    def _on_tree_request_show_message(self, message, timeout):
        self.sbar.showMessage(message, timeout)
    
    def _on_tree_adding_folder(self, path):
        self.folder_filter_button.add_folder_to_tree(path)
        #print("_on_tree_adding_folder")
        #print(self.folder_filter_button.includedFolders())
        #print(" * * *")
    
    def _on_tree_removing_folder(self, path):
        self.folder_filter_button.remove_folder_from_tree(path)
        #print(f"_on_tree_removing_folder: {path=}")

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
        size = QEDialog.instance.preferred_big_thumbnail_height*2
        thumbnail = app.icon('window-close').pixmap(size,size)
    
    return thumbnail
