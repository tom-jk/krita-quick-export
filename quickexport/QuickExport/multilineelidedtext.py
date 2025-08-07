from PyQt5.QtWidgets import QDialog
from krita import *
from timeit import default_timer
app = Krita.instance()

#        0         10        20        30        40
#        01234567890123456789012345678901234567890123456789
text = ("Lorem_ipsum_dolor sit amet, consectetur adipiscing" #0-49
        "elit, sed do eiusmod tempor incididunt ut labore e" #50-99
        "t dolore magna aliqua. Ut enim ad minim veniam, qu" #100-149
        "is nostrud exercitation excuse me but abcdefghijkl" #150-199
        "mnopqrstuvwxyz thanks for listening. ullamco labor" #200-249
        "is nisi ut aliquip ex ea commodo consequat. Duis a" #250-299
        "ute irure dolor in reprehenderit in voluptate veli" #300-349
        "t esse cillum dolore eu fugiat nulla pariatur. Exc" #350-399
        "epteur sint occaecat cupidatat non proident, sunt " #400-449
        "in culpa qui officia deserunt mollit anim id est l" #450-499
        "aborum.")                                           #500-506

doc = app.activeDocument()
if doc.fileName() != "":
    text = doc.fileName()

#text =  "abcdefghijklmnopqrstuvwxyz"

#text = text * 10

'abcdefghijklmnopqrstuvwxyz '
#012345678901234567890123456
#0         10        20

'consectetur '
#012345678901

class Dialog(QDialog):
    def paintEvent(self, event):
        super().paintEvent(event)
        r = event.rect()
        
        if text == "":
            return
        
        painter = QPainter(self)
        fm = QFontMetrics(self.font())
        h = fm.height()
        
        # max_lines = 1, perform single line elide.
        # max_lines = 2, elide on line 2,      elide post-ellipsis text on line 1 st from bottom
        # max_lines = 3, elide on line 2,      elide post-ellipsis text on line 2 nd from bottom
        # max_lines = 4, elide on line 3,      elide post-ellipsis text on line 2 nd from bottom
        # max_lines = 5, elide on line 3,      elide post-ellipsis text on line 3 rd from bottom
        # max_lines = 6, elide on line 4,      elide post-ellipsis text on line 3 rd from bottom
        # max_lines = 7, elide on line 4,      elide post-ellipsis text on line 4 th from bottom
        # max_lines = n, elide on line n//2+1, elide post-ellipsis text on line n - (n//2+1) + 1 from bottom
        max_lines = 3
        elide_at_line = (max_lines // 2) + 1
        elide_at_line_from_end = max_lines - elide_at_line + 1
        
        gw = 32
        
        ellipsis = "… …"
        ellipsis_w = fm.horizontalAdvance(ellipsis)
        ellipsis_hw = ellipsis_w // 2
        ellipsis_sx = (r.width()-gw*2) // 2 - ellipsis_hw
        ellipsis_ex = (r.width()-gw*2) // 2 + ellipsis_hw
        
        #pen = painter.pen()
        #pen.setColor(QColor(255,255,255,64))
        #painter.setPen(pen)
        o = painter.opacity()
        painter.setOpacity(0.1)
        painter.drawLine(gw, 0, gw, r.height())
        painter.drawLine(r.width()-gw, 0, r.width()-gw, r.height())
        painter.setOpacity(o)
        
        if r.width() - gw*2 <= max(2, fm.horizontalAdvance("M")):
            for y in range(1, max_lines+1):
                painter.drawText(gw + (r.width()-gw*2)//2 - fm.horizontalAdvance("…")//2, y * h, "…")
            return
        
        if max_lines < 1:
            return
        
        if max_lines == 1:
            # single line elide.
            painter.drawText(gw, h, fm.elidedText(text, Qt.ElideMiddle, r.width()-gw*2))
            return
        
        # test height of text, draw if fits.
        wrapped_text = self.wrapped_text(r.width()-gw*2, soft_max_lines=max_lines+1)
        if wrapped_text[-1][1] // h <= max_lines:
            self.draw_words(gw, 0, 1, wrapped_text, ellipsis, ellipsis_w, ellipsis_hw, ellipsis_sx, ellipsis_ex, r, painter, fm, h)
            return
        
        # text taller than maxlines, perform multi-line elide.
        
        start_time = default_timer()
        
        wrapped_text = self.wrapped_text(r.width()-gw*2, soft_max_lines=elide_at_line+1, elide_at_line=elide_at_line, elide_at_x=ellipsis_sx)
        #self.draw_words(gw, 0, 1, wrapped_text, ellipsis, ellipsis_w, ellipsis_hw, ellipsis_sx, ellipsis_ex, r, painter, fm, h)
        
        wrapped_text = [
            v
            for v in wrapped_text
            if v[1]//h < (max_lines if max_lines>2 else 3) and (v[1]//h < elide_at_line or (v[1]//h == elide_at_line and v[0] < ellipsis_sx))
        ]
        # truncate end of last word before ellipsis.
        if len(wrapped_text) > 0:
            last_word = wrapped_text[-1]
            if last_word[1]//h == elide_at_line and last_word[0] < ellipsis_sx:
                while ((numloops1:=locals().get('numloops1',-1)+1) < 9999) and last_word[0] + last_word[2] > ellipsis_sx and len(last_word[3]) > 0:
                    last_word[3] = last_word[3][:-1]
                    last_word[2] = fm.horizontalAdvance(last_word[3])
                if numloops1 == 100: print("truncate last word overran")
        #wrapped_text.append([wrapped_text[-1][0]+wrapped_text[-1][2], 2*h, ellipsis_w, ellipsis])
        wrapped_text_b = self.wrapped_text(r.width()-gw*2, direction=-1, soft_max_lines=elide_at_line_from_end+1, elide_at_line=elide_at_line_from_end, elide_at_x=ellipsis_ex)
        wrapped_text_b = [
            [v[0],-v[1]+h+((max_lines)*h),v[2],v[3]]
            for v in reversed(wrapped_text_b)
            if v[1]//h < max_lines and (v[1]//h < elide_at_line_from_end or (v[1]//h == elide_at_line_from_end and v[0]+v[2] > ellipsis_ex))
        ]
        # truncate start of first word after ellipsis.
        if len(wrapped_text_b) > 0:
            first_word = wrapped_text_b[0]
            first_word_ex = first_word[0] + first_word[2]
            #print(first_word, first_word_ex, ellipsis_ex, first_word[1]//h, elide_at_line)
            if first_word[1]//h == elide_at_line and first_word_ex > ellipsis_ex:
                while ((numloops2:=locals().get('numloops2',-1)+1) < 9999) and first_word[0] < ellipsis_ex and len(first_word[3]) > 0:
                    first_word[3] = first_word[3][1:]
                    first_word[2] = fm.horizontalAdvance(first_word[3])
                    first_word[0] = first_word_ex - first_word[2]
                if numloops2 == 100: print("truncate first word overran")
            # left-justify post-ellipsis text.
            if True:
                line_x = 0
                word_idx = 0
                word = wrapped_text_b[word_idx]
                line = word[1] // h
                while ((numloops3:=locals().get('numloops3',-1)+1) < 9999) and line == elide_at_line:
                    word_idx += 1
                    word = wrapped_text_b[word_idx]
                    line = word[1] // h
                if numloops3 == 100: print("loop3 overran")
                line_x = word[0]
                while ((numloops4:=locals().get('numloops4',-1)+1) < 9999) and word_idx < len(wrapped_text_b):
                    word = wrapped_text_b[word_idx]
                    if word[1] // h > line:
                        line = word[1] // h
                        line_x = word[0]
                    word[0] -= line_x
                    word_idx += 1
                if numloops4 == 100: print("loop4 overran")
            wrapped_text.extend(wrapped_text_b)
        
        if r.width()-gw*2 >= ellipsis_w*2:
            painter.drawText(gw + last_word[0]+last_word[2], h*elide_at_line, "…")
            painter.drawText(gw + first_word[0]-fm.horizontalAdvance("…"), h*elide_at_line, "…")
        else:
            painter.drawText(gw + (r.width()-gw*2)//2 - fm.horizontalAdvance("…")//2, h * elide_at_line, "…")
        self.draw_words(gw, 0, 1, wrapped_text, ellipsis, ellipsis_w, ellipsis_hw, ellipsis_sx, ellipsis_ex, r, painter, fm, h)
        
        end_time = default_timer()
        print(f"multi-line text elide took {1000*(end_time-start_time):.4} ms.")
        
        
    def draw_words(self, x_pos, y_pos, y_dir, wrapped_text, ellipsis, ellipsis_w, ellipsis_hw, ellipsis_sx, ellipsis_ex, r, painter, fm, h):
        line_count = wrapped_text[-1][1]//h
        #print(f"{line_count=}")
        word_idx = 0
        y_offset = 0
        while word_idx < len(wrapped_text):
            word = wrapped_text[word_idx]
            x = word[0]
            y = word[1]
            w = word[2]
            t = word[3]
            
            line = y // h
            if False:#line_count > 3:
                if line == 2:
                    if x+w >= ellipsis_sx:
                        # truncate current word to fit on left side of ellipsis.
                        numloops=0
                        while x+w >= ellipsis_sx:
                            t = t[:-1]
                            w = fm.horizontalAdvance(t)
                            numloops += 1
                            if numloops > 128:
                                print("too many loops 1")
                                return
                        painter.drawText(x_pos+x,y_pos+y-y_offset if y_dir==1 else y_pos-y+y_offset, t)
                        x_offset = x
                        y_offset = -y
                        while True:
                            word_idx += 1
                            if word_idx >= len(wrapped_text):
                                print(f"something's gone awry, {word_idx=} at line={y//h} of {line_count=}")
                                break
                            word = wrapped_text[word_idx]
                            x = word[0]
                            y = word[1]
                            w = word[2]
                            line = y // h
                            #print(f"check for {word_idx=} {x=} {y=} {w=}")
                            if line == line_count-1:
                                if x+w >= ellipsis_ex:
                                    break
                        t = word[3]
                        ex = x+w
                        # truncate current word to fit on right side of ellipsis.
                        numloops=0
                        while x < ellipsis_ex:
                            t = t[1:]
                            w = fm.horizontalAdvance(t)
                            x = ex - w
                            numloops += 1
                            if numloops > 128:
                                print("too many loops 2")
                                return
                        y_offset += y
                        painter.drawText(x_pos+ellipsis_sx,y_pos+y-y_offset if y_dir==1 else y_pos-y+y_offset,ellipsis)
            painter.drawText(x_pos+x, y_pos+y-y_offset if y_dir==1 else y_pos-y+y_offset, t)
            
            word_idx += 1
    
    def wrapped_text(self, width, direction=1, soft_max_lines=9999, elide_at_line=9999, elide_at_x=None):
        if elide_at_x == None:
            elide_at_x = 999999 if direction==1 else -999999
        
        fm = QFontMetrics(self.font())
        h = fm.height()
        
        def print(*args):
            pass
        
        words = []
        
        break_s = 0 if direction==1 else len(text)-1
        break_e = 0 if direction==1 else len(text)-1
        te = 0 if direction==1 else len(text)-1
        sx = 0 if direction==1 else width-1
        #x = 0
        y = h
        num_loops = 0
        print(f"- FLOW {len(text)} CHARS OF TEXT {'FORWARDS' if direction==1 else 'BACKWARDS'} INTO RECTANGLE with WIDTH = {width} -")
        while (direction==1 and te < len(text)) or (direction==-1 and te >= 0):
            if text[te] in (" ", ".NO", ",NO", "/", ":NO", ";NO","_") or (direction==1 and te == len(text)-1) or (direction==-1 and te == 0):
                break_s = break_e
                break_e = max(-1, te + direction)
            else:
                te = max(-1, te + direction)
                continue
            t = text[break_s:break_e] if direction==1 else text[break_e+1:break_s+1]
            tw = fm.horizontalAdvance(t)
            print(f"TOP: consider {break_s=} {break_e=} {tw=} {t=}")
            if y // 2 == elide_at_line:
                pass#width = elide_at_x
            if (direction==1 and y // 2 > elide_at_line) or (direction==-1 and y // 2 < elide_at_line):
                pass#break
            if (direction==1 and sx + tw < width) or (direction==-1 and sx - tw >= 0):
                # fit word onto end of current line.
                print(f"M-1: draw: {break_s=} {break_e=} {tw=} {sx=} {y=} {te=} {t=}")
                #painter.drawText(sx,y,t)
                words.append([sx,y,tw,t] if direction==1 else [sx-tw,y,tw,t])
                te += direction
                break_s = break_e
                #break_e = te
                sx += tw * direction
                print(f"M-1: end:  {break_s=} {break_e=} {tw=} {sx=} {y=} {te=} {t=}")
            elif (direction==1 and sx > width/2 and tw < width) or (direction==-1 and sx < width/2 and tw < width):
                # put word at start of next line.
                # UNLESS would leave half or more of the current line blank.
                print(f"M-2: draw: {break_s=} {break_e=} {tw=} {sx=} {y=} {te=} {t=}")
                y += h
                #painter.drawText(0,y,t)
                words.append([0,y,tw,t] if direction==1 else [width-1-tw,y,tw,t])
                te += direction
                break_s = break_e
                sx = tw if direction==1 else width-1-tw
                print(f"M-2: end:  {break_s=} {break_e=} {tw=} {sx=} {y=} {te=} {t=}")
            else:
                # word too long to fit wholly on one line, break over multiple.
                t_s = 0 if direction==1 else len(t)-1
                t_e = t_s-1 if direction==1 else t_s+1
                if (direction==1 and sx + fm.horizontalAdvance(t[0]) > width) or (direction==-1 and sx - fm.horizontalAdvance(t[-1]) < -1):
                    y += h
                    sx = 0 if direction==1 else width-1
                for i in range(0, 256):#, len(t)):
                    t_e += direction
                    print(f"M-3: consider {t_s=} {t_e=}, t[substring]='{t[t_s:t_e+1] if direction==1 else t[max(0,t_e):t_s+1]}'")
                    tnextw = fm.horizontalAdvance(t[t_s:t_e+1] if direction==1 else t[max(0,t_e):t_s+1])
                    if (direction==1 and sx + tnextw < width and t_e < len(t)) or (direction==-1 and sx - tnextw >= 0 and t_e >= 0):
                        tw = tnextw
                        continue
                    tsubnext = t[t_s:t_e] if direction==1 else t[t_e+1:t_s+1]
                    if tsubnext == "":
                        y += h
                        #tnextw = fm.horizontalAdvance(t[t_s+1:t_e+1] if direction==1 else t[t_e:t_s]
                        tw = tnextw
                        sx = 0 if direction==1 else width-1
                        continue
                    if (direction==1 and t_e == len(t)) or (direction==-1 and t_e < 0):
                        tw = tnextw
                    print(f"M-3: draw: {t_s=} {t_e=} {tw=} {sx=} {y=} t[substring]='{tsubnext}'")
                    #painter.drawText(sx,y,t[t_s:t_e])
                    words.append([sx,y,tw,tsubnext] if direction==1 else [sx-tw,y,tw,tsubnext])
                    if (direction==1 and t_e == len(t)) or (direction==-1 and t_e < 0):
                        break
                    sx = 0 if direction==1 else width-1
                    y += h
                    t_s = t_e# if direction==1 else 
                    #t_e -= 1
                #te -= 1
                if i == 255:
                    print("M-3: INNER BAILED")
                break_e = te + direction
                break_s = break_e
                sx = tw if direction==1 else width-1-tw
                print(f"M-3: end:  {i=} {t_s=} {t_e=} {break_s=} {break_e=} {sx=} {te=} {len(t)=} {t=}")
            if (direction==1 and te == len(text)) or (direction==-1 and te <= 0):
                break
            if y // h > soft_max_lines:
                break
            num_loops += 1
            if num_loops > 512:
                print("BAILED")
                break
        return words

dialog = Dialog(app.activeWindow().qwindow())
dialog.resize(176+64,670)
#dialog.resize(36+64,670)
#dialog.resize(18+64,670)

dialog.show()
