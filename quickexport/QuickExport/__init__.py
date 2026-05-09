#
#  SPDX-License-Identifier: GPL-3.0-or-later
#

import logging
import logging.handlers

class CustomFormatter(logging.Formatter):
    def format(self, record):
        try:
            record.levelname = ("Dbg ","Info","Warn","ERR ","CRIT")[("DEBUG","INFO","WARNING","ERROR","CRITICAL").index(record.levelname)]
        except ValueError:
            record.levelname = record.levelname[0:4].ljust(4, " ")
        result = super().format(record)
        return result

logLevelStream = logging.WARNING

logger = logging.getLogger("tomjk_quickexport")

if not logger.hasHandlers():
    # first activation.
    logger.propagate = False
    logger.setLevel(logLevelStream)
    logHandlerS = logging.StreamHandler()
    logHandlerS.setFormatter(CustomFormatter('Quick Export: %(levelname)s: %(message)s'))
    logHandlerS.setLevel(logLevelStream)
    logger.addHandler(logHandlerS)

    logger.info("Begin.")
    
    from .quickexport import QuickExportExtension
