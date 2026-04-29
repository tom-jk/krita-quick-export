from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QObject
import sip
from timeit import default_timer
from traceback import format_tb
from pathlib import Path
from os.path import relpath
from functools import reduce
from enum import IntEnum, auto
import platform, os, subprocess
import re
import math
import json
from copy import deepcopy
from krita import *
app = Krita.instance()

PathRole = Qt.UserRole
ItemTypeRole = Qt.UserRole + 1

class QEItemType(IntEnum):
    INVALID = -1
    PROJECT = auto()
    FOLDER = auto()
    FILE = auto()

class QEFileNameSource(IntEnum):
    PROJECT = 0
    FILE = auto()
    CUSTOM = auto()

class QEFolderNameSource(IntEnum):
    PROJECT = 0
    CUSTOM = auto()

class QELocation(IntEnum):
    IN_SAME_FOLDER = 0
    IN_SUBFOLDER = auto()
    IN_PARENT_OF_FOLDER = auto()
    IN_SIBLING_OF_FOLDER = auto()
    CUSTOM = auto()

class QEImageEdge(IntEnum):
    NONE = -1
    WIDTH = auto()
    HEIGHT = auto()
    SHORTEST = auto()
    LONGEST = auto()
    BOTH = auto()

class QEUnits(IntEnum):
    NONE = -1
    PIXELS = auto()
    PERCENT = auto()

class QEScaleStrategy(IntEnum):
    NONE = -1
    AUTO = auto()
    BELL = auto()
    BICUBIC = auto()
    BILINEAR = auto()
    BSPLINE = auto()
    HERMITE = auto()
    LANCZOS3 = auto()
    MITCHELL = auto()
    NEAREST = auto()
    

config_clipboard = {"default":{}}

class WidgetBin(QObject):
    instance = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.__class__.instance = self
        
        self.deleted_ = []
        
        self.update_timer = QTimer()
        self.update_timer.setInterval(10)
        self.update_timer.timeout.connect(self._on_update_timer_timeout)

    @classmethod
    def addWidget(cls, widget):
        print(f"WidgetBin: adding widget {widget}.")
        item = [
            default_timer(),
            widget
        ]
        cls.instance.deleted_.append(item)
        
        if not cls.instance.update_timer.isActive():
            cls.instance.update_timer.start()
    
    def _on_update_timer_timeout(self):
        current_time = default_timer()
        item_index = 0
        while True:
            item = self.deleted_[item_index]
            delete_time = item[0]
            if current_time - delete_time > 0.01:
                print(f"WidgetBin: deleting widget {item[1]}.")
                self.deleted_.pop(item_index)
                sip.delete(item[1])
                del item
                if len(self.deleted_) == 0:
                    self.update_timer.stop()
                    break
            else:
                item_index += 1
                if item_index >= len(self.deleted_):
                    break

widget_bin = WidgetBin()

windows_forbidden_filename_chars = r"^<>:;?\*|/"

qe_settings_last_load = {}
qe_settings = {}

def update_qe_settings_last_load():
    global qe_settings_last_load
    global qe_settings
    qe_settings_last_load = deepcopy(qe_settings)

def settings_last_load():
    return qe_settings_last_load

qe_extension = None

setting_defaults = {"show_unstored":"true", "show_unopened":"false", "show_non_kra":"false", "auto_save_on_close":"true", "use_custom_icons":"true",
                    "custom_icons_theme":"follow", "show_export_name_in_menu":"true", "default_export_unsaved":"false", "show_thumbnails_for_unopened":"true",
                    "visible_types":".avif .exr .gif .ico .jpg .jpeg .jxl .png .tif .webp", "dialogWidth":"1024", "dialogHeight":"640", "columns_state":"",
                    "wide_column_resize_grabber":"false", "create_missing_folders_at_export":"ask", "settings_version":""}

filter_strategy_display_strings = ["Auto", "Bell", "Bicubic", "Bilinear", "BSpline", "Hermite", "Lanczos3", "Mitchell", "Nearest"]
filter_strategy_store_strings     = {"Auto":"A", "Bell":"B", "Bicubic":"Bic", "Bilinear":"Bil", "BSpline":"BS", "Hermite":"H", "Lanczos3":"L", "Mitchell":"M", "NearestNeighbor":"NN"}
filter_strategy_aliases           = {"Nearest Neighbor":"NearestNeighbor", "Nearest":"NearestNeighbor"}
filter_strategy_rev_store_strings = {v:k for k,v in filter_strategy_store_strings.items()}

colour_label_colours = (
    Qt.transparent,     QColor(91,173,220),  QColor(151,202,63),
    QColor(247,229,61), QColor(255,170,63),  QColor(177,102,63),
    QColor(238,50,51),  QColor(191,106,209), QColor(118,119,114)
)

def set_extension(extension):
    global qe_extension
    qe_extension = extension

def extension():
    return qe_extension

def readSetting(setting, default_override=None):
    return app.readSetting("TomJK_QuickExport", setting, default_override if default_override!=None else setting_defaults[setting])

def writeSetting(setting, value):
    app.writeSetting("TomJK_QuickExport", setting, value)

def bool2str(boolval):
    return "true" if boolval else "false"

def str2bool(strval):
    return True if strval == "true" else False

def str2qtcheckstate(strval, true="true"):
    return Qt.Checked if strval == true else Qt.Unchecked

def bool2flag(*args):
    return reduce(lambda a,b: a+b, (("1" if b else "0") for b in args))

def flag2bool(strval):
    return True if strval == "1" else False

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

qe_supported_extensions = (".avif", ".bmp", ".csv", ".exr", ".gbr", ".gif", ".gih", ".hdr", ".heic", ".ico", ".jpg", ".jpeg", ".jxl", ".krz", ".kpp", ".ora",
                           ".pbm", ".pgm", ".png", ".ppm", ".psd", ".qml", ".r16", ".r32", ".r8", ".scml", ".tga", ".tif", ".webp", ".xbm", ".xpm")

qe_configless_extensions = (".bmp", ".csv", ".gif", ".ico", ".krz", ".ora", ".pbm", ".pgm", ".ppm", ".psd", ".qml", ".scml", ".tga", ".xbm", ".xpm")

qe_config_aliases = {"jpg":"jpeg"}

def supported_extensions():
    return qe_supported_extensions

def configless_extensions():
    return qe_configless_extensions

def config_aliases():
    return qe_config_aliases

def default_settings(path, *, node_type=QEItemType.INVALID, document=None, doc_index=1024, store=False, output_name="", ext=".png"):
    settings = {
        "config_path_string":"",
        "config_macros_string":"",
        "config_basic_string":"",
        "path":path,
        "node_type":node_type,
        "export":{},
        "basic":{
            "file_name_source":QEFileNameSource.PROJECT,
            "file_name_custom":"",
            "ext":ext,
            "location":QELocation.IN_SAME_FOLDER,
            "location_name_source":QEFolderNameSource.PROJECT,
            "location_name_custom":"",
            "location_custom":Path(),
            "scale":False,
            "scale_side":QEImageEdge.HEIGHT,
            "scale_width":100.0,
            "scale_width_mode":QEUnits.PERCENT,
            "scale_height":100.0,
            "scale_height_mode":QEUnits.PERCENT,
            "scale_keep_aspect":True,
            "scale_filter":QEScaleStrategy.AUTO,
            "scale_res":-1
        }
    }
    generate_save_string(path, settings)
    return settings

def is_any_qe_setting_modified():
    # TODO: quite fragile, affected by order of items in dictionary.
    #       but safe-ish; errs on side of false-positive.
    #       Update: actually seems to be caused by colour strings (eg.
    #       for transparency colour) rearranging elements randomly.
    #       fixing this goes a bit against the "hands-off" approach to
    #       type-specific export configs, so not sure what's best to do.
    return qe_settings != qe_settings_last_load

# TODO: needs work upgrading old versions up to latest.
def load_settings_from_config(soft_warning_for_unsupported_version=False, suppress_version_warning=False):
    qe_settings.clear()
    
    settings_version = readSetting("settings_version")
    
    if settings_version == "":
        # <0.0.3 settings were saved as a single string with key 'settings'.
        # 0.0.3+ save to different keys and leave 'settings' unchanged, so
        # we don't have to backup these settings; they are their own backup.
        # TODO: add a button somewhere so user can overwrite it with "".
        load_0_0_2_settings_from_config()
        for s in qe_settings:
            generate_save_string(s)
        save_settings_to_config()
    
    elif settings_version == "0.0.3":
        return load_0_0_3_settings_from_config()
    
    else:
        if suppress_version_warning:
            return True
        
        msgBox = QMessageBox(app.activeWindow().qwindow() if app.activeWindow() else None)
        msgBox.setText("Quick Export settings in unsupported format found.")
        msgBox.setInformativeText(
            "Settings were saved in a different format by a later version of QuickExport. They can not be read by this version.\n\n" \
            "compatible versions: 0.0.3 and below\n" \
            f"saved as version: {settings_version}\n\n" \
            "It may be that a backup was made before saving the later version settings - check in your kritarc file.\n\n" \
            "You may also try opening an issue on the Github to request a converter, but using the latest version of the plugin is recommended.\n\n" \
            f"{'You should now either update the plugin, or close Krita and retrieve your settings in a compatible format.' if soft_warning_for_unsupported_version else 'If you continue, your existing export settings will be lost.'}"
        )
        if soft_warning_for_unsupported_version:
            msgBox.setStandardButtons(QMessageBox.Ok)
        else:
            msgBox.setStandardButtons(QMessageBox.Discard | QMessageBox.Cancel)
            discard_button = msgBox.button(QMessageBox.Discard)
            discard_button.setText('Continue')
            msgBox.setDefaultButton(QMessageBox.Cancel)
        ret = msgBox.exec()
        
        if ret in (QMessageBox.Ok, QMessageBox.Cancel):
            return False
    
    update_qe_settings_last_load()
    
    return True

def load_0_0_3_settings_from_config():
    """
    read in settings from kritarc. example:
    file0/macros=
    file0/path=/home/user/mypic
    file0/png={"alpha":false,"compression":3,"downsample":false  ..  "transparencyFillcolor":"<!DOCTYPE color>\n<color channeldepth=\"U8\">\n <RGB space=\"sRGB-elle-V2-srgbtrc.icc\" r=\"1\" g=\"1\" b=\"1\"/>\n</color>\n"}
    file0/basic=p,p,,png,s,p,,.,1,1.0,1.0,0,-1
    """
    global qe_settings
    qe_settings_backup = deepcopy(qe_settings)
    
    settings_index = 0
    
    try:
        while readSetting(f"file{settings_index}/path", "") != "":

            config_path_string = readSetting(f"file{settings_index}/path", "")
            path = Path(config_path_string)

            settings = default_settings(path, store=True)
            
            settings["config_path_string"]   = config_path_string
            settings["config_macros_string"] = readSetting(f"file{settings_index}/macros", "")
            settings["config_basic_string"]  = readSetting(f"file{settings_index}/basic", "")
            
            settings["path"] = path
            
            def read_settings_string(string):
                start_idx = 0
                end_idx = 0
                final_idx = len(string)
                subs = ""
                while True:
                    end_idx += 1
                    if end_idx == final_idx:
                        yield string[start_idx:end_idx]
                        break
                    subs += string[end_idx]
                    if subs.endswith("//"):
                        subs = ""
                    elif subs.endswith("/,"):
                        subs == ""
                    elif subs.endswith(","):
                        subs = ""
                        yield string[start_idx:end_idx]
                        start_idx = end_idx+1
            
            s_basic = settings["basic"]
            ss = read_settings_string(settings["config_basic_string"])
            settings["node_type"]             = ('p','f').index(next(ss))
            s_basic["file_name_source"]       = ('p','f','c').index(next(ss))
            s_basic["file_name_custom"]       = unescape_settings_string(next(ss))
            s_basic["ext"]                    = "." + next(ss)
            s_basic["location"]               = ('s','d','u','ud','c').index(next(ss))
            s_basic["location_name_source"]   = ('p','c').index(next(ss))
            s_basic["location_name_custom"]   = unescape_settings_string(next(ss))
            s_basic["location_custom"]        = Path(unescape_settings_string(next(ss)))
            s_basic["scale"]                  = flag2bool(next(ss))
            s_basic["scale_side"]             = int(next(ss))
            sm = int(next(ss))
            s_basic["scale_width_mode"]       = sm
            s_basic["scale_width"]            = int(next(ss)) if sm == QEUnits.PIXELS else float(next(ss))
            sm = int(next(ss))
            s_basic["scale_height_mode"]      = sm
            s_basic["scale_height"]           = int(next(ss)) if sm == QEUnits.PIXELS else float(next(ss))
            s_basic["scale_keep_aspect"]      = flag2bool(next(ss))
            s_basic["scale_filter"]           = int(next(ss))
            sr = next(ss)
            s_basic["scale_res"]              = float(sr) if sr != "-1" else -1
            
            for ext in supported_extensions():
                ext_key = ext[1:]
                ext_ss = readSetting(f"file{settings_index}/{ext_key}", "")
                
                if not ext_ss:
                    continue
                
                settings[f"config_export_{ext_key}_string"] = ext_ss
                settings["export"][ext_key] = json.loads(ext_ss)
            
            qe_settings[path] = settings
            settings_index += 1
        return True
        
    except Exception as e:
        from traceback import format_tb
        e_tb = format_tb(e.__traceback__)
        msgBox = QMessageBox(QMessageBox.Critical,
                             "Quick Export",
                             "The Quick Export plugin configuration could not be read.",
                             QMessageBox.Ok,
                             app.activeWindow().qwindow() if app.activeWindow() else None)
        msgBox.setDetailedText(f"You can try removing or editing the lines with keys starting 'file{settings_index}' under the [TomJK_QuickExport] group in your kritarc file. Be sure to close Krita before doing so.\n\n"
                               "----\n\n"
                               f"While loading settings for file #{settings_index}, the following error occured:\n\n{type(e).__name__}: {e}\n\n"
                               f"{"\n".join(e_tb)}\n"
                               "----\n\n"
                               f"Settings values at time of error:\n\n{'\n'.join((f'{k}: {v}' for k,v in settings.items()))}")
        msgBox.exec()
        qe_settings = qe_settings_backup

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
    
    #print()
    
    for file_kvpairs in settings_per_file:
        #print("found file settings", file_kvpairs)
        settings = default_settings(store=True)
        output_string = ""
        for k,v in file_kvpairs:
            if k == "path":
                settings[k] = Path(v)
                for i, d in enumerate(app.documents()):
                    if d.fileName() == v:
                        settings["document"] = d
                        settings["doc_index"] = i
                        break
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
            #print(f" found {k}:{v}")
        if output_string:
            output = deserialize_stored_output_string(settings["path"].parent, output_string)
            settings["output_is_abs"] = output[0]
            settings["output_abs_dir"] = output[1]
            settings["output_name"] = output[2]
        qe_settings.append(settings)
        #print()

def find_settings_path_for_file(file_path):
    """
    for given path to a file "/path/to/file.kra", find path of best (most specific) matching export settings.
    
    if export settings exist for the base /path/to/file, prioritise that.
    if export settings exist for the parent /path/to, fallback to that.
    otherwise, no settings exist for the file.
    
    return: settings path if found, else None.
    """
    
    def print(*args):
        pass
    
    if not file_path:
        return None
    
    folder_path = file_path.parent
    base_version_string, match_version_number = base_stem_and_version_number_for_versioned_file(file_path, unversioned_version_num=0)
    base_path = folder_path / Path(base_version_string)
    
    print(f"find_settings_path_for_file {file_path}: looking for {base_path=}")
    if base_path in qe_settings:
        print(f"find_settings_path_for_file {file_path}: got settings for project.")
        return base_path
    
    print(f"find_settings_path_for_file {file_path}: looking for {folder_path=}")
    if folder_path in qe_settings:
        print(f"find_settings_path_for_file {file_path}: got settings for containing folder.")
        return folder_path
    
    print(f"find_settings_for_file {file_path}: no settings found.")
    return None

def generate_save_string(settings_path, s=None):
    """
    settings_path accepts a Path object.
    s accepts a settings dictionary.
    If s is None, settings_path is used as key to qe_settings.
    """
    if not s:
        s = qe_settings[settings_path]
        
    s_basic = s["basic"]
    scale_width = int(s_basic['scale_width']) if s_basic['scale_width_mode'] == QEUnits.PIXELS else s_basic['scale_width']
    scale_height = int(s_basic['scale_height']) if s_basic['scale_height_mode'] == QEUnits.PIXELS else s_basic['scale_height']
    scale_res = f"{s_basic['scale_res']:.4f}".rstrip('0').rstrip('.') if s_basic["scale_res"] != -1 else "-1"
    
    s["config_path_string"] = settings_path.as_posix()
    s["config_macros_string"] = ""
    s["config_basic_string"] = (
        f"{('p','f')[s['node_type']]},"
        f"{('p','f','c')[s_basic['file_name_source']]},"
        f"{escape_settings_string(s_basic['file_name_custom'])},"
        f"{s_basic['ext'][1:]},"
        f"{('s','d','u','ud','c')[s_basic['location']]},"
        f"{('p','c')[s_basic['location_name_source']]},"
        f"{escape_settings_string(s_basic['location_name_custom'])},"
        f"{escape_settings_string(s_basic['location_custom'].as_posix())},"
        f"{bool2flag(s_basic['scale'])},{int(s_basic['scale_side'])},{int(s_basic['scale_width_mode'])},{scale_width},{int(s_basic['scale_height_mode'])},{scale_height},{bool2flag(s_basic['scale_keep_aspect'])},{s_basic["scale_filter"]},{scale_res}"
    )
    
    print(f"{s['config_basic_string']=}")

    for ext in supported_extensions():
        ext_key = ext[1:]
        
        if ext_key not in s["export"]:
            continue
        
        s[f"config_export_{ext_key}_string"] = json.dumps(s["export"][ext_key], separators=(",",":"))

def save_settings_to_config():
    print("save_settings_to_config")
    
    settings_index = 0
    
    for path,s in qe_settings.items():
        generate_save_string(path)
        
        path_string   = s["config_path_string"]
        macros_string = s["config_macros_string"]
        basic_string  = s["config_basic_string"]
        
        writeSetting(f"file{settings_index}/path", path_string)
        #writeSetting(f"file{settings_index}/macros", macros_string)
        writeSetting(f"file{settings_index}/basic", basic_string)
        
        for ext in supported_extensions():
            ext_key = ext[1:]
            
            if ext_key in s["export"]:
                export_string = s[f"config_export_{ext_key}_string"] # ~ or s[f"config_stored_export_{ext_key}_string"]
            else:
                # erase export config for extension if exists.
                if not readSetting(f"file{settings_index}/{ext_key}", ""):
                    continue
                export_string = ""
            
            writeSetting(f"file{settings_index}/{ext_key}", export_string)
        
        settings_index += 1
    
    # clear up old config remnants.
    while readSetting(f"file{settings_index}/path", "") != "":
        writeSetting(f"file{settings_index}/path", "")
        #writeSetting(f"file{settings_index}/macros", "")
        writeSetting(f"file{settings_index}/basic", "")
        for ext in supported_extensions():
            ext_key = ext[1:]
            if readSetting(f"file{settings_index}/{ext_key}", ""):
                writeSetting(f"file{settings_index}/{ext_key}", "")
        settings_index += 1
    
    writeSetting("settings_version", "0.0.3")
    
    update_qe_settings_last_load()

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

def escape_settings_string(s):
    return s.replace("/", "//").replace(",", "/,")

def unescape_settings_string(s):
    return s.replace("//", "/").replace("/,", ",")

def auto_filter_strategy(original_width, original_height, desired_width, desired_height):
    """Python copy of krita/libs/image/kis_filter_strategy.cc method KisFilterStrategyRegistry::autoFilterStrategy."""

    # Default to nearest neighbor scaling for tiny source images. (i.e: icons or small sprite sheets.)
    pixel_art_threshold = 256
    if original_width <= pixel_art_threshold or original_height <= pixel_art_threshold:
        return "NearestNeighbor"

    x_scale_factor = desired_width / original_width
    y_scale_factor = desired_height / original_height

    if x_scale_factor > 1.0 or y_scale_factor > 1.0: # Enlargement.
        return "Bicubic"
    elif x_scale_factor < 1.0 or y_scale_factor < 1.0: # Reduction.
        return "Bicubic"

    return "NearestNeighbor"

def export_file_path(settings, source_path, item_type=QEItemType.FILE):
    """
    settings: dictionary of settings to use.
    source_path: the file being exported.
    item_type: a QEItemType. how to interpret source_path.
    returns path to export to (for base and folder types, sample path for display only).
    """
    
    if item_type in (QEItemType.PROJECT, QEItemType.FILE):
        folder = source_path.parent
        base = base_stem_and_version_number_for_versioned_file(source_path)[0]
        #print(base)
        file_name = source_path.stem if item_type == QEItemType.FILE else "<FileName>"
    else:
        folder = source_path
        base = "<ProjectName>"
        file_name = "<FileName>"
    
    s_basic = settings["basic"]
    file_name_source_index = s_basic["file_name_source"]
    file_name_custom = s_basic["file_name_custom"]
    output_extension = s_basic["ext"]
    location_index = s_basic["location"]
    location_name_source_index = s_basic["location_name_source"]
    location_name_custom = s_basic["location_name_custom"]
    location_custom = s_basic["location_custom"]
    
    output_stem = (base, file_name, file_name_custom)[file_name_source_index]
    folder_name = base if location_name_source_index == QEFolderNameSource.PROJECT else location_name_custom
    output_folder = (folder, folder / folder_name, folder.parent, folder.parent / folder_name, location_custom)[location_index]
    
    return output_folder / (output_stem + output_extension)
    

export_failed_msg_ = ""

def export_failed_msg():
    return export_failed_msg_

def set_export_failed_msg(msg):
    global export_failed_msg_
    export_failed_msg_ = msg

def export_image(settings_path, document=None):
    exportParameters = InfoObject()
    
    settings = qe_settings[settings_path]
    s_basic = settings["basic"]
    s_export = settings["export"]
    
    ext = s_basic["ext"]
    ext_key = ext[1:]
    
    if ext_key in config_aliases():
        ext_key = config_aliases()[ext_key]
    
    if not ext in configless_extensions():
        if ext_key in s_export:
            for k,v in s_export[ext_key].items():
                exportParameters.setProperty(k, v)
        else:
            set_export_failed_msg(f"No configuration for {ext} file type.")
            return False
    
    for p in exportParameters.properties():
        print(p)
    
    if not document:
        document = settings["document"]
    
    export_path = export_file_path(settings, Path(document.fileName()))
    
    if not export_path.is_absolute():
        set_export_failed_msg(f"The configured export path is invalid.")
        return False
    
    if export_path.parent.is_file():
        set_export_failed_msg(f"There is already a file at {export_path.parent}.")
        return False
    
    if not export_path.parent.exists():
        create_missing_folders_at_export = readSetting("create_missing_folders_at_export")
        if create_missing_folders_at_export == "never":
            set_export_failed_msg(f"The export folder '{export_path.parent}' doesn't exist.")
            return False
        
        # if an ancestor folder exists, automatically create intermediary folders.
        ancestor_path = export_path.parent
        folders_to_make = []
        while not ancestor_path.exists():
            if ancestor_path == ancestor_path.parent:
                break
            folders_to_make.append(ancestor_path)
            ancestor_path = ancestor_path.parent
        if not ancestor_path.exists():
            set_export_failed_msg(f"The export folder '{export_path.parent}' doesn't exist.")
            return False
        
        folders_to_make.reverse()
        plural = len(folders_to_make) > 1
        
        if create_missing_folders_at_export == "ask":
            if QMessageBox.question(app.activeWindow().qwindow(), "Create missing folders?",
                                    f"You are exporting to a folder that does not exist. The following folder{'s' if plural else ''} must be created first:\n\n"
                                    f"{'\n'.join((str(f) if i==0 else ' ... '+str(f.name) for i,f in enumerate(folders_to_make)))}\n\n"
                                    f"Do you want to create {'them' if plural else 'it'} now?") != QMessageBox.Yes:
                set_export_failed_msg(f"The export folder '{export_path.parent}' doesn't exist.")
                return False
        
        print("Creating missing folders...")
        try:
            export_path.parent.mkdir(parents=True)
        except PermissionError:
            set_export_failed_msg(f"The export folder '{export_path.parent}' could not be created: Permission denied.")
            return False
        except FileExistsError:
            pass # so long as it exists...
        except Exception as e:
            set_export_failed_msg(f"The export folder '{export_path.parent}' could not be created: f{e}")
            return False
    
    do_resize = False
    
    if s_basic["scale"]:
        scale_side = s_basic["scale_side"]
        scale_keep_aspect = s_basic["scale_keep_aspect"]
        
        doc_width = document.width()
        doc_height = document.height()
        
        scale_width = doc_width
        scale_height = doc_height
        
        if scale_side in (QEImageEdge.WIDTH,  QEImageEdge.BOTH) or (scale_side == QEImageEdge.SHORTEST and doc_width <= doc_height) or (scale_side == QEImageEdge.LONGEST and doc_width >= doc_height):
            scale_width  = max(1, int(s_basic["scale_width"]) if s_basic["scale_width_mode"]  == QEUnits.PIXELS else round(doc_width  * s_basic["scale_width"] * 0.01))
        if scale_side in (QEImageEdge.HEIGHT, QEImageEdge.BOTH) or (scale_side == QEImageEdge.SHORTEST and doc_width >= doc_height) or (scale_side == QEImageEdge.LONGEST and doc_width <= doc_height):
            # short/long side modes store scale value in primary (ie. width) setting.
            scale_source = "scale_width" if scale_side in (QEImageEdge.SHORTEST, QEImageEdge.LONGEST) else "scale_height"
            scale_height = max(1, int(s_basic[scale_source])  if s_basic["scale_height_mode"] == QEUnits.PIXELS else round(doc_height * s_basic[scale_source]  * 0.01))
        
        if scale_side != QEImageEdge.BOTH and scale_keep_aspect and not (scale_side in (QEImageEdge.SHORTEST, QEImageEdge.LONGEST) and doc_width == doc_height):
            if scale_width != doc_width:
                scale_height = max(1, round(scale_height * (scale_width / doc_width)))
            elif scale_height != doc_height:
                scale_width = max(1, round(scale_width * (scale_height / doc_height)))
        
        # example: 0 -> 'Auto', 8 -> 'Nearest'.
        scale_filter = filter_strategy_display_strings[s_basic["scale_filter"]]
        if scale_filter in filter_strategy_aliases:
            # example: 'Nearest' -> 'NearestNeighbor'.
            scale_filter = filter_strategy_aliases[scale_filter]
        
        do_resize = s_basic["scale"] and (scale_width != document.width() or scale_height != document.height())
        #print(f"export: do resize: {do_resize}")
    
    if do_resize:
        if scale_filter == "Auto":
            scale_filter = auto_filter_strategy(document.width(), document.height(), scale_width, scale_height)
        
        if scale_filter not in app.filterStrategies():
            set_export_failed_msg(f"Chosen filter strategy '{scale_filter}' not recognised.")
            return False
        
        # TODO: (low priority): resolution probably not handled correctly.
        scale_xres = document.xRes()
        scale_yres = document.yRes()
        if s_basic["scale_res"] != -1:
            aspect = scale_height / scale_width
            scale_xres = s_basic["scale_res"]
            scale_yres = s_basic["scale_res"] * aspect
        
        doc_copy = document.clone()

        doc_copy.flatten()
        print(f"export: scale: {doc_width} x {doc_height}  ->  {scale_width} x {scale_height}")
        doc_copy.scaleImage(scale_width, scale_height, int(scale_xres), int(scale_yres), scale_filter)

        doc_copy.setBatchmode(True)
        doc_copy.waitForDone()
        result = doc_copy.exportImage(str(export_path), exportParameters)
        doc_copy.setBatchmode(False)

        if doc_copy.close() == False:
            print("Export copy of document didn't close?")

    else:

        document.setBatchmode(True)
        document.waitForDone()
        result = document.exportImage(str(export_path), exportParameters)
        document.setBatchmode(False)
    
    return result

def truncated_name_suggestions(text):
    l = []
    ss = 0
    se = 0
    tlen = len(text)
    while ss < tlen:
        char = text[ss]
        if char in ",._-)]}+'":
            # Punctuation Mark: consume characters until character is not THAT punctuation mark.
            se = ss + 1
            while se < tlen:
                if text[se] != char:
                    break
                se += 1
            l.append(text[ss:se])
            ss = se
        elif char in "([{":
            # Opening Bracket: consume characters until character is a closing bracket.
            se = ss + 1
            while se < tlen:
                if text[se] in ")]}":
                    se += 1
                    break
                se += 1
            l.append(text[ss:se])
            ss = se
        elif char in "0123456789":
            # Digit: consume characters until character is not ANY number.
            se = ss + 1
            while se < tlen:
                if text[se] not in "0123456789":
                    break
                se += 1
            l.append(text[ss:se])
            ss = se
        else:
            # General Text: consume characters until character is a punctuation mark, digit, or
            #               possible version number (eg. 'v001' in 'myfilev001').
            se = ss + 1
            while se < tlen:
                if text[se] in ",._-()[]{}+'0123456789" or  (text[se] in "vV" and se+1 < tlen and text[se+1] in "0123456789"):
                    break
                se += 1
            l.append(text[ss:se])
            ss = se
    return l

def base_stem_and_version_number_for_versioned_file(file_path, unversioned_version_num=None):
    """
    for file with stem "filename0_000", return ("filename0", 0).
    for file with stem "filename0_003", return ("filename0", 3).
    for file with stem "filename0_003_007", return ("filename0_003", 7).
    if not versioned, eg. "filename0", return ("filename0", unversioned_version_num).
    """
    matches = list(re.finditer("(_[0-9]+)$", file_path.stem))
    base_version_stem = file_path.stem
    match_version_num = unversioned_version_num
    if matches:
        match = matches[0]
        base_version_stem = file_path.stem[:match.start()]
        match_version_num = int(match.group()[1:])
    return base_version_stem, match_version_num

# https://stackoverflow.com/a/16204023
def open_folder_in_file_browser(path):
    if not (path.exists() and path.is_dir()):
        print(f"Folder not found at {path}")
        QMessageBox.critical(dialog, "Krita", f"Folder {path} does not exist.")
        return
    
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

def rotate_point_around_point(px, py, ox, oy, angle):
    """
    rotate the point (px,py) clockwise around the point (ox,oy) by angle.
    """
    offset_x = px - ox
    offset_y = py - oy
    start_angle = math.atan2(offset_y, offset_x)
    distance = math.sqrt(offset_x**2 + offset_y**2)
    end_angle = start_angle + angle
    x = ox + math.cos(end_angle) * distance
    y = oy + math.sin(end_angle) * distance
    return x,y

def find_layers(root_node, name, name_is_regex, respect_locks, colour_labels, bad_regex_return_error=False):
    # match name.
    if name_is_regex:
        import re
        try:
            pattern = re.compile(name)
        except re.error as e:
            print("Bad regular expression:", e)
            return e if bad_regex_return_error else []
        nodes = root_node.findChildNodes("", True, True, "", 0)
        nodes = list(filter(lambda node: pattern.match(node.name()), nodes))
    else:
        nodes = root_node.findChildNodes(name, True, False, "", 0)
    
    # remove invalid nodes, eg. locked if respect_locks, or decorations-wrapper-layer for grids.
    nodes = list(filter(lambda node: node.type() != "" and not (respect_locks and node.locked()), nodes))
    
    # match colour label.
    if isinstance(colour_labels, list) and any(label==True for label in colour_labels):
        nodes = list(filter(lambda node: colour_labels[node.colorLabel()], nodes))

    print("find_layers results:")
    for node in nodes:
        print(f" - {node.name()}")

    return nodes

# from https://www.geeksforgeeks.org/python/pyqt5-how-to-get-cropped-square-image-from-rectangular-image/
def square_thumbnail(pixmap, size=8):
    image = QImage(pixmap)#.fromData(imgdata, imgtype)

    image.convertToFormat(QImage.Format_ARGB32)

    imgsize = min(image.width(), image.height())
    rect = QRect(
        (image.width() - imgsize) // 2,
        (image.height() - imgsize) // 2,
        imgsize,
        imgsize,
    )
    image = image.copy(rect)

    out_img = QImage(imgsize, imgsize, QImage.Format_ARGB32)
    out_img.fill(Qt.transparent)

    # Create a texture brush and paint a circle
    # with the original image onto
    # the output image:
    brush = QBrush(image)

    # Paint the output image
    painter = QPainter(out_img)
    painter.setBrush(brush)
    painter.setPen(Qt.NoPen)

    # drawing square
    painter.drawRect(0, 0, imgsize, imgsize)

    painter.end()

    # Convert the image to a pixmap and rescale it.
    pr = QWindow().devicePixelRatio()
    pm = QPixmap.fromImage(out_img)
    pm.setDevicePixelRatio(pr)
    size = int(size * pr)
    pm = pm.scaled(size, size, Qt.KeepAspectRatio, 
                               Qt.SmoothTransformation)

    # return back the pixmap data
    return pm
