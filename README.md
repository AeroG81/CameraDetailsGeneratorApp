1) Support Generation of Camera Settings Summary and combine with original image (JPEG/JPG/PNG)
2) Support Image Preview 
3) Support Manual Input for missing attributes
4) Ability to convert RAW images to JPEG directly

Supported image formats:
*.png *.jpeg *.jpg *.bmp *.cr2 *.raf *.raw *.tiff

Requirement:
1) EXIFTOOL from https://exiftool.org/ for command line use
2) Valid brand logo path and output image path at settings.json

Steps:
1) Please specify the brand logo path and output image path at settings.json before launching the exe file
2) settings.json is located inside _internal directory
3) Brand logo path should be located inside _internal/logo, please specify the brand logo path manually
4) Output image path can be set to any location user prefered to

NOTE: 
- Character "\" needs to be replaced with "/" for the program to work
- Current program is still in development, application execution speed is not optimal
