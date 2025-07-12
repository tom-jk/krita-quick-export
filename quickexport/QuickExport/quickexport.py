from PyQt5.QtWidgets import QAction, QMessageBox
from PyQt5.QtCore import QTimer
from functools import partial
from pathlib import Path
from krita import *

app = Krita.instance()
app_notifier = app.notifier()
app_notifier.setActive(True)

class QuickExportExtension(Extension):

    def __init__(self, parent):
        super().__init__(parent)
        print("QuickExport init.")
        
        self.settings = []
        self.load_settings_from_config()

    def setup(self):
        pass

    def createActions(self, window):
        self.qe_action = window.createAction("tomjk_quick_export", "Quick export", "file")
        self.qe_action.setIcon(app.icon('document-export'))
        #self.qe_action.setEnabled(False)
        self.qe_action.triggered.connect(self._on_quick_export_triggered)
        self.qec_action = window.createAction("tomjk_quick_export_configure", "Quick export configuration...", "file")
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
        self.window.activeViewChanged.connect(self._on_active_view_changed)
    
    def _on_active_view_changed(self):
        print("QE: _on_active_view_changed")
        window = app.activeWindow()
        view = window.activeView()
        if view:
            doc = view.document()
            if doc:
                print(f"QE: active view in {window=} changed to {doc.fileName() or 'Untitled'}")
                if doc.fileName():
                    file_settings = self.find_settings_for_file(Path(doc.fileName()))
                    print(f"QE: {file_settings=}")
                    if file_settings:
                        output_filename = file_settings["output"]
                        print("QE: set action text..")
                        self.qe_action.setText(f"Quick export to '{output_filename}'")
                        #self.qe_action.setEnabled(True)
                        print("QE: ..text set")
                        return
        self.qe_action.setText(f"Quick export")
        #self.qe_action.setEnabled(False)
    
    def _on_quick_export_triggered(self):
        print("QE: _on_quick_export_triggered!!!")
        doc = app.activeDocument()
        if not doc:
            return
        if doc.fileName() == "":
            msg = "Quick Export: image must be saved first."
            app.activeWindow().activeView().showFloatingMessage(msg, app.icon('document-export'), 5000, 2)
    
    def load_settings_from_config(self):
        """
        read in settings string from kritarc.
        example: "path=a/b.kra,alpha=false,ouput=b.png;c/d.kra,alpha=true,output=e/f.png"
        becomes: settings[{"document":<obj>, "store":True, "path":"a/b.kra", "alpha":False, "output":"b.png"}, {"document":<obj>, "store":True, "path":"c/d.kra", "alpha":True, "output":"d.png"}]
        """
        # TODO: will break if a filename contains a comma ',' char.
        settings_string = app.readSetting("TomJK_QuickExport", "settings", "")
        #print(f"{settings_string=}")
        
        if settings_string != "":
            settings_as_arrays = [[[y for y in kvpair.split('=', 1)] for kvpair in file.split(',')] for file in settings_string.split(';')]
            #print(f"{settings_as_arrays=}")
            
            #print()
            
            for file_settings in settings_as_arrays:
                #print("found file settings", file_settings)
                self.settings.append({"document":None, "doc_index":1024, "store":True})
                for kvpair in file_settings:
                    if kvpair[0] == "path":
                        self.settings[-1][kvpair[0]] = Path(kvpair[1])
                        for i, d in enumerate(app.documents()):
                            if d.fileName() == kvpair[1]:
                                self.settings[-1]["document"] = d
                                self.settings[-1]["doc_index"] = i
                                break
                    elif kvpair[0] == "alpha":
                        self.settings[-1][kvpair[0]] = True if kvpair[1] == "true" else False
                    elif kvpair[0] == "compression":
                        self.settings[-1][kvpair[0]] = int(kvpair[1])
                    elif kvpair[0] == "output":
                        self.settings[-1][kvpair[0]] = kvpair[1]
                    else:
                        print(f" unrecognised parameter name '{kvpair[0]}'")
                        continue
                    #print(" found", kvpair)
                #print()
    
    def find_settings_for_file(self, file_path):
        for s in self.settings:
            if s["path"] == file_path:
                return s
        return None

# And add the extension to Krita's list of extensions:
app.addExtension(QuickExportExtension(app))
