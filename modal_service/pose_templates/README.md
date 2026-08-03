# Official pose-template package

Product supplies this directory outside the APK. Do not commit private reference images here.

An installable package contains `manifest.json` and 6-20 pose directories such as `pose_01/reference.png`. Every pose entry records `pose_id`, `name`, `version`, `difficulty`, `reference`, `instruction`, and the lowercase SHA-256 of the reference image. The manifest selects exactly three consistency poses and six MVP poses.

Run `python -m modal_service.tools.install_pose_templates <package>` only after every image and instruction is approved. The entire package is validated first, its immutable version is uploaded, and the active pointer is written last. Android cannot install or modify templates.
