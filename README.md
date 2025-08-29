![krita_quickexport_githubimage3](https://github.com/user-attachments/assets/3496f959-d800-4ca6-9792-05a712a02a03)

Work-in-progress, but feedback welcome.

Install in Krita as a plugin by the usual method. Actions will be added to the File menu, and can also be added to toolbars with Settings/Configure Toolbars.

Once you've configured export settings for an image in the configuration dialog, you can export the image without being asked where or how to save each time.

#### Configuration Dialog

All (saved) images currently open in Krita will be listed.
Choose the output file name, location, type and export settings for each image.
Click "Export now" to export the image. The exported file will be saved to the same folder as the source file by default.

The settings for each image are saved in Krita's config file (kritarc) and will persist between Krita sessions.

#### Features:
- export as png or jpeg, plus some minor formats (gif, bmp, ico, tga, pbm/pgm/ppm, xbm/xpm)
- choose output file name and location
- adjust all export settings, including scale
- choose to keep or forget export settings for each image

#### Missing/To-Do:
- can't currently export as any type other than those mentioned above
- can't automatically export a chain of dependent images (eg. when exporting a texture atlas, first update file layers)
- can't group images together in list or enforce a specific custom sort order
