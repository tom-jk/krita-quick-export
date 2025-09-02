from PyQt5.QtWidgets import QWidget, QPushButton
from krita import *
from timeit import default_timer
app = Krita.instance()


class MultiLineElidedText(QWidget):
    def __init__(self, text, margin=0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = text
        self._margin = margin
        self._max_lines = 4
        self._total_height = 0
        self._invalidated = True
        self._wrapped_text_words = []
        self._old_size = QSize()
    
    def setText(self, text):
        if self._text == text:
            return
        self._text = text
        self._invalidated = True
    
    def setMaxLines(self, max_lines):
        if self._max_lines == max_lines:
            return
        self._max_lines = max_lines
        self._invalidated = True
    
    def resizeEvent(self, event):
        if event.size().width() != self._old_size.width():
            self._invalidated = True
        self._old_size = event.size()
    
    def sizeHint(self):
        w = self.width()
        return QSize(w, self.heightForWidth(w))
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, w):
        if self._old_size.width() != w:
            self._invalidated = True
        fm = QFontMetrics(self.parentWidget().font())
        self.multi_line_elided_text(fm, self._text, w, self._max_lines)
        #print(f"heightForWidth: {w=} h={self._total_height}")
        return self._total_height + self._margin*2
    
    def paintEvent(self, event):
        super().paintEvent(event)
        r = self.geometry().translated(-self.visibleRegion().boundingRect().topLeft())
        
        parent = self.parentWidget()
        
        painter = QPainter(self)
        
        if False:
            o = painter.opacity()
            painter.setOpacity(0.1)
            painter.drawLine(0, 0, 0, r.height())
            painter.drawLine(r.width()-1, 0, r.width()-1, r.height())
            painter.drawLine(0, 0, r.width()-1, 0)
            painter.drawLine(0, r.height()-1, r.width()-1, r.height()-1)
            painter.setOpacity(o)
        
        fm = QFontMetrics(parent.font())
        self.multi_line_elided_text(fm, self._text, r.width(), self._max_lines)
        
        if len(self._wrapped_text_words) == 0:
            return
        
        x_pos = self._margin
        y_kludge = 2
        y_pos = self._margin + ((r.height()-self._margin*2) // 2) - (self._total_height // 2) - y_kludge
        for word in self._wrapped_text_words:
            x = word[0]
            y = word[1]
            #w = word[2]
            t = word[3]
            painter.drawText(x_pos+x, y_pos+y, t)
    
    def multi_line_elided_text(self, fm, text, width, max_lines):
        if not self._invalidated:
            return
        
        self._total_height = self._flow(fm, text, width - self._margin*2, max_lines)
        self.align_text(fm, width - self._margin*2)
        self._invalidated = False
            
    def _flow(self, fm, text, width, max_lines):
    
        h = fm.height()
        #lineSpacing = fm.lineSpacing()
        
        if text == "":
            self._wrapped_text_words = []
            self.setToolTip("")
            return h + fm.descent()
    
        if max_lines < 1:
            self._wrapped_text_words = []
            self.setToolTip("")
            return h + fm.descent()
    
        if max_lines == 1:
            # single line elide.
            wrapped_text = fm.elidedText(text, Qt.ElideMiddle, width)
            self._wrapped_text_words = [[0, h, fm.horizontalAdvance(wrapped_text), wrapped_text]]
            self.setToolTip(text if text != wrapped_text else "")
            return h + fm.descent()
    
        if False:#width <= max(2, fm.horizontalAdvance("M")):
            wrapped_text = []
            wrapped_text.append([width//2 - fm.horizontalAdvance("…")//2, (max_lines//2+1)*h, fm.horizontalAdvance("…"), "…"])
            self._wrapped_text_words = wrapped_text
            return h*max_lines + fm.descent()
    
        elide_at_line = (max_lines // 2) + 1
        elide_at_line_from_end = max_lines - elide_at_line + 1
    
        ellipsis = "… …"
        ellipsis_w = fm.horizontalAdvance(ellipsis)
        ellipsis_hw = ellipsis_w // 2
        ellipsis_sx = width // 2 - ellipsis_hw
        ellipsis_ex = width // 2 + ellipsis_hw
    
        # test height of text, draw if fits.
        wrapped_text = self.wrapped_text(fm, text, width, soft_max_lines=max_lines+1)
        if wrapped_text[-1][1] // h <= max_lines:
            self._wrapped_text_words = wrapped_text
            self.setToolTip("")
            return self._wrapped_text_words[-1][1] + fm.descent()
    
        # text taller than maxlines, perform multi-line elide.
        self.setToolTip(text)
    
        start_time = default_timer()
    
        wrapped_text = self.wrapped_text(fm, text, width, soft_max_lines=elide_at_line+1, elide_at_line=elide_at_line, elide_at_x=ellipsis_sx)
    
        wrapped_text = [
            v
            for v in wrapped_text
            if v[1]//h < (max_lines if max_lines>2 else 3) and (v[1]//h < elide_at_line or (v[1]//h == elide_at_line and v[0] < ellipsis_sx))
        ]
        # truncate end of last word before ellipsis.
        if len(wrapped_text) > 0:
            last_word_idx = len(wrapped_text) - 1
            last_word = wrapped_text[-1]
            if last_word[1]//h == elide_at_line and last_word[0] < ellipsis_sx:
                while ((numloops1:=locals().get('numloops1',-1)+1) < 9999) and last_word[0] + last_word[2] > ellipsis_sx and len(last_word[3]) > 0:
                    last_word[3] = last_word[3][:-1]
                    last_word[2] = fm.horizontalAdvance(last_word[3])
                if numloops1 == 9999: print("truncate last word overran")
                if last_word[3] == "":
                    wrapped_text.pop(last_word_idx)
                    last_word_idx -= 1
                    last_word = wrapped_text[last_word_idx]
        wrapped_text_b = self.wrapped_text(fm, text, width, direction=-1, soft_max_lines=elide_at_line_from_end+1, elide_at_line=elide_at_line_from_end, elide_at_x=ellipsis_ex)
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
                if numloops2 == 9999: print("truncate first word overran")
                if first_word[3] == "":
                    wrapped_text_b.pop(0)
                    first_word = wrapped_text_b[0] if len(wrapped_text_b) > 0 else None
            wrapped_text.extend(wrapped_text_b)
        
        # if available width is less than that of any single char to be displayed, don't display text.
        if len(wrapped_text)==0 or any(word[2]+1 >= width and len(word[3])==1 for word in wrapped_text):
            wrapped_text = []
            wrapped_text.append([width//2 - fm.horizontalAdvance("…")//2, (max_lines//2+1)*h, fm.horizontalAdvance("…"), "…"])
            self._wrapped_text_words = wrapped_text
            return h*max_lines + fm.descent()
        
        num_lines = wrapped_text[-1][1] // h
        total_height = wrapped_text[-1][1] + fm.descent()
        
        if num_lines > 1:
            if width >= ellipsis_w*2 and first_word != None:
                wrapped_text.insert(last_word_idx+1, [last_word[0]+last_word[2], h*elide_at_line, fm.horizontalAdvance("…"), "…"])
                wrapped_text.insert(last_word_idx+2, [first_word[0]-fm.horizontalAdvance("…"), h*elide_at_line, fm.horizontalAdvance("…"), "…"])
            else:
                wrapped_text.insert(last_word_idx+1, [width//2 - fm.horizontalAdvance("…")//2, h*elide_at_line, fm.horizontalAdvance("…"), "…"])
        
        end_time = default_timer()
        #print(f"multi-line text elide took {1000*(end_time-start_time):.4} ms.")
        
        self._wrapped_text_words = wrapped_text
        return total_height

    def align_text(self, fm, width):
        if len(self._wrapped_text_words) == 0:
            return
        
        h = fm.height()
        
        def print(*args):
            pass
        
        # center-align all text.
        if True:
            print("//// begin text alignment ////")
            print(f"wrapped text has {len(self._wrapped_text_words)} words")
            line_sx = 0
            line_ex = 0
            line_si = 0
            line_ei = 0
            line = 0
            word_idx = 0
            while word_idx < len(self._wrapped_text_words):
                word = self._wrapped_text_words[word_idx]
                print(f"considering word id {word_idx}, text '{word[3]}'")
                if word[1] // h > line:
                    # start of new line.
                    print(f"start of line {word[1]//h} at x={word[0]} with w={word[2]} with word id {word_idx}, text '{word[3]}'")
                    line = word[1] // h
                    line_sx = word[0]
                    line_si = word_idx
                    line_ex = word[0] + word[2]
                    line_ei = word_idx
                    word_idx += 1
                    while word_idx < len(self._wrapped_text_words):
                        word = self._wrapped_text_words[word_idx]
                        print(f" scanning to line end, currently id {word_idx}, text '{word[3]}'")
                        at_end_of_text = False
                        if word[1] // h > line or (at_end_of_text := word_idx + 1 == len(self._wrapped_text_words)):
                            if not at_end_of_text:
                                word_idx -= 1
                                word = self._wrapped_text_words[word_idx]
                            print(f" scan found line end at id {word_idx}, text '{word[3]}'")
                            line_ex = word[0] + word[2]
                            line_ei = word_idx
                            break
                        word_idx += 1
                    line_w = line_ex - line_sx
                    line_disp_x = width//2 - line_w//2 - line_sx
                    for wi in range(line_si, line_ei+1):
                        self._wrapped_text_words[wi][0] += line_disp_x
                word_idx += 1

    def wrapped_text(self, fm, text, width, direction=1, soft_max_lines=9999, elide_at_line=9999, elide_at_x=None):
        if elide_at_x == None:
            elide_at_x = 999999 if direction==1 else -999999
    
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


class MultiLineElidedButton(QToolButton):
    def __init__(self, text, margin=-1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.setAutoRaise(True)
        
        self.layout = QHBoxLayout(self)
        self.text_widget = MultiLineElidedText(text)
        self.layout.addWidget(self.text_widget)
        
        if margin > -1:
            self.layout.setContentsMargins(margin, margin, margin, margin)
        
        self.setLayout(self.layout)
    
    def setText(self, text):
        self.text_widget.setText(text)
    
    def text(self):
        return self.text_widget._text
    
    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance("a"*16),-1)
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, w):
        margins = self.layout.contentsMargins()
        h = self.text_widget.heightForWidth(w - margins.left() - margins.right()) + margins.top() + margins.bottom()
        return h
