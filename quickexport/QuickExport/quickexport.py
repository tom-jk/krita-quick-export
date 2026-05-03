from PyQt5.QtCore import QTimer, pyqtSignal
from functools import partial
from pathlib import Path
from krita import *

from .utils import *
from .qedialog import QEDialog

app = Krita.instance()
app_notifier = app.notifier()
app_notifier.setActive(True)

known_windows = []

class QuickExportExtension(Extension):
    themeChanged = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        print("QuickExport init.")
        
        set_extension(self)

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
                "qec-notify":       icon("document-quick-export-configure-notify"),
                "settings":         icon("settings"),
                "visibility": {
                    "hide":         app.icon("novisible"),
                    "show":         app.icon("visible")
                },
                "scale":            icon("scale")
            }
        
        self.set_default_icons()
        
        self.theme_name = ""
        self.theme_is_dark = False
        self.use_custom_icons = False
    
    def set_default_icons(self):
        self.icons["default"] = {
            "qe":                   app.icon("document-export"),
            "qec":                  app.icon("configure"),
            "qec-notify":           app.icon("configure"),
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
        correct_settings_version = readSetting("settings_version") == "0.0.3"
        for win in known_windows:
            win["qe_action"].setIcon(self.get_icon("qe"))
            win["qec_action"].setIcon(self.get_icon("qec") if correct_settings_version else self.get_icon("qec-notify"))
    
    def update_action_icons(self):
        self.use_custom_icons = str2bool(readSetting("use_custom_icons"))
        custom_icons_theme = readSetting("custom_icons_theme")
        
        self.theme_is_dark = True if custom_icons_theme == "dark" else False if custom_icons_theme == "light" else self.is_theme_dark()
        self.set_action_icons()
        self.themeChanged.emit()
    
    def createActions(self, window):
        print("QE: createActions")
        
        qe_action = window.createAction("tomjk_quick_export", "Quick export", "file")
        qe_action.setEnabled(False)
        qe_action.triggered.connect(self._on_quick_export_triggered)
        qec_action = window.createAction("tomjk_quick_export_configure", "Quick export configuration...", "file")
        qec_action.triggered.connect(self._on_quick_export_configuration_triggered)
        
        move_partial = partial(self.moveAction, [qe_action, qec_action], "file_export_advanced", window.qwindow())
        call_later = partial(self.finishCreateActions, move_partial, qe_action, qec_action, window.qwindow())
        QTimer.singleShot(0, call_later)
    
    def finishCreateActions(self, move_partial, qe_action, qec_action, qwindow):
        move_partial.func(*move_partial.args)
        
        theme_menu_action = next(
            (a for a in app.actions() if a.objectName() == "theme_menu"), None
        )
        
        for theme_action in theme_menu_action.menu().actions():
            theme_action.triggered.connect(lambda checked, tn=theme_action.text().lower(): self._on_theme_change_triggered(tn))
            if theme_action.isChecked():
                self.theme_name = theme_action.text().lower()
        
        self.theme_is_dark = self.is_theme_dark(self.theme_name)
        
        window = next((w for w in app.windows() if w.qwindow() == qwindow), None)
        if not window:
            print(f"Couldn't find window assocated with qwindow '{qwindow.objectName()}'.")
            return
        known_windows.append({"window":window, "qe_action":qe_action, "qec_action":qec_action})
        
        self.update_action_icons()
        
        window.activeViewChanged.connect(self.update_quick_export_display)
        window.windowClosed.connect(partial(self._on_window_closed, window))
        qe_action.changed.connect(self.update_quick_export_display)
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
        #print("update_quick_export_display")
        if len(known_windows) == 0:
            return
        
        qe_action = app.action("tomjk_quick_export")
        shortcut_text = qe_action.shortcut().toString()
        shortcut_text = f" ({shortcut_text})" if shortcut_text else ""
        window = app.activeWindow()
        view = window.activeView()
        if view:
            doc = view.document()
            if doc:
                if doc.fileName():
                    doc_file_path = Path(doc.fileName())
                    if doc_file_path.suffix == ".kra":
                        qe_action.setEnabled(True)
                        file_settings_path = find_settings_path_for_file(doc_file_path)
                        if file_settings_path:
                            # file has QE settings.
                            file_settings = qe_settings[file_settings_path]
                            show_export_name_in_menu = str2bool(readSetting("show_export_name_in_menu"))
                            output_file_path = export_file_path(file_settings, doc_file_path)
                            if show_export_name_in_menu:
                                qe_action.setText(f"Quick export to '{output_file_path.name}'")
                            else:
                                qe_action.setText("Quick export")
                            qe_action.setToolTip(f"Quick export{shortcut_text}\n{str(output_file_path)}")
                            return
                        # file has been saved but has no settings.
                        qe_action.setText("Quick export...")
                        qe_action.setToolTip(f"Quick export{shortcut_text}")
                        return
        # no doc, unsaved doc or non-.kra doc.
        reason = "No active document." if not doc else "Document has not been saved." if not doc.fileName() else "Document is not saved as a Krita project file (kra)."
        qe_action.setText(f"Quick export")
        qe_action.setToolTip(f"Quick export{shortcut_text}\n{reason}")
        default_export_unsaved = str2bool(readSetting("default_export_unsaved"))
        qe_action.setEnabled(default_export_unsaved)

    def _on_window_closed(self, window):
        print(f"_on_window_closed: {window=} {window.qwindow().objectName()}")
        for i,win in enumerate(known_windows):
            if window == win["window"]:
                del known_windows[i]
                break
        
        if len(known_windows) > 0:
            return
            
        # Krita is closing, force dialog closed if open.
        dialog = QEDialog.instance
        if dialog and dialog.isVisible():
            dialog.close()

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
                app.action("file_export_file").trigger()
                return
        
        path = Path(doc.fileName())
        file_settings_path = find_settings_path_for_file(path)
        
        if file_settings_path == None:
            self.run_dialog(msg="Configure export settings for the project first then try again.", doc=doc)
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
        dialog = QEDialog.instance
        
        # give focus if already running.
        if dialog and dialog.isVisible():
            dialog.activateWindow()
            dialog.raise_()
            return
        
        # ensure settings up to date.
        if not load_settings_from_config():
            return
        
        if not dialog:
            dialog = QEDialog()
        
        dialog.setup(msg=msg, doc=doc)
        dialog.show()
        
        #from .qemacrobuilder import QEMacroBuilder

# And add the extension to Krita's list of extensions:
app.addExtension(QuickExportExtension(app))
