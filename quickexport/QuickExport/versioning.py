from PyQt5.QtWidgets import QDialog, QStyle, QButtonGroup, QRadioButton, QDialogButtonBox
from PyQt5.QtGui import QColor
from pathlib import Path
from os.path import relpath
import re
from krita import *

from .utils import *

app = Krita.instance()

filter_strategy_store_strings     = {"Auto":"A", "Bell":"B", "Bicubic":"Bic", "Bilinear":"Bil", "BSpline":"BS", "Hermite":"H", "Lanczos3":"L", "Mitchell":"M", "NearestNeighbor":"NN"}
filter_strategy_rev_store_strings = {v:k for k,v in filter_strategy_store_strings.items()}

def deserialize_stored_output_string(base, s):
    """
    arguments
        base    Path    path that s is relative to, if s is relative.
                        note this is the source path, not the source file (eg. Path("/home/user/Pictures"), not Path("/home/user/Pictures/pic.kra")).
        s       str     stored file path string to deserialize.
                        note this is the output file without extension (eg. "pic", "./../pic", "/home/user/pic").
    returns tuple
                bool    if path is stored absolute.
                Path    path as absolute, without file name.
                str     file name without extension.
    
    output path can be:
            same as source: no leading slash, no slashes anywhere (name only)
        relative to source: leading dot-slash (./)
             absolute path: leading slash (/)
    examples:
    path=/home/user/a/b.kra,output=b,ext=.png             ->  base = Path("/home/user/a"), s="b"             ->  returns (False, Path("/home/user/a"),  "b")  ->  same as source:     /home/user/a/b.png, shortened path for special case of same directory
    path=/home/user/a/b.kra,output=./b,ext=.png           ->  base = Path("/home/user/a"), s="./b"           ->  returns (False, Path("/home/user/a"),  "b")  ->  relative to source: /home/user/a/b.png, equivalent but redundant version of above
    path=/home/user/a/b.kra,output=./../b,ext=.png        ->  base = Path("/home/user/a"), s="./../b"        ->  returns (False, Path("/home/user"),    "b")  ->  relative to source: /home/user/b.png
    path=/home/user/a/b.kra,output=./../x/b,ext=.png      ->  base = Path("/home/user/a"), s="./../x/b"      ->  returns (False, Path("/home/user/x"),  "b")  ->  relative to source: /home/user/x/b.png, which succeeds only if x already exists
    path=/home/user/a/b.kra,output=./../../b,ext=.png     ->  base = Path("/home/user/a"), s="./../../b"     ->  returns (False, Path("/home"),         "b")  ->  relative to source: /home/b.png, which I think would fail
    path=/home/user/a/b.kra,output=./f/b,ext=.png         ->  base = Path("/home/user/a"), s="./f/b"         ->  returns (False, Path("/home/user/a/f), "b")  ->  relative to source: /home/user/a/f/b.png, which succeeds only if f already exists
    path=/home/user/a/b.kra,output=/home/user/b,ext=.png  ->  base = Path("/home/user/a"), s="/home/user/b"  ->  returns (True,  Path("/home/user),     "b")  ->  absolute path:      /home/user/b.png
    """
    
    p = Path(s)
    
    if s.startswith("./"):
        # relative to base path.
        #print(f"deserialize_stored_output_string:\n args\n  {base=}\n  {s=}\n returns (1. relative to base path)\n  {(False, base.joinpath(p.parent).resolve(), p.name)}")
        return (False, base.joinpath(p.parent).resolve(), p.name)
    
    if s.startswith("/"):
        # absolute path.
        #print(f"deserialize_stored_output_string:\n args\n  {base=}\n  {s=}\n returns (2. absolute path)\n  {(True, p.parent, p.name)}")
        return (True, p.parent, p.name)
    
    # special case of same directory as base.
    #print(f"deserialize_stored_output_string:\n args\n  {base=}\n  {s=}\n returns (3. same directory as base)\n  {(False, base, s)}")
    return (False, base, s)

def serialize_stored_output_string(base, is_abs, abs_dir, name):
    """
    arguments
        base        Path    path that abs_dir is relative to, if is_abs is True.
                            note this is the source path, not the source file (eg. Path("/home/user/Pictures"), not Path("/home/user/Pictures/pic.png")).
        is_abs      bool    if path is stored absolute.
        abs_dir     Path    path as absolute, without file name.
        name        str     file name without extension.
    returns
                    str     string to be stored.
    
    examples:
    base = Path("/home/user/Pictures"), is_abs = False, abs_dir = Path("/home/user"),                 name = "pic" -> returns "./../pic"
    base = Path("/home/user/Pictures"), is_abs = False, abs_dir = Path("/home/user/Pictures/subdir"), name = "pic" -> returns "./subdir/pic"
    base = Path("/home/user/Pictures"), is_abs = False, abs_dir = Path("/home/user/Pictures"),        name = "pic" -> returns "pic"
    base = Path("/home/user/Pictures"), is_abs = True,  abs_dir = Path("/home/user/Pictures"),        name = "pic" -> returns "/home/user/Pictures/pic"
    """
    
    if is_abs:
        # absolute path.
        return str(abs_dir.joinpath(name))
    
    if base == abs_dir:
        # special case of same directory as base.
        return name
    
    else:
        # relative to base path.
        return "./" + relpath(abs_dir.joinpath(name), base)

def tokenize_settings_string(s, tokens):
    i = 0
    while True:
        subs = s[i:]
        mo = re.search(r"=|,|;|\[|\]", subs)
        #print(mo)
        if not mo:
            break
        if subs[:mo.end()-1] != "":
            tokens.append(subs[:mo.end()-1])
        tokens.append(mo.group())
        i += mo.end()

def unescape_tokenized_settings_string(tokens):
    token_id = 0
    while token_id < len(tokens)-1:
        if tokens[token_id].endswith("/") and tokens[token_id+1] == ",":
            tokens[token_id] = tokens[token_id][:-1] + ","
            tokens.pop(token_id+1)
            if not tokens[token_id+1] == ",":
                tokens[token_id] += tokens.pop(token_id+1)
            continue
        token_id += 1



def load_0_0_2_settings_from_config():
    """
    read in settings string from kritarc.
    example: "path=/a/b.kra,output=b,ext=.png,scale=[e=1,w=1024,h=768,f=Bic,r=72],png=[fc=#ffffff,co=9,flag=110000000],jpeg=[];"
    becomes: settings[{"document":<obj>, "store":True, "path":Path("/a/b.kra"), "output_is_abs":False, "output_abs_dir":Path("/a"), "output_name":"b", "ext":".png", "scale":True,
                       "scale_width":1024, ... "png_fillcolour":QColor('#ffffff'), "png_compression":9, "png_alpha":True, "png_indexed":True, ... etc.}]
    
    commas (,) in file paths and names are replaced with slash-comma (/,).
    example: settings[{"path":Path("path=/pa,th/to/,a/file.kra", "output_name":"file,", "ext":".png", ... }]
    becomes: "path=/pa/,th/to//,a/file.kra,output=file/,,ext=.png ... "
    """
    
    global qe_settings
    
    intermediate_settings = []
    
    settings_string = readSetting("settings", "")
    #print(f"{settings_string=}")
    
    if settings_string == "":
        return
    
    settings_tokens = []
    tokenize_settings_string(settings_string, settings_tokens)
    unescape_tokenized_settings_string(settings_tokens)
    
    if settings_tokens[-1] != ";":
        settings_tokens.append(";")
    
    token_prefix = ""
    token_stack = []
    settings_per_file = []
    settings_kvpairs = []
    
    for token in settings_tokens:
        if token == ",":
            continue
        elif token == ";":
            settings_per_file.append(settings_kvpairs)
            settings_kvpairs = []
        elif token == "=":
            continue
        elif token == "[":
            token_prefix = token_stack.pop() + "_"
        elif token == "]":
            token_prefix = ""
        else:
            token_stack.append(token)
            if len(token_stack) == 2:
                settings_kvpairs.append([token_prefix + token_stack.pop(-2), token_stack.pop()])
    
    print()
    
    for file_kvpairs in settings_per_file:
        print("found file settings", file_kvpairs)
        settings = default_settings(Path(), store=True)
        output_string = ""
        for k,v in file_kvpairs:
            if k == "path":
                settings[k] = Path(v)
            elif k == "v":
                settings["versions"] = {"s":"single", "a":"all", "f":"all_forward"}[v]
            elif k == "output":
                output_string = v
            elif k == "ext":
                settings["ext"] = v
            elif k == "scale_e":
                settings["scale"] = flag2bool(v)
            elif k == "scale_w":
                settings["scale_width"] = int(v)
            elif k == "scale_h":
                settings["scale_height"] = int(v)
            elif k == "scale_f":
                settings["scale_filter"] = filter_strategy_rev_store_strings.get(v, v)
            elif k == "scale_r":
                settings["scale_res"] = float(v)
            elif k == "png_fc":
                settings["png_fillcolour"] = QColor(v)
            elif k == "png_co":
                settings["png_compression"] = int(v)
            elif k == "png_flag":
                settings["png_alpha"]       = flag2bool(v[0])
                settings["png_indexed"]     = flag2bool(v[1])
                settings["png_interlaced"]  = flag2bool(v[2])
                settings["png_hdr"]         = flag2bool(v[3])
                settings["png_embed_srgb"]  = flag2bool(v[4])
                settings["png_force_srgb"]  = flag2bool(v[5])
                settings["png_metadata"]    = flag2bool(v[6])
                settings["png_author"]      = flag2bool(v[7])
                settings["png_force_8bit"]  = flag2bool(v[8])
            elif k == "jpeg_fc":
                settings["jpeg_fillcolour"] = QColor(v)
            elif k == "jpeg_qu":
                settings["jpeg_quality"] = int(v)
            elif k == "jpeg_sm":
                settings["jpeg_smooth"] = int(v)
            elif k == "jpeg_ss":
                settings["jpeg_subsampling"] = v
            elif k == "jpeg_flag":
                settings["jpeg_progressive"]      = flag2bool(v[0])
                settings["jpeg_icc_profile"]      = flag2bool(v[1])
                settings["jpeg_force_baseline"]   = flag2bool(v[2])
                settings["jpeg_optimise"]         = flag2bool(v[3])
                settings["jpeg_exif"]             = flag2bool(v[4])
                settings["jpeg_iptc"]             = flag2bool(v[5])
                settings["jpeg_xmp"]              = flag2bool(v[6])
                settings["jpeg_tool_information"] = flag2bool(v[7])
                settings["jpeg_anonymiser"]       = flag2bool(v[8])
                settings["jpeg_metadata"]         = flag2bool(v[9])
                settings["jpeg_author"]           = flag2bool(v[10])
            else:
                print(f" unrecognised parameter name '{k}'")
                continue
            print(f" found {k}:{v}")
        if output_string:
            output = deserialize_stored_output_string(settings["path"].parent, output_string)
            print(f" output: is_abs:{output[0]}, abs_dir:'{output[1]}', name:'{output[2]}'")
            settings["output_is_abs"] = output[0]
            settings["output_abs_dir"] = output[1]
            settings["output_name"] = output[2]
        intermediate_settings.append(settings)
        print()
    
    base_paths = {}
    
    used_multiple_per_path = False
    used_project_versions = False
    used_non_kra_projects = False
    used_scale_res = False
    
    for idx, settings in enumerate(intermediate_settings):
        
        settings["versioning_issues"] = {"msg":[], "versions":False}
        path = settings["path"]
        if path.suffix != ".kra":
            used_non_kra_projects = True
            print(" - NON-KRITA PROJECT FILE")
        base, version = base_stem_and_version_number_for_versioned_file(path)
        base_path = path.with_name(base)
        print(f"Inspecting 0.0.2 settings for '{path}' ...")
        if base_path in base_paths:
            used_multiple_per_path = True
            print(f" - DUPLICATED PROJECT SETTING: '{base_path}' is used by another setting.")
            if not base_paths[base_path]["group"]:
                base_paths[base_path]["group"] = QButtonGroup()
            if version > base_paths[base_path]["latest_version"]:
                base_paths[base_path]["latest_version"] = version
                base_paths[base_path]["latest_path"] = path
                base_paths[base_path]["latest_idx"] = idx
        else:
            base_paths[base_path] = {"group":None, "latest_version":version, "latest_path":path, "latest_idx":idx}
        if settings["versions"] != "all":
            used_project_versions = True
            print(" - UNSUPPORTED: single and all-forward versions modes.")
        if "scale_res" in settings and settings["scale_res"] != -1:
            used_scale_res = True
            print(" - UNSUPPORTED: scale print resolution.")
    
    used_unsupported_features = used_project_versions or used_non_kra_projects or used_multiple_per_path or used_scale_res
    
    msgBox = QDialog(app.activeWindow().qwindow() if app.activeWindow() else None)
    msgBox.setWindowTitle("Quick Export")
    style = msgBox.style()
    layout = QHBoxLayout(msgBox)
    icon_label = QLabel()
    icon_label.setPixmap(style.standardIcon(QStyle.SP_MessageBoxQuestion if used_unsupported_features else QStyle.SP_MessageBoxInformation).pixmap(style.pixelMetric(QStyle.PM_MessageBoxIconSize)))
    icon_label.setAlignment(Qt.AlignTop)
    layout.setAlignment(Qt.AlignTop)
    layout.addWidget(icon_label)
    msg_layout = QVBoxLayout()
    title_label = QLabel("<b>Upgrading v0.0.2 settings to v0.1.0.</b>")
    msg_layout.addWidget(title_label)
    warning_label = QLabel(("<b>Your settings use features that are no longer supported.</b> There may be some changes to your settings. Read about them below" +
                           (" and make any adjustments if required." if used_multiple_per_path else ".") + "<br/><br/>") if used_unsupported_features else
                           "Information for each file in the settings is available below. Your settings use only supported features so no changes need to be made.")
    warning_label.setWordWrap(True)
    msg_layout.addWidget(warning_label)
    info_used_scale_res = "Setting print resolution when scaling is no longer supported.<br/>"
    info_used_project_versions = "The single-file and all-forward version options have been removed. Settings now affect all version files of a project.<br/>"
    info_used_non_kra_projects = "Only Krita project files (.kra) are recognised as project files that can be exported.<br/>"
    info_used_multiple_per_path = ("Settings for individual version files of a project are no longer supported.<br/>"
                                   "You will have to choose which of those settings you want to use for the project. <b>Use the radio buttons in the table to choose.</b><br/>"
                                   "For example, of the settings for 'path/to/project_001.kra' and 'path/to/project_002.kra', one must be chosen to be settings for 'path/to/project'.<br/>")
    info_label = QLabel("<ul>" + "".join(f"<li>{s}</li>" for s in (info_used_scale_res if used_scale_res else None,
                                              info_used_project_versions if used_project_versions else None,
                                              info_used_non_kra_projects if used_non_kra_projects else None,
                                              info_used_multiple_per_path if used_multiple_per_path else None) if s) + "</ul><br/>")
    msg_layout.addWidget(info_label)
    
    table = QTableWidget(len(intermediate_settings), 2)
    for i, info in enumerate(intermediate_settings):
        item0 = QTableWidgetItem(info["path"].as_posix())
        table.setItem(i, 0, item0)
        bp = info["path"].with_name(base_stem_and_version_number_for_versioned_file(info["path"])[0])
        if base_paths[bp]["group"]:
            item1 = QRadioButton(bp.name)
            base_paths[bp]["group"].addButton(item1, i)
            if base_paths[bp]["latest_path"] == info["path"]:
                item1.setChecked(True)
            table.setCellWidget(i, 1, item1)
        else:
            item1 = QTableWidgetItem(bp.name)
            table.setItem(i, 1, item1)
    table.setHorizontalHeaderLabels(("File", "Project (path omitted)"))
    table.setAlternatingRowColors(True)
    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    msg_layout.addWidget(table)
    
    layout.addLayout(msg_layout)
    
    msgBtns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Discard | QDialogButtonBox.Cancel)
    
    msgBtns_clicked_save = False
    def _on_msgBtns_clicked(btn):
        nonlocal msgBtns_clicked_save
        if btn in (msgBtns.button(QDialogButtonBox.Save), msgBtns.button(QDialogButtonBox.Discard)):
            if btn == msgBtns.button(QDialogButtonBox.Save):
                msgBtns_clicked_save = True
            msgBox.accept()
        else:
            msgBox.reject()
    
    msgBtns.clicked.connect(_on_msgBtns_clicked)
    
    action_label = QLabel(f"'{msgBtns.button(QDialogButtonBox.Save).text().replace("&","")}' upgrades your settings. "
                          f"'{msgBtns.button(QDialogButtonBox.Discard).text().replace("&","")}' ignores them and proceeds with no settings. "
                          f"Press '{msgBtns.button(QDialogButtonBox.Cancel).text().replace("&","")}' to not do anything right now. "
                          "In any case, your v0.0.2 settings will remain in your kritarc file (in settings, under TomJK_QuickExport).")
    action_label.setWordWrap(True)
    msg_layout.addWidget(action_label)
    
    msg_layout.addWidget(msgBtns)
    
    w = round((table.columnWidth(0)+table.columnWidth(1)+icon_label.sizeHint().width())*1.1)
    h = round((table.rowHeight(0)*len(intermediate_settings)+title_label.sizeHint().height()+warning_label.sizeHint().height()+info_label.sizeHint().height()+action_label.sizeHint().height())*1.1)
    g = QApplication.primaryScreen().availableGeometry()
    maxw = round(g.width()*0.75)
    maxh = round(g.height()*0.75)
    msgBox.resize(min(maxw, max(480, w)), min(maxh, max(320, h)))
    msgBox.exec()
    
    if msgBox.result() != msgBox.Accepted:
        print("v0.0.2 settings upgrade cancelled.")
        return False
    
    if not msgBtns_clicked_save:
        print("v0.0.2 settings not upgraded.")
        return True
    
    print("v0.0.2 settings upgrade started...")
    
    for base_path, base_path_info in base_paths.items():
        if base_path_info["group"]:
            i = base_path_info["group"].checkedId()
        else:
            i = base_path_info["latest_idx"]
        print(f"Settings for {base_path} will come from {intermediate_settings[i]['path']}.")
            
        src = intermediate_settings[i]
        settings = default_settings(base_path, node_type=QEItemType.PROJECT)
        
        s_basic = settings["basic"]
        s_basic["file_name_source"] = (QEFileNameSource.PROJECT if src["output_name"] == base_path.name else
                                       QEFileNameSource.FILE if src["output_name"] == src["path"].stem else
                                       QEFileNameSource.CUSTOM)
        s_basic["file_name_custom"] = src["output_name"] if s_basic["file_name_source"] == QEFileNameSource.CUSTOM else ""
        s_basic["ext"] = src["ext"]
        
        output_folder = src["output_abs_dir"]
        base_folder = base_path.parent
        s_basic["location"] = (QELocation.IN_SAME_FOLDER if output_folder == base_folder else
                               QELocation.IN_SUBFOLDER if output_folder.parent == base_folder else
                               QELocation.IN_PARENT_OF_FOLDER if base_folder.parent == output_folder else
                               QELocation.IN_SIBLING_OF_FOLDER if base_folder.parent == output_folder.parent else
                               QELocation.CUSTOM)
        if s_basic["location"] != QELocation.CUSTOM:
            s_basic["location_name_source"] = (QEFolderNameSource.PROJECT if output_folder.name == base_path.name else
                                               QEFolderNameSource.CUSTOM)
            if s_basic["location_name_source"] == QEFolderNameSource.CUSTOM:
                s_basic["location_name_custom"] = output_folder.name
        else:
            s_basic["location_custom"] = output_folder.relative_to(base_folder, walk_up=True)
        s_basic["scale"] = src["scale"]
        s_basic["scale_side"] = QEImageEdge.BOTH
        if "scale_width" in src:
            s_basic["scale_width"] = src["scale_width"]
            s_basic["scale_width_mode"] = QEUnits.PIXELS
        if "scale_height" in src:
            s_basic["scale_height"] = src["scale_height"]
            s_basic["scale_height_mode"] = QEUnits.PIXELS
        s_basic["scale_filter"] = filter_strategy_strings.index(src["scale_filter"]) if src["scale_filter"] in filter_strategy_strings else QEScaleStrategy.AUTO
        if "scale_res" in src:
            s_basic["scale_res"] = src["scale_res"]
        
        settings["export"]["png"] = {
            "alpha":                 src["png_alpha"],
            "compression":           src["png_compression"],
            "downsample":            src["png_force_8bit"],
            "forceSRGB":             src["png_force_srgb"],
            "indexed":               src["png_indexed"],
            "interlaced":            src["png_interlaced"],
            "saveAsHDR":             src["png_hdr"],
            "saveSRGBProfile":       src["png_embed_srgb"],
            "storeAuthor":           src["png_author"],
            "storeMetaData":         src["png_metadata"],
            "transparencyFillcolor": ManagedColor.fromQColor(src["png_fillcolour"]).toXML()
        }
        
        settings["export"]["jpeg"] = {
            "baseline":              src["jpeg_force_baseline"],
            "exif":                  src["jpeg_exif"],
            "filters":               ("ToolInfo," if src["jpeg_tool_information"] else "") + ("Anonymizer," if src["jpeg_anonymiser"] else ""),
            "iptc":                  src["jpeg_iptc"],
            "optimize":              src["jpeg_optimise"],
            "progressive":           src["jpeg_progressive"],
            "quality":               src["jpeg_quality"],
            "saveProfile":           src["jpeg_icc_profile"],
            "smoothing":             src["jpeg_smooth"],
            "storeAuthor":           src["jpeg_author"],
            "storeMetaData":         src["jpeg_metadata"],
            "subsampling":           src["jpeg_subsampling"],
            "transparencyFillcolor": ManagedColor.fromQColor(src["jpeg_fillcolour"]).toXML(),
            "xmp":                   src["jpeg_xmp"]
        }
        
        qe_settings[base_path] = settings
    
    print("v0.0.2 settings upgrade finished.")
    return True
