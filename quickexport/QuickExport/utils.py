from PyQt5.QtGui import QColor
from pathlib import Path
from functools import reduce
import re
from krita import *
app = Krita.instance()

qe_settings = []

qe_extension = None

def set_extension(extension):
    global qe_extension
    qe_extension = extension

def extension():
    return qe_extension

def bool2str(boolval):
    return "true" if boolval else "false"

def str2bool(strval):
    return True if strval == "true" else False

def bool2flag(*args):
    return reduce(lambda a,b: a+b, (("1" if b else "0") for b in args))

def flag2bool(strval):
    return True if strval == "1" else False

def default_settings(document=None, doc_index=1024, store=False, path=None, output="", ext=".png"):
    settings = {
        "document":document,
        "doc_index":doc_index,
        "store":store,
        "path":path,
        "output":output,
        "ext":ext,
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
    example: "path=a/b.kra,output=b,ext=.png,png=[fc=#ffffff,co=9,flag=110000000],jpeg=[];"
    becomes: settings[{"document":<obj>, "store":True, "path":"a/b.kra", "output":"b", "ext":".png", "png_fillcolour":QColor('#ffffff'), "compression":9, "png_alpha":True, "png_indexed":True, "png_interlaced":False ... etc.}]
    """
    qe_settings.clear()
    
    # TODO: will break if a filename contains a comma ',' char.
    settings_string = app.readSetting("TomJK_QuickExport", "settings", "")
    #print(f"{settings_string=}")
    
    if settings_string == "":
        return
    
    settings_tokens = []
    tokenize_settings_string(settings_string, settings_tokens)
    
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
        for k,v in file_kvpairs:
            if k == "path":
                settings[k] = Path(v)
                for i, d in enumerate(app.documents()):
                    if d.fileName() == v:
                        settings["document"] = d
                        settings["doc_index"] = i
                        break
            elif k in ("output", "ext"):
                settings[k] = v
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
        qe_settings.append(settings)
        #print()

def find_settings_for_file(file_path):
    for s in qe_settings:
        if s["path"] == file_path:
            return s
    return None

def generate_save_string():
    save_strings = []
    
    for s in qe_settings:
        if not s["store"]:
            continue
        
        save_strings.append(
            f"path={str(s['path'])},"
            f"output={s['output']},"
            f"ext={s['ext']},"
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
    app.writeSetting("TomJK_QuickExport", "settings", save_string)

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
    elif ext == ".jpg":
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
    
    export_path = settings["path"].with_name(settings["output"]).with_suffix(settings["ext"])
    
    if not document:
        document = settings["document"]
    
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
        if char in "._-)]}+'":
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
                if text[se] in "._-()[]{}+'0123456789" or  (text[se] in "vV" and se+1 < tlen and text[se+1] in "0123456789"):
                    break
                se += 1
            l.append(text[ss:se])
            ss = se
    return l
