from PyQt5.QtWidgets import (QLabel, QTreeWidget, QTreeWidgetItem, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QCheckBox, QSpinBox, QSlider, QStyledItemDelegate, QMenu,
                             QSizePolicy, QWidget, QLineEdit, QMessageBox, QStatusBar, QButtonGroup,
                             QActionGroup, QToolButton, QComboBox, QStackedWidget, QStyle, QStyleOption,
                             QStyleOptionButton, QSpinBox, QStyleOptionSpinBox, QGraphicsOpacityEffect,
                             QFileDialog)
from PyQt5.QtCore import Qt, QObject, QRegExp, QModelIndex, pyqtSignal, QEvent
from PyQt5.QtGui import QFontMetrics, QRegExpValidator, QIcon, QPixmap, QColor, QPainter, QPalette, QMouseEvent, QTabletEvent
import zipfile
from pathlib import Path
from functools import partial
from enum import IntEnum, auto
from krita import InfoObject, ManagedColor
import krita
from .utils import *
from .qewidgets import QEMenu, SnapSlider, UncheckableButtonGroup, SpinBoxSlider, QEComboBox
from .qetree import QECols, QETree
from .multilineelidedbutton import MultiLineElidedText, MultiLineElidedButton
from .filenameedit import FileNameEdit

app = Krita.instance()

class QEDialog(QDialog):
    instance = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.__class__.instance = self

        self.setWindowModality(Qt.ApplicationModal)

        self.first_setup()

    def setup(self, msg="", doc=None):
        
        self.highlighted_doc = doc
        
        layout = self.layout()
        
        # TODO: save user changes to tree column sizes and retrieve at each start.
        self.tree_is_ready = False
        self.tree = QETree(self)
        self.tree.setup()
        # TODO: disallow sorting by thumbnail and action button columns.
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(QECols.OPEN_FILE_COLUMN, Qt.AscendingOrder)
        layout.insertWidget(0, self.tree)
        self.tree_is_ready = True
        self.tree.set_settings_modified()
        
        self.tree.set_settings_display_mode()

        if self.tree.focused_item:
            self.tree.scrollToItem(self.tree.focused_item, QAbstractItemView.PositionAtCenter)
        
        self.set_advanced_mode(self.advanced_mode_button.checkState() == Qt.Checked)
        
        self.update_show_extensions_in_list_for_all_types()
        
        # status bar.
        self.sbar_ready_label.setText(" Ready." if msg == "" else " "+msg) # extra space to align with showmessage.
        
        # TODO: inform user about having multiple copies of same file open.
        if len(self.tree.dup_counts) == 1:
            self.sbar_ready_label.setText(f"Note: Multiple copies of '{list(self.tree.dup_counts.keys())[0]}' are currently open in Krita.")
        elif len(self.tree.dup_counts) > 1:
            self.sbar_ready_label.setText(f"Note: Multiple copies of multiple files (hover mouse here to see) are currently open in Krita.")
            self.sbar_ready_label.setToolTip("\n".join(self.tree.dup_counts.keys()))

    def first_setup(self):

        layout = QVBoxLayout()

        view_buttons = QWidget()
        view_buttons_layout = QHBoxLayout()

        # TODO: inform user that some items are currently hidden, and how many.

        # show unstored button.
        self.show_unstored_button = QCheckBox("unstored")
        self.show_unstored_button.setToolTip("Enable this to pick the images you're interested in exporting, then disable it to hide the rest.")
        self.show_unstored_button.setCheckState(str2qtcheckstate(readSetting("show_unstored")))
        self.show_unstored_button.clicked.connect(self._on_show_unstored_button_clicked)

        # show unopened button.
        self.show_unopened_button = QCheckBox("unopened")
        self.show_unopened_button.setToolTip("Show the export settings of every file - currently open or not - for which settings have been saved.")
        self.show_unopened_button.setCheckState(str2qtcheckstate(readSetting("show_unopened")))
        self.show_unopened_button.clicked.connect(self._on_show_unopened_button_clicked)

        # show non-kra files button.
        self.show_non_kra_button = QCheckBox("non-kra")
        self.show_non_kra_button.setToolTip("Show export settings for files of usually exported types, such as .png and .jpg. Disabled by default because it's kind of redundant.")
        self.show_non_kra_button.setCheckState(str2qtcheckstate(readSetting("show_non_kra")))
        self.show_non_kra_button.clicked.connect(self._on_show_non_kra_button_clicked)

        self.settings_display_mode_combobox = QEComboBox()
        self.settings_display_mode_combobox.addItem("Minimized", "minimized", "All rows are minimized.")
        self.settings_display_mode_combobox.addItem("Compact", "compact", "All rows are compact.")
        self.settings_display_mode_combobox.addItem("Focused", "focused", "The focused row is expanded, all others are compact or minimized.\nDouble-click a row to focus it.")
        self.settings_display_mode_combobox.addItem("Expanded", "expanded", "All rows are expanded.")
        self.settings_display_mode_combobox.setCurrentIndex(self.settings_display_mode_combobox.findData(readSetting("settings_display_mode")))
        self.settings_display_mode_combobox.currentIndexChanged.connect(self._on_settings_display_mode_combobox_current_index_changed)

        self.settings_minimize_unfocused_button = QCheckBox("minimize unfocused")
        self.settings_minimize_unfocused_button.setToolTip("In focused display mode, reduce the size of the unfocused rows.")
        self.settings_minimize_unfocused_button.setCheckState(str2qtcheckstate(readSetting("minimize_unfocused")))
        self.settings_minimize_unfocused_button.setVisible(readSetting("settings_display_mode") == "focused")
        self.settings_minimize_unfocused_button.clicked.connect(self._on_settings_minimize_unfocused_button_clicked)

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
        view_buttons_layout.addStretch()
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
        self.advanced_mode_button = QCheckBox("Advanced mode")
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

        config_buttons_layout.addWidget(self.advanced_mode_button)
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
        options_button = QToolButton()
        options_button.setIcon(app.icon('view-choose'))
        options_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        options_button.setAutoRaise(True)
        options_button.setStyleSheet("QToolButton::menu-indicator {image: none;}")
        options_button.setPopupMode(QToolButton.InstantPopup)
        status_layout.addWidget(options_button)
        
        options_menu = QEMenu()
        options_menu.setToolTipsVisible(True)

        custom_icons_menu = QEMenu()
        custom_icons_menu.setToolTipsVisible(True)

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
        
        options_button.setMenu(options_menu)
        
        # status bar.
        # TODO: allow custom prompt messages on startup to be reset once eg. an image has been exported?
        self.sbar = QStatusBar()
        self.sbar_ready_label = QLabel()
        self.sbar.insertWidget(0, self.sbar_ready_label)
        status_layout.addWidget(self.sbar)
        
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
        
        if self.auto_save_on_close_button.checkState() == Qt.Checked:
            # save without asking.
            ret = QMessageBox.Save
        elif self.save_button.isEnabled():
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
        
        self.tree.thumbnail_worker.close()
        
        if len(self.tree.items) > 0:
            # only write columns state if they've been fit to any items.
            state = self.tree.header().saveState()
            state_str = str(state.toBase64()).lstrip("b'").rstrip("'")
            writeSetting("columns_state", state_str)
        
        self.layout().removeWidget(self.tree)
        WidgetBin.addWidget(self.tree)
        QETree.instance = None
        self.tree = None
        
        if ret == QMessageBox.Save:
            save_settings_to_config()
        else:
            load_settings_from_config()
        
        extension().update_quick_export_display()
        event.accept()

    def _on_show_unstored_button_clicked(self, checked):
        writeSetting("show_unstored", bool2str(checked))
        self.tree.refilter()

    def _on_show_unopened_button_clicked(self, checked):
        writeSetting("show_unopened", bool2str(checked))
        self.tree.refilter()

    def _on_show_non_kra_button_clicked(self, checked):
        writeSetting("show_non_kra", bool2str(checked))
        self.tree.refilter()
    
    def _on_settings_display_mode_combobox_current_index_changed(self, index):
        mode = self.settings_display_mode_combobox.itemData(index)
        writeSetting("settings_display_mode", mode)
        self.settings_minimize_unfocused_button.setVisible(mode == "focused")
        self.tree.set_settings_display_mode(mode)
    
    def _on_settings_minimize_unfocused_button_clicked(self, checked):
        writeSetting("minimize_unfocused", bool2str(checked))
        self.tree.set_settings_display_mode()
    
    def _on_fade_button_clicked(self, checked):
        checked = not str2bool(readSetting("show_fade_sliders"))
        writeSetting("show_fade_sliders", bool2str(checked))
        self.update_fade_sliders_visibility(checked)
    
    def update_fade_sliders_visibility(self, visible):
        if visible:
            self.fade_button.setText("Fade:")
            self.alt_row_contrast_slider.show()
            self.unhovered_fade_slider.show()
            self.stored_highlight_slider.show()
        else:
            self.fade_button.setText("Fade...")
            self.alt_row_contrast_slider.hide()
            self.unhovered_fade_slider.hide()
            self.stored_highlight_slider.hide()
    
    def _on_alt_row_contrast_slider_value_changed(self):
        writeSetting("alt_row_contrast", str(self.alt_row_contrast_slider.value()))
        self.tree.updateAlternatingRowContrast()
        self.tree.redraw()
    
    def _on_unhovered_fade_slider_value_changed(self):
        writeSetting("unhovered_fade", str(self.unhovered_fade_slider.value()))
        root = self.tree.invisibleRootItem()
        for item in (root.child(i) for i in range(root.childCount())):
            self.tree.itemWidget(item, QECols.SETTINGS_COLUMN).setOpacity(hover=False)
        self.tree.redraw()
    
    def _on_stored_highlight_slider_value_changed(self):
        writeSetting("highlight_alpha", str(self.stored_highlight_slider.value()))
        self.tree.set_stored_highlight_alpha(round(self.stored_highlight_slider.value() * 0.64))
        self.tree.redraw()

    def _on_advanced_mode_button_clicked(self, checked):
        writeSetting("advanced_mode", bool2str(checked))
        self.set_advanced_mode(checked)

    def set_advanced_mode(self, enabled):
        if enabled:
            self.tree.showColumn(QECols.STORE_SETTINGS_COLUMN)
            self.show_unstored_button.show()
            self.show_unstored_button.setCheckState(str2qtcheckstate(readSetting("show_unstored")))
            self.auto_store_label.show()
            self.auto_store_on_modify_button.show()
            self.auto_store_on_modify_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_modify")))
            self.auto_store_on_export_button.show()
            self.auto_store_on_export_button.setCheckState(str2qtcheckstate(readSetting("auto_store_on_export")))
            self.auto_save_on_close_button.show()
            self.auto_save_on_close_button.setCheckState(str2qtcheckstate(readSetting("auto_save_on_close")))
            self.save_button.show()
        else:
            self.tree.hideColumn(QECols.STORE_SETTINGS_COLUMN)
            self.show_unstored_button.hide()
            self.show_unstored_button.setCheckState(Qt.Checked)
            self.auto_store_label.hide()
            self.auto_store_on_modify_button.hide()
            self.auto_store_on_modify_button.setCheckState(Qt.Checked)
            self.auto_store_on_export_button.hide()
            self.auto_store_on_export_button.setCheckState(Qt.Checked)
            self.auto_save_on_close_button.hide()
            self.auto_save_on_close_button.setCheckState(Qt.Checked)
            self.save_button.hide()

    def _on_auto_store_on_modify_button_clicked(self, checked):
        writeSetting("auto_store_on_modify", bool2str(checked))

    def _on_auto_store_on_export_button_clicked(self, checked):
        writeSetting("auto_store_on_export", bool2str(checked))

    def _on_auto_save_on_close_button_clicked(self, checked):
        writeSetting("auto_save_on_close", bool2str(checked))

    def _on_use_custom_icons_action_toggled(self, checked):
        writeSetting("use_custom_icons", bool2str(checked))
        extension().update_action_icons()

    def _on_custom_icons_theme_action_group_triggered(self, action, group):
        writeSetting("custom_icons_theme", ["follow","light","dark"][group.actions().index(action)])
        extension().update_action_icons()
    
    def _on_show_export_name_in_menu_action_toggled(self, checked):
        writeSetting("show_export_name_in_menu", bool2str(checked))
        extension().update_quick_export_display()
    
    def _on_default_export_unsaved_action_toggled(self, checked):
        writeSetting("default_export_unsaved", bool2str(checked))
        extension().update_quick_export_display()

    def update_show_extensions_in_list_for_all_types(self):
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
        for combobox in self.tree.extension_comboboxes:
            model = combobox.model()
            for item_idx in range(combobox.count()):
                t = combobox.itemText(item_idx)
                if t != ext:
                    continue
                combobox.view().setRowHidden(item_idx, not show)
                item = model.item(item_idx)
                flags = item.flags()
                item.setFlags((flags & ~Qt.ItemIsEnabled) if not show else (flags | Qt.ItemIsEnabled))

    def _on_wide_column_resize_grabber_action_toggled(self, checked):
        writeSetting("wide_column_resize_grabber", bool2str(checked))
        self.tree.header().setStyle(self.tree.wide_header_style if checked else self.tree.style())

    def _on_save_button_clicked(self, checked):
        save_settings_to_config()
        self.save_button.setText("Save Settings")
        self.save_button.setIcon(QIcon())
        self.save_button.setDisabled(True)
        self.sbar.showMessage("Settings saved.", 2500)


# TODO: if __main__ etc. to allow running script by itself?
