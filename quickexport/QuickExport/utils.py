from PyQt5.QtGui import QColor
from PyQt5.QtCore import QObject
import sip
from timeit import default_timer
from pathlib import Path
from os.path import relpath
from functools import reduce
import re
from krita import *
app = Krita.instance()

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

qe_settings = []

qe_extension = None

filter_strategy_store_strings = {"Auto":"A", "Bell":"B", "Bicubic":"Bic", "Bilinear":"Bil", "BS":"BSpline", "Hermite":"H", "Lanczos3":"L", "Mitchell":"M", "NearestNeighbor":"NN"}

def set_extension(extension):
    global qe_extension
    qe_extension = extension

def extension():
    return qe_extension

def readSetting(setting, default_value):
    return app.readSetting("TomJK_QuickExport", setting, default_value)

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

qe_supported_extensions = (".gif", ".jpg", ".jpeg", ".pbm", ".pgm", ".png", ".ppm", ".tga", ".bmp", ".ico", ".xbm", ".xpm")

def supported_extensions():
    return qe_supported_extensions

def default_settings(document=None, doc_index=1024, store=False, path=None, versions=None, output_name="", ext=".png", set_scale=False, scale_filter="Auto"):
    bvs = None
    mvn = None
    if path:
        bvs, mvn = base_stem_and_version_number_for_versioned_file(path)
        if not versions:
            versions = "all" if bvs == path.stem else "all_forward"
    set_scale = set_scale and document
    settings = {
        "document":document,
        "doc_index":doc_index,
        "store":store,
        "path":path,
        "versions": versions,
        "base_version_string": bvs,
        "matched_version_number": mvn,
        "output_is_abs": False,
        "output_abs_dir": path.parent if isinstance(path, Path) else None,
        "output_name":output_name,
        "ext":ext,
        "scale":False,
        "scale_width":document.width() if set_scale else -1,
        "scale_height":document.height() if set_scale else -1,
        "scale_filter":scale_filter,
        "scale_res":document.xRes() if set_scale else -1,
        "png_alpha":False,
        "png_fillcolour":QColor('white'),
        "png_compression":9,
        "png_indexed":True,
        "png_interlaced":False,
        "png_hdr":False,
        "png_embed_srgb":False,
        "png_force_srgb":False,
        "png_metadata":False,
        "png_author":False,
        "png_force_8bit":False,
        "jpeg_progressive":False,
        "jpeg_icc_profile":False,
        "jpeg_fillcolour":QColor('white'),
        "jpeg_quality":80,
        "jpeg_force_baseline":True,
        "jpeg_optimise":False,
        "jpeg_smooth":0,
        "jpeg_subsampling":"2x2",
        "jpeg_exif":True,
        "jpeg_iptc":True,
        "jpeg_xmp":True,
        "jpeg_tool_information":False,
        "jpeg_anonymiser":False,
        "jpeg_metadata":False,
        "jpeg_author":False
    }
    return settings

def load_settings_from_config():
    """
    read in settings string from kritarc.
    example: "path=/a/b.kra,output=b,ext=.png,scale=[e=1,w=1024,h=768,f=Bic,r=72],png=[fc=#ffffff,co=9,flag=110000000],jpeg=[];"
    becomes: settings[{"document":<obj>, "store":True, "path":Path("/a/b.kra"), "output_is_abs":False, "output_abs_dir":Path("/a"), "output_name":"b", "ext":".png", "scale":True,
                       "scale_width":1024, ... "png_fillcolour":QColor('#ffffff'), "png_compression":9, "png_alpha":True, "png_indexed":True, ... etc.}]
    
    commas (,) in file paths and names are replaced with slash-comma (/,).
    example: settings[{"path":Path("path=/pa,th/to/,a/file.kra", "output_name":"file,", "ext":".png", ... }]
    becomes: "path=/pa/,th/to//,a/file.kra,output=file/,,ext=.png ... "
    """
    
    qe_settings.clear()
    
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
                sf = [fk for fk,fv in filter_strategy_store_strings.items() if fv == v]
                settings["scale_filter"] = sf[0] if len(sf) > 0 else v
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

def find_settings_for_file(file_path):
    """
    for given path "/path/to/file.kra", find best (most specific) matching export settings.
    
    match quality goes: base name (all), base name (all forward), base name with progressively closer lower versions (all forward), exact file name.
    
    example: "/path/to/file0_005.kra"
    x. "path/to/file.kra"      - any version settings   - is not a match.
    1. "path/to/file0.kra"     - versions = all         - is a match.
    2. "path/to/file0.kra"     - versions = all_forward - is a match. (two entries for the same path shouldn't exist but if they do, this is considered a better match than 1.)
    3. "path/to/file0_003.kra" - versions = all_forward - is a better match than 2.
    4. "path/to/file0_004.kra" - versions = all-forward - is a better match than 3.
    5* "path/to/file0_005.kra" - any versions settings  - is the best possible match.
    x. "path/to/file0_006.kra" - any version settings   - is not a match.
    """
    
    def print(*args):
        pass
    
    print(f" **** find_settings_for_file {file_path} ****")
    
    # TODO: cache some of these things.
    
    base_version_string, match_version_number = base_stem_and_version_number_for_versioned_file(file_path)
    stem = file_path.stem
    suffix = file_path.suffix
    best_s = None
    best_version_number = 0
    for s in qe_settings:
        if not s["store"]:
            # only match stored settings.
            print(f" - {s['path']} is not a stored setting.")
            continue
        
        if s["path"] == file_path:
            # exact match.
            print(f" - {s['path']} is exact match.")
            print("   done.")
            return s
        
        if s["versions"] == "single":
            # these settings are for a single file, and it's not this one.
            print(f" - {s['path']} does not match (single file only).")
            continue
        
        s_parent = s["path"].parent
        if file_path.parent != s_parent:
            # wrong directory, can't be match.
            print(f" - {s['path']} does not match (wrong directory).")
            continue
        
        s_stem = s["path"].stem
        s_suff = s["path"].suffix
        s_bvs, s_mvn = base_stem_and_version_number_for_versioned_file(s["path"])
        
        if base_version_string != s_bvs:
            # not versions of the same image.
            print(f" - {s['path']} does not match (not a version of this image).")
            continue
        
        if s["versions"] == "all":
            # is version of image, but set only to apply to subversions of itself. eg. for "filename0_004":
            # "filename0_002" (all_forward) matches ("filename0_003", "filename0_004", "filename0_005", etc), but
            # "filename0_002" (all) does not match ("filename0_002_001", "filename0_002_002", "filename0_002_003", etc).
            print(f" - {s['path']} does not match (is its own base file, so excluded from set of versions of this image).")
            continue
        
        if suffix != s_suff:
            # accepts only same extension.
            print(f" - {s['path']} does not match (different extension).")
            continue
        
        if match_version_number < s_mvn:
            # these settings are for a later version.
            print(f" - {s['path']} does not match (settings for later versions only).")
            continue
        
        if best_version_number > s_mvn:
            # it's a match, but we already have a better match.
            print(f" - {s['path']} does match, but a better match has already been found.")
            continue
        
        print(f" - {s['path']} matches, new best.")
        best_s = s
        best_version_number = s_mvn
        
        # can't do this, may yet find exact match if continue looking.
        # if s_mvn == match_version_number - 1:
            # # won't find a closer match.
            # print(f" - {s['path']} is as close a match as you can get.")
            # print("   done.")
            # return s
    
    if best_s:
        print(f"best settings found were for {best_s['path']}.")
    else:
        print("no matching settings were found.")
    print("done.")
    return best_s

def generate_save_string():
    save_strings = []
    
    for s in qe_settings:
        if not s["store"]:
            continue
        
        scale_filter = filter_strategy_store_strings[s['scale_filter']] if s['scale_filter'] in filter_strategy_store_strings else s['scale_filter']
        scale_strings = []
        scale_strings.append(f"w={s['scale_width']}" if s['scale_width'] != -1 else "")
        scale_strings.append(f"h={s['scale_height']}" if s['scale_height'] != -1 else "")
        scale_strings.append(f"f={scale_filter}")
        scale_strings.append(f"r={s['scale_res']:.4f}".rstrip('0').rstrip('.') if s['scale_res'] != -1 else "")
        scale_string = ",".join([x for x in scale_strings if x != ""])
        
        versions_string = {'single':'s', 'all':'a', 'all_forward':'f'}[s['versions']]
        
        save_strings.append(
            f"path={escape_settings_string(str(s['path']))},"
            f"v={versions_string},"
            f"output={escape_settings_string(serialize_stored_output_string(s['path'].parent, s['output_is_abs'], s['output_abs_dir'], s['output_name']))},"
            f"ext={s['ext']},"
            f"scale=["
            f"e={bool2flag(s['scale'])},{scale_string}"
            f"],"
            f"png=["
            f"fc={s['png_fillcolour'].name(QColor.HexRgb)},"
            f"co={s['png_compression']},"
            f"flag={bool2flag(s['png_alpha'], s['png_indexed'], s['png_interlaced'], s['png_hdr'], s['png_embed_srgb'], s['png_force_srgb'], s['png_metadata'], s['png_author'], s['png_force_8bit'])}"
            f"],"
            f"jpeg=["
            f"fc={s['jpeg_fillcolour'].name(QColor.HexRgb)},"
            f"qu={s['jpeg_quality']},"
            f"sm={s['jpeg_smooth']},"
            f"ss={s['jpeg_subsampling']},"
            f"flag={bool2flag(s['jpeg_progressive'], s['jpeg_icc_profile'], s['jpeg_force_baseline'], s['jpeg_optimise'], s['jpeg_exif'], s['jpeg_iptc'], s['jpeg_xmp'], s['jpeg_tool_information'], s['jpeg_anonymiser'], s['jpeg_metadata'], s['jpeg_author'])}"
            f"]"
        )
    
    return ";".join(save_strings)

def save_settings_to_config():
    print("save_settings_to_config")
    
    save_string = generate_save_string()

    print(f"{save_string=}")
    writeSetting("settings", save_string)

def tokenize_settings_string(s, tokens):
    i = 0
    while True:
        subs = s[i:]
        mo = re.search("=|,|;|\[|\]", subs)
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
    return s.replace(",", "/,")

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

export_failed_msg_ = ""

def export_failed_msg():
    return export_failed_msg_

def set_export_failed_msg(msg):
    global export_failed_msg_
    export_failed_msg_ = msg

def export_image(settings, document=None):
    exportParameters = InfoObject()
    
    ext = settings["ext"]
    
    if ext == ".png":
        exportParameters.setProperty("alpha",                 settings["png_alpha"])
        exportParameters.setProperty("compression",           int(settings["png_compression"]))
        exportParameters.setProperty("forceSRGB",             settings["png_force_srgb"])
        exportParameters.setProperty("indexed",               settings["png_indexed"])
        exportParameters.setProperty("interlaced",            settings["png_interlaced"])
        exportParameters.setProperty("saveSRGBProfile",       settings["png_embed_srgb"])
        exportParameters.setProperty("transparencyFillcolor", settings["png_fillcolour"])
        exportParameters.setProperty("downsample",            settings["png_force_8bit"])       # not documented.
        exportParameters.setProperty("storeMetaData",         settings["png_metadata"])         # not documented.
        exportParameters.setProperty("storeAuthor",           settings["png_author"])           # not documented.
    elif ext in (".jpg", ".jpeg"):
        exportParameters.setProperty("baseline",              settings["jpeg_force_baseline"])
        exportParameters.setProperty("exif",                  settings["jpeg_exif"])
        exportParameters.setProperty("filters",               ",".join(filter(lambda item: bool(item), ["ToolInfo" * settings['jpeg_tool_information'], "Anonymizer" * settings["jpeg_anonymiser"]])))
        #exportParameters.setProperty("forceSRGB",            settings["??"])                   # probably safe to ignore for now.
        exportParameters.setProperty("iptc",                  settings["jpeg_iptc"])
        #exportParameters.setProperty("is_sRGB",              settings["??"])                   # probably safe to ignore for now.
        exportParameters.setProperty("optimize",              settings["jpeg_optimise"])
        exportParameters.setProperty("progressive",           settings["jpeg_progressive"])
        exportParameters.setProperty("quality",               int(settings["jpeg_quality"]))
        exportParameters.setProperty("saveProfile",           settings["jpeg_icc_profile"])
        exportParameters.setProperty("smoothing",             int(settings["jpeg_smooth"]))
        exportParameters.setProperty("subsampling",           ("2x2","2x1","1x2","1x1").index(settings["jpeg_subsampling"]))
        exportParameters.setProperty("transparencyFillcolor", settings["jpeg_fillcolour"])
        exportParameters.setProperty("xmp",                   settings["jpeg_xmp"])
        exportParameters.setProperty("storeMetaData",         settings["jpeg_metadata"])        # not documented.
        exportParameters.setProperty("storeAuthor",           settings["jpeg_author"])          # not documented.
    
    export_path = settings["output_abs_dir"].joinpath(settings["output_name"]).with_suffix(settings["ext"])
    
    if not document:
        document = settings["document"]
    
    scale_width = settings["scale_width"] if settings["scale_width"] != -1 else document.width()
    scale_height = settings["scale_height"] if settings["scale_height"] != -1 else document.height()
    scale_filter = settings["scale_filter"]
    
    do_resize = settings["scale"] and (scale_width != document.width() or scale_height != document.height())
    
    if do_resize:
        if scale_filter == "Auto":
            scale_filter = auto_filter_strategy(document.width(), document.height(), scale_width, scale_height)
        
        if scale_filter not in app.filterStrategies():
            set_export_failed_msg(f"Chosen filter strategy '{scale_filter}' not recognised.")
            return False
        
        scale_xres = document.xRes()
        scale_yres = document.yRes()
        if settings["scale_res"] != -1:
            aspect = scale_height / scale_width
            scale_xres = settings["scale_res"]
            scale_yres = settings["scale_res"] * aspect
        
        doc_copy = document.clone()

        doc_copy.flatten()
        doc_copy.scaleImage(scale_width, scale_height, int(scale_xres), int(scale_yres), scale_filter) # TODO: are these x/yres values correct?

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

def base_stem_and_version_number_for_versioned_file(file_path):
    """
    for file with stem "filename0_003", return ("filename0", 3).
    for file with stem "filename0_003_007", return ("filename0_003", 7).
    if not versioned, eg. "filename0", return ("filename0", 0).
    """
    matches = list(re.finditer("(_[0-9]+)$", file_path.stem))
    base_version_stem = file_path.stem
    match_version_num = 0
    if matches:
        match = matches[0]
        base_version_stem = file_path.stem[:match.start()]
        match_version_num = int(match.group()[1:])
    return base_version_stem, match_version_num
