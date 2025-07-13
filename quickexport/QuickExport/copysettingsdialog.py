from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QDialog, QLabel, QRadioButton, QDialogButtonBox, QApplication, QStyle
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QPixmap
from pathlib import Path
from enum import IntEnum, auto
from krita import *

app = Krita.instance()

class CopySettingsDialogResult(IntEnum):
    NONE = 0
    NEW = auto()
    COPY = auto()
    REPLACE = auto()

class CopySettingsDialog(QDialog):
    def __init__(self, items, item_msgs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        style = QApplication.style()
        icon = style.standardIcon(QStyle.SP_MessageBoxQuestion)
        
        self.selected_item_index = -1
        self.result = CopySettingsDialogResult.NONE
        self.item_msgs = item_msgs

        self.setWindowTitle(f"Copy Quick Export Settings")

        layout = QVBoxLayout()

        body = QWidget()
        body_layout = QHBoxLayout()

        iconSize = style.pixelMetric(QStyle.PM_MessageBoxIconSize)
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(QSize(iconSize, iconSize)))
        icon_label.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        body_layout.addWidget(icon_label)

        main = QWidget()
        main_layout = QVBoxLayout()

        info = QWidget()
        info_layout = QHBoxLayout()
        info_label = QLabel("You can copy or replace export settings from a previous version of this file.")
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        info.setLayout(info_layout)
        main_layout.addWidget(info)

        files = QWidget()
        files_layout = QVBoxLayout()
        for index,t in enumerate(items):
            rb = QRadioButton(t)
            rb.clicked.connect(lambda checked, i=index: self._on_file_button_clicked(checked, i))
            files_layout.addWidget(rb)
        files.setLayout(files_layout)
        main_layout.addWidget(files)
        
        msg = QWidget()
        msg_layout = QHBoxLayout()
        self.msg_label = QLabel("Select a file.")
        msg_layout.addWidget(self.msg_label)
        msg.setLayout(msg_layout)
        main_layout.addWidget(msg)

        main.setLayout(main_layout)
        body_layout.addWidget(main)

        body.setLayout(body_layout)
        layout.addWidget(body)

        self.dialog_buttons = QDialogButtonBox()
        self.dialog_buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.dialog_buttons.addButton("New...", QDialogButtonBox.HelpRole)
        self.dialog_buttons.addButton("Copy", QDialogButtonBox.YesRole)
        self.dialog_buttons.addButton("Replace", QDialogButtonBox.AcceptRole)
        self.dialog_buttons.clicked.connect(self._on_dialog_button_clicked)
        layout.addWidget(self.dialog_buttons)

        self.setLayout(layout)
        
        files_layout.itemAt(0).widget().click()

    def _on_file_button_clicked(self, checked, index):
        self.selected_item_index = index
        self.msg_label.setText(self.item_msgs[index])
    
    def _on_dialog_button_clicked(self, button):
        role = self.dialog_buttons.buttonRole(button)
        if role == QDialogButtonBox.RejectRole:
            self.done(QDialog.Rejected)
        else:
            if role == QDialogButtonBox.HelpRole:
                self.result = CopySettingsDialogResult.NEW
            elif role == QDialogButtonBox.YesRole:
                self.result = CopySettingsDialogResult.COPY
            elif role == QDialogButtonBox.AcceptRole:
                self.result = CopySettingsDialogResult.REPLACE
            self.done(QDialog.Accepted)
