from PyQt5.QtWidgets import (QDialog, QFrame, QLayout, QHBoxLayout, QVBoxLayout, QSpinBox, QComboBox,
                             QPushButton, QToolButton, QLabel, QMenu, QAction, QSizePolicy, QStyle,
                             QDoubleSpinBox, QCheckBox)
from PyQt5.QtGui import QMouseEvent, QValidator
from PyQt5.QtCore import Qt, QObject, QEvent, QSize, QRegExp, pyqtSignal, QVariant
from datetime import datetime
from krita import *
app = Krita.instance()

class SpinBox(QSpinBox):
    def __init__(self, range_min=1, range_max=100000000, value=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setRange(range_min, range_max)
        self.setValue(value)
        self._old_value = value
        self._last_value = value
        self._base_value = value
        self.valueChanged.connect(self.onValueChanged)
    
    def setValue(self, value):
        super().setValue(value)
    
    def onValueChanged(self, value):
        self._old_value = self._last_value
        self._last_value = value
    
    def validate(self, value, pos):
        print(f"validate: {value=} {pos=}")
        rx = QRegExp("[0-9]*[%]?$")
        if rx.exactMatch(value):
            if value.endswith("%"):
                if len(value) == 1:
                    return QValidator.Invalid, value, pos
                value = str(round(self._base_value * (float(value[:-1])/100.0)))
                pos = len(value)
            return QValidator.Acceptable, value, pos
        if len(value) == 0:
            return QValidator.Intermediate, value, pos
        return QValidator.Invalid, value, pos

class DoubleSpinBox(QDoubleSpinBox):
    def __init__(self, range_min=1, range_max=100000000, value=1.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_value = value
        self._last_value = value
        self._base_value = value
        self.setRange(range_min, range_max)
        self.setValue(value)
        self.valueChanged.connect(self.onValueChanged)
    
    def setValue(self, value):
        super().setValue(value)
    
    def onValueChanged(self, value):
        self._old_value = self._last_value
        self._last_value = value
    
    def validate(self, value, pos):
        if len(value) == 0:
            #print(f"intermediate: zero chars")
            return QValidator.Intermediate, value, pos
        
        dec_sep = self.locale().decimalPoint()
        regexp_string = f"[0-9]*[{dec_sep}]?[0-9]*[%]?$"
        rx = QRegExp(regexp_string)
        ps = f"validate: {value=} {pos=}, {rx.exactMatch(value)}"
        
        if rx.exactMatch(value):
            if value.endswith("%"):
                if len(value) == 1:
                    print(f"{ps} - invalid: one char, '%'") 
                    return QValidator.Invalid, value, pos
                value = str(round(self._base_value * (float(value[:-1])/100.0)))
                pos = len(value)
            if float(value) > self.maximum():
                value = str(self.maximum())
            print(f"{ps} - acceptable")
            return QValidator.Acceptable, value, pos
        
        print(f"{ps} - invalid")
        return QValidator.Invalid, value, pos

class ConstrainedSpinBoxPair(QWidget):
    valueChanged = pyqtSignal(QVariant, QVariant)
    constrainToggled = pyqtSignal(bool)
    
    def __init__(self, range_min=1, range_max=100000000, label1_text="Spin1:", value1=1, label2_text="Spin2:", value2=1, reset_tooltip="Reset to default values.", floating=False, single_step=1, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.floating = floating

        self.layout = QHBoxLayout()

        frameleft = QWidget()
        frameleft_layout = QVBoxLayout()
        frameleft_layout.setContentsMargins(0,0,0,0)

        frameright = QWidget()
        frameright_layout = QHBoxLayout()
        frameright_layout.setContentsMargins(0,0,0,0)
        frameright_layout.setSpacing(0)

        self.suppress_constraint_update = False
        
        spin1_widget = QWidget()
        spin1_layout = QHBoxLayout()
        spin1_layout.setContentsMargins(0,0,0,0)

        spin1_label = QLabel(label1_text)
        spin1_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin1_layout.addWidget(spin1_label)
        self.spin1_spinbox = DoubleSpinBox(range_min=range_min, range_max=range_max, value=value1) if floating else SpinBox(range_min=range_min, range_max=range_max, value=value1)
        self.spin1_spinbox.setSingleStep(single_step)
        self.spin1_spinbox.valueChanged.connect(self._on_spin1_spinbox_value_changed)
        self.spin1_spinbox.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin1_layout.addWidget(self.spin1_spinbox)

        spin1_widget.setLayout(spin1_layout)

        frameleft_layout.addWidget(spin1_widget)

        spin2_widget = QWidget()
        spin2_layout = QHBoxLayout()
        spin2_layout.setContentsMargins(0,0,0,0)

        spin2_label = QLabel(label2_text)
        spin2_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin2_layout.addWidget(spin2_label)
        self.spin2_spinbox = DoubleSpinBox(range_min=range_min, range_max=range_max, value=value2) if floating else SpinBox(range_min=range_min, range_max=range_max, value=value2)
        self.spin2_spinbox.setSingleStep(single_step)
        self.spin2_spinbox.valueChanged.connect(self._on_spin2_spinbox_value_changed)
        self.spin2_spinbox.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin2_layout.addWidget(self.spin2_spinbox)

        spin2_widget.setLayout(spin2_layout)

        frameleft_layout.addWidget(spin2_widget)

        self.constrain_button = QToolButton()
        self.constrain_button.setCheckable(True)
        self.constrain_button.setChecked(True)
        self.constrain_button.setIcon(app.icon('chain-icon'))
        self.constrain_button.setIconSize(QSize(9, 24))
        self.constrain_button.setFixedSize(19, 34)
        self.constrain_button.setAutoRaise(True)
        self.constrain_button.toggled.connect(self._on_constrain_button_toggled)
        frameright_layout.addWidget(self.constrain_button)

        self.constrain_ratio = self.spin2_spinbox.value() / self.spin1_spinbox.value()
        print(f"{self.constrain_ratio=}")

        # TODO: hide reset button until I get around to verifying it works sensibly.
        self.reset_button = QToolButton()
        self.reset_button.setToolTip("Reset to current image size.")
        self.reset_button.setIcon(app.icon('edit-undo'))
        self.reset_button.setFixedSize(34, 34)
        self.reset_button.setAutoRaise(True)
        #self.reset_button.clicked.connect(self._on_reset_button_clicked)
        #frameright_layout.addWidget(self.reset_button)
        
        frameleft.setLayout(frameleft_layout)
        frameright.setLayout(frameright_layout)

        self.layout.addWidget(frameleft)
        self.layout.addWidget(frameright)
        
        self.setLayout(self.layout)
    
    def _on_spin1_spinbox_value_changed(self, value):
        print("ConstrainedSpinBoxPair:_on_spin1_spinbox_value_changed:", self.spin1_spinbox._old_value, "->", value, self.constrain_ratio)
        if self.constrain_button.isChecked() and not self.suppress_constraint_update:
            self.suppress_constraint_update = True
            fvalue = value * self.constrain_ratio
            self.spin2_spinbox.setValue(fvalue if self.floating else round(fvalue))
            self.suppress_constraint_update = False
        self.valueChanged.emit(value, self.spin2_spinbox.value())

    def _on_spin2_spinbox_value_changed(self, value):
        print("ConstrainedSpinBoxPair:_on_spin2_spinbox_value_changed:", self.spin2_spinbox._old_value, "->", value, self.constrain_ratio)
        if self.constrain_button.isChecked() and not self.suppress_constraint_update:
            self.suppress_constraint_update = True
            fvalue = value / self.constrain_ratio
            self.spin1_spinbox.setValue(fvalue if self.floating else round(fvalue))
            self.suppress_constraint_update = False
        self.valueChanged.emit(self.spin1_spinbox.value(), value)

    def _on_constrain_button_toggled(self, checked):
        self.constrain_button.setIcon(app.icon('chain-icon') if checked else app.icon('chain-broken-icon'))
        if checked:
            self.constrain_ratio = self.spin2_spinbox.value() / self.spin1_spinbox.value()
        self.constrainToggled.emit(checked)

    def _on_reset_button_clicked(self, checked):
        constrain_checked = self.constrain_button.isChecked()
        self.constrain_button.setChecked(False)
        self.spin1_spinbox.setValue(self.spin1_spinbox._base_value)
        self.spin2_spinbox.setValue(self.spin2_spinbox._base_value)
        self.constrain_button.setChecked(constrain_checked)

class ScaleDialog(QDialog):
    def __init__(self, doc, width, height, filter_, res, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.doc = doc
        
        self.result_accepted = False
        self.result_width = width
        self.result_height = height
        self.result_filter = filter_
        self.result_res = res

        self.suppress_constraint_update = False

        #self.setStyleSheet("border:1px solid")
        dialog_layout = QVBoxLayout()
        dialog_layout.setSizeConstraint(QLayout.SetFixedSize)

        label = QLabel("Pixel Dimensions")
        dialog_layout.addWidget(label)

        frame = QFrame()
        frame.setFrameStyle(QFrame.Box | QFrame.Sunken)
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(0,0,0,0)
        frame_layout.setSpacing(0)

        fsize = QWidget()
        fsize_layout = QHBoxLayout()

        # TODO: reset is supposed to reset to image size, but instead resets to whatever the value was when the dialog started.
        self.pixel_size_widget = ConstrainedSpinBoxPair(label1_text="Width:", value1=width, label2_text="Height", value2=height, reset_tooltip="Reset to image size.")
        self.print_size_widget = ConstrainedSpinBoxPair(label1_text="Width:", value1=width/res, label2_text="Height", value2=height/res, reset_tooltip="Reset to image size.", floating=True, single_step=0.01, range_min=0.01)

        self.pixel_size_widget.valueChanged.connect(self._on_pixel_size_widget_value_changed)
        self.print_size_widget.valueChanged.connect(self._on_print_size_widget_value_changed)
        
        self.pixel_size_widget.constrainToggled.connect(self._on_pixel_size_widget_constrain_toggled)
        self.print_size_widget.constrainToggled.connect(self._on_print_size_widget_constrain_toggled)

        filterframe = QFrame()
        filterframe_layout = QHBoxLayout()
        style = filterframe.style()
        lm = style.pixelMetric(QStyle.PM_LayoutLeftMargin)
        rm = style.pixelMetric(QStyle.PM_LayoutRightMargin)
        bm = style.pixelMetric(QStyle.PM_LayoutBottomMargin)
        filterframe_layout.setContentsMargins(lm, 0, rm, bm)

        filter_widget = QWidget()
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0,0,0,0)

        filter_label = QLabel("Filter:")
        filter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_layout.addWidget(filter_label)
        self.filter_combobox = QComboBox()
        self.filter_combobox.addItem("Auto")
        for fs in app.filterStrategies():
            self.filter_combobox.addItem(fs)
        self.filter_combobox.setCurrentText(filter_)
        filter_layout.addWidget(self.filter_combobox)

        filter_widget.setLayout(filter_layout)

        filterframe_layout.addWidget(filter_widget)
        filterframe_layout.addStretch()
        filterframe.setLayout(filterframe_layout)
        
        fsize_layout.addWidget(self.pixel_size_widget)

        fsize.setLayout(fsize_layout)

        frame_layout.addWidget(fsize)

        frame_layout.addWidget(filterframe)

        frame.setLayout(frame_layout)

        dialog_layout.addWidget(frame)
        
        dialog_layout.addWidget(QLabel("Print Dimensions (Inches)"))
        
        fpsize = QFrame()
        fpsize.setFrameStyle(QFrame.Box | QFrame.Sunken)
        fpsize_layout = QVBoxLayout()
        fpsize_layout.setContentsMargins(0,0,0,0)
        fpsize_layout.setSpacing(0)
        
        fpsize_layout.addWidget(self.print_size_widget)
        
        resframe = QFrame()
        resframe_layout = QHBoxLayout()
        style = resframe.style()
        lm = style.pixelMetric(QStyle.PM_LayoutLeftMargin)
        rm = style.pixelMetric(QStyle.PM_LayoutRightMargin)
        bm = style.pixelMetric(QStyle.PM_LayoutBottomMargin)
        resframe_layout.setContentsMargins(lm, 0, rm, bm)

        res_widget = QWidget()
        res_layout = QHBoxLayout()
        res_layout.setContentsMargins(0,0,0,0)

        res_label = QLabel("Resolution:")
        res_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        res_layout.addWidget(res_label)
        self.res_spinbox = DoubleSpinBox(range_min=0.01, range_max=10000, value=res)
        self.res_spinbox.setSingleStep(0.01)
        self.res_spinbox.valueChanged.connect(self._on_print_res_spinbox_value_changed)
        res_layout.addWidget(self.res_spinbox)
        res_units_label = QLabel("Pixels/Inch")
        res_layout.addWidget(res_units_label)

        res_widget.setLayout(res_layout)

        resframe_layout.addWidget(res_widget)
        resframe_layout.addStretch()
        resframe.setLayout(resframe_layout)
        
        fpsize_layout.addWidget(resframe)
        
        fpsize.setLayout(fpsize_layout)
        dialog_layout.addWidget(fpsize)

        self.adjust_print_separately_checkbox = QCheckBox("Adjust print size separately")
        self.adjust_print_separately_checkbox.toggled.connect(self._on_adjust_print_separately_checkbox_toggled)
        dialog_layout.addWidget(self.adjust_print_separately_checkbox)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        dialog_layout.addWidget(self.warning_label)
        self._on_size_changed()

        dbbox = QDialogButtonBox()
        dbbox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dbbox.accepted.connect(self._on_dialog_accepted)
        dbbox.rejected.connect(self._on_dialog_rejected)
        dialog_layout.addWidget(dbbox)

        self.setLayout(dialog_layout)

    def _on_pixel_size_widget_value_changed(self, value1, value2):
        if self.suppress_constraint_update:
            print("(_on_pixel_size_widget_value_changed - suppressed)")
            return
        print("_on_pixel_size_widget_value_changed:", value1, value2, "will set print size", value1 / self.res_spinbox.value(), value2 / self.res_spinbox.value())
        
        print_size_constrained = self.print_size_widget.constrain_button.isChecked()
        
        if self.adjust_print_separately_checkbox.isChecked():
            self.print_size_widget.constrain_button.setChecked(self.pixel_size_widget.constrain_button.isChecked())
        
        self.suppress_constraint_update = True
        self.print_size_widget.spin1_spinbox.setValue(value1 / self.res_spinbox.value())
        self.print_size_widget.spin2_spinbox.setValue(value2 / self.res_spinbox.value())
        self.suppress_constraint_update = False
        
        if self.adjust_print_separately_checkbox.isChecked():
            self.print_size_widget.constrain_button.setChecked(print_size_constrained)
        
        self._on_size_changed()

    def _on_print_size_widget_value_changed(self, value1, value2):
        if self.suppress_constraint_update:
            print("(_on_print_size_widget_value_changed - suppressed)")
            return
        print("_on_print_size_widget_value_changed:", value1, value2, "will set pixel size", round(value1 * self.res_spinbox.value()), round(value2 * self.res_spinbox.value()))
        
        if self.adjust_print_separately_checkbox.isChecked():
            self.suppress_constraint_update = True
            self.res_spinbox.setValue(self.pixel_size_widget.spin1_spinbox.value() / value1)
            self.suppress_constraint_update = False
            return
        
        self.suppress_constraint_update = True
        self.pixel_size_widget.spin1_spinbox.setValue(round(value1 * self.res_spinbox.value()))
        self.pixel_size_widget.spin2_spinbox.setValue(round(value2 * self.res_spinbox.value()))
        self.suppress_constraint_update = False
        
        self._on_size_changed()

    def _on_print_res_spinbox_value_changed(self, value):
        if self.suppress_constraint_update:
            print("(_on_print_res_spinbox_value_changed - suppressed)")
            return
        self.suppress_constraint_update = True
        
        if self.adjust_print_separately_checkbox.isChecked():
            print("_on_print_res_spinbox_value_changed:", value, "will set print size", self.pixel_size_widget.spin1_spinbox.value() / value, self.pixel_size_widget.spin2_spinbox.value() / value)
            self.print_size_widget.spin1_spinbox.setValue(self.pixel_size_widget.spin1_spinbox.value() / value)
            self.print_size_widget.spin2_spinbox.setValue(self.pixel_size_widget.spin2_spinbox.value() / value)
        else:
            print("_on_print_res_spinbox_value_changed:", value, "will set pixel size", round(self.print_size_widget.spin1_spinbox.value() * value), round(self.print_size_widget.spin2_spinbox.value() * value))
            self.pixel_size_widget.spin1_spinbox.setValue(round(self.print_size_widget.spin1_spinbox.value() * value))
            self.pixel_size_widget.spin2_spinbox.setValue(round(self.print_size_widget.spin2_spinbox.value() * value))
        
        self.suppress_constraint_update = False
        
        self._on_size_changed()

    def _on_adjust_print_separately_checkbox_toggled(self, checked):
        if checked:
            self.print_size_widget.constrain_button.setChecked(True)
            self.print_size_widget.constrain_button.setDisabled(True)
        else:
            self.print_size_widget.constrain_button.setChecked(self.pixel_size_widget.constrain_button.isChecked())
            self.print_size_widget.constrain_button.setDisabled(False)

    def _on_pixel_size_widget_constrain_toggled(self, checked):
        if self.adjust_print_separately_checkbox.isChecked():
            return
        
        self.print_size_widget.constrain_button.setChecked(checked)
    
    def _on_print_size_widget_constrain_toggled(self, checked):
        if self.adjust_print_separately_checkbox.isChecked():
            return
        
        self.pixel_size_widget.constrain_button.setChecked(checked)

    def _on_size_changed(self):
        # TODO: this is not necessarily peak memory usage. It may be the flattened document after scaling
        #       (which is what's calculated here), or it could be the full document clone pre-flattening.
        #       I don't think the python api provides a way to get a document's current memory usage, so
        #       might have to make an estimate.
        dims = self.pixel_size_widget.spin1_spinbox.value() * self.pixel_size_widget.spin2_spinbox.value()
        depth_s = self.doc.colorDepth()
        depth = 8 if depth_s == "U8" else 16 if depth_s in ("U16", "F16") else 32 if depth_s == "F32" else 0
        if depth == 0:
            self.warning_label.setText("Unrecognised image depth string.")
            return
        size = dims * depth
        size_s = (f"{size} bytes" if size < 2**10 else
                  f"{size/(2**10):.2f} kb" if size < 2**20 else
                  f"{size/(2**20):.2f} mb" if size < 2**30 else
                  f"{size/(2**30):.2f} gb"
        )
        self.warning_label.setText(f"On export, a copy of the document will be flattened, scaled, exported then removed."
                              f"<br/><br/>Memory usage after scaling: ~<b>{size_s}</b>."
                              f"<br/><br/>Please ensure that you have sufficient memory available at export time; enough for the copied document before flattening, or after flattening and scaling, whichever is greater."
        )

    def _on_dialog_accepted(self):
        self.result_accepted = True
        self.result_width = self.pixel_size_widget.spin1_spinbox.value()
        self.result_height = self.pixel_size_widget.spin2_spinbox.value()
        self.result_filter = self.filter_combobox.currentText()
        self.result_res = self.result_width / self.print_size_widget.spin1_spinbox.value()
        print(f"OK with pixel size {self.result_width} x {self.result_height}, filter {self.result_filter}, print res {self.result_res}.")
        self.accept()

    def _on_dialog_rejected(self):
        print("CANCEL")
        self.reject()
