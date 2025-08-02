![krita_quickexport_githubimage2](https://github.com/user-attachments/assets/bbd4246b-fb55-42be-9cd8-c005b0b9be7c)

Work-in-progress.

Install in Krita as a plugin by the usual method. Actions will be added to the File menu, and can also be added to toolbars with Settings/Configure Toolbars.

Once you've configured export settings for an image in the configuration dialog, you can export the image without being asked where or how to save each time.

#### Configuration Dialog

All (saved) images currently open in Krita will be listed.
Choose the output file name, type and export settings for each image.
Click "Export now" to export the image. The exported file will be saved to the same folder as the source file.

The settings for each image are saved in Krita's config file (kritarc) and will persist between Krita sessions.

#### Features:
- export as png or jpeg
- choose output file name
- adjust all export settings, including scale
- choose to keep or forget export settings for each image

#### Missing/To-Do:
- can't currently export as any type other than png and jpeg
- can't export the image to a different directory than that of the source image
- can't automatically export a chain of dependent images (eg. when exporting a texture atlas, first update file layers)
- can't group images together in list or enforce a specific custom sort order
