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
        qe_settings.append({"document":None, "doc_index":1024, "store":True})
        for kvpair in file_settings:
            if kvpair[0] == "path":
                qe_settings[-1][kvpair[0]] = Path(kvpair[1])
                for i, d in enumerate(app.documents()):
                    if d.fileName() == kvpair[1]:
                        qe_settings[-1]["document"] = d
                        qe_settings[-1]["doc_index"] = i
                        break
            elif kvpair[0] == "alpha":
                qe_settings[-1][kvpair[0]] = True if kvpair[1] == "true" else False
            elif kvpair[0] == "compression":
                qe_settings[-1][kvpair[0]] = int(kvpair[1])
            elif kvpair[0] == "output":
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
        
        save_strings.append(f"path={str(s['path'])},alpha={'true' if s['alpha']==True else 'false'},compression={s['compression']},output={s['output']}")
    
    return ";".join(save_strings)

def save_settings_to_config():
    print("save_settings_to_config")
    
    save_string = generate_save_string()

    print(f"{save_string=}")
    app.writeSetting("TomJK_QuickExport", "settings", save_string)

def export_image(image_settings, document=None):
    exportParameters = InfoObject()
    exportParameters.setProperty("alpha", image_settings["alpha"])
    exportParameters.setProperty("compression", int(image_settings["compression"]))
    exportParameters.setProperty("indexed", True)
    
    export_path = image_settings["path"].with_name(image_settings["output"])
    
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
