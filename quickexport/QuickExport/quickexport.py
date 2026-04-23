from PyQt5.QtWidgets import QAction, QMessageBox, QDialog
from PyQt5.QtCore import QTimer, pyqtSignal
from functools import partial
from pathlib import Path
from krita import *

from .utils import *
#from .dialog import QEDialog
from .qedialog import QEDialog

app = Krita.instance()
app_notifier = app.notifier()
app_notifier.setActive(True)

class QuickExportExtension(Extension):
    themeChanged = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        print("QuickExport init.")
        
        set_extension(self)
        
        load_settings_from_config(soft_warning_for_unsupported_version=True)

    def setup(self):
        print("QE: setup")
        
        plugin_dir = Path(app.getAppDataLocation()) / "pykrita" / "QuickExport"
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
                "settings":         icon("settings"),
                "visibility": {
                    "hide":         app.icon("novisible"),
                    "show":         app.icon("visible")
                },
                "scale":            icon("scale")
            }
        
        self.set_default_icons()
        
        self.default_export_action = None
        
        self.theme_name = ""
        self.theme_is_dark = False
        self.use_custom_icons = False
    
    def set_default_icons(self):
        self.icons["default"] = {
            "qe":                   app.icon("document-export"),
            "qec":                  app.icon("configure"),
            "settings":             app.icon("configure"),
            "visibility": {
                "hide":             app.icon("novisible"),
                "show":             app.icon("visible")
            },
            "scale":                app.icon("transform_icons_liquify_resize")
        }
    
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
        self.refresh_actions()
        self.qe_action.setIcon(self.get_icon("qe"))
        self.qec_action.setIcon(self.get_icon("qec"))
    
    def update_action_icons(self):
        self.use_custom_icons = str2bool(readSetting("use_custom_icons"))
        custom_icons_theme = readSetting("custom_icons_theme")
        
        self.theme_is_dark = True if custom_icons_theme == "dark" else False if custom_icons_theme == "light" else self.is_theme_dark()
        self.set_action_icons()
        self.set_default_icons()
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
    
    def refresh_actions(self):
        """retrieve action objects if we lose them for some reason."""
        try:
            self.qe_action.objectName()
            self.qec_action.objectName()
        except RuntimeError:
            self.qe_action = next((a for a in app.actions() if a.objectName() == "tomjk_quick_export"), None)
            self.qec_action = next((a for a in app.actions() if a.objectName() == "tomjk_quick_export_configure"), None)
    
    def update_quick_export_display(self):
        self.refresh_actions()
        shortcut_text = self.qe_action.shortcut().toString()
        shortcut_text = f" ({shortcut_text})" if shortcut_text else ""
        window = app.activeWindow()
        view = window.activeView()
        if view:
            doc = view.document()
            if doc:
                if doc.fileName():
                    self.qe_action.setEnabled(True)
                    doc_file_path = Path(doc.fileName())
                    file_settings_path = find_settings_path_for_file(doc_file_path)
                    if file_settings_path:
                        # file has QE settings.
                        file_settings = qe_settings[file_settings_path]
                        show_export_name_in_menu = str2bool(readSetting("show_export_name_in_menu"))
                        output_file_path = export_file_path(file_settings, doc_file_path)
                        if show_export_name_in_menu:
                            # ~ output_filename = file_settings["output_name"] + file_settings["ext"]
                            self.qe_action.setText(f"Quick export to '{output_file_path.name}'")
                        else:
                            self.qe_action.setText("Quick export")
                        self.qe_action.setToolTip(f"Quick export{shortcut_text}\n{str(output_file_path)}")
                        return
                    # file has been saved but has no settings.
                    self.qe_action.setText("Quick export...")
                    self.qe_action.setToolTip(f"Quick export{shortcut_text}")
                    return
        # no doc or unsaved doc.
        self.qe_action.setText("Quick export")
        self.qe_action.setToolTip(f"Quick export{shortcut_text}")
        default_export_unsaved = str2bool(readSetting("default_export_unsaved"))
        self.qe_action.setEnabled(default_export_unsaved)
    
    def _on_quick_export_triggered(self):
        doc = app.activeDocument()
        if not doc:
            print("QE: no document to export.")
            return
        
        if doc.fileName() == "":
            default_export_unsaved = str2bool(readSetting("default_export_unsaved"))
            if not default_export_unsaved:
                msg = "Quick Export: image must be saved first."
                app.activeWindow().activeView().showFloatingMessage(msg, app.icon('document-export'), 5000, 2)
                return
            else:
                self.default_export_action.trigger()
                return
        
        path = Path(doc.fileName())
        file_settings_path = find_settings_path_for_file(path)
        
        if file_settings_path == None:
            self.run_dialog(msg="Configure export settings for the image then try again, or just click 'Export now'.", doc=doc)
            return
        
        result = export_image(file_settings_path, doc)
        
        if not result:
            failed_msg = export_failed_msg()
            print(f"QE: Export failed! {failed_msg}")
            app.activeWindow().activeView().showFloatingMessage(f"Export failed! {failed_msg}", app.icon('warning'), 5000, 0)
        else:
            export_path = export_file_path(qe_settings[file_settings_path], path)
            print(f"QE: Exported to '{str(export_path)}'")
            app.activeWindow().activeView().showFloatingMessage(f"Exported to '{str(export_path)}'", app.icon('document-export'), 5000, 1)
    
    def _on_quick_export_configuration_triggered(self):
        self.run_dialog(doc=app.activeDocument())
    
    def run_dialog(self, msg="", doc=None):
        # ensure settings up to date.
        if not load_settings_from_config():
            return
        
        dialog = QEDialog.instance or QEDialog()
        dialog.setup(msg=msg, doc=doc)
        dialog.show()
        
        #from .qemacrobuilder import QEMacroBuilder

# And add the extension to Krita's list of extensions:
app.addExtension(QuickExportExtension(app))
