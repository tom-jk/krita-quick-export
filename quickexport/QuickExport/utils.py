from pathlib import Path
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
    example: "path=a/b.kra,alpha=false,ouput=b.png;c/d.kra,alpha=true,output=e/f.png"
    becomes: settings[{"document":<obj>, "store":True, "path":"a/b.kra", "alpha":False, "output":"b.png"}, {"document":<obj>, "store":True, "path":"c/d.kra", "alpha":True, "output":"d.png"}]
    """
    qe_settings.clear()
    
    # TODO: will break if a filename contains a comma ',' char.
    settings_string = app.readSetting("TomJK_QuickExport", "settings", "")
    #print(f"{settings_string=}")
    
    if settings_string == "":
        return
    
    settings_as_arrays = [[[y for y in kvpair.split('=', 1)] for kvpair in file.split(',')] for file in settings_string.split(';')]
    #print(f"{settings_as_arrays=}")
    
    #print()
    
    for file_settings in settings_as_arrays:
        #print("found file settings", file_settings)
        qe_settings.append(default_settings(store=True))
        for kvpair in file_settings:
            if kvpair[0] == "path":
                qe_settings[-1][kvpair[0]] = Path(kvpair[1])
                for i, d in enumerate(app.documents()):
                    if d.fileName() == kvpair[1]:
                        qe_settings[-1]["document"] = d
                        qe_settings[-1]["doc_index"] = i
                        break
            elif kvpair[0] == "png_alpha":
                qe_settings[-1][kvpair[0]] = str2bool(kvpair[1])
            elif kvpair[0] == "png_compression":
                qe_settings[-1][kvpair[0]] = int(kvpair[1])
            elif kvpair[0] == "jpeg_quality":
                qe_settings[-1][kvpair[0]] = int(kvpair[1])
            elif kvpair[0] == "output":
                qe_settings[-1][kvpair[0]] = kvpair[1]
            elif kvpair[0] == "ext":
                qe_settings[-1][kvpair[0]] = kvpair[1]
            else:
                print(f" unrecognised parameter name '{kvpair[0]}'")
                continue
            #print(" found", kvpair)
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
            f"png_alpha={bool2str(s['png_alpha'])},"
            f"png_compression={s['png_compression']},"
            f"jpeg_quality={s['jpeg_quality']},"
            f"output={s['output']},"
            f"ext={s['ext']}"
        )
    
    return ";".join(save_strings)

def save_settings_to_config():
    print("save_settings_to_config")
    
    save_string = generate_save_string()

    print(f"{save_string=}")
    app.writeSetting("TomJK_QuickExport", "settings", save_string)

def export_image(image_settings, document=None):
    exportParameters = InfoObject()

    extension = image_settings["ext"]
    
    if extension == ".png":
        exportParameters.setProperty("alpha", image_settings["png_alpha"])
        exportParameters.setProperty("compression", int(image_settings["png_compression"]))
        exportParameters.setProperty("indexed", True)
    elif extension == ".jpg":
        exportParameters.setProperty("quality", image_settings["jpeg_quality"])
    
    export_path = image_settings["path"].with_name(image_settings["output"]).with_suffix(image_settings["ext"])
    
    if not document:
        document = image_settings["document"]
    
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
