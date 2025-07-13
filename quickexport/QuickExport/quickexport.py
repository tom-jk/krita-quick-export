from PyQt5.QtWidgets import QAction, QMessageBox, QDialog
from PyQt5.QtCore import QTimer
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

    def __init__(self, parent):
        super().__init__(parent)
        print("QuickExport init.")
        
        load_settings_from_config()

    def setup(self):
        pass

    def createActions(self, window):
        self.qe_action = window.createAction("tomjk_quick_export", "Quick export", "file")
        self.qe_action.setEnabled(False)
        self.qe_action.triggered.connect(self._on_quick_export_triggered)
        self.qec_action = window.createAction("tomjk_quick_export_configure", "Quick export configuration...", "file")
        self.qec_action.triggered.connect(self._on_quick_export_configuration_triggered)
        call_later = partial(self.moveAction, [self.qe_action, self.qec_action], "file_export_advanced", window.qwindow())
        QTimer.singleShot(0, call_later)
    
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
        
        self.window = app.activeWindow()
        self.window.activeViewChanged.connect(self.update_quick_export_enabled)
        self.qe_action.changed.connect(self.update_quick_export_enabled)
        app_notifier.imageSaved.connect(partial(self.update_quick_export_enabled))
    
    def update_quick_export_enabled(self):
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
                        output_filename = file_settings["output"]
                        self.qe_action.setText(f"Quick export to '{output_filename}'")
                        return
                    # file has been saved but has no settings.
                    self.qe_action.setText("Quick export...")
                    return
        # no doc or unsaved doc.
        self.qe_action.setText("Quick export")
        self.qe_action.setEnabled(False)
    
    def _on_quick_export_triggered(self):
        doc = app.activeDocument()
        if not doc:
            print("QE: no document to export.")
            return
        
        if doc.fileName() == "":
            msg = "Quick Export: image must be saved first."
            app.activeWindow().activeView().showFloatingMessage(msg, app.icon('document-export'), 5000, 2)
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
                
                csBox = CopySettingsDialog(
                    [p.name for p in possible_previous_paths],
                    [f"Will export to '{find_settings_for_file(p)['output']}'." for p in possible_previous_paths],
                    app.activeWindow().qwindow()
                )
                ret = csBox.exec()
                
                if ret == QDialog.Rejected:
                    return
                
                if csBox.result == CopySettingsDialogResult.NEW:
                    self.run_dialog(msg="Configure export settings for the image, or just click 'Export now'.", doc=doc)
                    return
                else:
                    prev_path = possible_previous_paths[csBox.selected_item_index]
                    load_settings_from_config()
                    s = find_settings_for_file(prev_path)
                    if csBox.result == CopySettingsDialogResult.REPLACE:
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
            print("QE: Export failed!")
            app.activeWindow().activeView().showFloatingMessage("Export failed!", app.icon('warning'), 5000, 0)
        else:
            export_path = file_settings['path'].with_name(file_settings['output'])
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
