from PyQt5.QtWidgets import QAction, QMessageBox, QDialog
from PyQt5.QtCore import QTimer, pyqtSignal
from functools import partial
from pathlib import Path
from krita import *

from .utils import *
from .dialog import QEDialog
from .copysettingsdialog import CopySettingsDialogResult, CopySettingsDialog

app = Krita.instance()
app_notifier = app.notifier()
app_notifier.setActive(True)

class QuickExportExtension(Extension):
    themeChanged = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        print("QuickExport init.")
        
        set_extension(self)
        
        load_settings_from_config()

    def setup(self):
        print("QE: setup")
        
        plugin_dir = Path(app.getAppDataLocation()) / "pykrita/QuickExport"
        icons_dir = plugin_dir / "icons"
        
        if not plugin_dir.is_dir():
            # do something about it
            pass
        
        self.icons = {}
        for theme in ("light", "dark"):
            icon = lambda name: QIcon(str(icons_dir/f"{theme}_{name}.svg"))
            self.icons[theme] = {
                "qe":               icon("document-quick-export"),
                "qec":              icon("document-quick-export-configure"),
                "alpha":            app.icon("transparency-unlocked"),
                "indexed":          icon("indexed"),
                "progressive":      icon("progressive"),
                "hdr":              icon("hdr"),
                "embed_profile":    icon("embed-profile"),
                "force_profile":    icon("force-profile"),
                "force_8bit":       icon("force-8bit"),
                "metadata_options": icon("metadata-options"),
                "metadata":         icon("metadata"),
                "author":           icon("author"),
                "scale":            icon("scale"),
                "subsampling": {
                    "1x1":          icon("subsampling-1x1"),
                    "1x2":          icon("subsampling-1x2"),
                    "2x1":          icon("subsampling-2x1"),
                    "2x2":          icon("subsampling-2x2")
                },
                "jpeg_baseline":    icon("jpeg-baseline"),
                "optimise":         icon("optimise")
            }
        
        self.icons["default"] = {
            "qe":                   None,
            "qec":                  None,
            "alpha":                app.icon("transparency-unlocked"),
            "indexed":              app.icon("wheel-sectors"),
            "progressive":          app.icon("krita_tool_grid"),
            "hdr":                  app.icon("wheel-light"),
            "embed_profile":        app.icon("curve-preset-s"),
            "force_profile":        app.icon("locked"),
            "force_8bit":           app.icon("merge-layer-below"),
            "metadata_options":     app.icon("tag"),
            "metadata":             app.icon("view-list-details"),
            "author":               app.icon("im-user"),
            "scale":                app.icon("transform_icons_liquify_resize"),
            "subsampling": {
                "1x1":              app.icon("tool_similar_selection"),
                "1x2":              app.icon("tool_similar_selection"),
                "2x1":              app.icon("tool_similar_selection"),
                "2x2":              app.icon("tool_similar_selection"),
            },
            "jpeg_baseline":        app.icon("krita_tool_rectangle"),
            "optimise":             app.icon("tool_crop")
        }
        
        self.default_export_action = None
        
        self.theme_name = ""
        self.theme_is_dark = False
        self.use_custom_icons = False
    
    def get_icon(self,  *args):
        return self._get_icons_internal(self.icons["default" if not self.use_custom_icons else "light" if self.theme_is_dark else "dark"], *args)
    
    def _get_icons_internal(self, sublist, *args):
        if len(args) > 1:
            return self._get_icons_internal(sublist[args[0]], *args[1:])
        else:
            return sublist[args[0]]
    
    def is_theme_dark(self, theme_name=None):
        # TODO: find out more common keywords used in dark theme names, including non-english.
        theme_name = theme_name or self.theme_name
        if theme_name in ("breeze dark", "breeze high contrast", "krita blender", "krita dark", "krita dark orange", "krita darker"):
            return True
        if any(test in theme_name for test in ("dark", "black", "night", "dusk", "sleep")):
            return True
        return False
    
    def _on_theme_change_triggered(self, theme_name):
        self.theme_name = theme_name
        self.update_action_icons()
    
    def set_action_icons(self):
        self.qe_action.setIcon(self.get_icon("qe"))
        self.qec_action.setIcon(self.get_icon("qec"))
    
    def update_action_icons(self):
        self.use_custom_icons = str2bool(app.readSetting("TomJK_QuickExport", "use_custom_icons", "true"))
        custom_icons_theme = app.readSetting("TomJK_QuickExport", "custom_icons_theme", "follow")
        
        self.theme_is_dark = True if custom_icons_theme == "dark" else False if custom_icons_theme == "light" else self.is_theme_dark()
        self.set_action_icons()
        self.themeChanged.emit()
    
    def createActions(self, window):
        print("QE: createActions")
        
        self.qe_action = window.createAction("tomjk_quick_export", "Quick export", "file")
        self.qe_action.setEnabled(False)
        self.qe_action.triggered.connect(self._on_quick_export_triggered)
        self.qec_action = window.createAction("tomjk_quick_export_configure", "Quick export configuration...", "file")
        self.qec_action.triggered.connect(self._on_quick_export_configuration_triggered)
        
        self.icons["default"]["qe"] = self.qe_action.icon()
        self.icons["default"]["qec"] = self.qec_action.icon()
        
        move_partial = partial(self.moveAction, [self.qe_action, self.qec_action], "file_export_advanced", window.qwindow())
        call_later = partial(self.finishCreateActions, move_partial)
        QTimer.singleShot(0, call_later)
    
    def finishCreateActions(self, move_partial):
        move_partial.func(*move_partial.args)
        
        theme_menu_action = next(
            (a for a in app.actions() if a.objectName() == "theme_menu"), None
        )
        
        for theme_action in theme_menu_action.menu().actions():
            theme_action.triggered.connect(lambda checked, tn=theme_action.text().lower(): self._on_theme_change_triggered(tn))
            if theme_action.isChecked():
                self.theme_name = theme_action.text().lower()
        
        self.theme_is_dark = self.is_theme_dark(self.theme_name)
        self.update_action_icons()
        
        for action in app.actions():
            if action.objectName() == "file_export_file":
                self.default_export_action = action
        
        # TODO: only works for initial window.
        self.window = app.activeWindow()
        self.window.activeViewChanged.connect(self.update_quick_export_display)
        self.qe_action.changed.connect(self.update_quick_export_display)
        app_notifier.imageSaved.connect(partial(self.update_quick_export_display))
    
    def moveAction(self, actions_to_move, name_of_action_to_insert_before, qwindow):
        menu_bar = qwindow.menuBar()
        file_menu_action = next(
            (a for a in menu_bar.actions() if a.objectName() == "file"), None
        )
        if file_menu_action:
            file_menu = file_menu_action.menu()
            for file_action in file_menu.actions():
                if file_action.objectName() == name_of_action_to_insert_before:
                    for action in actions_to_move:
                        file_menu.removeAction(action)
                        file_menu.insertAction(file_action, action)
                    break
    
    def update_quick_export_display(self):
        window = app.activeWindow()
        view = window.activeView()
        if view:
            doc = view.document()
            if doc:
                if doc.fileName():
                    self.qe_action.setEnabled(True)
                    file_settings = find_settings_for_file(Path(doc.fileName()))
                    if file_settings:
                        # file has QE settings.
                        show_export_name_in_menu = app.readSetting("TomJK_QuickExport", "show_export_name_in_menu", "true") == "true"
                        if show_export_name_in_menu:
                            output_filename = file_settings["output"]
                            self.qe_action.setText(f"Quick export to '{output_filename}'")
                        else:
                            self.qe_action.setText("Quick export")
                        return
                    # file has been saved but has no settings.
                    self.qe_action.setText("Quick export...")
                    return
        # no doc or unsaved doc.
        self.qe_action.setText("Quick export")
        default_export_unsaved = app.readSetting("TomJK_QuickExport", "default_export_unsaved", "false") == "true"
        self.qe_action.setEnabled(default_export_unsaved)
    
    def _on_quick_export_triggered(self):
        doc = app.activeDocument()
        if not doc:
            print("QE: no document to export.")
            return
        
        if doc.fileName() == "":
            default_export_unsaved = app.readSetting("TomJK_QuickExport", "default_export_unsaved", "false") == "true"
            if not default_export_unsaved:
                msg = "Quick Export: image must be saved first."
                app.activeWindow().activeView().showFloatingMessage(msg, app.icon('document-export'), 5000, 2)
                return
            else:
                self.default_export_action.trigger()
                return
        
        path = Path(doc.fileName())
        file_settings = find_settings_for_file(path)
        
        if file_settings == None:
            print("check previous versions")
            # check to see if this might be an incremental save of an already stored file.
            import re
            nums_list = re.finditer(r"[0-9]+", path.stem)
            possible_previous_paths = []
            for item in nums_list:
                print(f" {item}")
                # try substituting in decrements of each number into original path.
                # eg. 'name03.002' tests for 'name02.002' and 'name03.001'.
                # TODO: keep decrementing number until settings found (as user
                #       may have incremented version twice without exporting).
                # TODO: won't find 'filename.kra' -> 'filename_001.kra'.
                # TODO: actually, what if user is exporting an *earlier* version of
                #       an image where settings are stored for a *later* version?
                # TODO: maybe allow user to store settings for a file path with a
                #       wildcard? eg. settings for 'path/img*' would apply to
                #       'path/img_001.kra', 'path/img_002.kra', 'path/img2.kra' etc.
                if int(item.group()) == 0:
                    # who saves version -1 of a file?
                    continue
                for t in ("", "_", " ", ".", "-"):
                    test_name = (
                          path.stem[0:item.start()]
                        + t
                        + str(int(item.group())-1).zfill(len(item.group()))
                        + path.stem[item.end():]
                    )
                    test_path = Path(f"{path.parent.joinpath(test_name)}"+path.suffix)
                    #print(f"  testing {test_path}")
                    if find_settings_for_file(test_path):
                        possible_previous_paths.append(test_path)
            
            # HACK: test specifically for 'filename.kra' -> 'filename_001.kra' case.
            if path.stem.endswith("_001", 1):
                test_path = Path(f"{path.parent.joinpath(path.stem[:-4])}"+path.suffix)
                #print(f" testing  {test_path}")
                if find_settings_for_file(test_path):
                    possible_previous_paths.append(test_path)
            
            if possible_previous_paths:
                print("Possible Previous Paths:")
                for i, p in enumerate(possible_previous_paths):
                    print(f" {i} {repr(p)}")
                
                use_previous_version_settings = app.readSetting("TomJK_QuickExport", "use_previous_version_settings", "replace")
                result = CopySettingsDialogResult.NONE
                selected_item_index = 0
                
                if len(possible_previous_paths) > 1 or use_previous_version_settings == "ask":
                    csBox = CopySettingsDialog(
                        [p.name for p in possible_previous_paths],
                        [f"Will export to '{find_settings_for_file(p)['output']}'." for p in possible_previous_paths],
                        app.activeWindow().qwindow()
                    )
                    ret = csBox.exec()
                    if ret == QDialog.Rejected:
                        return
                    result = csBox.result
                    selected_item_index = csBox.selected_item_index
                else:
                    result = (
                             CopySettingsDialogResult.COPY if use_previous_version_settings == "copy"
                        else CopySettingsDialogResult.NEW if use_previous_version_settings == "new"
                        else CopySettingsDialogResult.REPLACE
                    )
                
                if result == CopySettingsDialogResult.NEW:
                    self.run_dialog(msg="Configure export settings for the image, or just click 'Export now'.", doc=doc)
                    return
                else:
                    prev_path = possible_previous_paths[selected_item_index]
                    load_settings_from_config()
                    s = find_settings_for_file(prev_path)
                    if result == CopySettingsDialogResult.REPLACE:
                        s["path"] = path
                        file_settings = s
                    else:
                        i = qe_settings.index(s) + 1
                        qe_settings.insert(i, s.copy())
                        qe_settings[i]["path"] = path
                        file_settings = qe_settings[i]
                    save_settings_to_config()
                    
            else:
                self.run_dialog(msg="Configure export settings for the image then try again, or just click 'Export now'.", doc=doc)
                return
        
        result = export_image(file_settings, doc)
        
        if not result:
            failed_msg = export_failed_msg()
            print(f"QE: Export failed! {failed_msg}")
            app.activeWindow().activeView().showFloatingMessage(f"Export failed! {failed_msg}", app.icon('warning'), 5000, 0)
        else:
            export_path = file_settings['path'].with_name(file_settings['output']).with_suffix(file_settings['ext'])
            print(f"QE: Exported to '{str(export_path)}'")
            app.activeWindow().activeView().showFloatingMessage(f"Exported to '{str(export_path)}'", app.icon('document-export'), 5000, 1)
    
    def _on_quick_export_configuration_triggered(self):
        self.run_dialog(doc=app.activeDocument())
    
    def run_dialog(self, msg="", doc=None):
        # ensure settings up to date.
        load_settings_from_config()
        
        # TODO: reuse instead of destroy?
        dialog = QEDialog(msg=msg, doc=doc)
        dialog.exec_()
        del dialog
        
        # reload settings to remove temporary stuff (TODO: automatic based on store flag?)
        load_settings_from_config()

# And add the extension to Krita's list of extensions:
app.addExtension(QuickExportExtension(app))
