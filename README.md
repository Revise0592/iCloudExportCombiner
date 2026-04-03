# iCloud Export Combiner

Extracts iCloud Photos export `.zip` files and sorts the contents into `Photos/` and `Videos/` folders. Non-media files (`.csv`, `.json`, etc.) are ignored.

## Requirements

- Python 3.10+
- No third-party packages — stdlib only

## Usage

```bash
# Source zips are in the current directory, output here too
python icloud_extract.py

# Specify the folder containing your zips
python icloud_extract.py /path/to/zips

# Write sorted output to a different directory
python icloud_extract.py /path/to/zips -o /path/to/output

# Preview what would happen without extracting anything
python icloud_extract.py /path/to/zips --dry-run
```

## Output structure

```
output/
├── Photos/   ← .jpg .jpeg .png .heic .heif .gif .tiff .bmp .webp .raw .cr2 .nef .arw .dng …
└── Videos/   ← .mp4 .mov .avi .mkv .m4v .wmv .flv .3gp .mts .m2ts …
```

Duplicate filenames are renamed automatically (e.g. `IMG_0001_1.jpg`).

## Expected zip naming

The script recognises the standard iCloud naming convention:

```
iCloud Photos Part 1 of 103.zip
iCloud Photos Part 2 of 103.zip
…
iCloud Photos Part 103 of 103.zip
```

Files are processed in numeric order. If no files match this pattern, all `.zip` files in the source directory are processed alphabetically.
