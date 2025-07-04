Work-in-progress.

Open quickexport/QuickExport/dialog.py in Krita with Scripter or Ten Scripts (under Tools->Scripts).

All (saved) images currently open in Krita will be listed.
Choose the output file name, whether to save alpha, and the compression level for each image.
Click "Export now" to export the image. The exported file will be saved to the same folder as the source file.

The settings for each image are saved in Krita's config file (kritarc) and will persist between Krita sessions.

Features:
- export as png
- choose output file name
- adjust export settings: alpha and compression level
- settings for each image are remembered and persist between Krita sessions

Missing/To-Do:
- can't export as jpg or any other type besides png
- can't export the image to a different directory than that of the source image
- can't adjust any other settings (transparency colour, embed sRGB profile, resize, etc.)
- settings for files can't be removed
- incremental saves do not automatically copy settings from prior saves
- can't automatically export a chain of dependent images (eg. when exporting a texture atlas, first update file layers)
- can't manage settings for images not currently open in Krita
- can't sort or group list of images, or hide those not intended for export
- no thumbnail for images
