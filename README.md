
<img alt="krita_quickexport_githubimage5" align="right" src="https://github.com/user-attachments/assets/7d134e8a-7c98-41b1-a887-08203b7d73f7">

### Quick Export plugin for Krita
Quick Export provides a set and forget workflow that reduces the
export round-trip time when working on images in Krita for use
elsewhere.

_Work-in-progress, but feedback welcome._

#### Installation

##### Requirements
Compatible: Krita 5.3

Not compatible: Krita 5.2 and earlier, Krita 6.

Tested on Linux, untested on Windows/Mac.

##### Instructions
Install in Krita following [these instructions](https://docs.krita.org/en/user_manual/python_scripting/install_custom_python_plugin.html). Actions will be added to the File menu, and can also be added to toolbars with Settings → Configure Toolbars.

##### Upgrading
If you are upgrading from an older version, you need to uninstall it. Open Settings → Configure Krita. Disable the plugin in Python Plugin Manager. Then go to General → Resources tab. Press the button to open a file dialog on the resources folder. Navigate into pykrita and delete the QuickExport folder. Now restart krita and install as normal.

A settings upgrade dialog will appear the first time you interact with the plugin if you have settings from an older version.

#### Configuration Dialog

All images saved as .kra files currently open in Krita will be listed.
Choose the output file name, location, type and export settings for each image.

Once you've configured export settings for an image in the configuration dialog, you can export the image without being asked where or how to save each time.
Use the Quick Export entry in the File menu or the button on the toolbar if added. Krita's normal export button remains, so be sure to use the appropriate one.

The settings for each image are saved in Krita's config file (kritarc) and will persist between Krita sessions.

#### Features:
- add settings on individual projects, or on folders to use for all projects in them
- export as any type
- many options for output file name and location
- adjust all export settings, including scale

#### Missing/To-Do:
- can't automatically export a chain of dependent images (eg. when exporting a texture atlas, first update file layers)

#### History

- [v0.1.1](https://github.com/tom-jk/krita-quick-export/releases/tag/v0.1.1) (Latest)
- v0.1.0
  - Feature: new dialog design: compact, non-modal, drag-n-drop, revert changes without restart
  - Feature: configs on folders, inherited by projects in folder
  - Improvement: export as any type, native Krita settings dialogs
  - Removed: set export print resolution
  - Removed: individual settings for version files of project
  - Removed: non-.kra files as projects

<details><summary>older</summary>

- v0.0.2
![krita_quickexport_githubimage4](https://github.com/user-attachments/assets/f635ee93-d2e4-4da4-b782-118e6e277ef4)

</details>
